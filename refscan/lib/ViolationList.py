from pathlib import Path
from dataclasses import fields, astuple
from collections import UserList
import csv

from refscan.lib.Violation import Violation


class ViolationList(UserList):
    """
    A list of violations.
    """

    def dump_to_tsv_file(
        self, file_path: str | Path, include_name_of_collection_containing_target: bool = True
    ) -> None:
        """
        Helper function that dumps the violations to a TSV file at the specified path.
        """
        column_names = [field_.name for field_ in fields(Violation)]
        if not include_name_of_collection_containing_target:
            column_names = [cn for cn in column_names if cn != "name_of_collection_containing_target"]
        with open(file_path, "w", newline="") as tsv_file:
            writer = csv.writer(tsv_file, delimiter="\t")
            writer.writerow(column_names)  # header row
            for violation in self.data:
                writer.writerow(astuple(violation))  # data row
