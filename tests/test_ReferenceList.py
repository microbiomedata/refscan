import pytest
from rich.table import Table

from refscan.lib.Reference import Reference
from refscan.lib.ReferenceList import ReferenceList


# Define a `pytest` fixture.
#
# Note: Tests can tell `pytest` they depend upon a given fixture, by
#       having a parameter whose name matches that of the fixture.
#       Reference: https://docs.pytest.org/en/6.2.x/fixture.html
#
@pytest.fixture
def reference_list():
    references = ReferenceList()
    references.append(
        Reference(
            source_collection_name="employees",
            source_class_name="Employee",
            source_field_name="employer",
            target_collection_name="companies",
            target_class_name="Company",
        )
    )
    references.append(
        Reference(
            source_collection_name="companies",
            source_class_name="Company",
            source_field_name="owner",
            target_collection_name="persons",
            target_class_name="Person",
        )
    )
    return references


def test_get_source_collection_names(reference_list):
    collection_names = reference_list.get_source_collection_names()
    assert len(collection_names) == 2
    assert "employees" in collection_names
    assert "companies" in collection_names
    assert "persons" not in collection_names


def test_get_source_field_names_of_source_collection(reference_list):
    field_names = reference_list.get_source_field_names_of_source_collection("employees")
    assert len(field_names) == 1
    assert "employer" in field_names

    field_names = reference_list.get_source_field_names_of_source_collection("companies")
    assert len(field_names) == 1
    assert "owner" in field_names

    field_names = reference_list.get_source_field_names_of_source_collection("persons")
    assert len(field_names) == 0


def test_get_target_collection_names(reference_list):
    collection_names = reference_list.get_target_collection_names("Employee", "employer")
    assert len(collection_names) == 1
    assert "companies" in collection_names

    collection_names = reference_list.get_target_collection_names("Employee", "foo")
    assert len(collection_names) == 0


def test_get_reference_field_names_by_source_class_name(reference_list):
    field_names_by_class_name = reference_list.get_reference_field_names_by_source_class_name()
    assert len(field_names_by_class_name.keys()) == 2
    assert "Employee" in field_names_by_class_name
    assert "Company" in field_names_by_class_name
    assert field_names_by_class_name["Employee"] == ["employer"]
    assert field_names_by_class_name["Company"] == ["owner"]


def test_as_table(reference_list):
    assert isinstance(reference_list.as_table(), Table)
