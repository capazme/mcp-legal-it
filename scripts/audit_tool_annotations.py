#!/usr/bin/env python3
"""Audit the tool annotations and regenerate (or verify) the policy.

`readOnlyHint` is a promise to the host: "this tool does not change anything,
you may run it without asking". Deriving that promise by hand for 221 tools is
how it silently becomes false, so it is derived from the code instead: every
implementation reachable from a `@mcp.tool()` function is walked (helpers and
imported clients included) looking for

  * filesystem writes -- `open(..., "w"/"a"/"x")`, `write_text`, `write_bytes`,
    `mkdir`, `makedirs`, `unlink`, `rmdir`, `rename`, `rmtree`, `copy`, `move`,
    `os.replace`, `shutil.*`
  * document and archive constructors -- `Document`, `Workbook`, `FPDF`,
    `ZipFile`, `NamedTemporaryFile`, `TemporaryDirectory`
  * mutating HTTP verbs -- `post`, `put`, `patch`, `send`

and for the tools that reach outside the process (the `src/lib` clients other
than `_data`, `_result`, `_egress`, `_http`, plus direct `httpx` usage).

The other half of the promise is the disk. Four cache files are the only things
this server ever writes on its own, and they are enumerated in
`CACHE_LOCATIONS`: for each one the entry names the module, the literals that
must still be in it, and the switch that turns it off.

The calendar is audited as well: `date.today()`/`datetime.now()` may only be
called in `src/lib/_clock.py`, which honours `LEGAL_TODAY`/`LEGAL_NOW`. Without
that, the tools that are "as of today" could not be frozen in
`tests/fixtures/golden/calcoli_locali/`, and a test on their numbers would
drift with the calendar instead of failing when a rate or a forensic parameter
changes.

The same walk yields two views of the hand-maintained tables: `reads(fq)`, the
tables the reachable code opens (including derived constants such as
`_INDICI_FOI = _FOI_DATA["indici"]`, preloaded ones bound through a subscript
or a comprehension, and loads inside a function body), and `datasets(fq)`, that
set joined with the tool's `@sourced(...)` declaration -- which is what writes
the `dati_applicati` line into the answer. `reads` is what `verify_provenance`
compares the declaration against, in both directions: a table read without being
declared answers without provenance, a table declared but never read advertises a
vintage that has nothing to do with the numbers. `datasets` is what the golden
reference is split by -- one file per set of tables -- so a refreshed rate shows
up as a diff in the tools that read it and nowhere else.

Usage:

    python scripts/audit_tool_annotations.py            # --check (default)
    python scripts/audit_tool_annotations.py --write    # regenerate the policy,
                                                        # cache inventory, bindings
    python scripts/audit_tool_annotations.py --json     # full per-tool report
    python scripts/audit_tool_annotations.py --caches   # cache inventory (md)

`--check` regenerates the policy in memory and compares it with the committed
`src/tool_annotations.py`, so a tool that starts writing a file fails the suite
instead of quietly keeping the read-only hint. It also verifies the caches: an
undeclared module resolving a cache directory, a declared cache that lost its
literals, or a cache writer that stopped consulting the switch are all failures,
and the generated `docs/cache-inventory.md` has to match too. The provenance is
checked the same way: a tool whose code reads a table it does not declare, a
declaration no code backs, and a shipped table no tool opens at all.

The same walk also emits the runtime side of that claim. `src/table_bindings.py`
(names, per module, which constant holds which table) is generated here and
installed by `src/lib/_ledger.py`, which wraps the payloads so a call can declare
in its result `_meta` the tables it actually read. The audit only checks that the
bindings match the source and that the server still installs them; the comparison
with `reads(fq)` happens in `tests/unit/test_golden_calcoli.py`, on the wire, so
a reader the walk cannot follow fails there instead of being assumed away.

One last check closes the other direction: a literal that restates a shipped
table. A hand-kept copy reads no file, so it declares no provenance, the golden
reference never sees the table move, and it drifts from the table it was taken
from without a single test failing. The comparison is on content and across
shapes, because the bands of `contributo_unificato` were copied as a list of
two-tuples while the table stores them as dicts.

Run it with an environment that has fastmcp-free access -- it only parses
source, so the standard library is enough.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
TARGET = REPO / "plugin/server/src/tool_annotations.py"

WRITE_ATTRS = {
    "write_text", "write_bytes", "mkdir", "makedirs", "unlink", "rmdir", "rename",
    "rmtree", "copy", "copy2", "copytree", "move", "save", "output", "writelines",
    "to_csv", "to_excel", "to_pickle", "dump", "touch", "truncate",
}
NET_WRITE_ATTRS = {"post", "put", "patch", "send"}
OS_ATTRS = {"replace", "rename", "remove", "unlink", "mkdir", "makedirs", "rmtree"}
OS_BASES = {"os", "shutil", "path", "Path", "_path", "PATH", "p", "pth"}
WRITE_CTORS = {
    "Workbook", "FPDF", "PDF", "Document", "Presentation", "NamedTemporaryFile",
    "TemporaryDirectory", "ZipFile", "open_docx", "FileIO",
}
WRITE_OPEN_MODES = set("wax+")
NET_READ_ATTRS = {"get", "request", "stream", "head", "Client", "AsyncClient"}
NET_BASES = {"httpx", "client", "_client", "http", "_http", "session", "async_client"}
# src/lib modules that only hold in-process helpers: reaching one of these is
# not reaching outside the process. `_cache` resolves the local cache directory
# and `_clock` reads the (pinnable) wall clock.
# src/lib modules that only hold in-process helpers: reaching one of these is
# not reaching outside the process. `_cache` resolves the local cache directory,
# `_clock` reads the (pinnable) wall clock, `_ledger` and `_tables_open` are the
# runtime half of the provenance. Every module directly under src/lib belongs
# here -- the clients are packages -- and `verify_lib_modules` fails when one is
# missing, so a new helper cannot quietly become an "external service".
LOCAL_LIB_MODULES = {
    "_cache",
    "_clock",
    "_data",
    "_egress",
    "_http",
    "_ledger",
    "_precision",
    "_result",
    "_tables_open",
}
# Evidence that a tool produces something for the user rather than refreshing a
# cache: a document, a spreadsheet or a PDF handle.
ARTIFACT_SIGNALS = {
    "ctor Document()", "ctor Presentation()", "ctor Workbook()", "ctor FPDF()",
    "ctor PDF()", "doc.save()", "wb.save()", "presentation.save()",
}
CACHE_BASES = ("cache", "disk_path", "hits_path", "url_params_path")

# ---------------------------------------------------------------------------
# The declared on-disk caches
# ---------------------------------------------------------------------------
# `markers` are literals that have to still appear in `module`, and `switch` is
# the call that has to appear there too: a cache whose writer stops consulting
# the switch would be documentation for something that no longer happens.
# `module` is relative to plugin/server/, so its dotted name is derived, not
# written twice.
CACHE_LOCATIONS = (
    {
        "module": "src/lib/visualex/akn_fetch.py",
        "label": "akn_acts",
        "dir": "${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/akn_acts",
        "files": [
            "{codice}_{data_gu}_{data_vigenza}.json -- parsed act",
            "akn_hits.json -- access counter per act",
            "akn_url_params.json -- act URL -> export parameters",
        ],
        "retention": "in-memory LRU capped at AKN_CACHE_MAX_ACTS (50); the disk copy has no TTL",
        "markers": ("akn_acts", "akn_hits.json", "akn_url_params.json"),
        "switch": "cache_enabled()",
    },
    {
        "module": "src/lib/brocardi/client.py",
        "label": "cache root",
        "dir": "${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}",
        "files": ["brocardi_urls.json -- article URL map"],
        "retention": "no TTL; an entry is dropped when the article 404s",
        "markers": ("brocardi_urls.json",),
        "switch": "cache_enabled()",
    },
    {
        "module": "src/lib/corte_cost/client.py",
        "label": "corte_cost",
        "dir": "${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/corte_cost",
        "files": ["{kind}/{year}.json -- Consulta pronunce and massime"],
        "retention": "7 days (_CACHE_TTL_SECONDS)",
        "markers": ("corte_cost",),
        "switch": "cache_enabled()",
    },
)
#: The module that reads the switch and resolves MCP_CACHE_DIR -- the one place
#: both variables are read, so no tool can touch the disk without declaring it.
CACHE_SWITCH_MODULE = "src/lib/_cache.py"
#: The module that reads the wall clock, with `LEGAL_TODAY`/`LEGAL_NOW` to pin it.
#: Tools that are "as of today" are only reproducible if every calendar read
#: goes through here, so nothing else may call today()/now().
CLOCK_MODULE = "src/lib/_clock.py"
CLOCK_CALLS = {"today", "now", "utcnow"}
CLOCK_BASES = {"date", "datetime"}
CACHE_DOC = REPO / "docs/cache-inventory.md"

TEMPLATE = '''"""MCP tool annotations, so hosts can tell a read-only lookup from a file writer.

