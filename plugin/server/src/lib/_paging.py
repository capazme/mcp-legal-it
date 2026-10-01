"""Paged reading of long texts: the ``da_carattere`` parameter of the reading tools.

Every tool that reads a full decision or act caps its answer (a judgment can run
to 90,000 characters, more than a model should take in one call). Before this
module the part beyond the cap was simply unreachable: a long CGUE judgment kept
its beginning and its operative part, but the Court's reasoning in between could
not be read at all.

The contract, shared by all the reading tools:

- ``da_carattere=1`` (the default) keeps each tool's own first answer (some keep
  the dispositivo or the epigrafe of a long text); when something is left out,
  the note says from which character to resume (:func:`resume_hint`).
- ``da_carattere=N`` returns the window of the same full text that starts at
  character ``N`` (1-based, the numbering the notes use), at most ``limit``
  characters long, and says where the next window starts (:func:`page`).

Positions always refer to the full text the tool reads, so the numbers in a
note ("Omessi i caratteri 25001-61449") can be passed back unchanged.
"""

PARAM_DOC = (
    "da_carattere: Carattere da cui leggere (1 = inizio, default). Se il testo supera il limite, "
    "la nota finale indica il valore con cui ripetere la chiamata per leggere il seguito"
)


def resume_hint(next_start: int) -> str:
    """The sentence that tells how to read on from ``next_start``."""
    return f"per leggere il seguito ripetere la chiamata con da_carattere={next_start}"


def invalid_start(da_carattere: int) -> str | None:
    """Error message for an unusable ``da_carattere``, or None when it is valid."""
    if not isinstance(da_carattere, int) or isinstance(da_carattere, bool) or da_carattere < 1:
        return f"da_carattere deve essere un intero maggiore o uguale a 1 (ricevuto: {da_carattere!r})"
    return None


def page(text: str, da_carattere: int, limit: int) -> tuple[str, str]:
    """Window of ``text`` from character ``da_carattere`` (1-based), and its note.

    Returns ``(body, note)``. The note always states the range returned and the
    total; it ends with the next ``da_carattere`` when text remains, or says the
    text is over. A start beyond the end returns an empty body and a note saying so.
    """
    total = len(text)
    if da_carattere > total:
        return "", f"*[da_carattere={da_carattere} oltre la fine del testo ({total} caratteri)]*"
    start = da_carattere - 1
    end = min(total, start + limit)
    body = text[start:end]
    if end < total:
        note = f"*[Caratteri {da_carattere}-{end} su {total} totali: {resume_hint(end + 1)}]*"
    else:
        note = f"*[Caratteri {da_carattere}-{end} su {total} totali: fine del testo]*"
    return body, note
