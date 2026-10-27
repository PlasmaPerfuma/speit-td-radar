from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from quality import gate  # noqa: E402

CLEAN = (
    "Soit E un espace vectoriel et F un sous-espace vectoriel de E. "
    "On veut montrer que la somme est directe. Pour tout x dans E, "
    "il existe f dans F et g dans G tels que x = f + g. "
) * 40


class QualityGateTest(unittest.TestCase):
    def test_clean_text_passes(self) -> None:
        result = gate(CLEAN)
        self.assertTrue(result["good"], result["reasons"])
        self.assertEqual(result["mojibake"], 0)

    def test_garbled_text_fails(self) -> None:
        result = gate(CLEAN[:500] + "¡¢£¤¥")
        self.assertFalse(result["good"])
        self.assertGreaterEqual(result["mojibake"], 5)


if __name__ == "__main__":
    unittest.main()
