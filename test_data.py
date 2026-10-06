"""Generate a small, self-contained set of BOMs to experiment with.

Every BOM has exactly one output, with the primary role; the items of these
outputs are called output items. Every BOM has 2 or 3 components, each
consuming either an output item of another BOM or a raw item. Every item is
referenced by at least one output or component, so the returned BOMs carry
the entire data set.

To keep the BOM structure acyclic, BOM i only consumes output items of BOMs
i + 1, ..., NUM_BOMS - 1, so the last BOM consumes raw items only.

Run it to print the generated BOMs.
"""

import decimal
import itertools
import random
import uuid

from common import models

NUM_BOMS = 10
NUM_RAW_ITEMS = 6
TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _item(code: str, item_type: models.ItemType, uom: str) -> models.Item:
    """Returns a new item of the test tenant.

    Args:
        code: Part number of the item.
        item_type: Kind of the item.
        uom: Base unit of measure of the item.

    Returns:
        The item.
    """
    return models.Item(
        item_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        code=code,
        name=f"Item {code}",
        item_type=item_type,
        base_uom=uom,
        is_sellable=item_type == models.ItemType.FINISHED,
        is_purchasable=item_type == models.ItemType.RAW,
        is_lot_tracked=False,
        is_active=True,
    )


def create_test_data(seed: int = 0) -> list[models.Bom]:
    """Creates NUM_BOMS BOMs together with all the items they reference.

    The objects are transient (not attached to a session) and have their
    IDs and foreign keys set, so they can be inspected as they are or
    persisted with `session.add_all(boms)`, which cascades to the outputs,
    components and items.

    Args:
        seed: Seed of the random generator; equal seeds give equal data
            except for the IDs.

    Returns:
        The BOMs.
    """
    rng = random.Random(seed)
    raw_items = [
        _item(f"RAW-{i:02d}", models.ItemType.RAW, "kg")
        for i in range(1, NUM_RAW_ITEMS + 1)
    ]
    # The type is set below, once it is known which items are consumed.
    output_items = [
        _item(f"PROD-{i:02d}", models.ItemType.FINISHED, "ea")
        for i in range(1, NUM_BOMS + 1)
    ]
    # Hand out raw items round-robin so that each is used at least once.
    next_raw_items = itertools.cycle(raw_items)

    boms = []
    for i, output_item in enumerate(output_items):
        bom = models.Bom(
            bom_id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            primary_item_id=output_item.item_id,
            primary_item=output_item,
            version="1",
            base_qty=decimal.Decimal(1),
            base_uom=output_item.base_uom,
            is_active=True,
        )
        bom.outputs.append(
            models.BomOutput(
                bom_output_id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                bom_id=bom.bom_id,
                item_id=output_item.item_id,
                item=output_item,
                role=models.BomOutputRole.PRIMARY,
                qty=bom.base_qty,
                uom=bom.base_uom,
            )
        )

        num_components = rng.choice([2, 3])
        lower_output_items = output_items[i + 1 :]
        # Keep at least one raw component per BOM.
        num_output_components = rng.randint(
            0, min(num_components - 1, len(lower_output_items))
        )
        consumed_items = rng.sample(lower_output_items, num_output_components)
        consumed_items += [
            next(next_raw_items)
            for _ in range(num_components - num_output_components)
        ]
        for line_no, item in enumerate(consumed_items, start=1):
            bom.components.append(
                models.BomComponent(
                    bom_component_id=uuid.uuid4(),
                    tenant_id=TENANT_ID,
                    bom_id=bom.bom_id,
                    item_id=item.item_id,
                    item=item,
                    line_no=line_no,
                    qty_per_base=decimal.Decimal(rng.randint(1, 20)) / 4,
                    uom=item.base_uom,
                )
            )
        boms.append(bom)

    consumed_ids = {c.item_id for bom in boms for c in bom.components}
    for item in output_items:
        if item.item_id in consumed_ids:
            item.item_type = models.ItemType.SEMI_FINISHED
            item.is_sellable = False
    return boms


def main() -> None:
    """Prints the generated BOMs."""
    for bom in create_test_data():
        print(f"{bom.primary_item.code} ({bom.primary_item.item_type.value})")
        for component in bom.components:
            print(
                f"  {component.line_no}. {component.qty_per_base}"
                f" {component.uom} {component.item.code}"
            )


if __name__ == "__main__":
    main()
