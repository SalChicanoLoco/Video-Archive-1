"""
File renaming module.

Provides a function to rename a file in the input directory to a
standardised name. The rename operation is atomic: if the target
exists, an error is raised to avoid accidental overwrites.
"""

import os
from pathlib import Path

from . import utils


def rename_file(path: str, new_name: str) -> str:
    """Rename the file at ``path`` to ``new_name`` in the same directory.

    Args:
        path: Absolute path to an existing file (must be within INPUT_ROOT).
        new_name: New filename (may include extension). Unsafe characters
            will be replaced.

    Returns:
        The absolute path of the renamed file.

    Raises:
        ValueError: If the target file already exists.
        OSError: If renaming fails for other reasons.
    """
    src = Path(path).resolve()
    # Ensure path is valid and within INPUT_ROOT
    utils.validate_input_path(str(src))
    # Sanitize new name
    safe_name = utils.safe_filename(new_name)
    dest = src.with_name(safe_name)
    if dest.exists():
        raise ValueError(f"Target file already exists: {dest}")
    src.rename(dest)
    return str(dest)