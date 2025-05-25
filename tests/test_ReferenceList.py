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
            source_collection_name="companies",
            source_class_name="Company",
            source_field_name="parent",
            target_collection_name="companies",
            target_class_name="Company",
        )
    )
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
    assert len(field_names) == 2
    assert "owner" in field_names
    assert "parent" in field_names

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
    assert len(field_names_by_class_name["Employee"]) == 1
    assert "employer" in field_names_by_class_name["Employee"]
    assert len(field_names_by_class_name["Company"]) == 2
    assert "owner" in field_names_by_class_name["Company"]
    assert "parent" in field_names_by_class_name["Company"]


def test_get_by_target_class_name(reference_list):
    filtered_references = reference_list.get_by_target_class_name("Company")
    assert len(filtered_references) == 2
    assert filtered_references[0].target_class_name == "Company"
    assert filtered_references[1].target_class_name == "Company"

    filtered_references = reference_list.get_by_target_class_name("Person")
    assert len(filtered_references) == 1
    assert filtered_references[0].target_class_name == "Person"

    filtered_references = reference_list.get_by_target_class_name("NonExistentClass")
    assert len(filtered_references) == 0


def test_group_by_source_collection_name(reference_list):
    grouped_references = reference_list.group_by_source_collection_name()
    assert len(grouped_references) == 2
    assert "companies" in grouped_references
    assert "employees" in grouped_references
    assert len(grouped_references["companies"]) == 2
    assert len(grouped_references["employees"]) == 1


def test_as_table(reference_list):
    assert isinstance(reference_list.as_table(), Table)
