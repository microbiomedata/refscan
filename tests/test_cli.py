from refscan.cli.cli import app
from typer.testing import CliRunner
from pathlib import Path


def test_graph_command_no_args():
    """Test the `graph` command with no arguments."""
    runner = CliRunner()
    result = runner.invoke(app, ["graph"])
    assert result.exit_code != 0, "The command should fail when no arguments are provided."
    assert "Usage:" in result.output, "Help message should be displayed when no arguments are provided."


def test_graph_command_with_valid_schema():
    """Test the `graph` command with a valid schema file."""
    runner = CliRunner()
    schema_path = Path("tests/schemas/database_with_references.yaml")
    output_path = Path("graph.html")

    result = runner.invoke(
        app,
        [
            "graph",
            "--schema",
            str(schema_path),
            "--graph",
            str(output_path),
            "--subject",
            "collection",
            "--verbose",
        ],
    )

    assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}"
    assert "Graph generated at:" in result.output, "Graph generation message not displayed."
    assert output_path.exists(), "The output graph file should be created."


def test_graph_command_with_custom_output_path():
    """Test the `graph` command with a custom output file path."""
    runner = CliRunner()
    schema_path = Path("tests/schemas/database_with_references.yaml")
    custom_output_path = Path("custom_graph.html")

    result = runner.invoke(
        app,
        [
            "graph",
            "--schema",
            str(schema_path),
            "--graph",
            str(custom_output_path),
        ],
    )

    assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}"
    assert "Graph generated at:" in result.output, "Graph generation message not displayed."
    assert custom_output_path.exists(), "The custom output graph file should be created."


def test_graph_command_help():
    """Test the `graph` command with the --help flag."""

    # Note: For this test, we define an environment variable (in the context of the `CliRunner`) named `TERM` having
    #       a value `"unknown"`. When Rich "sees" that environment variable, Rich will refrain from coloring its output.
    #       The reason we influence Rich in this way here is that, when we don't, this test fails when run via GitHub
    #       Actions. I think it has to do with the fact that GitHub Actions Runners do not allocate a TTY.
    #
    # References:
    # - https://click.palletsprojects.com/en/stable/api/#click.testing.CliRunner (re: the `env` kwarg)
    # - https://rich.readthedocs.io/en/stable/console.html#environment-variables (re: the `TERM` environment variable)
    # - https://github.com/actions/runner/issues/241 (re: GHA Runners not allocating a TTY)
    #
    runner = CliRunner(env=dict(TERM="unknown"))
    result = runner.invoke(app, ["graph", "--help"])

    assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}"
    assert "Usage:" in result.output, "Help message should be displayed."
    assert "--schema" in result.output, "Schema option should be described in the help message."
    assert "--graph" in result.output, "Graph option should be described in the help message."
    assert "--subject" in result.output, "Subject option should be described in the help message."
    assert "--verbose" in result.output, "Verbose option should be described in the help message."
