# """Jupyter notebook helper functions."""


import nbformat

from .globals import NBFORMAT_VERSION


def safe_read_notebook(p, as_version=NBFORMAT_VERSION):
    """Return read and return a Jupyter notebook from path `p`.

    Unlike `nbformat.reads (which this wraps)`, this function returns None
    if `string` is not a valid notebook.
    """
    try:
        return nbformat.reads(p, as_version=as_version)
    except nbformat.reader.NotJSONError:
        return None
