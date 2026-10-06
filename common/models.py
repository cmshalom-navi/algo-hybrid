"""Data models shared by the api, the worker and the solver.

Holds the pydantic models exchanged with the solver, the SQLAlchemy ORM
models of the master-data tables (items and bills of materials), and an
immutable view of a BOM as an operation consuming and producing materials.
"""

import dataclasses
import datetime
import decimal
import enum
from typing import Any
import uuid

import pydantic
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.dialects import postgresql


class ToyInstance(pydantic.BaseModel):
    """Input to the solver.

    Attributes:
        a: Objective coefficient of x.
        b: Objective coefficient of y.
    """

    a: float
    b: float


class ToySolution(pydantic.BaseModel):
    """Output of the solver.

    Attributes:
        status: Solver status, e.g. "OPTIMAL" or "UNBOUNDED".
        x: Optimal value of x, if an optimum was found.
        y: Optimal value of y, if an optimum was found.
        objective: Optimal objective value, if an optimum was found.
    """

    status: str
    x: float | None = None
    y: float | None = None
    objective: float | None = None


class Base(orm.DeclarativeBase):
    """Declarative base of all ORM models.

    Maps Python annotations to the PostgreSQL column types used by the schema.
    """

    type_annotation_map = {
        uuid.UUID: postgresql.UUID(as_uuid=True),
        str: sa.String(),
        decimal.Decimal: sa.Numeric(),
        datetime.datetime: sa.DateTime(timezone=True),
        dict[str, Any]: postgresql.JSONB(),
    }


class ItemType(enum.Enum):
    """Kind of an item."""

    RAW = "raw"
    COMPONENT = "component"
    SEMI_FINISHED = "semi_finished"
    FINISHED = "finished"
    PACKAGING = "packaging"
    CONSUMABLE = "consumable"


class BomOutputRole(enum.Enum):
    """Role of an output of a BOM run."""

    PRIMARY = "primary"
    CO_PRODUCT = "co_product"
    BY_PRODUCT = "by_product"


def _pg_enum(enum_class: type[enum.Enum], name: str) -> sa.Enum:
    """Returns a native PostgreSQL enum type storing the members' values.

    Args:
        enum_class: The Python enum to map.
        name: Name of the PostgreSQL enum type.

    Returns:
        The SQLAlchemy enum type.
    """
    return sa.Enum(
        enum_class,
        name=name,
        values_callable=lambda members: [m.value for m in members],
    )


class _SourceProvenance:
    """Mixin with the columns tracing a row back to its source system."""

    source_system_id: orm.Mapped[uuid.UUID | None]
    source_record_id: orm.Mapped[str | None]
    source_url: orm.Mapped[str | None]
    raw_ingest_event_id: orm.Mapped[int | None] = orm.mapped_column(
        sa.BigInteger
    )
    mapper_version: orm.Mapped[str | None]
    last_source_updated_at: orm.Mapped[datetime.datetime | None]
    custom_fields: orm.Mapped[dict[str, Any] | None]


