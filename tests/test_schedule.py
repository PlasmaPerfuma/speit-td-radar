from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import scheduler  # noqa: E402

CFG = {
    "task_name": "TD Radar Poll",
    "command": "C:\\fake\\tdradar.exe",
    "arguments": "canvas poll --once --download --process",
    "trigger": {
        "type": "weekly",
        "time": "11:30",
        "weekdays": ["MON", "TUE"],
        "interval_minutes": 5,
        "until": "23:59",
        "other_days_time": "12:00",
    },
}


class ScheduleTest(unittest.TestCase):
    def test_actions_split_weekdays_and_others(self) -> None:
        actions = scheduler.build_actions(CFG)
        self.assertEqual(actions[0]["weekday"], "Monday")
        self.assertEqual(actions[1]["weekday"], "Tuesday")
        self.assertEqual(actions[0]["interval"], 5)
        self.assertEqual(actions[-1]["interval"], 0)
        self.assertIn("Wednesday", actions[-1]["weekday"])

    def test_no_other_days(self) -> None:
        cfg = {"trigger": dict(CFG["trigger"], other_days_time="")}
        self.assertEqual(len(scheduler.build_actions(cfg)), 2)

    def test_ps_quote_escapes(self) -> None:
        self.assertEqual(scheduler._ps_quote("a'b"), "'a''b'")


if __name__ == "__main__":
    unittest.main()
