from enum import Enum
from typing import Union, List, Dict, Any
import json
import base64
from importlib import resources

import linkml_runtime

from refscan import get_package_metadata
from refscan.lib.constants import console
from refscan.lib.helpers import (
    get_collection_name_to_class_names_map,
    print_section_header,
    get_collection_names_from_schema,
    identify_references,
)

# Define some type aliases that we can reference later, to simplify the latter type hints.
# TODO: Update these type hints to not use `Any`.
NodeType = Dict[str, Dict[str, Any]]
EdgeType = Dict[str, Dict[str, Any]]


class Subject(str, Enum):
    r"""The subject (i.e. focal point) of the graph."""

    collection = "collection"
    class_ = "class"


def load_template(resource_path: str) -> str:
    r"""
    Returns the contents of a template file as a string.

    Note: We do this via `importlib.resources` instead of a regular `open()` so
          that the path is accurate both when this script is run in a development
          environment and when this script is run when installed from PyPI,
          instead of it only being accurate in the former case.
          Reference: https://docs.python.org/3.9/library/importlib.html#importlib.resources.files
    """
    package_name = "refscan"
    return resources.files(package_name).joinpath(resource_path).read_text(encoding="utf-8")


def encode_json_value_as_base64_str(json_value: Union[dict, list]) -> str:
    r"""Helper function that encodes the specified JSON value as a base64 string."""

    value_as_string = json.dumps(json_value)
    string_as_bytes = value_as_string.encode("utf-8")
    encoded_bytes = base64.b64encode(string_as_bytes)
    encoded_bytes_as_string = encoded_bytes.decode("utf-8")
    return encoded_bytes_as_string


def is_class_abstract(class_name: str, schema_view: linkml_runtime.SchemaView) -> bool:
    r"""
    Returns whether the specified schema class is abstract.

    Note: The `abstract` property can contain `True`, `False`, or `None`.

    Reference: https://linkml.io/linkml/schemas/inheritance.html#abstract-classes-and-slots
    """

    return schema_view.get_class(class_name).abstract is True


def graph(
    schema_view: linkml_runtime.SchemaView,
    subject: Subject,
    verbose: bool = False,
) -> str:
    r"""
    Generates an interactive graph (network diagram) of the references described by a schema.
    """

    # Show a header on the console, to tell the user which stage of execution we're entering.
    print_section_header(console, text="Identifying references")

    # Get a list of collection names (technically, `Database` slot names) from the schema.
    # e.g. ["study_set", ...]
    collection_names = get_collection_names_from_schema(schema_view)
    console.print(f"Collections described by schema: {len(collection_names)}")

    # For each collection, determine the names of the classes whose instances can be stored in that collection.
    collection_name_to_class_names = get_collection_name_to_class_names_map(schema_view=schema_view)

    # Identify the inter-document references that the schema allows to exist.
    references = identify_references(
        schema_view=schema_view, collection_name_to_class_names=collection_name_to_class_names
    )
    console.print(f"References described by schema: {len(references)}")

    console.print(f"References: {len(references)}")
    if verbose:
        console.print(references)

    print_section_header(console, text="Generating graph")

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
    nodes: List[NodeType] = []
    edges: List[EdgeType] = []
    for r in references:
        # Get the source and target names depending upon the subject of the graph.
        source_name = r.source_collection_name if subject == Subject.collection else r.source_class_name
        target_name = r.target_collection_name if subject == Subject.collection else r.target_class_name

        # If the subject of the graph is "class", determine whether the source class is abstract. Same for the target class.
        # Note: This will allow us to display abstract classes differently from concrete classes in the diagram.
        is_source_abstract = is_class_abstract(source_name, schema_view) if subject == Subject.class_ else None
        is_target_abstract = is_class_abstract(target_name, schema_view) if subject == Subject.class_ else None

        # Append a node for the source subject if we haven't already done so. Same for the target subject.
        node_ids = [n["data"]["id"] for n in nodes]
        if source_name not in node_ids:
            nodes.append(dict(data=dict(id=source_name, is_abstract=is_source_abstract)))
        if target_name not in node_ids:
            nodes.append(dict(data=dict(id=target_name, is_abstract=is_target_abstract)))

        # Append an edge for this source subject-to-target subject relationship if we haven't already done so.
        edge_id = f"{source_name}__to__{target_name}"
        edge_ids = [e["data"]["id"] for e in edges]
        if edge_id not in edge_ids:
            edge = dict(data=dict(id=edge_id, source=source_name, target=target_name, source_fields=[]))
            edges.append(edge)

        # Ensure this edge's `data.source_fields` list accounts for this reference's source field name.
        edge = next(e for e in edges if e["data"]["id"] == edge_id)  # gets the matching edge
        if r.source_field_name not in edge["data"]["source_fields"]:  # avoids repeating the field name
            edge["data"]["source_fields"].append(r.source_field_name)

    # Replace each edge's `source_fields` property with a `label` property containing a comma-delimited string.
    # Example: if `source_fields` contains ["a", "b", "c"] -> `label` will contain "a, b, c"
    # Reference: https://docs.python.org/3/library/stdtypes.html#dict.pop
    for edge in edges:
        source_fields: list = edge["data"].pop("source_fields", [])  # removes the `source_fields` property
        edge["data"]["label"] = ", ".join(source_fields)

    console.print(f"Nodes: {len(nodes)}")
    console.print(f"Edges: {len(edges)}")
    console.print()

    elements = nodes + edges  # join the lists

    # Load the HTML template file.
    html_template = load_template(r"templates/graph.template.html")

    # Generate an HTML file (based upon the template) that contains those elements.
    graph_data_json_base64_str = encode_json_value_as_base64_str(elements)
    graph_metadata_json_base64_str = encode_json_value_as_base64_str(
        dict(
            app_version=get_package_metadata("Version"),
            schema_version=schema_view.schema.version,
            subject_singular="class" if subject == Subject.class_ else "collection",
            subject_plural="classes" if subject == Subject.class_ else "collections",
        )
    )
    html_result = html_template.replace("{{ graph_data_json_base64 }}", graph_data_json_base64_str)
    html_result = html_result.replace("{{ graph_metadata_json_base64 }}", graph_metadata_json_base64_str)

    return html_result