class Item(_SourceProvenance, Base):
    """A part, material or product."""

    __tablename__ = "item"
    __table_args__ = (
        sa.Index("uq_item_tenant_code", "tenant_id", "code", unique=True),
        sa.Index(
            "uq_item_tenant_source",
            "tenant_id",
            "source_system_id",
            "source_record_id",
            unique=True,
        ),
    )

    item_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tenant_id: orm.Mapped[uuid.UUID]
    code: orm.Mapped[str] = orm.mapped_column(
        comment="normalised part number used across the product"
    )
    raw_code: orm.Mapped[str | None] = orm.mapped_column(
        comment=(
            "original source part number if code was rewritten during ingest"
        )
    )
    name: orm.Mapped[str | None]
    item_type: orm.Mapped[ItemType] = orm.mapped_column(
        _pg_enum(ItemType, "item_type")
    )
    item_group: orm.Mapped[str | None] = orm.mapped_column(
        comment="source classification, e.g. RAW-STEEL, FINISHED-BEVERAGE"
    )
    base_uom: orm.Mapped[str]
    is_sellable: orm.Mapped[bool] = orm.mapped_column(
        default=False, server_default=sa.false()
    )
    is_purchasable: orm.Mapped[bool] = orm.mapped_column(
        default=False, server_default=sa.false()
    )
    is_lot_tracked: orm.Mapped[bool] = orm.mapped_column(
        default=False,
        server_default=sa.false(),
        comment="gates every nullable lot_id in the model",
    )
    is_active: orm.Mapped[bool] = orm.mapped_column(
        default=True, server_default=sa.true()
    )
    deleted_at: orm.Mapped[datetime.datetime | None]

    uoms: orm.Mapped[list["ItemUom"]] = orm.relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class ItemUom(Base):
    """A unit-of-measure conversion factor for an item.

    Buy in drums, stock in kg, consume in grams. Movements record the uom AS
    CAPTURED; this table converts, it does not normalise on write.
    """

    __tablename__ = "item_uom"
    __table_args__ = (
        sa.Index(
            "uq_item_uom_tenant_item_uoms",
            "tenant_id",
            "item_id",
            "from_uom",
            "to_uom",
            unique=True,
        ),
    )

    item_uom_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tenant_id: orm.Mapped[uuid.UUID]
    item_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("item.item_id")
    )
    from_uom: orm.Mapped[str]
    to_uom: orm.Mapped[str]
    factor: orm.Mapped[decimal.Decimal]

    item: orm.Mapped[Item] = orm.relationship(back_populates="uoms")


class Bom(_SourceProvenance, Base):
    """A bill of materials.

    An item can have MANY BOMs (alt materials, per-plant, lot-size
    dependent). Which pairs with which routing is production_version.
    """

    __tablename__ = "bom"
    __table_args__ = (
        sa.Index(
            "uq_bom_tenant_item_version",
            "tenant_id",
            "primary_item_id",
            "version",
            unique=True,
        ),
        sa.Index(
            "uq_bom_tenant_source",
            "tenant_id",
            "source_system_id",
            "source_record_id",
            unique=True,
        ),
    )

    bom_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tenant_id: orm.Mapped[uuid.UUID]
    primary_item_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("item.item_id"),
        comment=(
            "denormalised; MUST equal the bom_output row with role = primary."
            " Enforced in the write path, not by the DB."
        ),
    )
    version: orm.Mapped[str]
    base_qty: orm.Mapped[decimal.Decimal] = orm.mapped_column(
        comment="components are per this quantity"
    )
    base_uom: orm.Mapped[str]
    is_active: orm.Mapped[bool] = orm.mapped_column(
        default=True, server_default=sa.true()
    )
    valid_from: orm.Mapped[datetime.datetime | None]
    valid_to: orm.Mapped[datetime.datetime | None]
    deleted_at: orm.Mapped[datetime.datetime | None]

    primary_item: orm.Mapped[Item] = orm.relationship()
    components: orm.Mapped[list["BomComponent"]] = orm.relationship(
        back_populates="bom",
        cascade="all, delete-orphan",
        order_by="BomComponent.line_no",
    )
    outputs: orm.Mapped[list["BomOutput"]] = orm.relationship(
        back_populates="bom", cascade="all, delete-orphan"
    )


class BomComponent(Base):
    """An input of a BOM.

    Pairs with bom_output (OUTPUTS). An item needing 2 raws has 2 rows here.
    """

    __tablename__ = "bom_component"
    __table_args__ = (
        sa.Index(
            "uq_bom_component_tenant_bom_line",
            "tenant_id",
            "bom_id",
            "line_no",
            unique=True,
        ),
        sa.Index("ix_bom_component_tenant_item", "tenant_id", "item_id"),
    )

    bom_component_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tenant_id: orm.Mapped[uuid.UUID]
    bom_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("bom.bom_id")
    )
    item_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("item.item_id"),
        comment="consumed item - the INPUT side",
    )
    routing_operation_id: orm.Mapped[uuid.UUID | None] = orm.mapped_column(
        comment=(
            "WHERE in the routing it is consumed - drives backflush timing,"
            " WIP value and scrap cost"
        )
    )
    line_no: orm.Mapped[int]
    qty_per_base: orm.Mapped[decimal.Decimal] = orm.mapped_column(
        comment="per bom.base_qty, not per single unit"
    )
    uom: orm.Mapped[str]
    scrap_pct: orm.Mapped[decimal.Decimal | None] = orm.mapped_column(
        comment="expected yield loss"
    )

    bom: orm.Mapped[Bom] = orm.relationship(back_populates="components")
    item: orm.Mapped[Item] = orm.relationship()


