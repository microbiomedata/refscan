from importlib.metadata import metadata, PackageMetadata, PackageNotFoundError


def get_package_metadata(key: str) -> str:
    r"""
    Returns metadata about the installed package.

    References:
    - https://docs.python.org/3/library/importlib.metadata.html#distribution-metadata
    - https://github.com/python-poetry/poetry/issues/273#issuecomment-570999678
    """
    metadata_value = ""
    try:
        package_metadata: PackageMetadata = metadata("refscan")
        metadata_value = package_metadata.get(key)
    except PackageNotFoundError:
        pass
    return metadata_value
