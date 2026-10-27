from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from analyze import normalize  # noqa: E402


class NormalizeTest(unittest.TestCase):
    def test_idea_numbering_and_blocks(self) -> None:
        raw = {
            "exercises": [
                {
                    "statement_fr": "Montrer que $E=F\\oplus G$.",
                    "statement_zh": "证明 $E=F\\oplus G$。",
                    "statement_notes": ["$E=F+G$"],
                    "knowledge": [
                        {"title": "直和", "fr": "somme directe",
                         "body": ["定义。"], "formulas": ["E=F\\oplus G"]}
                    ],
                    "idea": [{"text": "1. 先验证。", "formula": ""}],
                    "subquestions": [
                        {
                            "label_zh": "第 1 问",
                            "label_fr": "Question 1",
                            "idea": [{"text": "1. 使用条件。", "formula": ""}],
                            "solution": [
                                {
                                    "label": "Étape 1",
                                    "blocks": [
                                        {"type": "text", "fr": "Comme $G\\subset H$,", "zh": "因为 $G\\subset H$，"},
                                        {"type": "math", "tex": "F\\cap G=\\{0_E\\}"},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        data = normalize(raw, "Algèbre I", "TD7")
        ex = data["exercises"][0]
        self.assertEqual(ex["idea"][0]["text"], "先验证。")
        self.assertEqual(ex["subquestions"][0]["idea"][0]["text"], "使用条件。")
        blocks = ex["subquestions"][0]["solution"][0]["blocks"]
        self.assertEqual(blocks[1]["type"], "math")
        self.assertEqual(blocks[1]["tex"], "F\\cap G=\\{0_E\\}")
        self.assertEqual(ex["statement_notes"], ["$E=F+G$"])


if __name__ == "__main__":
    unittest.main()
