"""Domain models built on top of the shared data models.

Holds an immutable view of a BOM as an operation consuming and producing
materials.
"""

import dataclasses
import uuid

from common import cdm


@dataclasses.dataclass(frozen=True)
class OperationMaterial:
    """A quantity of an item.

    Attributes:
        qty: The quantity, in the unit of measure of the row it comes from.
        item: The item.
    """

    qty: float
    item: cdm.Item


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

    def __init__(self, bom: cdm.Bom) -> None:
        """Builds the operation of a BOM.

        Args:
            bom: The BOM; its outputs and components, and their items, must
                be loaded.

        Raises:
            ValueError: If the BOM does not have exactly one output with the
                primary role, or if some component and some output of the
                BOM have the same item.
        """
        roles = cdm.BomOutputRole
        outputs: dict[cdm.BomOutputRole, list[OperationMaterial]] = {
            role: [] for role in roles
        }
        for output in bom.outputs:
            outputs[output.role].append(
                OperationMaterial(float(output.qty), output.item)
            )
        if len(outputs[roles.PRIMARY]) != 1:
            raise ValueError(
                f"BOM {bom.bom_id} has"
                f" {len(outputs[roles.PRIMARY])} primary outputs,"
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
        object.__setattr__(self, "product", outputs[roles.PRIMARY][0])
        object.__setattr__(
            self, "co_products", tuple(outputs[roles.CO_PRODUCT])
        )
        object.__setattr__(
            self, "by_products", tuple(outputs[roles.BY_PRODUCT])
        )
        object.__setattr__(
            self,
            "consumables",
            tuple(
                OperationMaterial(float(c.qty_per_base), c.item)
                for c in bom.components
            ),
        )
