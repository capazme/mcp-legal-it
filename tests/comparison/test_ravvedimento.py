"""Comparison tests: ravvedimento_operoso vs avvocatoandreani.it/servizi/calcolo-ravvedimento-operoso.php.

SKIPPED: This calculator requires login/registration on the site.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Site calculator requires login — cannot compare without account")


class TestRavvedimentoComparison:

    def test_30_giorni(self):
        pass

    def test_90_giorni(self):
        pass
