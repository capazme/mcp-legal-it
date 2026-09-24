"""Record, per tool call, which hand-maintained tables the call actually read.

`@sourced(...)` declares which tables a tool's answer rests on, and
`scripts/audit_tool_annotations.py` verifies that declaration against the source
-- statically. This module adds the runtime half of the same claim: the
module-level constants that hold a table (or a projection of one, such as
`_CATEGORIE = sorted({v["categoria"] for v in _CATALOGO.values()})`) are replaced
by dict and list subclasses that note their dataset when they are read, so the
server can report which tables a *call* opened rather than which ones the code
might open.

The two oracles are deliberately independent, and that is the point: the audit
walks the call graph and says what the code can read, the ledger observes the
process and says what it did read. A table the ledger reports that the audit does
not attribute to the tool means the walk misses a reader -- the failure mode that
hid `codici_tributo`, `modelli_atti` and `preavviso_ccnl` -- and the suite fails
on it instead of trusting the derivation.

The same observation drives the answer itself: `src/lib/_data.py` names in the
`dati_applicati` footer the tables the call actually read, falling back to the
declaration only when the ledger saw nothing (a table reached through a bare
scalar computed at import cannot be wrapped). And a call that rests on a table
which is expired or unverified says so structurally, in `_meta`, not only in the
prose of the footer -- including what `src/lib/_precision.py` did to the claim
the tool declares in its docstring: the grade it kept, or the refusal it earned.

The wrapping is shallow on purpose. Reaching the top of a table is what proves
the call consulted it, and leaving nested values plain keeps `json.dumps`, `==`
and the host's serialization working on exactly the same objects as before.

Nothing is recorded outside a `recording()` block, so prompts, resources and
import-time projections cost nothing.
"""

from __future__ import annotations

import sys
from typing import Any

from fastmcp.server.middleware import Middleware

from . import _clock, _precision, _refusals, _regime, _sources
from ._data import warnings as data_warnings
from ._tables_open import CURRENT, note, opened, recording

#: Key under which a call declares the tables it opened, in the result `_meta`.
OPENED_TABLES_KEY = "mcp-legal-it/opened_tables"
#: Key under which it flags the tables that are expired or unverified.
DATA_WARNINGS_KEY = "mcp-legal-it/data_warnings"
#: Key under which it reports what the answer is worth, when that is less than
#: the tool declared.
PRECISION_KEY = "mcp-legal-it/precisione"
#: Key under which a tool result reports the refusal ledger, when asked for.
REFUSALS_KEY = "mcp-legal-it/verbale_rifiuti"
#: Key under which a call declares the online sources it consulted. Same meta,
#: same pass, so a host reads one place to know what an answer rests on.
CONSULTED_SOURCES_KEY = "mcp-legal-it/fonti_consultate"
#: Key under which a call declares that the tool computes under a superseded
#: rule (`Regime: PREVIGENTE` in its docstring, see `src/lib/_regime.py`).
REGIME_KEY = _regime.META_KEY

__all__ = [
    "CONSULTED_SOURCES_KEY",
    "CURRENT",
    "DATA_WARNINGS_KEY",
    "OPENED_TABLES_KEY",
    "PRECISION_KEY",
    "REFUSALS_KEY",
    "REGIME_KEY",
    "TableDict",
    "TableLedgerMiddleware",
    "TableList",
    "apply_table_ledger",
    "install",
    "note",
    "opened",
    "recording",
]


class TableDict(dict):
    """A table payload that notes its dataset when it is read."""

    def __init__(self, payload: dict, dataset: str = "") -> None:
        super().__init__(payload)
        self.dataset = dataset

    def __getitem__(self, key: Any) -> Any:
        note(self.dataset)
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        note(self.dataset)
        return super().get(key, default)

    def keys(self):  # type: ignore[override]
        note(self.dataset)
        return super().keys()

    def values(self):  # type: ignore[override]
        note(self.dataset)
        return super().values()

    def items(self):  # type: ignore[override]
        note(self.dataset)
        return super().items()

    def __iter__(self):
        note(self.dataset)
        return super().__iter__()

    def __contains__(self, key: Any) -> bool:
        note(self.dataset)
        return super().__contains__(key)


