from pathlib import Path
from typing import Optional
from typing_extensions import Annotated
import csv
import json
import base64

import typer

from refscan.lib.constants import console
from refscan.lib.helpers import (
    print_section_header,
)
from refscan.lib.Reference import Reference

app = typer.Typer(
    help="Generates an interactive graph (network diagram) of a reference report.",
    add_completion=False,  # hides the shell completion options from `--help` output
    rich_markup_mode="markdown",  # enables use of Markdown in docstrings and CLI help
)

html_template_path = r"refscan/templates/graph.template.html"


@app.command("graph")
def graph(
    reference_report_file_path: Annotated[
        Path,
        typer.Option(
            "--reference-report",
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Filesystem path at which the reference report resides.",
        ),
    ],
    graph_file_path: Annotated[
        Optional[Path],
        typer.Option(
            "--graph",
            dir_okay=False,
            writable=True,
            readable=False,
            resolve_path=True,
            help="Filesystem path at which you want **refgraph** to generate the graph.",
        ),
    ] = "graph.html",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show verbose output.",
        ),
    ] = False,
):
    r"""
    Generates an interactive graph (network diagram) of a reference report.
    """

    print_section_header(console, text="Reading reference report")

    # Instantiate a `Reference` for each data row in the reference report.
    references = []
    with open(reference_report_file_path, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")  # automatically gets field names from first row
        for reference_dict in reader:
            assert isinstance(reference_dict, dict)  # added because, otherwise, PyCharm thinks it's a `str`
            reference = Reference(**reference_dict)  # uses dict (i.e. keys and their values) as kwargs
            references.append(reference)

    console.print(f"References: {len(references)}")
    if verbose:
        console.print(references)

    print_section_header(console, text="Generating graph")

    # Read the HTML template file.
    html_template = ""
    with open(html_template_path, "r") as f:
        html_template = f.read()

    # Generate a list of elements (i.e. nodes and edges) for use by the `cytoscape` JavaScript library.
    #
    # Note: Nodes are represented like this (here are two examples):
    #       ```
    #       { data: { id: "data_generation_set" } }
    #       { data: { id: "study_set" } }
    #       ```
    #       Edges are represented like this (here is one example):
    #       ```
    #       { data: { id: "data_generation_set__to__study_set", source: "data_generation_set", target: "study_set" } }
    #       ```
    #
    # Reference: https://js.cytoscape.org/#notation/elements-json
    #
    nodes = []
    edges = []
    for r in references:
        # Append a node for the source collection if we haven't already done so. Same for the target collection.
        source_name = r.source_collection_name
        target_name = r.target_collection_name
        node_ids = [n["data"]["id"] for n in nodes]
        if source_name not in node_ids:
            nodes.append(dict(data=dict(id=source_name)))
        if target_name not in node_ids:
            nodes.append(dict(data=dict(id=target_name)))

        # Append an edge for this collection-to-collection relationship if we haven't already done so.
        edge_id = f"{source_name}__to__{target_name}"
        edge_ids = [e["data"]["id"] for e in edges]
        if edge_id not in edge_ids:
            edges.append(dict(data=dict(id=edge_id, source=source_name, target=target_name)))

    console.print(f"Nodes: {len(nodes)}")
    console.print(f"Edges: {len(edges)}")
    console.print()

    elements = nodes + edges  # join the lists

    # Generate an HTML file (based upon the template) that contains those elements.
    graph_data_json_str = json.dumps(elements)
    graph_data_json_bytes = graph_data_json_str.encode("utf-8")
    graph_data_json_base64 = base64.b64encode(graph_data_json_bytes)
    graph_data_json_base64_str = graph_data_json_base64.decode("utf-8")
    placeholder = "{{ graph_data_json_base64 }}"
    html_result = html_template.replace(placeholder, graph_data_json_base64_str)

    if verbose:
        console.print(html_result)

    with open(graph_file_path, "w") as f:
        f.write(html_result)

    console.print(f"Graph generated at: {graph_file_path}")
    console.print()


if __name__ == "__main__":
    app()
