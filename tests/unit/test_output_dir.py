"""The folder of generated documents is private to the user running the server."""

import os
import stat
import sys

import pytest

from mcp_legal_it.lib._output import CartellaNonSicura, ensure_private_dir

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX owner and mode")


@posix_only
def test_new_folder_is_0700(tmp_path):
    path = ensure_private_dir(str(tmp_path / "mcp-legal-it"))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o700


@posix_only
def test_existing_open_folder_is_tightened(tmp_path):
    path = tmp_path / "mcp-legal-it"
    path.mkdir()
    path.chmod(0o777)
    ensure_private_dir(str(path))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o700


def test_symlink_is_refused(tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = tmp_path / "mcp-legal-it"
    link.symlink_to(target)
    with pytest.raises(CartellaNonSicura):
        ensure_private_dir(str(link))


def test_a_file_in_its_place_is_refused(tmp_path):
    path = tmp_path / "mcp-legal-it"
    path.write_text("x")
    with pytest.raises(OSError):
        ensure_private_dir(str(path))


@posix_only
def test_folder_of_another_user_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "mcp-legal-it"
    path.mkdir()
    monkeypatch.setattr(os, "getuid", lambda: os.stat(path).st_uid + 1)
    with pytest.raises(CartellaNonSicura, match="altro utente"):
        ensure_private_dir(str(path))


def test_every_generator_saves_through_the_private_folder():
    from mcp_legal_it.lib._output import OUTPUT_DIR
    from mcp_legal_it.tools import analisi_fornitori, legal_citations, modelli_atti, procure_quotazioni

    assert analisi_fornitori._OUTPUT_DIR == OUTPUT_DIR
    assert procure_quotazioni._OUTPUT_DIR == OUTPUT_DIR
    assert legal_citations._PDF_OUTPUT_DIR == OUTPUT_DIR
    assert modelli_atti._OUTPUT_DIR == OUTPUT_DIR