class TableList(list):
    """A table payload (or a projection of one) that notes its dataset."""

    def __init__(self, payload: list, dataset: str = "") -> None:
        super().__init__(payload)
        self.dataset = dataset

    def __getitem__(self, index: Any) -> Any:
        note(self.dataset)
        return super().__getitem__(index)

    def __iter__(self):
        note(self.dataset)
        return super().__iter__()

    def __contains__(self, item: Any) -> bool:
        note(self.dataset)
        return super().__contains__(item)


def install(bindings: dict[str, dict[str, str]]) -> int:
    """Wrap the table-carrying constants of already-imported modules.

    Only modules already in `sys.modules` are touched: importing one here would
    run its module-level loads inside this function, and a table that no import
    reached is one no tool can read anyway. Constants whose value is already a
    wrapper are skipped, so calling this twice is not a double wrap.
    """
    wrapped = 0
    for module_name, constants in bindings.items():
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for name, dataset in constants.items():
            value = getattr(module, name, None)
            if isinstance(value, (TableDict, TableList)):
                continue
            replacement: Any = None
            if isinstance(value, dict):
                replacement = TableDict(value, dataset)
            elif isinstance(value, list):
                replacement = TableList(value, dataset)
            if replacement is None:
                continue
            setattr(module, name, replacement)
            wrapped += 1
    return wrapped


