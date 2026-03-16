"""Tests for the modelli_atti catalog and genera_modello_atto dispatcher."""

import json
from pathlib import Path

from src.tools.modelli_atti import genera_modello_atto, lista_categorie_atti, _CATALOGO


# ---------------------------------------------------------------------------
# Catalog data integrity
# ---------------------------------------------------------------------------

class TestCatalogoIntegrity:
    def test_catalog_has_entries(self):
        assert len(_CATALOGO) >= 90, f"Expected >=90 entries, got {len(_CATALOGO)}"

    def test_all_entries_have_required_fields(self):
        required = {"categoria", "descrizione", "tier", "routing",
                     "campi_obbligatori", "riferimenti_normativi"}
        for tipo, entry in _CATALOGO.items():
            missing = required - set(entry.keys())
            assert not missing, f"{tipo} missing fields: {missing}"

    def test_all_tiers_are_valid(self):
        for tipo, entry in _CATALOGO.items():
            assert entry["tier"] in (1, 2, 3, 4), f"{tipo} has invalid tier: {entry['tier']}"

    def test_all_routing_types_are_valid(self):
        valid_types = {"tool_diretto", "tool_enhance", "resource", "preventivo_procedura"}
        for tipo, entry in _CATALOGO.items():
            rt = entry["routing"]["tipo"]
            assert rt in valid_types, f"{tipo} has invalid routing type: {rt}"

    def test_tier1_entries_have_tool_diretto(self):
        for tipo, entry in _CATALOGO.items():
            if entry["tier"] == 1:
                assert entry["routing"]["tipo"] == "tool_diretto", (
                    f"Tier 1 entry {tipo} should have routing.tipo=tool_diretto"
                )

    def test_tier3_entries_have_resource(self):
        for tipo, entry in _CATALOGO.items():
            if entry["tier"] == 3:
                assert entry["routing"]["tipo"] == "resource", (
                    f"Tier 3 entry {tipo} should have routing.tipo=resource"
                )
                assert "resource" in entry["routing"], (
                    f"Tier 3 entry {tipo} missing routing.resource"
                )

    def test_tier4_entries_have_preventivo_procedura(self):
        for tipo, entry in _CATALOGO.items():
            if entry["tier"] == 4:
                assert entry["routing"]["tipo"] == "preventivo_procedura", (
                    f"Tier 4 entry {tipo} should have routing.tipo=preventivo_procedura"
                )

    def test_categories_are_consistent(self):
        cats = {v["categoria"] for v in _CATALOGO.values()}
        expected_cats = {
            "atti_introduttivi", "esecuzione", "notifiche", "attestazioni",
            "procure", "stragiudiziale", "istanze", "pct", "preventivi", "privacy",
        }
        assert cats == expected_cats, f"Unexpected categories: {cats - expected_cats}"

    def test_json_file_matches_loaded_data(self):
        data_path = Path(__file__).resolve().parent.parent.parent / "src" / "data" / "modelli_atti.json"
        with open(data_path) as f:
            raw = json.load(f)
        assert len(raw) == len(_CATALOGO)


# ---------------------------------------------------------------------------
# genera_modello_atto — catalog mode
# ---------------------------------------------------------------------------

class TestGeneraModelloAttoCatalogo:
    def test_catalogo_returns_all_entries(self):
        result = genera_modello_atto(tipo_atto="catalogo")
        assert "totale_tipi" in result
        assert result["totale_tipi"] == len(_CATALOGO)
        assert "categorie" in result
        assert "catalogo" in result

    def test_catalogo_grouped_by_category(self):
        result = genera_modello_atto(tipo_atto="catalogo")
        total = sum(len(items) for items in result["catalogo"].values())
        assert total == result["totale_tipi"]


# ---------------------------------------------------------------------------
# genera_modello_atto — search mode
# ---------------------------------------------------------------------------

class TestGeneraModelloAttoCerca:
    def test_search_by_keyword(self):
        result = genera_modello_atto(tipo_atto="cerca", parametri={"query": "ingiuntivo"})
        assert result["totale"] > 0
        assert all("ingiuntivo" in r["tipo_atto"] or "ingiuntivo" in r["descrizione"].lower()
                    for r in result["risultati"])

    def test_search_by_norma(self):
        result = genera_modello_atto(tipo_atto="cerca", parametri={"query": "633"})
        assert result["totale"] > 0

    def test_search_no_results(self):
        result = genera_modello_atto(tipo_atto="cerca", parametri={"query": "xyznonexistent"})
        assert result["totale"] == 0

    def test_search_empty_query(self):
        result = genera_modello_atto(tipo_atto="cerca", parametri={})
        assert "errore" in result


# ---------------------------------------------------------------------------
# genera_modello_atto — specific type lookup
# ---------------------------------------------------------------------------

