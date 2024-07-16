from rich.progress import Progress
import linkml_runtime

from refscan.lib.helpers import (
    get_lowercase_key,
    init_progress_bar,
    get_collection_names_from_schema,
    get_names_of_classes_eligible_for_collection,
)


def test_get_lowercase_key():
    key_value_tuple = ("FOO_bar", "baz")
    assert get_lowercase_key(key_value_tuple) == "foo_bar"


def test_init_progress_bar():
    assert isinstance(init_progress_bar(), Progress)


def test_get_collection_names_from_schema():
    schema_view = linkml_runtime.SchemaView(schema="tests/schemas/database_class.yaml")
    assert isinstance(schema_view, linkml_runtime.SchemaView)

    collection_names = get_collection_names_from_schema(schema_view)
    assert len(collection_names) == 2
    assert "biosample_set" in collection_names
    assert "study_set" in collection_names


def test_get_names_of_classes_eligible_for_collection():
    schema_view = linkml_runtime.SchemaView(schema="tests/schemas/database_class.yaml")
    assert isinstance(schema_view, linkml_runtime.SchemaView)

    collection_names = get_names_of_classes_eligible_for_collection(schema_view, "biosample_set")
    assert len(collection_names) == 1
    assert "Biosample" in collection_names

    collection_names = get_names_of_classes_eligible_for_collection(schema_view, "study_set")
    assert len(collection_names) == 1
    assert "Study" in collection_names

    # Focus on the "is_a" hierarchical relationship.
    collection_names = get_names_of_classes_eligible_for_collection(schema_view, "material_entity_set")
    assert len(collection_names) == 2
    assert "Biosample" in collection_names
    assert "MaterialEntity" in collection_names
