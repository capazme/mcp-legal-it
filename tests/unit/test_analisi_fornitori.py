"""Unit tests for genera_report_fornitori: validation and xlsx rendering."""

import importlib

import pytest

from src.tools.analisi_fornitori import _valida_fornitori


def _tool(fn_name: str):
    mod = importlib.import_module("src.tools.analisi_fornitori")
    fn = getattr(mod, fn_name)
    return fn.fn if hasattr(fn, "fn") else fn


def _riga_ok(**overrides) -> dict:
    """A fully valid 'responsabile' canonical record; override per-test."""
    base = {
        "denominazione_mastrino": "ACME CLOUD SRL",
        "piva_cf": "01234567890",
        "fonte_piva": "mastrino",
        "attivita": "Hosting e SaaS gestionale",
        "categorie_dati": "Dati di clienti/utenti del titolare",
        "qualificazione": "responsabile",
        "motivazione": "SaaS che tratta dati per conto del titolare",
        "probabilita_responsabile": "alta",
        "dpa_proprio": "no",
        "confidenza": "medio",
        "fonti": ["https://esempio.it"],
        "note": "",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None or k in overrides}


class TestValidazione:
    def test_lista_valida(self):
        assert _valida_fornitori([_riga_ok()]) == []

    def test_lista_vuota(self):
        errs = _valida_fornitori([])
        assert len(errs) == 1 and "vuota" in errs[0]

    def test_non_lista(self):
        errs = _valida_fornitori("non una lista")
        assert len(errs) == 1

    def test_riga_non_dict(self):
        errs = _valida_fornitori(["stringa"])
        assert errs and errs[0].startswith("riga 1:")

    def test_campi_obbligatori_mancanti(self):
        errs = _valida_fornitori([_riga_ok(denominazione_mastrino="", motivazione=None)])
        joined = " | ".join(errs)
        assert "denominazione_mastrino" in joined and "motivazione" in joined

    def test_enum_qualificazione(self):
        errs = _valida_fornitori([_riga_ok(qualificazione="RESPONSABILE")])
        assert errs and "qualificazione" in errs[0]

    def test_enum_confidenza(self):
        errs = _valida_fornitori([_riga_ok(confidenza="altissimo")])
        assert errs and "confidenza" in errs[0]

    def test_responsabile_richiede_probabilita_e_dpa(self):
        errs = _valida_fornitori([_riga_ok(probabilita_responsabile=None, dpa_proprio=None)])
        joined = " | ".join(errs)
        assert "probabilita_responsabile" in joined and "dpa_proprio" in joined

    def test_non_responsabile_vieta_campi_responsabile(self):
        riga = _riga_ok(qualificazione="titolare_autonomo")
        errs = _valida_fornitori([riga])
        joined = " | ".join(errs)
        assert "probabilita_responsabile" in joined and "dpa_proprio" in joined

    def test_titolare_autonomo_valido(self):
        riga = _riga_ok(
            qualificazione="titolare_autonomo",
            probabilita_responsabile=None,
            dpa_proprio=None,
        )
        riga.pop("probabilita_responsabile")
        riga.pop("dpa_proprio")
        assert _valida_fornitori([riga]) == []

    def test_fonti_non_lista(self):
        errs = _valida_fornitori([_riga_ok(fonti="https://esempio.it")])
        assert errs and "fonti" in errs[0]

    def test_indici_multipli(self):
        errs = _valida_fornitori([_riga_ok(), _riga_ok(confidenza="x"), _riga_ok(qualificazione="y")])
        assert any(e.startswith("riga 2:") for e in errs)
        assert any(e.startswith("riga 3:") for e in errs)

    def test_qualificazione_unhashable(self):
        """qualificazione as list → 'campo obbligatorio' error, no TypeError."""
        errs = _valida_fornitori([_riga_ok(qualificazione=["responsabile"])])
        assert errs
        assert any("qualificazione" in e and "mancante o vuoto" in e for e in errs)

    def test_probabilita_dpa_unhashable(self):
        """probabilita and dpa as unhashable types → errors, no TypeError."""
        errs = _valida_fornitori([_riga_ok(probabilita_responsabile=["alta"], dpa_proprio={"si"})])
        assert errs
        assert any("probabilita_responsabile" in e for e in errs)
        assert any("dpa_proprio" in e for e in errs)