class TableLedgerMiddleware(Middleware):
    """Declare, on every tool result, the tables that call actually opened.

    The list lives in the result's `_meta`, next to the answer it belongs to, so
    a host can show it and a test can read it over the wire instead of trusting
    the source. An answer that reads nothing carries no key: absence is the
    honest report for a pure algorithm, and an empty list would look like a
    declaration nobody could distinguish from a missing one.

    Three keys, three facts. `opened_tables` is the raw observation. `data_warnings`
    is the part a reader has to act on -- the tables in play whose vintage is
    expired or unverified -- and it is computed from the tables the answer
    actually rests on, which is the observed set when there is one and the
    tool's declared set when the ledger could not see anything. `precisione` is
    what those states did to the answer's claim: the grade the tool declared and
    the grade the answer can sustain, or `nessuna` when the tool refused to
    compute. It is reported here as well as in the body because a tool that
    answers with a string has nowhere else to say it.

    The block also collects the two observations the decision needs, so that a
    single call is observed once: which tables were opened, and whether the call
    asked the clock what day it is -- an answer anchored to today cannot keep
    using an expired table, while one about a closed period can say so and go on.
    """

    def __init__(
        self,
        tool_tables: dict[str, tuple[str, ...]] | None = None,
        tool_alternatives: dict[str, str] | None = None,
        tool_sources: dict[str, tuple[str, ...]] | None = None,
        tool_regimes: dict[str, dict] | None = None,
    ) -> None:
        self.tool_tables = tool_tables or {}
        self.tool_alternatives = tool_alternatives or {}
        # The committed policy of which tool computes under a superseded rule
        # (PREVIGENTE in tool_annotations.py): the answer's body already carries
        # it, this stamps the same fact in `_meta` for a host that reads only that.
        self.tool_regimes = tool_regimes or {}
        # The committed policy of which tool may reach which online source (the
        # same names the audit collects). A source the observation saw but the
        # policy does not list means the walk missed a fetcher -- the suite
        # fails on it, exactly like the table half.
        self.tool_sources = tool_sources or {}

    async def on_call_tool(self, context, call_next):
        with (
            recording() as opened,
            _clock.recording(),
            _precision.recording(),
            _sources.recording(),
        ):
            result = await call_next(context)
            esito = _precision.current()
            # Read inside the recording block: once it exits, the contextvar is
            # cleared and the observation would be lost. `opened` survives the
            # block because it is the yielded set; the sources need the same
            # care, stamp included (the moment of the readback is still within
            # seconds of the fetches).
            consultate = _sources.consulted()
            consultate_al = _sources.now_stamp()
        if not hasattr(result, "meta"):
            return result

        message = getattr(context, "message", None)
        name = getattr(message, "name", None)
        seen = sorted(opened)
        politiche = self.tool_sources.get(name) or ()
        non_dichiarate = sorted({f["fonte"] for f in consultate} - set(politiche))
        if non_dichiarate:
            print(
                "[_ledger] %s consulted undeclared online sources: %s "
                "(add them to TOOL_SOURCES in table_bindings.py)" % (name, non_dichiarate),
                flush=True,
            )
        # A call that supplied the datum its table would have provided read no
        # table *because it needed none*: falling back to the declaration here
        # would flag the vintage of a table the call deliberately did not open.
        arguments = getattr(message, "arguments", None) or {}
        alternativa = self.tool_alternatives.get(name)
        fornita = bool(alternativa) and arguments.get(alternativa) is not None
        effective = seen or ([] if fornita else sorted(self.tool_tables.get(name, ())))
        meta = dict(result.meta or {})
        if seen:
            meta[OPENED_TABLES_KEY] = seen
        if consultate:
            blocco = {
                "consultate_al": consultate_al,
                "fonti": consultate,
                "non_dichiarate": non_dichiarate,
            }
            meta[CONSULTED_SOURCES_KEY] = blocco
        avvisi = data_warnings(effective)
        if avvisi:
            meta[DATA_WARNINGS_KEY] = avvisi
        regime = self.tool_regimes.get(name)
        if regime:
            meta[REGIME_KEY] = {"stato": _regime.PREVIGENTE.lower(), **regime}
        if esito is not None:
            meta[PRECISION_KEY] = esito.to_dict()
            # The refusal ledger: what the vintage policy blocked, as data. Only
            # the two outcomes worth ordering a backlog by are recorded -- the
            # refusal the caller hit, and the acceptance that bought the answer
            # anyway. Best-effort and opt-in (`LEGAL_REFUSAL_LEDGER=on`).
            if esito.rifiuta:
                _refusals.record(
                    {
                        "evento": "rifiuto",
                        "tool": name,
                        "tables": sorted({a["tabella"] for a in avvisi}),
                        "stati": sorted(esito.motivi),
                        "dichiarata": esito.dichiarata,
                        "concedibile": esito.concedibile,
                    }
                )
            elif esito.accettata:
                _refusals.record(
                    {
                        "evento": "accettazione",
                        "tool": name,
                        "accettata": esito.accettata,
                        "dichiarata": esito.dichiarata,
                        "tables": sorted({a["tabella"] for a in avvisi}),
                    }
                )
        if meta:
            result.meta = meta
        if name == "verbale_mensile":
            # The readback names the file the report came from, so a host can
            # tell "empty because nobody used the server" from "empty because
            # the report is reading somewhere else". The result may carry no
            # meta at all: create it rather than stay silent.
            meta = getattr(result, "meta", None)
            if not isinstance(meta, dict):
                result.meta = meta = dict(meta or {})
            meta[REFUSALS_KEY] = {"ledger": str(_refusals.ledger_path())}
        return result


def apply_table_ledger(
    server,
    bindings: dict[str, dict[str, str]],
    tool_tables: dict[str, tuple[str, ...]] | None = None,
    tool_alternatives: dict[str, str] | None = None,
    tool_sources: dict[str, tuple[str, ...]] | None = None,
    tool_regimes: dict[str, dict] | None = None,
) -> int:
    """Wrap the table constants and install the ledger middleware.

    Returns how many constants were wrapped, which the server logs on startup so
    a bindings file that matches no imported module is visible instead of silent.
    `tool_sources` is the committed online-source policy (TOOL_SOURCES): the
    middleware compares it with what the calls really fetched and the suite
    fails on the difference. `tool_regimes` is the committed map of the tools
    that compute under a superseded rule (PREVIGENTE), stamped in `_meta` too.
    """
    wrapped = install(bindings)
    server.add_middleware(
        TableLedgerMiddleware(tool_tables, tool_alternatives, tool_sources, tool_regimes)
    )
    return wrapped
