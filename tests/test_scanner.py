import linkml_runtime
import mongomock
import pytest

from refscan.lib.Finder import Finder
from refscan.lib.helpers import get_collection_name_to_class_names_map, identify_references
from refscan.scanner import (
    identify_referring_documents,
    scan_outgoing_references,
)


@pytest.fixture()
def schema_view():
    sv = linkml_runtime.SchemaView(schema="tests/schemas/database_with_class_uri.yaml")
    assert isinstance(sv, linkml_runtime.SchemaView)
    return sv


@pytest.fixture()
def seeded_db():
    r"""Returns a (mock) database that has been seeded with interrelated, schema-compliant documents."""

    db = mongomock.MongoClient().db

    # Seed the database with interrelated, schema-compliant data.
    db["company_set"].insert_many(
        [
            {"id": "c-0", "type": "refscan:Company"},
            {"id": "c-1", "type": "refscan:Company"},
            {"id": "c-2", "shareholders": ["e-1", "e-3"], "type": "refscan:Company"},
        ]
    )
    db["employee_set"].insert_many(
        [
            {"id": "e-1", "works_for": "c-1", "type": "refscan:Employee"},
            {"id": "e-2", "works_for": "c-2", "type": "refscan:Employee"},
            {"id": "e-3", "works_for": "c-2", "type": "refscan:Employee"},
        ]
    )
    # Note: These documents lack an `id` field. There is a collection in the real NMDC schema
    #       whose documents lack an `id` field (i.e. the `functional_annotation_agg` collection),
    #       and we want to ensure that case is handled correctly.
    db["testimonial_set"].insert_many(
        [
            {"company": "c-2", "message": "Good company!", "type": "refscan:Testimonial"},
            {"company": "c-2", "message": "Great company!", "type": "refscan:Testimonial"},
        ]
    )

    return db


def test_identify_referring_documents(schema_view, seeded_db):
    # Initialize other dependencies for the test (besides the `SchemaView`).
    finder = Finder(database=seeded_db)
    collection_name_to_class_names = get_collection_name_to_class_names_map(schema_view=schema_view)
    references = identify_references(schema_view, collection_name_to_class_names)

    # Case 1: A company that has 0 referring documents.
    referring_document_descriptors = identify_referring_documents(
        document={"id": "c-0", "type": "refscan:Company"},
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(referring_document_descriptors) == 0

    # Case 2: A company that has 1 referring documents.
    referring_document_descriptors = identify_referring_documents(
        document={"id": "c-1", "type": "refscan:Company"},
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(referring_document_descriptors) == 1
    assert referring_document_descriptors[0]["source_document_id"] == "e-1"
    assert referring_document_descriptors[0]["source_collection_name"] == "employee_set"
    assert referring_document_descriptors[0]["source_class_name"] == "Employee"

    # Case 3: A company that has 4 referring documents.
    referring_document_descriptors = identify_referring_documents(
        document={"id": "c-2", "type": "refscan:Company"},
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(referring_document_descriptors) == 4
    assert set(d["source_collection_name"] for d in referring_document_descriptors) == {
        "employee_set",
        "testimonial_set",
    }
    assert set(d["source_class_name"] for d in referring_document_descriptors) == {"Employee", "Testimonial"}
    assert set(d["source_document_id"] for d in referring_document_descriptors) == {"e-2", "e-3", ""}


def test_scan_outgoing_references(schema_view, seeded_db):
    # Initialize other dependencies for the test (besides the `SchemaView`).
    finder = Finder(database=seeded_db)
    collection_name_to_class_names = get_collection_name_to_class_names_map(schema_view=schema_view)
    references = identify_references(schema_view, collection_name_to_class_names)

    # Case 1: A company that has 0 outgoing references.
    violations = scan_outgoing_references(
        document={"_id": None, "id": "c-99", "type": "refscan:Company"},
        source_collection_name="company_set",
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(violations) == 0

    # Case 2: A company that has 1 intact outgoing reference.
    violations = scan_outgoing_references(
        document={"_id": None, "id": "c-99", "shareholders": ["e-1"], "type": "refscan:Company"},
        source_collection_name="company_set",
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(violations) == 0

    # Case 3: A company that has 2 intact outgoing references.
    violations = scan_outgoing_references(
        document={"_id": None, "id": "c-99", "shareholders": ["e-1", "e-2"], "type": "refscan:Company"},
        source_collection_name="company_set",
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(violations) == 0

    # Case 4: A company that has 1 invalid reference (out of 2).
    violations = scan_outgoing_references(
        document={"_id": None, "id": "c-99", "shareholders": ["e-1", "e-99"], "type": "refscan:Company"},
        source_collection_name="company_set",
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(violations) == 1
    assert violations[0].source_document_id == "c-99"
    assert violations[0].source_collection_name == "company_set"
    assert violations[0].source_class_name == "Company"
    assert violations[0].source_field_name == "shareholders"
    assert violations[0].target_id == "e-99"
    assert violations[0].name_of_collection_containing_target is None

    # Case 5: A company that has 2 invalid references (out of 2).
    violations = scan_outgoing_references(
        document={"_id": None, "id": "c-99", "shareholders": ["e-98", "e-99"], "type": "refscan:Company"},
        source_collection_name="company_set",
        schema_view=schema_view,
        references=references,
        finder=finder,
    )
    assert len(violations) == 2
    assert set(v.target_id for v in violations) == {"e-98", "e-99"}
    assert set(v.source_field_name for v in violations) == {"shareholders"}
    assert set(v.source_document_id for v in violations) == {"c-99"}
    assert set(v.source_collection_name for v in violations) == {"company_set"}
    assert set(v.source_class_name for v in violations) == {"Company"}
    assert set(v.name_of_collection_containing_target for v in violations) == {None}
