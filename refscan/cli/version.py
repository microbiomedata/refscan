import typer

from refscan.lib.constants import console
from refscan import get_package_metadata

app_version = get_package_metadata("Version")


def version() -> None:
    r"""
    Show version number and exit.
    """
    console.print(f"[white]{app_version}[/white]")
    raise typer.Exit()
