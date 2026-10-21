"""Where the generators save the files they produce, and who may read them.

Procure, quotazioni, atti, supplier reports and law PDFs carry client data.
They go to `<tempdir>/mcp-legal-it`, which on Linux is `/tmp/mcp-legal-it`: a
directory shared by every user of the machine. Created with the default
umask it is world-readable, and a directory another user created first (or a
symlink they planted there) would receive the files. So the folder is made
private to the user running the server, and a folder that belongs to someone
else is refused rather than written into.
"""

from __future__ import annotations

import os
import stat
import tempfile

#: Default folder of the generated files.
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "mcp-legal-it")


class CartellaNonSicura(OSError):
    """The output folder exists but is not a private folder of this user."""


def ensure_private_dir(path: str) -> str:
    """Create `path` readable only by this user (0700) and return it.

    An existing folder owned by this user is tightened to 0700. A symlink, a
    non-directory, or a folder owned by another user raises `CartellaNonSicura`.
    On Windows (no POSIX owner or mode) only the directory check applies.
    """
    os.makedirs(path, mode=0o700, exist_ok=True)
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise CartellaNonSicura(f"{path} non è una cartella: file non salvato")
    if hasattr(os, "getuid"):
        if info.st_uid != os.getuid():
            raise CartellaNonSicura(
                f"{path} appartiene a un altro utente: file non salvato"
            )
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.chmod(path, 0o700)
    return path
