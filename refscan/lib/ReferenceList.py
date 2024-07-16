from typing import List, Dict
from pathlib import Path
from dataclasses import fields, astuple
from collections import UserList
from itertools import groupby
import csv

from rich.table import Table, Column

from refscan.lib.Reference import Reference


class ReferenceList(UserList):
    """
    A list of references.

    Note: `UserList` is a base class that facilitates the implementation of custom list classes.
          One thing it does is enable sorting via `sorted(the_list)`.
    """

    def get_source_collection_names(self) -> list[str]:
        """
        Returns the distinct `source_collection_names` values among all references in the list.
        """
        distinct_source_collection_names = []
        for reference in self.data:
            if reference.source_collection_name not in distinct_source_collection_names:
                distinct_source_collection_names.append(reference.source_collection_name)
        return distinct_source_collection_names

    def count_source_collections(self) -> int:
        r"""
        Returns the number of distinct source collection names among all references in the list.
        """
        return len(self.get_source_collection_names())

    def get_source_field_names_of_source_collection(self, collection_name: str) -> list[str]:
        """
        Returns the distinct source field names of the specified source collection.
        """
        distinct_source_field_names = []
        for reference in self.data:
            if reference.source_collection_name == collection_name:
                if reference.source_field_name not in distinct_source_field_names:
                    distinct_source_field_names.append(reference.source_field_name)
        return distinct_source_field_names

    def get_target_collection_names(
        self,
        source_class_name: str,
        source_field_name: str,
    ) -> list[str]:
        """
        Returns a list of the names of the collections in which a [target] document referenced by the specified field
        of a [source] document representing an instance of the specified schema class, might exist.

        TODO: Execution spends a lot of time in this function. Consider replacing it with something faster (e.g. a LUT).
        """
        target_collection_names = []
        for reference in self.data:  # note: in a `UserList`, `self.data` refers to the underlying list data structure

            # If this reference's source describes the specified source, record the reference's target collection name.
            if reference.source_class_name == source_class_name and reference.source_field_name == source_field_name:
                target_collection_names.append(reference.target_collection_name)

        distinct_target_collection_names = list(set(target_collection_names))
        return distinct_target_collection_names

    def get_groups(self, field_names: list[str]):
        r"""
        Returns an iterable of groups, where each group has a distinct combination of values in the specified fields.

        TODO: Add a type hint that indicates the return type. It's an instance of a class named `groupby` (lowercase).

        Note: This method can be used to "consolidate" references that have the same source collection name,
              source field name, and target collection name (i.e. ones that only differ by target class name).
        """

        def make_group_key(reference: Reference) -> tuple:
            """Helper function that returns a key that can be used to group references."""
            values = []
            for field_name in field_names:
                if not hasattr(reference, field_name):
                    raise ValueError(f"No such field: {field_name}")
                values.append(getattr(reference, field_name))
            return tuple(values)

        groups = groupby(sorted(self.data), key=make_group_key)
        return groups

    def dump_to_tsv_file(self, file_path: str | Path) -> None:
        r"""
        Helper function that dumps the references to a TSV file at the specified path.
        """
        column_names = [field_.name for field_ in fields(Reference)]
        with open(file_path, "w", newline="") as tsv_file:
            writer = csv.writer(tsv_file, delimiter="\t")
            writer.writerow(column_names)  # header row
            for reference in self.data:
                writer.writerow(astuple(reference))  # data row

    def get_reference_field_names_by_source_class_name(self) -> Dict[str, List[str]]:
        r"""
        Returns a dictionary that maps source class names to a list of the
        names of the fields of that class that contain references.

        Example: {"Study": ["part_of"]}
        """
        reference_field_names_by_source_class_name: Dict[str, List[str]] = {}
        for reference in self.data:
            source_class_name = reference.source_class_name
            source_field_name = reference.source_field_name

            # Initialize a dictionary item for this source class, if one doesn't already exist.
            if source_class_name not in reference_field_names_by_source_class_name.keys():
                reference_field_names_by_source_class_name[source_class_name] = []

            # If the source field name isn't already in this class's list, append it.
            if source_field_name not in reference_field_names_by_source_class_name[source_class_name]:
                reference_field_names_by_source_class_name[source_class_name].append(source_field_name)

        return reference_field_names_by_source_class_name

    def as_table(self) -> Table:
        r"""
        Returns the references as a `rich.Table` instance.
        """

        # Make the data rows for the table. Data rows that would have had the same
        # (combination of) the following fields, get consolidated into a single row;
        # and all the target class names are displayed as a list on that row.
        fields_to_group_rows_by = [
            "source_collection_name",
            "source_class_name",
            "source_field_name",
            "target_collection_name",
        ]
        groups = self.get_groups(fields_to_group_rows_by)
        data_rows: list[tuple[str, str, str, str, str]] = []
        for key, group in groups:
            target_class_names = list(set([ref.target_class_name for ref in group]))  # omit duplicate class names
            row = (key[0], key[1], key[2], key[3], ", ".join(target_class_names))
            data_rows.append(row)

        # Initialize the table, then add the data rows to it.
        table = Table(
            Column(header="Source collection", footer=f"{len(data_rows)} rows"),
            Column(header="Source class"),
            Column(header="Source field"),
            Column(header="Target collection"),
            Column(header="Target class(es)"),
            title="References",
            show_footer=True,
        )
        for row in data_rows:
            table.add_row(*row)

        return table
