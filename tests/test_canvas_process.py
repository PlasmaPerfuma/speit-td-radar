from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import canvas  # noqa: E402


class CanvasProcessTest(unittest.TestCase):
    def test_download_then_process_marks_state(self) -> None:
        fake = {
            "course_id": 95175,
            "course_key": "algebre",
            "id": 123,
            "name": "Algèbre_TD7_e.pdf",
            "td": "TD7",
            "kind": "sujet",
            "size": 10,
            "updated_at": "2026-10-27T00:00:00Z",
            "url": "https://example.invalid/file",
        }
        tmp_path = ROOT / "tests" / "_tmp_canvas_process"
        shutil.rmtree(tmp_path, ignore_errors=True)
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            pdf = tmp_path / "fake.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            state_path = tmp_path / "state.json"
            with patch.object(canvas.paths, "STATE", state_path), \
                 patch.object(canvas, "discover", side_effect=lambda cid: [fake] if cid == 95175 else []), \
                 patch.object(canvas, "download", return_value=pdf), \
                 patch.object(canvas.pipeline, "process_pdf",
                              return_value={"render": {"pdf": str(tmp_path / "out.pdf")}}) as process:
                canvas.run_once(download_new=True, process_new=True)
                process.assert_called_once()
                state = canvas.load_state()
                entry = state["files"]["95175:123"]
                self.assertTrue(entry["processed"])
                self.assertEqual(entry["output_path"], str(tmp_path / "out.pdf"))
                self.assertEqual(entry["path"], str(pdf))
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