`readOnlyHint` is asserted only for tools whose implementation cannot reach any
filesystem or network write: `scripts/audit_tool_annotations.py` walks the call
graph of every `@mcp.tool()` function in `src/` (helpers and imported clients
included) looking for `open(..., "w"/"a"/"x")`, `Path.write_text/write_bytes`,
`mkdir`, `unlink`, `replace`, `shutil.*`, the document constructors
(`Document`, `Workbook`, `FPDF`, `ZipFile`) and HTTP verbs that mutate
(`post`, `put`, `patch`).

The 17 tools that do write are listed in `WRITES_FILES` and get an explicit
`readOnlyHint=False` instead of being left blank: most of them write a cache
file, five of them write a document the user asked for. Neither group is
`destructiveHint` -- they add or refresh files, they do not delete user data --
so hosts that gate on destructiveness can still treat them as safe.

The 12 cache writers are also in `CACHE_WRITES`: their only write goes under
`${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}` (`akn_acts/` for parsed acts, the hit
counter and the URL-params index, `brocardi_urls.json` for article URLs,
`corte_cost/{kind}/{year}.json` for the Consulta massime, 7-day TTL). The
writes are best-effort -- with an unwritable cache directory `cite_law()` still
answers -- and `LEGAL_CACHE=off` keeps the server off the disk entirely: the
directory is then never read nor created (`src/lib/_cache.py` is the one module
that reads the switch, and the only one that resolves `MCP_CACHE_DIR`).
`docs/cache-inventory.md` carries the per-cache and per-tool detail.

`openWorldHint` marks the tools that reach outside the process (Normattiva,
EUR-Lex, Italgiure, the Garante, SPARQL endpoints, VIES, ...); the %d
local-only ones are pure calculations over the bundled JSON tables.

`apply_tool_annotations` installs a middleware that stamps these annotations on
`tools/list`. It lives in one place on purpose: annotating 221 decorators would
be a diff nobody can review, and the audit rule is easier to re-run than to
re-derive. The policy is checked against the registered tools on the first
listing, so a renamed tool is reported instead of silently losing its hint.

Regenerate this file with `python scripts/audit_tool_annotations.py --write`;
`--check` fails the suite when it drifts from the source.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

from fastmcp.server.middleware import Middleware
from mcp.types import ToolAnnotations

# No reachable filesystem/network write.
READ_ONLY: frozenset[str] = frozenset({
%s
})

# Reachable write: cache refresh (12) or document generation (5).
WRITES_FILES: frozenset[str] = frozenset({
%s
})

# Reaches an external service.
OPEN_WORLD: frozenset[str] = frozenset({
%s
})

# Subset of WRITES_FILES whose only write refreshes the local cache under
# ${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}.
CACHE_WRITES: frozenset[str] = frozenset({
%s
})


def annotations_for(tool_name: str) -> ToolAnnotations | None:
    """Annotations for a tool, or None when the policy does not mention it."""
    if tool_name in READ_ONLY:
        return ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=tool_name in OPEN_WORLD,
        )
    if tool_name in WRITES_FILES:
        return ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=tool_name in OPEN_WORLD,
        )
    return None


