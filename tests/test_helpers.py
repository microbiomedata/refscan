from rich.progress import Progress
import linkml_runtime

from refscan.lib.helpers import (
    get_lowercase_key,
    init_progress_bar,
    get_collection_names_from_schema,
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
