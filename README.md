# refscan

`refscan` is a command-line tool people can use to scan the [NMDC](https://microbiomedata.org/) MongoDB database
for referential integrity violations.

```mermaid
%% This is the source code of a Mermaid diagram, which GitHub will render as a diagram.
%% Note: PyPI does not render Mermaid diagrams, and instead displays their source code.
%%       Reference: https://github.com/pypi/warehouse/issues/13083
graph LR
    schema[LinkML<br>schema]
    database[(MongoDB<br>database)]
    script[["refscan.py"]]
    violations["List of<br>violations"]
    references["List of<br>references"]:::dashed_border
    schema --> script
    database --> script
    script -.-> references
    script --> violations
    
    classDef dashed_border stroke-dasharray: 5 5
```

## How it works

`refscan` does its job in two stages:
1. It uses the LinkML schema to determine "what to scan;" i.e. all of the document-to-document references
   that _can_ exist in a database that conforms to the schema.
   > **Example:** The schema might say that, if a document exists in a collection named `cars`, that document must have
   > a field named `owner` that contains the `id` of a document in a collection named `persons`.
2. It scans the MongoDB database to check the integrity of all of the references that _do_ exist.
   > **Example:** For each document in the collection named `cars`, `refscan` checks whether the value in its `owner`
   > field matches the `id` of some document in the collection named `persons`.

## Usage

### Installation

Assuming you have `pipx` installed, you can install the tool by running the following command:

```shell
pipx install refscan
```

> [`pipx`](https://pipx.pypa.io/stable/) is a tool people can use to
> [download and install](https://pipx.pypa.io/stable/#where-does-pipx-install-apps-from)
> Python scripts that are hosted on PyPI.
> You can [install `pipx`](https://pipx.pypa.io/stable/installation/) by running `$ python -m pip install pipx`.

### Running

You can display the tool's `--help` snippet by running:

```shell
refscan --help
```

At the time of this writing, the tool's `--help` snippet is:

```console
 Usage: refscan [OPTIONS]

 Scans the NMDC MongoDB database for referential integrity violations.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --schema                                           FILE  Filesystem path at which the YAML file representing the  │
│                                                             schema is located.                                       │
│                                                             [default: None]                                          │
│                                                             [required]                                               │
│    --database-name                                    TEXT  Name of the database.                                    │
│                                                             [default: nmdc]                                          │
│    --mongo-uri                                        TEXT  Connection string for accessing the MongoDB server. If   │
│                                                             you have Docker installed, you can spin up a temporary   │
│                                                             MongoDB server at the default URI by running: $ docker   │
│                                                             run --rm --detach -p 27017:27017 mongo                   │
│                                                             [env var: MONGO_URI]                                     │
│                                                             [default: mongodb://localhost:27017]                     │
│    --verbose                          --no-verbose          Show verbose output.                                     │
│                                                             [default: no-verbose]                                    │
│    --skip-source-collection,--skip                    TEXT  Name of collection you do not want to search for         │
│                                                             referring documents. Option can be used multiple times.  │
│                                                             [default: None]                                          │
│    --reference-report                                 FILE  Filesystem path at which you want the program to         │
│                                                             generate its reference report.                           │
│                                                             [default: references.tsv]                                │
│    --violation-report                                 FILE  Filesystem path at which you want the program to         │
│                                                             generate its violation report.                           │
│                                                             [default: violations.tsv]                                │
│    --help                                                   Show this message and exit.                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

> Note: The above snippet was captured from a terminal window whose width was 120 characters.

#### The MongoDB connection string (`--mongo-uri`)

As documented in the `--help` snippet above, you can provide the MongoDB connection string to the tool via either
(a) the `--mongo-uri` option; or (b) an environment variable named `MONGO_URI`. The latter can come in handy
when the MongoDB connection string contains information you don't want to appear in your shell history,
such as a password.

Here's how you could create that environment variable:

```shell  
export MONGO_URI='mongodb://username:password@localhost:27017'
```

### Updating

You can update the tool to [the latest version available on PyPI](https://pypi.org/project/refscan/) by running:

```shell
pipx upgrade refscan
```

### Uninstallation

You can uninstall the tool from your computer by running:

```shell
pipx uninstall refscan
```

## Development

We use [Poetry](https://python-poetry.org/) to both (a) manage dependencies and (b) publish packages to PyPI.

- `pyproject.toml`: Configuration file for Poetry and other tools (was generated via `$ poetry init`)
- `poetry.lock`: List of dependencies, direct and indirect (was generated via `$ poetry update`)

### Clone repository

```shell
git clone https://github.com/microbiomedata/refscan.git
cd refscan
```

### Create virtual environment

Create a Poetry virtual environment and attach to its shell:

```shell
poetry shell
```

> You can see information about the Poetry virtual environment by running: `$ poetry env info`

> You can detach from the Poetry virtual environment's shell by running: `$ exit`

From now on, I'll refer to the Poetry virtual environment's shell as the "Poetry shell."

### Install dependencies

At the Poetry shell, install the project's dependencies:

```shell
poetry install
```

### Make changes

Edit the tool's source code and documentation however you want.

While editing the tool's source code, you can run the tool as you normally would in order to test things out.

```shell
refscan --help
```

## Building and publishing

### Build for production

Whenever someone publishes a [GitHub Release](https://github.com/microbiomedata/refscan/releases) in this repository,
a [GitHub Actions workflow](.github/workflows/build-and-publish-package-to-pypi.yml)
will automatically build a package and publish it to [PyPI](https://pypi.org/project/refscan/).
That package will have a version identifier that matches the name of the Git tag associated with the Release.

The GitHub Actions workflow will automatically 

### Testing the build process locally

In case you want to test the build process locally, you can do so by running:

```shell
poetry build
```

> That will create both a
> [source distribution](https://setuptools.pypa.io/en/latest/deprecated/distutils/sourcedist.html#creating-a-source-distribution)
> file (whose name ends with `.tar.gz`) and a
> [wheel](https://packaging.python.org/en/latest/specifications/binary-distribution-format/#binary-distribution-format)
> file (whose name ends with `.whl`) in the `dist` directory.

## Assumptions

`refscan` was designed under some assumptions about the schema and database, including:

1. Each source document (i.e. document containing references) has a field named `type`, whose value (a string) is the [class_uri](https://linkml.io/linkml/code/metamodel.html#linkml_runtime.linkml_model.meta.ClassDefinition.class_uri) of the schema class of which the document represents an instance. For example, the `type` field of each document in the `study_set` collection has the value `"nmdc:Study"`. 

## Tips

`refscan` requires the user to specify the path to a schema in YAML format. If you have `curl` installed, you can download a YAML file from GitHub by running the following command (after replacing the `{...}` placeholders and customizing the path):

```shell
# Download the raw content of https://github.com/{user_or_org}/{repo}/blob/{branch}/path/to/schema.yaml
curl -o schema.yaml https://raw.githubusercontent.com/{user_or_org}/{repo}/{branch}/path/to/schema.yaml
```

For example:

```shell
# Download the raw content of https://github.com/microbiomedata/berkeley-schema-fy24/blob/main/nmdc_schema/nmdc_materialized_patterns.yaml
curl -o schema.yaml https://raw.githubusercontent.com/microbiomedata/berkeley-schema-fy24/main/nmdc_schema/nmdc_materialized_patterns.yaml
```
