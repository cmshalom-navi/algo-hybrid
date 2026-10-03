"""Draw the BOM structure of the test data as a graph.

Nodes are the operations of the BOMs and an edge op1 -> op2 means that op2
consumes an item that op1 outputs. Items that no operation outputs (raw
materials) are nodes too, with edges into the operations that consume them,
and so are the products that no operation consumes, with edges out of the
operations that output them.

Run it to write an interactive HTML page (PyVis) and a static PNG image
(matplotlib) of the graph, and to open the HTML page in the browser:

    uv run --group viz python bom_graph.py [OUTPUT_PREFIX]
"""

import collections
import pathlib
import sys
import webbrowser

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot  # noqa: E402
import networkx  # noqa: E402
from pyvis import network  # noqa: E402

from common import models  # noqa: E402
import test_data  # noqa: E402

_COLORS = {
    models.ItemType.RAW: "#8fbc8f",
    models.ItemType.SEMI_FINISHED: "#87ceeb",
    models.ItemType.FINISHED: "#f4a460",
}
# Color of the nodes whose item has an item type missing from _COLORS.
_DEFAULT_COLOR = "#d3d3d3"
# Shapes of the item and operation nodes, as PyVis names them.
_ITEM_SHAPE = "box"
_OPERATION_SHAPE = "ellipse"
# The matplotlib marker and node size of every shape.
_PNG_SHAPES = {_ITEM_SHAPE: ("s", 1400), _OPERATION_SHAPE: ("o", 2400)}


def build_graph(operations: list[models.Operation]) -> networkx.MultiDiGraph:
    """Returns the material-flow graph of the given operations.

    The nodes are the operations, the items that some operation consumes
    but no operation outputs, and the products (as operation materials)
    whose items no operation consumes. For every pair of operation materials
    (output, consumable) where output is the product, a co-product or a
    by-product of op1, consumable is a consumable of op2, and both have the
    same item, there is an edge op1 -> op2 keyed by the pair. So there can
    be several edges between the same two operations. For every consumable
    of an operation whose item no operation outputs, there is an edge
    item -> operation keyed by the consumable, and for every operation
    whose product has an item no operation consumes, there is an edge
    operation -> product keyed by the product.

    Every node has the attribute `label`, the code of its item, of the item
    of its product, or of the item of its material, and every edge has the
    attribute `label`, the code of the item of its materials.

    Args:
        operations: The operations.

    Returns:
        The graph.

    Raises:
        ValueError: If some operation consumes an item it outputs.
    """
    graph = networkx.MultiDiGraph()
    for operation in operations:
        graph.add_node(operation, label=operation.product.item.code)
    consumers = collections.defaultdict(list)
    for operation in operations:
        for consumable in operation.consumables:
            consumers[consumable.item.item_id].append((operation, consumable))
    output_item_ids = set()
    for operation in operations:
        for output in (
            operation.product,
            *operation.co_products,
            *operation.by_products,
        ):
            output_item_ids.add(output.item.item_id)
            for consumer, consumable in consumers[output.item.item_id]:
                if consumer is operation:
                    raise ValueError(
                        f"Operation of BOM {operation.bom_id} both consumes"
                        f" and outputs item {output.item.code}"
                    )
                graph.add_edge(
                    operation,
                    consumer,
                    key=(output, consumable),
                    label=output.item.code,
                )
    for operation in operations:
        for consumable in operation.consumables:
            item = consumable.item
            if item.item_id not in output_item_ids:
                graph.add_node(item, label=item.code)
                graph.add_edge(item, operation, key=consumable, label=item.code)
        product = operation.product
        if not consumers[product.item.item_id]:
            graph.add_node(product, label=product.item.code)
            graph.add_edge(
                operation, product, key=product, label=product.item.code
            )
    return graph


def _node_id(
    node: models.Operation | models.Item | models.OperationMaterial,
) -> str:
    """Returns the ID of a node of a graph returned by `build_graph`.

    Args:
        node: The node.

    Returns:
        The BOM ID of an operation, the ID of an item, or the item ID and
        quantity of a material, as a string.
    """
    if isinstance(node, models.Operation):
        return str(node.bom_id)
    if isinstance(node, models.OperationMaterial):
        return f"{node.item.item_id}/{node.qty}"
    return str(node.item_id)


