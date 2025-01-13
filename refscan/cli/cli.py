import typer

from refscan.cli.version import version
from refscan.cli.scan import scan
from refscan.cli.graph import graph

app = typer.Typer(
    no_args_is_help=True,  # treats the absence of args like the `--help` arg
    add_completion=False,  # hides the shell completion options from `--help` output
    rich_markup_mode="markdown",  # enables use of Markdown in docstrings and CLI help
)

# Add commands—implemented in other modules—to our Typer app.
# Reference: https://typer.tiangolo.com/tutorial/one-file-per-command/
#
# Note: Instead of annotating (with a decorator) a function defined in this module, we decorate a function
#       that we import from a different module. While both approaches result in the "no-longer-bare" function
#       being defined in this module, only the latter approach allows for the "bare" function to be defined
#       in a different module (which I think will facilitate code maintenance).
#       Reference: https://github.com/fastapi/typer/issues/178#issuecomment-738853400
#
app.command()(version)
app.command()(scan)
app.command()(graph)

if __name__ == "__main__":
    app()