class ToolAnnotationMiddleware(Middleware):
    """Stamp the audited annotations on every `tools/list` response."""

    def __init__(self) -> None:
        self._checked = False

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        for tool in tools:
            annotations = annotations_for(tool.name)
            if annotations is not None:
                tool.annotations = annotations
        if not self._checked:
            self._checked = True
            self._warn_on_drift(t.name for t in tools)
        return tools

    def _warn_on_drift(self, registered: Iterable[str]) -> None:
        names = set(registered)
        missing = (READ_ONLY | WRITES_FILES) - names
        if missing:
            print(
                "tool_annotations: policy names no longer registered: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )


def apply_tool_annotations(server) -> None:
    """Install the annotation middleware on a FastMCP server."""
    server.add_middleware(ToolAnnotationMiddleware())
'''


class Audit:
    def __init__(self, src: pathlib.Path) -> None:
        self.src = src
        self.functions: dict[str, ast.AST] = {}
        self.imports: dict[str, dict[str, str]] = {}
        self.calls: dict[str, set[tuple[str, str]]] = {}
        self.evidence: dict[str, set[str]] = {}
        self.sources: dict[str, str] = {}
        self.tools: dict[str, str] = {}
        #: module -> {module-level constant: data table it was loaded from}
        self.eager_tables: dict[str, dict[str, str]] = {}
        #: function -> names it references (to tie a tool to those constants)
        self.referenced: dict[str, set[str]] = {}
        #: function -> datasets it opens itself (function-local table loads)
        self.loaded: dict[str, set[str]] = {}
        #: hand-maintained tables actually shipped in src/data
        self.available_datasets: set[str] = {
            path.stem for path in (src / "data").glob("*.json")
        }
        self._collect()

    def _collect(self) -> None:
        for py in sorted(self.src.rglob("*.py")):
            if "__pycache__" in str(py):
                continue
            module = ".".join(py.relative_to(self.src.parent).with_suffix("").parts)
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            aliases: dict[str, str] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        aliases[alias.asname or alias.name.split(".")[0]] = alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        aliases[alias.asname or alias.name] = "%s.%s" % (node.module, alias.name)
            self.imports[module] = aliases
            self.eager_tables[module] = _module_tables(tree, self.available_datasets)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._visit(module, node, "")

    def _visit(self, module: str, fn: ast.AST, prefix: str) -> None:
        name = "%s.%s%s" % (module, prefix, fn.name)
        self.functions[name] = fn
        aliases = self.imports[module]
        if any("mcp.tool" in ast.unparse(d) for d in fn.decorator_list):
            self.tools[name] = fn.name
        body: set[tuple[str, str]] = set()
        found: set[str] = set()
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                target = aliases.get(func.id, func.id)
                body.add((target, func.id))
                if func.id in WRITE_CTORS:
                    found.add("ctor %s()" % func.id)
                if func.id == "open":
                    values = [
                        a.value if isinstance(a, ast.Constant) else None
                        for a in [*node.args, *[k.value for k in node.keywords]]
                    ]
                    modes = [v for v in values if isinstance(v, str)]
                    if any(set(m) & WRITE_OPEN_MODES for m in modes):
                        found.add("open(%s)" % ",".join(modes))
            elif isinstance(func, ast.Attribute):
                base = ast.unparse(func.value)
                body.add(("%s.%s" % (aliases.get(base, base), func.attr), func.attr))
                if func.attr in WRITE_ATTRS:
                    found.add("%s.%s()" % (base, func.attr))
                if func.attr in NET_WRITE_ATTRS:
                    found.add("net %s.%s()" % (base, func.attr))
                if func.attr in OS_ATTRS and base.split(".")[0] in OS_BASES:
                    found.add("%s.%s()" % (base, func.attr))
                if func.attr in WRITE_CTORS:
                    found.add("ctor %s()" % func.attr)
        # A function handed over as a *value* is still reached. `_get_fonti()`
        # returns a dict of the four jurisprudence implementations
        # (`{"cassazione": (..., _cerca_giurisprudenza_impl), ...}`) and the
        # caller calls through it, so there is no `Call` node to follow -- the
        # edge is the bare name. Without it the walk stops at the dispatch table
        # and reports a tool that searches Italgiure, CeRDEF, Giustizia
        # Amministrativa and CGUE as if it read nothing: `cerca_giurisprudenza_
        # unificata` was annotated local, and pinned in the reproducible fixture,
        # on the strength of exactly that missing path.
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id in aliases:
                target = aliases[node.id]
                if target.startswith("src.") and "." in target:
                    body.add((target, node.id))
        self.calls[name] = body
        self.sources[name] = ast.unparse(fn)
        self.referenced[name] = {
            node.id for node in ast.walk(fn) if isinstance(node, ast.Name)
        }
        self.loaded[name] = _loaded_datasets(fn, self.available_datasets)
        if found:
            self.evidence[name] = found
        for child in fn.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit(module, child, "%s." % fn.name)

    def _resolve(self, module: str, target: str) -> str | None:
        if target in self.functions:
            return target
        short = target.split(".")[-1]
        candidate = "%s.%s" % (module, short)
        if candidate in self.functions:
            return candidate
        for name in self.functions:
            if name.endswith("." + short):
                return name
        return None

    def _reachable(self, selector, fq: str, seen=None) -> bool:
        seen = seen if seen is not None else set()
        if fq in seen:
            return False
        seen.add(fq)
        if selector.get(fq):
            return True
        module = fq.rsplit(".", 1)[0]
        for target, _ in self.calls.get(fq, set()):
            candidate = self._resolve(module, target)
            if candidate and self._reachable(selector, candidate, seen):
                return True
        return False

    def _net(self, fq: str) -> bool:
        def is_net_target(target: str) -> bool:
            if not target.startswith("src.lib."):
                return False
            parts = target.split(".")
            return (parts[2] if len(parts) > 2 else "") not in LOCAL_LIB_MODULES

        #: Answered once per function, and marked before it is explored: the
        #: static graph does contain cycles (`_clock.now()` resolves to the
        #: module's own `now` by suffix, which is how `_now_value -> now ->
        #: _now_value` appeared), and a walk that follows them without a marker
        #: ends in a RecursionError instead of an answer. Marking a function as
        #: False while it is in progress is safe because it can only be reached
        #: through itself: a cycle contributes no new evidence.
        memo: dict[str, bool] = {}

        def selector(name: str) -> bool:
            if name in memo:
                return memo[name]
            if name not in self.calls:
                memo[name] = False
                return False
            memo[name] = False
            module = name.rsplit(".", 1)[0]
            for target, short in self.calls[name]:
                base = target.rsplit(".", 1)[0] if "." in target else ""
                if short in NET_READ_ATTRS and base.split(".")[-1] in NET_BASES:
                    memo[name] = True
                    return True
                if is_net_target(target):
                    memo[name] = True
                    return True
                candidate = self._resolve(module, target)
                if candidate and candidate != name and selector(candidate):
                    memo[name] = True
                    return True
            return memo[name]

        return selector(fq)

    def chain(self, fq: str) -> list[str]:
        """Every function reachable from `fq` inside src/, `fq` included."""
        out: list[str] = []
        seen: set[str] = set()

        def walk(name: str) -> None:
            if name in seen:
                return
            seen.add(name)
            out.append(name)
            module = name.rsplit(".", 1)[0]
            for target, _ in self.calls.get(name, set()):
                candidate = self._resolve(module, target)
                if candidate:
                    walk(candidate)

        walk(fq)
        return out

    def reads_clock(self, fq: str) -> bool:
        """True when anything reachable from `fq` asks what day it is.

        The runtime answers this more precisely -- `_clock.consulted()` records the
        reads of a single call -- but a page rendered without starting a server
        can still answer it from the source, and that is the difference between
        an answer anchored to today (which an expired table stops) and one about a
        period already closed (which it only downgrades).
        """
        for name in self.chain(fq):
            for target, _ in self.calls.get(name, set()):
                parts = target.split(".")
                if len(parts) >= 2 and parts[-1] in ("today", "now") and parts[-2] == "_clock":
                    return True
        return False

    def write_sites(self, fq: str) -> list[tuple[str, str]]:
        """(owning function, evidence) for every write reachable from `fq`."""
        return [
            (name, item)
            for name in self.chain(fq)
            for item in sorted(self.evidence.get(name, set()))
        ]

    def writes_for(self, fq: str) -> list[str]:
        return sorted({item for _, item in self.write_sites(fq)})

    def _module_has_cache_root(self, module: str) -> bool:
        return any(
            name.startswith(module + ".")
            and ("MCP_CACHE_DIR" in source or "cache_root" in source)
            for name, source in self.sources.items()
        )

    def _site_is_cache(self, owner: str, item: str) -> bool:
        """A write that only refreshes the cache under MCP_CACHE_DIR.

        Document and archive constructors are artifacts whatever else the
        module does with the cache, so they never count as cache writes.
        """
        if item.startswith("open(") or item in ARTIFACT_SIGNALS:
            return False
        lowered = item.lower()
        if any(marker in lowered for marker in CACHE_BASES):
            return True
        source = self.sources.get(owner, "")
        if "MCP_CACHE_DIR" in source or "cache_root" in source:
            return True
        # The path often comes from a helper in the same client module
        # (`_cache_root() / ...` assigned elsewhere, then written here).
        return self._module_has_cache_root(owner.rsplit(".", 1)[0])

    def cache_sources(self, fq: str) -> list[str]:
        """Functions in the chain that resolve the MCP cache directory."""
        return sorted(
            name
            for name in self.chain(fq)
            if "MCP_CACHE_DIR" in self.sources.get(name, "") or "cache_root" in self.sources.get(name, "")
        )

    def modules(self, fq: str) -> set[str]:
        """Dotted modules contributing at least one function to the chain."""
        return {name.rsplit(".", 1)[0] for name in self.chain(fq)}

    def upstream_clients(self, fq: str) -> list[str]:
        """External services reached: the `src/lib/<client>` packages in the chain."""
        clients = set()
        for module in self.modules(fq):
            parts = module.split(".")
            if len(parts) >= 3 and parts[:2] == ["src", "lib"] and parts[2] not in LOCAL_LIB_MODULES:
                clients.add(parts[2])
        return sorted(clients)

    def reads(self, fq: str) -> list[str]:
        """Tables the code reachable from `fq` opens, declarations aside.

        Kept separate from `declared` on purpose: `verify_provenance` has to
        compare the two, and a `datasets()` that folded the declaration in would
        make "declares a table it never reads" unprovable -- `derived` would
        contain everything declared by construction.
        """
        out: set[str] = set()
        for name in self.chain(fq):
            module = name.rsplit(".", 1)[0]
            out.update(self.loaded.get(name, set()))
            referenced = self.referenced.get(name, set())
            for constant, dataset in self.eager_tables.get(module, {}).items():
                if constant in referenced:
                    out.add(dataset)
        return sorted(out)

    def datasets(self, fq: str) -> list[str]:
        """Hand-maintained tables this tool's answer rests on.

        What the code reads (`reads`) plus what the tool declares it applies --
        the declaration is what writes the `dati_applicati` line into the
        answer, so for grouping the golden reference and for reporting what a
        tool applies, both belong here. This is the key the golden fixture is
        split by, so a refreshed table shows up as a diff in the tools that
        actually read it.
        """
        return sorted(set(self.declared(fq)) | set(self.reads(fq)))

    def declared(self, fq: str) -> list[str]:
        """Datasets named by the `@sourced(...)` decorators in a tool's chain.

        A declaration may sit on the tool or on a helper it calls, and it is
        what writes the `dati_applicati` line into the answer.
        """
        out: set[str] = set()
        for name in self.chain(fq):
            for decorator in getattr(self.functions.get(name), "decorator_list", []):
                if isinstance(decorator, ast.Call) and "sourced" in ast.unparse(decorator.func):
                    out.update(
                        arg.value
                        for arg in decorator.args
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    )
        return sorted(out)

    def cache_locations(self, fq: str) -> list[str]:
        """Declared cache directories this tool can write to."""
        reached = self.modules(fq)
        return [entry["dir"] for entry in CACHE_LOCATIONS if _dotted(entry["module"]) in reached]

    def is_cache_only(self, fq: str) -> bool:
        """True when every reachable write refreshes the local cache."""
        sites = self.write_sites(fq)
        return bool(sites) and all(self._site_is_cache(owner, item) for owner, item in sites)

    def policy(self) -> dict[str, list[str]]:
        read_only, writes, open_world, cache = [], [], [], []
        for fq in self.tools:
            evidence = self.writes_for(fq)
            (writes if evidence else read_only).append(self.tools[fq])
            if evidence and self.is_cache_only(fq):
                cache.append(self.tools[fq])
            if self._net(fq):
                open_world.append(self.tools[fq])
        return {
            "read_only": sorted(read_only),
            "writes_files": sorted(writes),
            "open_world": sorted(open_world),
            "cache_writes": sorted(cache),
        }

    def report(self) -> dict[str, dict]:
        out = {}
        for fq, name in self.tools.items():
            evidence = self.writes_for(fq)
            out[name] = {
                "module": fq.rsplit(".", 1)[0].split(".")[-1],
                "read_only": not evidence,
                "evidence": evidence,
                "open_world": self._net(fq),
                "cache_only": self.is_cache_only(fq),
                "cache_sources": self.cache_sources(fq),
                "caches": self.cache_locations(fq),
                "clients": self.upstream_clients(fq),
                "datasets": self.datasets(fq),
            }
        return out


LOADING_CALLS = ("open", "load", "loads", "read_text", "read_bytes")
#: The one accessor that reads a table by name and records it (`src/lib/_data.py`).
#: A read through it is what the runtime ledger observes, so the static map has to
#: recognise the same call -- `_data.load("tegm")` names its table without the
#: `.json` suffix a filename carries.
TABLE_ACCESSOR = ("_data", "load")


def _loaded_datasets(fn: ast.AST, allowed: set[str]) -> set[str]:
    """Datasets a function loads itself, from the literals in its load calls.

    Covers `with open(_DATA / "tegm.json")` inside a tool body, which the
    module-level pass cannot see. A literal only counts when it sits in a call
    that opens or parses something: `data["comuni"]` is a dictionary key, not a
    file.

    Two shapes name a table, and both are reads: a filename, and
    `_data.load("tegm")`, which names the stem directly. The second is the one
    the runtime ledger observes, so leaving it out here would let the
    observation and the static map drift apart on a tool that uses it.
    """
    found: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if not any(word in ast.unparse(node.func) for word in LOADING_CALLS):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and child.value.endswith(".json")
                and pathlib.PurePosixPath(child.value).stem in allowed
            ):
                found.add(pathlib.PurePosixPath(child.value).stem)
        found.update(_accessor_datasets(node, allowed))
    return found


def _accessor_datasets(node: ast.AST, allowed: set[str]) -> list[str]:
    """Tables named by `_data.load("stem")` inside `node`.

    Only the canonical accessor counts, and only a string that names a table this
    repository ships: `load` is a common method name, and a bare string is
    otherwise indistinguishable from any other argument.
    """
    receiver, method = TABLE_ACCESSOR
    found: list[str] = []
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == method
            and isinstance(func.value, ast.Name)
            and func.value.id == receiver
        ):
            continue
        found.extend(
            argument.value
            for argument in call.args
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value in allowed
        )
    return found


def _module_bindings(
    tree: ast.Module, allowed: set[str]
) -> Iterator[tuple[list[ast.AST], ast.AST, str | None]]:
    """Every module-level assignment, with the table it loads if it loads one.

    Module scope here means "not inside a function or a class": the tool modules
    preload their tables inside a `with` block, and several derive a second
    constant from the first in the same block:

        with open(_DATA / "comuni.json") as f:
            _COMUNI_DATA = json.load(f)
            _COMUNI = _COMUNI_DATA["comuni"]

    Every binding in such a block that mentions the open handle *is* a binding
    of that file, whatever shape the load takes: `json.load(f)`, but also
    `json.load(f)["codici"]`, `{k: v for k, v in json.load(f).items()}` and an
    annotated `_X: dict = json.load(f)`. Anchoring on the handle rather than on a
    bare `X = json.load(f)` call is what keeps a constant like
    `_CODICI_TRIBUTO` — and therefore the tool that answers from it — from being
    filed under no table at all, i.e. answering without provenance.

    A constant derived from a tied one inherits the table by propagation in
    `_module_tables`. Walking past `tree.body` is what keeps `_COMUNI` in play,
    and stopping at function bodies is what keeps a *local* table load from being
    attributed to the module.

    Yields `(targets, value, dataset_stem_or_None)`.
    """
    loaded_under: dict[int, str] = {}
    seen: list[tuple[int, list[ast.AST], ast.AST | None]] = []

    def binds(statement: ast.stmt, handles: set[str]) -> bool:
        """True when the statement's right-hand side reads one of the handles.

        The test is on what the right-hand side *reads*, not on the shape of the
        statement: a constant that happens to sit in the same block but never
        touches the handle is not a binding of the file.
        """
        value = getattr(statement, "value", None)
        if value is None:
            return False
        if any(
            isinstance(node, ast.Name) and node.id in handles for node in ast.walk(value)
        ):
            return True
        return any(
            isinstance(node, ast.Call)
            and any(word in ast.unparse(node.func) for word in LOADING_CALLS)
            for node in ast.walk(value)
        )

    def record(statement: ast.Assign | ast.AnnAssign, stem: str | None) -> None:
        if stem and binds(statement, handles_within.get(id(statement), set())):
            loaded_under[id(statement)] = stem
        seen.append(
            (id(statement), statement.targets, statement.value)
            if isinstance(statement, ast.Assign)
            else (id(statement), [statement.target], statement.value)
        )

    #: statement -> handle names it may read (the enclosing `with` blocks)
    handles_within: dict[int, set[str]] = {}

    def walk(node: ast.AST, stem: str | None, handles: set[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                continue
            if isinstance(child, (ast.With, ast.AsyncWith)):
                inner, inner_handles = stem, set(handles)
                for item in child.items:
                    literals = _json_dataset_literals(item.context_expr, allowed)
                    if literals:
                        inner = pathlib.PurePosixPath(literals[0]).stem
                    if isinstance(item.optional_vars, ast.Name):
                        inner_handles.add(item.optional_vars.id)
                for statement in ast.walk(child):
                    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                        handles_within[id(statement)] = inner_handles
                walk(child, inner, inner_handles)
            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                handles_within.setdefault(id(child), handles)
                record(child, stem)
            else:
                walk(child, stem, handles)

    walk(tree, None, set())
    for statement_id, targets, value in seen:
        if value is None:
            continue
        yield targets, value, loaded_under.get(statement_id)


def _json_dataset_literals(node: ast.AST, allowed: set[str]) -> list[str]:
    """Tables inside `node` that this repository ships, as filenames or stems.

    A real filename, not merely a string equal to a dataset name: the bands of
    `contributo_unificato` are a hardcoded dict key in
    fatturazione_avvocati.py, and treating that key as a table would demand a
    declaration for a file the tool never opens. The exception is a bare stem
    handed to the canonical accessor, where naming the table *is* the read.
    """
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and child.value.endswith(".json")
        and pathlib.PurePosixPath(child.value).stem in allowed
    ] + _accessor_datasets(node, allowed)


def _module_tables(tree: ast.Module, allowed: set[str]) -> dict[str, str]:
    """Module-level constants tied to a `src/data/*.json` file, transitively.

    Both loading styles in this codebase are covered: the declared one
    (`@sourced("indici_foi")` + `lib._data.load`) and the eager one
    (`with open(_DATA / "irpef_scaglioni.json") as f: _IRPEF = json.load(f)`),
    which is how several tool modules preload their tables at import.

    A table also reaches a tool through a derived constant
    (`_INDICI_FOI = _FOI_DATA["indici"]`), so bindings propagate: a constant
    whose value mentions a constant already tied to a table inherits it. Without
    this, a tool reading FOI through a helper would be filed under no table and
    a refreshed FOI series would not point at it.

    Only literals naming a dataset this repository actually ships count: the
    clients build remote archive members with the same suffix
    (`Cc_Opendata_Pronunce_{year}.json`), and those are not tables.

    Returns `{constant_name: dataset_stem}` for the module.
    """
    tables: dict[str, str] = {}

    def json_literals(node: ast.AST) -> list[str]:
        return _json_dataset_literals(node, allowed)

    assignments: list[tuple[list[ast.AST], str | None, set[str]]] = []

    def collect(targets: list[ast.AST], value: ast.AST | None) -> None:
        literals = json_literals(value) if value is not None else []
        stem = pathlib.PurePosixPath(literals[0]).stem if literals else None
        names = {node.id for node in ast.walk(value) if isinstance(node, ast.Name)} if value else set()
        assignments.append((targets, stem, names))

    for targets, value, stem in _module_bindings(tree, allowed):
        collect(targets, value)
        if stem is not None:
            assignments[-1] = (targets, stem, assignments[-1][2])

    for _ in range(len(assignments) + 1):
        grew = False
        for targets, stem, names in assignments:
            inherited = stem or next((tables[name] for name in names if name in tables), None)
            if inherited is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and tables.get(target.id) != inherited:
                    tables[target.id] = inherited
                    grew = True
        if not grew:
            break
    return tables


def _dotted(module: str) -> str:
    """`src/lib/brocardi/client.py` -> `src.lib.brocardi.client`."""
    return ".".join(pathlib.PurePosixPath(module).with_suffix("").parts)


def _module_text(audit: "Audit", dotted: str) -> str:
    """Source of every function belonging to a dotted module, joined."""
    return "\n".join(
        source for name, source in audit.sources.items() if name.startswith(dotted + ".")
    )


def cache_inventory(audit: "Audit") -> list[dict]:
    """One row per declared cache: files, retention, writer module, tools."""
    rows = []
    for entry in CACHE_LOCATIONS:
        dotted = _dotted(entry["module"])
        tools = sorted(
            tool for fq, tool in audit.tools.items() if dotted in audit.modules(fq)
        )
        rows.append({**entry, "dotted": dotted, "tools": tools})
    return rows


def verify_caches(audit: "Audit") -> list[str]:
    """Failures that would make the cache documentation a lie.

    Four invariants, all about nobody writing outside the declared list:

    1. `MCP_CACHE_DIR` is read in one module only, so moving the cache cannot
       happen in a file the inventory does not mention.
    2. Every module that resolves a cache directory is declared.
    3. Every declared module still contains its literals and still consults
       `cache_enabled()` -- a cache writer that ignores the switch is a cache
       writer that cannot be turned off.
    4. The switch module still defines the env var and the off values.
    """
    problems: list[str] = []
    server_root = REPO / "plugin/server"

    declared = {_dotted(entry["module"]) for entry in CACHE_LOCATIONS}
    declares_env: set[str] = set()
    resolves_dir: set[str] = set()
    for py in sorted((server_root / "src").rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        dotted = _dotted(str(py.relative_to(server_root)))
        text = py.read_text(encoding="utf-8")
        # Only an actual read counts: the generated docstring in
        # src/tool_annotations.py mentions the variable without touching it.
        if any(
            "MCP_CACHE_DIR" in line and "environ" in line for line in text.splitlines()
        ):
            declares_env.add(dotted)
        if "cache_root(" in text:
            resolves_dir.add(dotted)

    switch_mod = _dotted(CACHE_SWITCH_MODULE)
    for module in sorted(declares_env - {switch_mod}):
        problems.append(
            "%s reads MCP_CACHE_DIR directly; only %s may resolve the cache"
            % (module, CACHE_SWITCH_MODULE)
        )
    for module in sorted(resolves_dir - declared - {switch_mod}):
        problems.append(
            "%s resolves the cache directory but is not declared in CACHE_LOCATIONS"
            % module
        )

    for entry in CACHE_LOCATIONS:
        dotted = _dotted(entry["module"])
        path = server_root / entry["module"]
        if not path.exists():
            problems.append("declared cache module %s no longer exists" % entry["module"])
            continue
        text = path.read_text(encoding="utf-8")
        for marker in entry["markers"]:
            if marker not in text:
                problems.append("%s: cache marker %r disappeared" % (entry["module"], marker))
        if entry["switch"] not in text:
            problems.append(
                "%s: cache is no longer disabled by %s" % (entry["module"], entry["switch"])
            )
        if dotted not in resolves_dir:
            problems.append(
                "%s: declared as a cache writer but no longer resolves the cache" % entry["module"]
            )

    switch_path = server_root / CACHE_SWITCH_MODULE
    if not switch_path.exists():
        problems.append("the cache switch module %s is missing" % CACHE_SWITCH_MODULE)
    else:
        text = switch_path.read_text(encoding="utf-8")
        for marker in ("LEGAL_CACHE", "cache_enabled", "cache_root", "DISABLED_VALUES"):
            if marker not in text:
                problems.append("%s: %s is gone" % (CACHE_SWITCH_MODULE, marker))

    if not cache_inventory(audit):
        problems.append("no cache is declared at all")
    return problems


def verify_provenance(audit: "Audit") -> list[str]:
    """Every table a tool reads must be declared, and every declaration true.

    The declaration is what puts `dati_applicati` (and the table's vintage) in
    the answer: a tool that reads a table without declaring it gives advice
    whose currency nobody can check. Both directions are failures -- a missing
    declaration silently drops the provenance, an extra one claims a table the
    tool does not use.

    A table that no tool declares is a failure for the same reason, from the
    other side: either the file is dead data (and should not be shipped as a
    table) or its reader is a path this walk cannot see, in which case the tool
    answering from it says nothing about the vintage. That check is what caught
    `codici_tributo`, `modelli_atti` and `preavviso_ccnl`, which three tools were
    answering from in complete silence: their loaders bind through a subscript
    and a dict comprehension, not through a bare `X = json.load(f)`.
    """
    problems: list[str] = []
    applied: dict[str, list[str]] = {}
    for fq, tool in audit.tools.items():
        for dataset in audit.reads(fq):
            applied.setdefault(dataset, []).append(tool)
    for dataset in sorted(audit.available_datasets):
        if dataset not in applied:
            problems.append(
                "src/data/%s.json is applied by no tool: either it is dead data "
                "or the tool that reads it does so through a load this walk does "
                "not follow, and then its answer carries no vintage" % dataset
            )
    for fq, tool in sorted(audit.tools.items(), key=lambda item: item[1]):
        derived = audit.reads(fq)
        declared = audit.declared(fq)
        unknown = [name for name in declared + derived if name not in audit.available_datasets]
        for name in unknown:
            problems.append("%s: %r is not a table shipped in src/data" % (tool, name))
        missing = sorted(set(derived) - set(declared))
        if missing:
            problems.append(
                "%s reads %s but does not declare it; add @sourced(%s) under @mcp.tool"
                % (tool, "+".join(missing), ", ".join('"%s"' % m for m in derived))
            )
        extra = sorted(set(declared) - set(derived))
        if extra:
            problems.append(
                "%s declares %s but its reachable code never reads %s"
                % (tool, "+".join(extra), "+".join(extra))
            )
    return problems


def verify_clock() -> list[str]:
    """Calendar calls outside the clock module: those would escape pinning.

    Found on the AST rather than on the text, so a docstring mentioning
    `date.today()` is not a failure.
    """
    problems: list[str] = []
    server_root = REPO / "plugin/server"
    allowed = _dotted(CLOCK_MODULE)
    for py in sorted((server_root / "src").rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        dotted = _dotted(str(py.relative_to(server_root)))
        if dotted == allowed:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:
            problems.append("%s does not parse: %s" % (py.relative_to(server_root), exc))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            base = node.func.value
            if (
                node.func.attr in CLOCK_CALLS
                and isinstance(base, ast.Name)
                and base.id in CLOCK_BASES
            ):
                problems.append(
                    "%s:%d reads the wall clock (%s.%s); go through %s so "
                    "LEGAL_TODAY/LEGAL_NOW can pin it"
                    % (
                        py.relative_to(server_root),
                        node.lineno,
                        base.id,
                        node.func.attr,
                        CLOCK_MODULE,
                    )
                )
    return problems


#: How many rows of a table a literal has to reproduce before it counts as a
#: copy. Below this, a short list of numbers is as likely to be a coincidence as
#: a duplicate (three IRPEF rates, five step names).
TABLE_COPY_MIN_ROWS = 4

#: Literals that reproduce a shipped table on purpose, each with the reason. The
#: audit fails on an entry that no longer matches anything, so an exemption
#: cannot outlive the code it excuses. Empty today: no copy is justified, one was
#: removed (see `TABLE_COPY_MIN_ROWS`).
TABLE_COPIES_ALLOWED: tuple[dict, ...] = ()

_INF = float("inf")


def _row(value: object) -> tuple | None:
    """A `(threshold, amount)` pair from any of the shapes a copy takes."""
    if isinstance(value, dict):
        keys = set(value)
        if "importo" in keys and ("fino_a" in keys or "oltre" in keys):
            threshold = value.get("fino_a")
            if value.get("oltre") and threshold is None:
                return None, float(value["importo"])
            if isinstance(threshold, (int, float)):
                return float(threshold), float(value["importo"])
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        threshold, amount = value
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            # The open-ended band is written `float("inf")` in a copy and
            # `{"oltre": true}` in the table: both mean "no ceiling", and a copy
            # that differs only there must still match.
            if threshold is None or threshold == _INF:
                return None, float(amount)
            if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
                return float(threshold), float(amount)
    return None


def _signatures(value: object, out: set | None = None) -> set:
    """Content fingerprints of a table payload, or of a literal in a module.

    Four shapes, because a copy does not have to be shaped like its source: the
    bands of `contributo_unificato` were copied as a list of two-tuples while the
    table stores them as dicts, and a diff of the two would have shown nothing.
    """
    out = set() if out is None else out

    def scalar(item: object) -> bool:
        return isinstance(item, (int, float)) and not isinstance(item, bool)

    if isinstance(value, (list, tuple)):
        rows = [_row(item) for item in value]
        if len(value) >= TABLE_COPY_MIN_ROWS and all(row is not None for row in rows):
            out.add(("pairs", tuple(rows)))
        elif (
            len(value) >= TABLE_COPY_MIN_ROWS + 1
            and all(scalar(item) for item in value)
        ):
            out.add(("numbers", tuple(float(item) for item in value)))
        elif (
            len(value) >= TABLE_COPY_MIN_ROWS + 1
            and all(isinstance(item, str) for item in value)
        ):
            out.add(("strings", frozenset(value)))
        for item in value:
            _signatures(item, out)
    elif isinstance(value, dict):
        if (
            len(value) >= TABLE_COPY_MIN_ROWS + 1
            and all(isinstance(key, str) for key in value)
            and all(scalar(item) for item in value.values())
        ):
            # A series stored as `{"01": 118.2, ...}` and copied as a plain list
            # of the same numbers in the same order still has to match, which is
            # why the values are compared in key order rather than as a set.
            out.add(("numbers", tuple(float(item) for _, item in sorted(value.items()))))
        if len(value) >= TABLE_COPY_MIN_ROWS and all(scalar(key) for key in value) and all(
            scalar(item) for item in value.values()
        ):
            out.add(
                (
                    "pairs",
                    tuple(
                        (None if key == _INF else float(key), float(item))
                        for key, item in sorted(value.items())
                    ),
                )
            )
        for item in value.values():
            _signatures(item, out)
    return out


def _literal_value(node: ast.AST):
    """The Python value of a literal, or `_UNKNOWN` when it needs the interpreter.

    Written out rather than delegated to `ast.literal_eval` because the copy
    this is meant to catch used `float("inf")` for its last band and `1_686` for
    an amount, and `literal_eval` refuses the first.
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        items = [_literal_value(item) for item in node.elts]
        return _UNKNOWN if _UNKNOWN in items else items
    if isinstance(node, ast.Tuple):
        items = [_literal_value(item) for item in node.elts]
        return _UNKNOWN if _UNKNOWN in items else tuple(items)
    if isinstance(node, ast.Dict):
        keys = [_literal_value(key) for key in node.keys]
        values = [_literal_value(item) for item in node.values]
        if _UNKNOWN in keys or _UNKNOWN in values:
            return _UNKNOWN
        return dict(zip(keys, values))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _literal_value(node.operand)
        return -inner if isinstance(inner, (int, float)) else _UNKNOWN
    if isinstance(node, ast.Name) and node.id in ("inf", "nan"):
        return float(node.id)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("float", "int")
        and len(node.args) == 1
    ):
        inner = _literal_value(node.args[0])
        if isinstance(inner, str) and inner in ("inf", "nan", "-inf"):
            return float(inner)
        if isinstance(inner, (int, float)):
            return float(inner) if node.func.id == "float" else int(inner)
    return _UNKNOWN


class _Unknown:
    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "<not a literal>"


_UNKNOWN = _Unknown()


def _matches(kind: str, copy: tuple | frozenset, table: tuple | frozenset) -> bool:
    """True when `copy` reproduces `table`, whole or as its first rows.

    A partial copy counts (up to the minimum), because that is what a copy looks
    like after someone updates the table and only notices the first rows. An
    unordered signature can only be compared whole.
    """
    if copy == table:
        return True
    if kind == "strings" or not isinstance(copy, tuple) or not isinstance(table, tuple):
        return False
    return len(copy) >= TABLE_COPY_MIN_ROWS and copy == table[: len(copy)]


def verify_table_copies(audit: "Audit") -> list[str]:
    """No module may restate a table that ships in `src/data`.

    A hand-kept copy is invisible to every other check in this file: the tool
    reads no file, so it declares no provenance, the golden reference does not
    see the table move, and the copy drifts from the table it was taken from
    without a single test failing. That is how the contributo unificato bands
    lived in `fatturazione_avvocati.py` while `contributo_unificato.json` was
    updated next to them.

    The comparison is on content, not on shape: a table of dicts copied as a
    list of two-tuples has to match, otherwise it is not detected exactly when
    it is hardest to notice.
    """
    problems: list[str] = []
    server_root = audit.src.parent
    tables: dict[str, set] = {}
    for path in sorted((audit.src / "data").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        tables[path.stem] = _signatures(payload)

    allowed = {(entry["module"], entry["dataset"]) for entry in TABLE_COPIES_ALLOWED}
    used: set[tuple[str, str]] = set()
    #: (module, dataset) -> first line that restates it, so one copy is one
    #: finding even though the literal nesting shows up as several nodes.
    seen: dict[tuple[str, str], int] = {}

    for py in sorted(audit.src.rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        relative = str(py.relative_to(server_root))
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:
            problems.append("%s does not parse: %s" % (relative, exc))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple, ast.Dict)):
                continue
            value = _literal_value(node)
            if isinstance(value, _Unknown):
                continue
            for kind, signature in _signatures(value):
                for dataset, signatures in tables.items():
                    for other_kind, other in signatures:
                        if other_kind != kind:
                            continue
                        if not _matches(kind, signature, other):
                            continue
                        if (relative, dataset) in allowed:
                            used.add((relative, dataset))
                            continue
                        seen.setdefault((relative, dataset), node.lineno)
    for (relative, dataset), lineno in sorted(seen.items(), key=lambda item: (item[0][0], item[1])):
        problems.append(
            "%s:%d restates src/data/%s.json as a literal; read the table instead, "
            "or its vintage cannot travel and the copy drifts from it in silence"
            % (relative, lineno, dataset)
        )
    for module, dataset in sorted(allowed - used):
        problems.append(
            "TABLE_COPIES_ALLOWED exempts %s in %s, but nothing there reproduces it "
            "any more" % (dataset, module)
        )
    return problems


BINDINGS_TARGET = REPO / "plugin/server/src/table_bindings.py"

BINDINGS_TEMPLATE = '''"""Which module-level constant holds which hand-maintained table.

Generated by `scripts/audit_tool_annotations.py --write`; do not edit.

`src/lib/_ledger.py` wraps every constant named here so a tool call can declare,
at runtime, which tables it actually read -- the other half of what
`@sourced(...)` promises statically. A constant that disappears from this file is
a table whose reader stops being observable, so `--check` regenerates and
compares rather than trusting the version on disk.
"""

from __future__ import annotations

#: module -> {module-level constant: dataset stem it was loaded from or derived
#: from}. Derived constants are included on purpose: a projection computed at
#: import (`_CATEGORIE = sorted({v["categoria"] for v in _CATALOGO.values()})`) is
#: still the table, and reading it during a call means the call applied it.
TABLE_CONSTANTS: dict[str, dict[str, str]] = {
%s
}

#: tool -> tables its code reads. The ledger observes the wrapped constants, so
#: this is not what the answer names; it is the fallback for the case where the
#: observation is blind (a table reached through a scalar computed at import),
#: where the declaration stays the best available statement -- and it is what
#: lets the middleware flag the vintage of a table it could not see being read.
TOOL_TABLES: dict[str, tuple[str, ...]] = {
%s
}

#: tool -> the parameter that replaces its table. A call that supplies it reads no
#: table by construction, so the middleware must not fall back to the declaration
#: and flag the vintage of a table the call deliberately did not open.
TOOL_ALTERNATIVES: dict[str, str] = {
%s
}
'''


def render_table_bindings(audit: "Audit") -> str:
    """The runtime binding maps: tables per constant, tables per tool, alternatives."""
    lines: list[str] = []
    for module in sorted(audit.eager_tables):
        constants = audit.eager_tables[module]
        if not constants:
            continue
        lines.append('    "%s": {' % module)
        for name in sorted(constants):
            lines.append('        "%s": "%s",' % (name, constants[name]))
        lines.append("    },")

    tools: list[str] = []
    for fq, tool in sorted(audit.tools.items(), key=lambda item: item[1]):
        reads = audit.reads(fq)
        if not reads:
            continue
        items = ['"%s"' % name for name in reads]
        tools.append(
            '    "%s": (%s%s),' % (tool, ", ".join(items), "," if len(items) == 1 else "")
        )
    if not tools:
        tools.append("    # no tool reads a hand-maintained table")

    alternatives = [
        '    "%s": "%s",' % (tool, parameter)
        for fq, tool in sorted(audit.tools.items(), key=lambda item: item[1])
        if (parameter := alternative_parameter(audit.functions[fq]))
    ]
    if not alternatives:
        alternatives.append("    # no tool offers a datum in place of its table")
    return BINDINGS_TEMPLATE % ("\n".join(lines), "\n".join(tools), "\n".join(alternatives))


def verify_lib_modules(audit: "Audit") -> list[str]:
    """Every in-process helper under `src/lib` has to be declared as one.

    A module the policy does not know is classified by `upstream_clients` as an
    upstream service, so a tool that merely imports it stops looking local: this
    is what happened to the ledger's own `_tables_open`, which put 71 read-only
    calculations in the report's "external" column and inflated its open-world
    count from 50 to 121 while every annotation stayed correct. The distinction
    is structural -- modules are helpers, packages are clients -- so it can be
    checked instead of remembered.
    """
    problems: list[str] = []
    lib = audit.src / "lib"
    declared = set(LOCAL_LIB_MODULES)
    for path in sorted(lib.iterdir()):
        if path.name.startswith("__") or path.name in {"__pycache__"}:
            continue
        if path.is_dir():
            if path.name in declared:
                problems.append(
                    "src/lib/%s is a client package and cannot be declared local" % path.name
                )
            continue
        if path.suffix != ".py":
            continue
        if path.stem not in declared:
            problems.append(
                "src/lib/%s is an in-process helper but is not in LOCAL_LIB_MODULES: "
                "tools that import it count as reaching an upstream service" % path.name
            )
    for name in sorted(declared):
        if not (lib / (name + ".py")).exists():
            problems.append("LOCAL_LIB_MODULES declares src/lib/%s.py, which does not exist" % name)
    return problems


def verify_ledger(audit: "Audit") -> list[str]:
    """The generated bindings have to be installed, or they observe nothing.

    A bindings file nobody imports is worse than none: the audit would keep
    generating it, `--check` would keep passing, and the runtime declaration
    would silently stop existing.
    """
    problems: list[str] = []
    server = (audit.src / "server.py").read_text(encoding="utf-8")
    if "apply_table_ledger" not in server:
        problems.append(
            "src/server.py no longer calls apply_table_ledger: the table ledger is "
            "generated but never installed, so no call declares what it read"
        )
    bindings = render_table_bindings(audit)
    if "TABLE_CONSTANTS: dict[str, dict[str, str]] = {\n}" in bindings:
        problems.append(
            "no module-level table constant was found: the ledger would record nothing"
        )
    ledger = audit.src / "lib" / "_ledger.py"
    if not ledger.exists():
        problems.append("src/lib/_ledger.py is missing: nothing records table reads")
    else:
        text = ledger.read_text(encoding="utf-8")
        for marker in ("def install", "TableDict", "TableList", "DATA_WARNINGS_KEY"):
            if marker not in text:
                problems.append("src/lib/_ledger.py: %s is gone" % marker)
    recorder = audit.src / "lib" / "_tables_open.py"
    if not recorder.exists():
        problems.append("src/lib/_tables_open.py is missing: nothing records table reads")
    else:
        text = recorder.read_text(encoding="utf-8")
        for marker in ("def recording", "def opened", "def note", "ContextVar"):
            if marker not in text:
                problems.append("src/lib/_tables_open.py: %s is gone" % marker)
    if "TOOL_TABLES: dict[str, tuple[str, ...]] = {}" in bindings:
        problems.append("no tool was tied to a table: the ledger fallback is empty")
    if "TOOL_ALTERNATIVES: dict[str, str] = {}" in bindings:
        problems.append(
            "no tool declares a parameter in place of its table: either the escapes "
            "are gone or the generator stopped reading them"
        )
    else:
        text = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
        if "tool_alternatives" not in text:
            problems.append(
                "src/lib/_ledger.py does not consult the tool alternatives: a call "
                "that supplied its own datum would still be flagged on its table"
            )
    data = audit.src / "lib" / "_data.py"
    for marker in ("def effective", "def warnings", "avvisi_dati"):
        if marker not in data.read_text(encoding="utf-8"):
            problems.append("src/lib/_data.py: %s is gone" % marker)
    return problems


#: The line that declares a grade, e.g. `Precisione: ESATTO per indici FOI`.
#: Kept in step with `src/lib/_precision.py`'s own pattern by
#: `verify_precision`, so a docstring the audit accepts is one the runtime reads.
PRECISION_RE = re.compile(r"^[ \t]*Precisione:[ \t]*([A-Za-zÀ-ÿ]+)", re.MULTILINE)


def declared_precision(fn: ast.AST) -> str | None:
    """The grade a tool declares in its docstring, or None when it declares none."""
    found = PRECISION_RE.search(ast.get_docstring(fn) or "")
    return found.group(1).upper() if found else None


#: `@sourced(..., alternativa="parametro")`: the escape a refusal points the
#: caller at, and therefore a promise that the parameter exists.
ALTERNATIVA_RE = re.compile(r"alternativa\s*=\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']")


def alternative_parameter(fn: ast.AST) -> str | None:
    """The parameter a tool offers in place of a table it cannot vouch for."""
    for decorator in getattr(fn, "decorator_list", []):
        found = ALTERNATIVA_RE.search(ast.unparse(decorator))
        if found:
            return found.group(1)
    return None


def _parameters(fn: ast.AST) -> dict[str, ast.arg | None]:
    """{parameter: its default node, or None when it is required}."""
    spec = getattr(fn, "args", None)
    if spec is None:
        return {}
    defaults = [None] * (len(spec.posonlyargs) + len(spec.args) - len(spec.defaults))
    defaults += list(spec.defaults)
    out: dict[str, ast.arg | None] = {}
    for argument, default in zip([*spec.posonlyargs, *spec.args], defaults):
        out[argument.arg] = default
    for argument, default in zip(spec.kwonlyargs, spec.kw_defaults):
        out[argument.arg] = default
    return out


def runtime_grades() -> list[str]:
    """The grades `src/lib/_precision.py` knows, read from its own source.

    Read rather than imported: the audit walks the source and must keep working
    without the server's dependencies installed, but a second copy of this
    vocabulary is exactly the kind of drift that lets the audit accept a word the
    runtime reads as the strongest claim. The tuple holds names, so the constants
    it points at are resolved too -- and a `GRADI` the module spells some other
    way is reported as empty, which `verify_precision` fails on rather than
    silently accepting every grade.
    """
    source = REPO / "plugin/server/src/lib/_precision.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
    gradi: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "GRADI" for t in node.targets):
            continue
        if not isinstance(node.value, ast.Tuple):
            continue
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                gradi.append(element.value)
            elif isinstance(element, ast.Name) and element.id in constants:
                gradi.append(constants[element.id])
    return gradi


def verify_precision(audit: "Audit") -> list[str]:
    """A tool that rests on a table has to declare how precise its answer is.

    That grade is what the vintage acts on: `src/lib/_precision.py` withdraws an
    exact claim an unverified table cannot support and steps an indicative one
    down, and a tool that declares nothing would be read as claiming exactness.
    So the declaration is a condition of applying a table, and the mechanism has
    to be installed where the answers are built, not merely described.
    """
    problems: list[str] = []
    gradi = runtime_grades()
    if not gradi:
        problems.append(
            "src/lib/_precision.py declares no GRADI: nothing says which words a "
            "docstring may claim"
        )
    for fq, name in sorted(audit.tools.items(), key=lambda kv: kv[1]):
        datasets = audit.datasets(fq)
        if not datasets:
            continue
        grado = declared_precision(audit.functions[fq])
        if grado is None:
            problems.append(
                "%s applies %s but declares no `Precisione:` grade: with nothing "
                "declared, a stale table has no claim to withdraw"
                % (name, ", ".join(datasets))
            )
        elif grado not in gradi:
            problems.append(
                "%s declares `Precisione: %s`, which src/lib/_precision.py does not "
                "know (it knows %s): an unknown grade is read as %s"
                % (name, grado, ", ".join(gradi), gradi[0] if gradi else "ESATTO")
            )

    for fq, name in sorted(audit.tools.items(), key=lambda kv: kv[1]):
        alternatively = alternative_parameter(audit.functions[fq])
        if not alternatively:
            continue
        parameters = _parameters(audit.functions[fq])
        if alternatively not in parameters:
            problems.append(
                "%s says a refusal can be answered with `%s`, which is not one of its "
                "parameters: the escape a refusal points at has to exist"
                % (name, alternatively)
            )
        elif parameters[alternatively] is None:
            problems.append(
                "%s declares `%s` as required, so the table is never the thing that "
                "decides: the alternative is meant to be optional"
                % (name, alternatively)
            )

    precision = audit.src / "lib" / "_precision.py"
    if not precision.exists():
        problems.append(
            "src/lib/_precision.py is missing: a table's vintage would no longer "
            "change what an answer claims"
        )
    else:
        text = precision.read_text(encoding="utf-8")
        for marker in ("def declared", "def decide", "def to_dict", "ridotta", "rifiuta"):
            if marker not in text:
                problems.append("src/lib/_precision.py: %s is gone" % marker)

    data = (audit.src / "lib" / "_data.py").read_text(encoding="utf-8")
    for marker in ("_precision.decide", "dati_non_affidabili", "come_sbloccare"):
        if marker not in data:
            problems.append(
                "src/lib/_data.py: %s is gone, so the declared grade no longer "
                "changes the answer" % marker
            )
    for marker in ("CONSENT_PARAM", "accetta_precisione", "__signature__", "_documented"):
        if marker not in data:
            problems.append(
                "src/lib/_data.py: %s is gone, so a refusal can no longer be "
                "answered by accepting a lower grade" % marker
            )
    ledger = (audit.src / "lib" / "_ledger.py").read_text(encoding="utf-8")
    for marker in ("PRECISION_KEY", "_precision.recording", "_clock.recording"):
        if marker not in ledger:
            problems.append("src/lib/_ledger.py: %s is gone" % marker)
    return problems


def render_cache_doc(audit: "Audit") -> str:
    """The generated cache inventory (`docs/cache-inventory.md`).

    The tool list is the policy's own `CACHE_WRITES`, not "every tool whose
    chain touches a cache module": a tool that also writes a document is a
    document writer and must not be listed as a pure cache refresher.
    """
    rows = cache_inventory(audit)
    cache_tools = sorted(tool for fq, tool in audit.tools.items() if audit.is_cache_only(fq))
    out = [
        "<!-- Generated by scripts/audit_tool_annotations.py --write. Do not edit. -->",
        "",
        "# On-disk cache inventory",
        "",
        "Everything this server writes on its own initiative is listed below;",
        "anything else it keeps between calls is in memory. The list is not",
        "hand-maintained: `scripts/audit_tool_annotations.py --check` fails when a",
        "module starts resolving a cache directory without being declared here, or",
        "when a declared cache stops honouring the `LEGAL_CACHE=off` switch.",
        "",
        "## Caches",
        "",
        "| Location | Files | Retention | Written by | Disabled by |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        out.append(
            "| `%s` | %s | %s | `%s` | `%s` |"
            % (
                row["dir"],
                "<br>".join("`%s`" % f for f in row["files"]),
                row["retention"],
                row["module"],
                row["switch"],
            )
        )
    out += [
        "",
        "## Tools that can write them",
        "",
        "These are the %d tools of the `CACHE_WRITES` subset of the annotation"
        % len(cache_tools),
        "policy, i.e. the tools whose only reachable write is a cache refresh; they",
        "are annotated `readOnlyHint: false` for exactly this reason. A tool that also",
        "writes a document is listed as a writer of the document, not of the cache.",
        "",
        "| Tool | Cache |",
        "| --- | --- |",
    ]
    for tool in cache_tools:
        fq = next(f for f, name in audit.tools.items() if name == tool)
        out.append("| `%s` | `%s` |" % (tool, "`<br>`".join(audit.cache_locations(fq)) or "-"))
    out += [
        "",
        "## Turning the caches off",
        "",
        "The writes are best-effort: an unwritable cache directory is reported on",
        "stderr and the tool still answers. `MCP_CACHE_DIR` relocates the files but",
        "does not stop them. To keep the server off the disk entirely, start it with",
        "`LEGAL_CACHE=off` (also `no`, `false`, `0`, `none`, `disabled`):",
        "`${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}` is then never read and never",
        "created, and the caches live only in memory for the life of the process.",
        "`src/lib/_cache.py` is the only module that reads either variable.",
        "",
        "Checks enforced by the audit:",
        "",
        "* `MCP_CACHE_DIR` is read in `src/lib/_cache.py` and nowhere else;",
        "* every module calling `cache_root()` is declared above;",
        "* every declared module still holds its literals and still consults",
        "  `cache_enabled()`;",
        "* this file is regenerated with `--write` and compared with `--check`.",
        "",
    ]
    return "\n".join(out)


def block(names, indent="    "):
    lines, current = [], []
    for name in sorted(names):
        current.append('"%s",' % name)
        if sum(len(x) + 1 for x in current) > 84:
            lines.append(indent + " ".join(current))
            current = []
    if current:
        lines.append(indent + " ".join(current))
    return "\n".join(lines)


def render(policy: dict[str, list[str]]) -> str:
    local = len(set(policy["read_only"]) - set(policy["open_world"]))
    return TEMPLATE % (
        local,
        block(policy["read_only"]),
        block(policy["writes_files"]),
        block(policy["open_world"] or {"none"}),
        block(policy["cache_writes"] or {"none"}),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", default=str(REPO / "plugin/server/src"))
    parser.add_argument("--write", action="store_true", help="regenerate the policy file")
    parser.add_argument("--json", action="store_true", help="print the per-tool report")
    parser.add_argument("--caches", action="store_true", help="print the cache inventory")
    parser.add_argument("--check", action="store_true", help="fail when the policy drifts (default)")
    args = parser.parse_args()

    audit = Audit(pathlib.Path(args.src))
    policy = audit.policy()
    rendered = render(policy)
    cache_doc = render_cache_doc(audit)

    print(
        "tools: %d | read-only: %d (%d local-only) | writes files: %d (%d cache-only) | open world: %d"
        % (
            len(audit.tools),
            len(policy["read_only"]),
            len(set(policy["read_only"]) - set(policy["open_world"])),
            len(policy["writes_files"]),
            len(policy["cache_writes"]),
            len(policy["open_world"]),
        )
    )
    if args.json:
        print(json.dumps(audit.report(), indent=1))
    if args.caches:
        print(cache_doc)

    failed = False
    for problem in verify_caches(audit):
        print("cache audit: %s" % problem, file=sys.stderr)
        failed = True
    for problem in verify_clock():
        print("clock audit: %s" % problem, file=sys.stderr)
        failed = True
    for problem in verify_provenance(audit):
        print("provenance audit: %s" % problem, file=sys.stderr)
        failed = True
    for problem in verify_table_copies(audit):
        print("table copy audit: %s" % problem, file=sys.stderr)
        failed = True
    for problem in verify_ledger(audit):
        print("ledger audit: %s" % problem, file=sys.stderr)
        failed = True
    for problem in verify_lib_modules(audit):
        print("lib module audit: %s" % problem, file=sys.stderr)
        failed = True
    for problem in verify_precision(audit):
        print("precision audit: %s" % problem, file=sys.stderr)
        failed = True

    bindings = render_table_bindings(audit)
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    current_doc = CACHE_DOC.read_text(encoding="utf-8") if CACHE_DOC.exists() else ""
    current_bindings = (
        BINDINGS_TARGET.read_text(encoding="utf-8") if BINDINGS_TARGET.exists() else ""
    )
    if args.write:
        TARGET.write_text(rendered, encoding="utf-8")
        print("%s %s" %("rewrote" if rendered != current else "unchanged", TARGET.relative_to(REPO)))
        CACHE_DOC.parent.mkdir(parents=True, exist_ok=True)
        CACHE_DOC.write_text(cache_doc, encoding="utf-8")
        print(
            "%s %s"
            % ("rewrote" if cache_doc != current_doc else "unchanged", CACHE_DOC.relative_to(REPO))
        )
        BINDINGS_TARGET.write_text(bindings, encoding="utf-8")
        print(
            "%s %s"
            % (
                "rewrote" if bindings != current_bindings else "unchanged",
                BINDINGS_TARGET.relative_to(REPO),
            )
        )
        return 1 if failed else 0

    if failed:
        return 1

    if bindings != current_bindings:
        print(
            "table bindings have drifted -- run "
            "`python scripts/audit_tool_annotations.py --write`",
            file=sys.stderr,
        )
        diff = difflib.unified_diff(
            current_bindings.splitlines(), bindings.splitlines(), "committed", "audited",
            lineterm="", n=1,
        )
        for line in list(diff)[:40]:
            print(line, file=sys.stderr)
        return 1

    if cache_doc != current_doc:
        print(
            "cache inventory has drifted -- run "
            "`python scripts/audit_tool_annotations.py --write`",
            file=sys.stderr,
        )
        diff = difflib.unified_diff(
            current_doc.splitlines(), cache_doc.splitlines(), "committed", "audited", lineterm="", n=1
        )
        for line in list(diff)[:40]:
            print(line, file=sys.stderr)
        return 1

    if rendered == current:
        print("policy is up to date: %s" % TARGET.relative_to(REPO))
        print(
            "caches: %d declared, %s"
            % (
                len(CACHE_LOCATIONS),
                ", ".join(
                    "%s (%d tools)" % (row["label"], len(row["tools"]))
                    for row in cache_inventory(audit)
                ),
            )
        )
        return 0

    print(
        "policy has drifted from the source -- run "
        "`python scripts/audit_tool_annotations.py --write`",
        file=sys.stderr,
    )
    diff = difflib.unified_diff(
        current.splitlines(), rendered.splitlines(), "committed", "audited", lineterm="", n=1
    )
    for line in list(diff)[:40]:
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
