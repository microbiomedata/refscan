# refscan

`refscan` is a command-line tool people can use to scan the NMDC MongoDB database
for referential integrity violations.

```mermaid
%% This is the source code of a Mermaid diagram, which GitHub will render as a diagram.
%% Note: PyPI does not render Mermaid diagrams, and instead displays their source code.
%%       Reference: https://github.com/pypi/warehouse/issues/13083
graph LR
    database[(MongoDB<br>Database)]
    script[["refscan.py"]]
    result["List of<br>violations"]
    database --> script --> result
```

## Development status

`refscan` is in early development and its author does not recommend anyone use it for anything.
