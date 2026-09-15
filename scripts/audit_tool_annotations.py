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
`tests/fixtures/golden/calcoli_locali.json`, and a test on their numbers would
drift with the calendar instead of failing when a rate or a forensic parameter
changes.

Usage:

    python scripts/audit_tool_annotations.py            # --check (default)
    python scripts/audit_tool_annotations.py --write    # regenerate the policy
    python scripts/audit_tool_annotations.py --json     # full per-tool report
    python scripts/audit_tool_annotations.py --caches   # cache inventory (md)

`--check` regenerates the policy in memory and compares it with the committed
`src/tool_annotations.py`, so a tool that starts writing a file fails the suite
instead of quietly keeping the read-only hint. It also verifies the caches: an
undeclared module resolving a cache directory, a declared cache that lost its
literals, or a cache writer that stopped consulting the switch are all failures,
and the generated `docs/cache-inventory.md` has to match too.

Run it with an environment that has fastmcp-free access -- it only parses
source, so the standard library is enough.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import pathlib
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
LOCAL_LIB_MODULES = {"_cache", "_clock", "_data", "_egress", "_http", "_result"}
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
        self.calls[name] = body
        self.sources[name] = ast.unparse(fn)
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

        def selector(name: str) -> bool:
            if name not in self.calls:
                return False
            module = name.rsplit(".", 1)[0]
            for target, short in self.calls[name]:
                base = target.rsplit(".", 1)[0] if "." in target else ""
                if short in NET_READ_ATTRS and base.split(".")[-1] in NET_BASES:
                    return True
                if is_net_target(target):
                    return True
                candidate = self._resolve(module, target)
                if candidate and candidate != name and selector(candidate):
                    return True
            return False

        return self._reachable({fq: selector(fq)}, fq)

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
            }
        return out


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

    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    current_doc = CACHE_DOC.read_text(encoding="utf-8") if CACHE_DOC.exists() else ""
    if args.write:
        TARGET.write_text(rendered, encoding="utf-8")
        print("%s %s" %("rewrote" if rendered != current else "unchanged", TARGET.relative_to(REPO)))
        CACHE_DOC.parent.mkdir(parents=True, exist_ok=True)
        CACHE_DOC.write_text(cache_doc, encoding="utf-8")
        print(
            "%s %s"
            % ("rewrote" if cache_doc != current_doc else "unchanged", CACHE_DOC.relative_to(REPO))
        )
        return 1 if failed else 0

    if failed:
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