class BomOutput(Base):
    """An output of a BOM.

    One run can yield a primary product plus co-products and by-products.
    Discrete tenants have exactly one row with role = primary.
    """

    __tablename__ = "bom_output"
    __table_args__ = (
        sa.Index(
            "uq_bom_output_tenant_bom_item_role",
            "tenant_id",
            "bom_id",
            "item_id",
            "role",
            unique=True,
        ),
    )

    bom_output_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tenant_id: orm.Mapped[uuid.UUID]
    bom_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("bom.bom_id")
    )
    item_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("item.item_id")
    )
    role: orm.Mapped[BomOutputRole] = orm.mapped_column(
        _pg_enum(BomOutputRole, "bom_output_role")
    )
    qty: orm.Mapped[decimal.Decimal]
    uom: orm.Mapped[str]

    bom: orm.Mapped[Bom] = orm.relationship(back_populates="outputs")
    item: orm.Mapped[Item] = orm.relationship()


@dataclasses.dataclass(frozen=True)
class OperationMaterial:
    """A quantity of an item.

    Attributes:
        qty: The quantity, in the unit of measure of the row it comes from.
        item: The item.
    """

    qty: float
    item: Item


@dataclasses.dataclass(frozen=True, init=False)
class Operation:
    """An immutable view of a BOM as the materials it produces and consumes.

    Attributes:
        bom_id: The ID of the BOM.
        product: The output of the BOM with the primary role.
        co_products: The outputs of the BOM with the co-product role.
        by_products: The outputs of the BOM with the by-product role.
        consumables: The components of the BOM, with their quantities per
            base quantity of the BOM.
    """

    bom_id: uuid.UUID
    product: OperationMaterial
    co_products: tuple[OperationMaterial, ...]
    by_products: tuple[OperationMaterial, ...]
    consumables: tuple[OperationMaterial, ...]

    def __init__(self, bom: Bom) -> None:
        """Builds the operation of a BOM.

        Args:
            bom: The BOM; its outputs and components, and their items, must
                be loaded.

        Raises:
            ValueError: If the BOM does not have exactly one output with the
                primary role, or if some component and some output of the
                BOM have the same item.
        """
        outputs: dict[BomOutputRole, list[OperationMaterial]] = {
            role: [] for role in BomOutputRole
        }
        for output in bom.outputs:
            outputs[output.role].append(
                OperationMaterial(float(output.qty), output.item)
            )
        if len(outputs[BomOutputRole.PRIMARY]) != 1:
            raise ValueError(
                f"BOM {bom.bom_id} has"
                f" {len(outputs[BomOutputRole.PRIMARY])} primary outputs,"
                " expected 1"
            )
        self_consumed = {o.item_id for o in bom.outputs} & {
            c.item_id for c in bom.components
        }
        if self_consumed:
            codes = sorted(
                c.item.code
                for c in bom.components
                if c.item_id in self_consumed
            )
            raise ValueError(
                f"BOM {bom.bom_id} both consumes and outputs items"
                f" {', '.join(codes)}"
            )
        # The dataclass is frozen, so the fields can only be set this way.
        object.__setattr__(self, "bom_id", bom.bom_id)
        object.__setattr__(self, "product", outputs[BomOutputRole.PRIMARY][0])
        object.__setattr__(
            self, "co_products", tuple(outputs[BomOutputRole.CO_PRODUCT])
        )
        object.__setattr__(
            self, "by_products", tuple(outputs[BomOutputRole.BY_PRODUCT])
        )
        object.__setattr__(
            self,
            "consumables",
            tuple(
                OperationMaterial(float(c.qty_per_base), c.item)
                for c in bom.components
            ),
        )
