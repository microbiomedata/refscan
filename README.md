# refscan

`refscan` is a command-line tool people can use to **scan** the [NMDC](https://microbiomedata.org/) MongoDB database
for referential integrity violations.

```mermaid
%% This is the source code of a Mermaid diagram, which GitHub will render as a diagram.
%% Note: PyPI does not render Mermaid diagrams, and instead displays their source code.
%%       Reference: https://github.com/pypi/warehouse/issues/13083
graph LR
    schema[LinkML<br>schema]
    database[(MongoDB<br>database)]
    script[["refscan"]]
    violations["List of<br>violations"]
    references["List of<br>references"]:::dashed_border
    schema --> script
    database --> script
    script -.-> references
    script --> violations
    
    classDef dashed_border stroke-dasharray: 5 5
```

In addition to using refscan to scan the NMDC MongoDB database for referential integrity violations,
people can use `refscan` to generate **graphs** (diagrams) depicting which collections' documents (or which classes'
instances) can contain references to which _other_ collections' documents (or classes' instances) while still being
schema compliant.

<!-- Note: We removed the hard-coded Table of Contents because—nowadays—GitHub automatically derives/presents one. -->

## How it works

Here is a summary of how each of `refscan`'s main functions works under the hood.

### Scan

`refscan` does this in two stages:
1. It uses the LinkML schema to determine where references _can_ exist in a MongoDB database that conforms to the schema.
   > **Example:** The schema might say that, if a document in the `biosample_set` collection has a field named
   > `associated_studies`, that field must contain a list of `id`s of documents in the `study_set` collection.
2. It scans the MongoDB database to check the integrity of all the references that _do_ exist.
   > **Example:** For each document in the `biosample_set` collection that _has_ a field named `associated_studies`,
   > for each value in that field, confirm there _is_ a document having that `id` in the `study_set` collection.

### Graph