def _drawing_graph(graph: networkx.MultiDiGraph) -> networkx.DiGraph:
    """Returns a graph returned by `build_graph` ready to be drawn.

    The nodes are as in `_node_id`, with the attributes `label` (as in
    `graph`), `title` (the item type of the item, of the product or of
    the item of the material),
    `color` (by that item type), `shape` and `layer` (the length of the
    longest path reaching the node, so nodes without incoming edges are on
    layer 0). The parallel edges of `graph` are merged into one edge whose
    `label` lists their labels.

    Args:
        graph: A graph returned by `build_graph`.

    Returns:
        The graph to draw.

    Raises:
        networkx.NetworkXUnfeasible: If the graph has a cycle.
    """
    drawing = networkx.DiGraph()
    for layer, nodes in enumerate(networkx.topological_generations(graph)):
        for node in nodes:
            if isinstance(node, models.Operation):
                item_type = node.product.item.item_type
                shape = _OPERATION_SHAPE
            elif isinstance(node, models.OperationMaterial):
                item_type = node.item.item_type
                shape = _ITEM_SHAPE
            else:
                item_type = node.item_type
                shape = _ITEM_SHAPE
            drawing.add_node(
                _node_id(node),
                label=graph.nodes[node]["label"],
                title=item_type.value,
                color=_COLORS.get(item_type, _DEFAULT_COLOR),
                shape=shape,
                layer=layer,
            )
    labels = collections.defaultdict(list)
    for u, v, label in graph.edges.data("label"):
        labels[_node_id(u), _node_id(v)].append(label)
    for (u, v), edge_labels in labels.items():
        drawing.add_edge(u, v, label="\n".join(edge_labels))
    return drawing


def write_html(graph: networkx.MultiDiGraph, path: str) -> None:
    """Writes an interactive, hierarchical drawing of the graph.

    Args:
        graph: A graph returned by `build_graph`.
        path: Path of the HTML file to write.
    """
    drawing = _drawing_graph(graph)
    net = network.Network(
        height="800px", width="100%", directed=True, cdn_resources="remote"
    )
    for node, data in drawing.nodes(data=True):
        net.add_node(
            node,
            label=data["label"],
            title=data["title"],
            color=data["color"],
            level=data["layer"],
            shape=data["shape"],
        )
    for u, v, label in drawing.edges.data("label"):
        net.add_edge(u, v, label=label)
    # Layer 0 at the bottom.
    net.set_options("""{
        "layout": {"hierarchical": {
            "direction": "DU", "sortMethod": "directed",
            "levelSeparation": 120, "nodeSpacing": 140
        }},
        "physics": {"enabled": false},
        "edges": {"smooth": {"type": "cubicBezier"}, "font": {"size": 11}}
    }""")
    net.write_html(path)


def write_png(graph: networkx.MultiDiGraph, path: str) -> None:
    """Writes a static, layered drawing of the graph.

    Args:
        graph: A graph returned by `build_graph`.
        path: Path of the PNG file to write.
    """
    drawing = _drawing_graph(graph)
    pos = networkx.multipartite_layout(
        drawing, subset_key="layer", align="horizontal"
    )
    figure, axes = pyplot.subplots(figsize=(12, 8))
    # Every call draws nodes of a single marker, so draw each shape apart.
    for shape, (marker, size) in _PNG_SHAPES.items():
        nodes = [n for n, s in drawing.nodes.data("shape") if s == shape]
        networkx.draw_networkx_nodes(
            drawing,
            pos,
            ax=axes,
            nodelist=nodes,
            node_color=[drawing.nodes[n]["color"] for n in nodes],
            node_size=size,
            node_shape=marker,
        )
    networkx.draw_networkx_labels(
        drawing,
        pos,
        ax=axes,
        labels=dict(drawing.nodes.data("label")),
        font_size=8,
    )
    # The node sizes make the arrows stop at the node borders.
    networkx.draw_networkx_edges(
        drawing,
        pos,
        ax=axes,
        node_size=[_PNG_SHAPES[s][1] for _, s in drawing.nodes.data("shape")],
        arrowsize=15,
        connectionstyle="arc3,rad=0.1",
    )
    networkx.draw_networkx_edge_labels(
        drawing,
        pos,
        ax=axes,
        edge_labels={
            (u, v): label for u, v, label in drawing.edges.data("label")
        },
        font_size=7,
        connectionstyle="arc3,rad=0.1",
    )
    axes.set_axis_off()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    pyplot.close(figure)


def main() -> None:
    """Draws the BOM graph of the test data."""
    prefix = sys.argv[1] if len(sys.argv) > 1 else "bom_graph"
    graph = build_graph(
        [models.Operation(bom) for bom in test_data.create_test_data()]
    )
    write_html(graph, f"{prefix}.html")
    write_png(graph, f"{prefix}.png")
    print(f"Wrote {prefix}.html and {prefix}.png")
    webbrowser.open_new(pathlib.Path(f"{prefix}.html").resolve().as_uri())


if __name__ == "__main__":
    main()
