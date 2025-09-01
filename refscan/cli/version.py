import typer

from refscan.lib.constants import console
from refscan import app_version


def version() -> None:
    r"""
    Show version number and exit.
    """
    console.print(f"[white]{app_version}[/white]")
    raise typer.Exit()