`refscan` does this in three stages:
1. It uses the LinkML schema to determine where references _can_ exist in a MongoDB database that conforms to the schema.
2. It formats that list of references into a data structure compatible with [`Cytoscape.js`](https://js.cytoscape.org/).
3. It outputs an HTML document that uses `Cytoscape.js` to visualize that data structure as a graph.

## Assumptions

`refscan` was designed under the assumption that **every document** in **every collection described by the schema** has
a **field named `type`**, whose value is the [class_uri](https://linkml.io/linkml/code/metamodel.html#linkml_runtime.linkml_model.meta.ClassDefinition.class_uri) of the schema class the document represents an instance
of. `refscan` uses that `class_uri` value (in that `type` field) to determine the _name_ of that schema class,
whose definition `refscan` then uses to determine _which fields_ of that document can contain references.

## Usage

### Install

Assuming you have `pipx` installed, you can install the tool by running the following command:

```shell
pipx install refscan
```

> [`pipx`](https://pipx.pypa.io/stable/) is a tool people can use to
> [download and install](https://pipx.pypa.io/stable/#where-does-pipx-install-apps-from)
> Python scripts that are hosted on PyPI.
> You can [install `pipx`](https://pipx.pypa.io/stable/installation/) by running `$ python -m pip install pipx`.

### Run

Once installed, you can display the tool's `--help` snippet by running:

```shell
refscan --help
```

At the time of this writing, the tool's `--help` snippet is:

```console
 Usage: refscan [OPTIONS] COMMAND [ARGS]...

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                            │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────╮
│ version   Show version number and exit.                                                │
│ scan      Scan the NMDC MongoDB database for referential integrity violations.         │
│ graph     Generate an interactive graph of the references described by a schema.       │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

<!-- Note: The above snippet was captured from a terminal window whose width was 90 characters. -->

Each command has its own `--help` snippet.

#### The `scan` command

At the time of this writing, the `--help` snippet for the `scan` command is:

```console
 Usage: refscan scan [OPTIONS]

 Scan the NMDC MongoDB database for referential integrity violations.

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ *  --schema                               FILE  Filesystem path at which the YAML file │
│                                                 representing the schema is located.    │
│                                                 [default: None]                        │
│                                                 [required]                             │
│    --database-name                        TEXT  Name of the database.                  │
│                                                 [default: nmdc]                        │
│    --mongo-uri                            TEXT  Connection string for accessing the    │
│                                                 MongoDB server. If you have Docker     │
│                                                 installed, you can spin up a temporary │
│                                                 MongoDB server at the default URI by   │
│                                                 running: $ docker run --rm --detach -p │
│                                                 27017:27017 mongo                      │
│                                                 [env var: MONGO_URI]                   │
│                                                 [default: mongodb://localhost:27017]   │
│    --verbose                                    Show verbose output.                   │
│    --skip-source-collection,--skip        TEXT  Name of collection you do not want to  │
│                                                 search for referring documents. Option │
│                                                 can be used multiple times.            │
│                                                 [default: None]                        │
│    --reference-report                     FILE  Filesystem path at which you want the  │
│                                                 program to generate its reference      │
│                                                 report.                                │
│                                                 [default: references.tsv]              │
│    --violation-report                     FILE  Filesystem path at which you want the  │
│                                                 program to generate its violation      │
│                                                 report.                                │
│                                                 [default: violations.tsv]              │
│    --no-scan                                    Generate a reference report, but do    │
│                                                 not scan the database for violations.  │
│    --locate-misplaced-documents                 For each referenced document not found │
│                                                 in any of the collections the schema   │
│                                                 allows, also search for it in all      │
│                                                 other collections.                     │
│    --help                                       Show this message and exit.            │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

<!-- Note: The above snippet was captured from a terminal window whose width was 90 characters. -->

##### The MongoDB connection string (`--mongo-uri`)

As documented in the `--help` snippet above, you can provide the MongoDB connection string to the tool via either
(a) the `--mongo-uri` option; or (b) an environment variable named `MONGO_URI`. The latter can come in handy
when the MongoDB connection string contains information you don't want to appear in your shell history,
such as a password.

Here's how you could create that environment variable:

```shell  
export MONGO_URI='mongodb://username:password@localhost:27017'
```

##### The schema (`--schema`)

As documented in the `--help` snippet above, you can provide the path to a YAML-formatted LinkML schema file to the tool
via the `--schema` option.

<details>

<summary>
Show/hide tips for getting a schema file
</summary>

---

If you have `curl` installed, you can download a YAML file from GitHub by running the following command (after replacing
the `{...}` placeholders and customizing the path):

```shell
# Download the raw content of https://github.com/{user_or_org}/{repo}/blob/{branch}/path/to/schema.yaml
curl -o schema.yaml https://raw.githubusercontent.com/{user_or_org}/{repo}/{branch}/path/to/schema.yaml
```

For example:

```shell
# Download the raw content of https://github.com/microbiomedata/nmdc-schema/blob/main/nmdc_schema/nmdc_materialized_patterns.yaml
curl -o schema.yaml https://raw.githubusercontent.com/microbiomedata/nmdc-schema/main/nmdc_schema/nmdc_materialized_patterns.yaml

# Download the raw content of https://github.com/microbiomedata/nmdc-schema/blob/v11.2.1/nmdc_schema/nmdc_materialized_patterns.yaml
curl -o schema.yaml https://raw.githubusercontent.com/microbiomedata/nmdc-schema/v11.2.1/nmdc_schema/nmdc_materialized_patterns.yaml
```

---
</details>

##### Output

While `refscan` is running, it will display console output indicating what it's currently doing.

![Screenshot of refscan console output](./docs/refscan-screenshot.png)

Once the scan is complete, the reference report (TSV file) and violation report (TSV file) will be available
in the current directory (or in custom directories, if any were specified via CLI options).

#### The `graph` command

At the time of this writing, the `--help` snippet for the `graph` command is:

```console
 Usage: refscan graph [OPTIONS]

 Generate an interactive graph of the references described by a schema.

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ *  --schema         FILE                Filesystem path at which the YAML file         │
│                                         representing the schema is located.            │
│                                         [default: None]                                │
│                                         [required]                                     │
│    --graph          FILE                Filesystem path at which you want refscan to   │
│                                         generate the graph.                            │
│                                         [default: graph.html]                          │
│    --subject        [collection|class]  Whether you want each node of the graph to     │
│                                         represent a collection or a class.             │
│                                         [default: collection]                          │
│    --verbose                            Show verbose output.                           │
│    --help                               Show this message and exit.                    │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

<!-- Note: The above snippet was captured from a terminal window whose width was 90 characters. -->

### Update

You can update the tool to [the latest version available on PyPI](https://pypi.org/project/refscan/) by running:

```shell
pipx upgrade refscan
```

### Uninstall

You can uninstall the tool from your computer by running:

```shell
pipx uninstall refscan
```

## Development

We use [`uv`](https://docs.astral.sh/uv/) to both (a) manage dependencies and (b) build distributable packages that can be published to PyPI.

- `pyproject.toml`: [Configuration file](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) for `uv` and other tools
- `uv.lock`: List of dependencies, both direct and [indirect/transitive](https://en.wikipedia.org/wiki/Transitive_dependency)

> Note: We initialized this repository using Poetry. We switched from Poetry to `uv` at around commit `#1449ceca`.

### Clone repository

```shell
git clone https://github.com/microbiomedata/refscan.git
cd refscan
```

### Set up Python virtual environment

You can set up a Python virtual environment by issuing the following command from the root directory of the repository:

```shell
uv sync
```

That command will:
1. **Create a Python virtual environment** at `.venv` (if one doesn't already exist there)
2. **Install all dependencies** described in `uv.lock` into that Python virtual environment
3. Uninstall all dependencies _not_ described in `uv.lock` from that Python virtual environment

### Activate Python virtual environment

Now that you have set up a Python virtual environment, you can activate it by issuing the following command:

```shell
source .venv/bin/activate
```

> Note: Once you're ready to _deactivate_ the Python virtual environment, you can do so by running `$ deactivate`.

### Make changes

Edit the tool's source code and documentation however you want.

While editing the tool's source code, you can run the tool as you normally would in order to test things out.

```shell
uv run refscan --help
```

### Check types

We use [mypy](https://mypy.readthedocs.io/en/stable/) as the static type checker for `refscan`.

You can perform static type checking by running the following command from the root directory of the repository:

```shell
uv run mypy
```

### Run tests

We use [pytest](https://docs.pytest.org/en/8.2.x/) as the testing framework for `refscan`.

Tests are defined in the `tests` directory.

You can run the tests by running the following command from the root directory of the repository:

```shell
uv run pytest
```

### Format code

We use [`ruff`](https://docs.astral.sh/ruff/formatter/) as the code _formatter_ for `refscan`.

We mostly use it with its default rules. All of the ways we deviate from those are listed
in the `[tool.ruff]` section of `pyproject.toml`.

You can _check_ the code's compliance with the "formatter rules" by running this command from the root directory of the repository:

```shell
uv run ruff format --check
```

That will output a _list_ of files that don't comply. To see the violations, themselves, you can run:

```shell
uv run ruff format --diff
```

You can _format_ the code by omitting the `--check` and `--diff` flags:

```shell
uv run ruff format
```

### Lint code

We also use [`ruff`](https://docs.astral.sh/ruff/linter/) as the code _linter_ for `refscan`.

We use it with its [default rules](https://docs.astral.sh/ruff/rules/), **plus** some additional ones,
all of which are listed in the `[tool.ruff.lint]` section of `pyproject.toml`.

You can _check_ the code's compliance with the "linter rules" by running this command from the root directory of the repository:

```shell
uv run ruff check
```

## Building and publishing

### Build for production

Whenever someone publishes a [GitHub Release](https://github.com/microbiomedata/refscan/releases) in this repository,
a [GitHub Actions workflow](.github/workflows/build-and-publish-package-to-pypi.yml)
will automatically build a package and publish it to [PyPI](https://pypi.org/project/refscan/).
That package will have a version identifier that matches the name of the Git tag associated with the Release.

### Test the build process locally

In case you want to test the build process locally, you can do so by running:

```shell
uv build
```

> That will create both a
> [source distribution](https://setuptools.pypa.io/en/latest/deprecated/distutils/sourcedist.html#creating-a-source-distribution)
> file (whose name ends with `.tar.gz`) and a
> [wheel](https://packaging.python.org/en/latest/specifications/binary-distribution-format/#binary-distribution-format)
> file (whose name ends with `.whl`) in the `dist` directory.
