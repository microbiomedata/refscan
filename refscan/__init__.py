import importlib.metadata


def get_package_metadata(key: str) -> str:
    r"""
    Returns metadata about the installed package.

    Reference: https://github.com/python-poetry/poetry/issues/273#issuecomment-570999678
    """
    package_metadata = importlib.metadata.metadata("refscan")
    return package_metadata[key] if key in package_metadata else ""
