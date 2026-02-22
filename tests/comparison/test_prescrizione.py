"""Comparison tests: prescrizione_reato vs avvocatoandreani.it/servizi/calcolo-prescrizione-reati.php.

SKIPPED: This calculator requires login/registration on avvocatoandreani.it.
The form has a JS onsubmit listener that checks authentication before submitting.
"""

import pytest


@pytest.mark.skip(reason="avvocatoandreani.it prescrizione calculator requires login")
class TestPrescrizioneComparison:

    def test_reclusione_6_anni(self, page):
        pass

    def test_reclusione_3_anni(self, page):
        pass
