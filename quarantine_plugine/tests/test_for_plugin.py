from random import randint

import pytest


class TestPlugin:
    def test_stable(self):
        pass

    def test_flaky(self):
        if randint(1, 2) == 1:
            pytest.fail("Incorrect result")

    def test_flaky_quarantined(self):
        if randint(1, 2) == 1:
            pytest.fail("Incorrect result. Quarantined")
