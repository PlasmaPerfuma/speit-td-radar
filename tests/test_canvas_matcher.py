from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from canvas import match_file, safe_name  # noqa: E402


class CanvasMatcherTest(unittest.TestCase):
    def test_algebra_sujet_and_corrige(self) -> None:
        self.assertEqual(match_file("Algèbre_TD7_e.pdf"), ("TD7", "sujet"))
        self.assertEqual(match_file("Algèbre_TD6_c.pdf"), ("TD6", "corrige"))

    def test_series_sujet_and_corrige(self) -> None:
        self.assertEqual(match_file("TD2-Landau.pdf"), ("TD2", "sujet"))
        self.assertEqual(match_file("TD1-cor.pdf"), ("TD1", "corrige"))

    def test_physics(self) -> None:
        self.assertEqual(match_file("PHY2301P_P2025_TD2_questions.pdf"), ("TD2", "sujet"))
        self.assertEqual(match_file("PHY2301P_P2025_TD2_solutions.pdf"), ("TD2", "corrige"))
        self.assertEqual(match_file("Sujet_TD3.pdf"), ("TD3", "sujet"))

    def test_non_td(self) -> None:
        self.assertIsNone(match_file("CorrigeDM1.pdf"))
        self.assertIsNone(match_file("notes.md"))

    def test_safe_name(self) -> None:
        self.assertEqual(safe_name('a:b/c?.pdf'), "a_b_c_.pdf")


if __name__ == "__main__":
    unittest.main()