class TestGeneraModelloAttoLookup:
    def test_tier1_tool_diretto(self):
        result = genera_modello_atto(tipo_atto="decreto_ingiuntivo_ordinario")
        assert result["tipo_atto"] == "decreto_ingiuntivo_ordinario"
        assert result["tool_diretto"] == "decreto_ingiuntivo"
        assert result["parametri_fissi"]["tipo_credito"] == "ordinario"
        assert "istruzioni" in result
        assert len(result["campi_obbligatori"]) > 0

    def test_tier2_tool_enhance(self):
        result = genera_modello_atto(tipo_atto="decreto_ingiuntivo_fatture")
        assert result["tool_diretto"] == "decreto_ingiuntivo"
        assert "disponibile_da_fase" in result
        assert result["disponibile_da_fase"] == 2

    def test_tier3_resource(self):
        result = genera_modello_atto(tipo_atto="citazione_ordinaria")
        assert "resource_modello" in result
        assert result["resource_modello"].startswith("legal://")
        assert "disponibile_da_fase" in result

    def test_tier4_preventivo(self):
        result = genera_modello_atto(tipo_atto="preventivo_mediazione")
        assert result["tool_diretto"] == "preventivo_procedura"
        assert "disponibile_da_fase" in result
        assert result["disponibile_da_fase"] == 4

    def test_unknown_type_returns_error(self):
        result = genera_modello_atto(tipo_atto="atto_inesistente_xyz")
        assert "errore" in result
        assert "suggerimenti" in result

    def test_fuzzy_match(self):
        result = genera_modello_atto(tipo_atto="precetto")
        # Should fuzzy-match to atto_di_precetto
        if "errore" in result:
            assert len(result["suggerimenti"]) > 0
        else:
            assert "tipo_atto" in result

    def test_campi_mancanti_without_params(self):
        result = genera_modello_atto(tipo_atto="decreto_ingiuntivo_ordinario")
        assert result["campi_mancanti"] == result["campi_obbligatori"]

    def test_campi_mancanti_with_partial_params(self):
        result = genera_modello_atto(
            tipo_atto="decreto_ingiuntivo_ordinario",
            parametri={"creditore": "Rossi Srl", "debitore": "Bianchi Srl"}
        )
        assert "importo" in result["campi_mancanti"]
        assert "creditore" not in result["campi_mancanti"]

    def test_campi_mancanti_all_provided(self):
        result = genera_modello_atto(
            tipo_atto="decreto_ingiuntivo_ordinario",
            parametri={"creditore": "A", "debitore": "B", "importo": 10000}
        )
        assert result["campi_mancanti"] == []

    def test_all_types_return_valid_routing(self):
        """Every catalog entry must produce a valid result with routing info."""
        for tipo in _CATALOGO:
            result = genera_modello_atto(tipo_atto=tipo)
            assert "errore" not in result, f"{tipo} returned error: {result.get('errore')}"
            has_routing = (
                "tool_diretto" in result
                or "resource_modello" in result
            )
            assert has_routing, f"{tipo} missing routing info"


# ---------------------------------------------------------------------------
# lista_categorie_atti
# ---------------------------------------------------------------------------

class TestListaCategorieAtti:
    def test_returns_all_categories(self):
        result = lista_categorie_atti()
        assert "categorie" in result
        assert result["totale_atti"] == len(_CATALOGO)

    def test_categories_have_counts(self):
        result = lista_categorie_atti()
        total = sum(c["totale"] for c in result["categorie"])
        assert total == result["totale_atti"]

    def test_sorted_by_count_descending(self):
        result = lista_categorie_atti()
        counts = [c["totale"] for c in result["categorie"]]
        assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Cross-reference: tool names in catalog exist in the server
# ---------------------------------------------------------------------------

class TestCrossReference:
    """Verify that tool names referenced in the catalog are plausible."""

    _KNOWN_TOOLS = {
        "decreto_ingiuntivo", "atto_di_precetto", "sfratto_morosita",
        "sollecito_pagamento", "nota_precisazione_credito", "dichiarazione_553_cpc",
        "procura_alle_liti", "attestazione_conformita", "relata_notifica_pec",
        "preventivo_civile", "preventivo_stragiudiziale", "preventivo_volontaria_giurisdizione",
        "contributo_unificato", "parcella_avvocato_civile", "parcella_avvocato_penale",
        "interessi_legali", "interessi_mora", "rivalutazione_monetaria",
        "scadenza_processuale", "scadenze_impugnazioni", "pignoramento_stipendio",
        "conta_giorni", "calcolo_hash", "calcolo_valore_catastale",
        "spese_mediazione", "compenso_ctu", "variazioni_istat",
        "genera_informativa_privacy", "genera_informativa_cookie",
        "genera_informativa_dipendenti", "genera_informativa_videosorveglianza",
        "genera_dpa", "genera_registro_trattamenti", "genera_dpia",
        "genera_notifica_data_breach", "valutazione_data_breach",
        # Future tools
        "preventivo_procedura",
    }

    def test_tier1_tools_exist(self):
        for tipo, entry in _CATALOGO.items():
            if entry["tier"] == 1:
                tool = entry["routing"]["tool"]
                assert tool in self._KNOWN_TOOLS, (
                    f"Tier 1 {tipo} references unknown tool: {tool}"
                )

    def test_calcolo_tools_are_known(self):
        for tipo, entry in _CATALOGO.items():
            for tool in entry.get("tool_calcolo", []):
                assert tool in self._KNOWN_TOOLS, (
                    f"{tipo} references unknown calcolo tool: {tool}"
                )
