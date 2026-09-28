"""Structured result type for jurisprudence search tools.

Internal contract — not exposed via MCP. Tools return SearchResult from
_impl functions; the @mcp.tool() wrappers call .to_str() for the user.
"""

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Result of a jurisprudence search across any source."""

    success: bool
    source: str  # "italgiure", "cerdef", "giustizia_amm", "cgue"
    # "source_down": the source did not answer; "source_error": it answered with an
    # error page or a payload the client cannot read; "no_results": the source itself
    # found nothing. Tools may add their own types (e.g. "bad_input") with a results_text.
    error_type: str | None = None
    error_message: str = ""
    num_found: int = 0
    results_text: str = ""
    raw_docs: list[dict] = field(default_factory=list)

    def to_str(self) -> str:
        """Convert to string for MCP tool response (backward-compatible).

        A source that answered with something unreadable is an error, never an
        empty result (#46).
        """
        if not self.success and self.error_type == "source_down":
            return f"**Errore**: {self.source} non raggiungibile. {self.error_message}"
        if not self.success and self.error_type == "source_error":
            return (
                f"**Errore**: risposta anomala da {self.source}, esito della ricerca non verificabile "
                f"(non equivale a zero risultati). {self.error_message}"
            )
        return self.results_text or f"Nessun risultato su {self.source}."
