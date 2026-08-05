import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = Path(
    r"C:\Users\xzh45\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)


class AlignmentGuideTests(unittest.TestCase):
    def run_alignment(self, dragged, targets, threshold=6):
        if not NODE.exists():
            self.skipTest("Node.js runtime is unavailable")
        module = ROOT / "static/js/alignment-guides.js"
        script = (
            "const a=require(process.argv[1]);"
            "const input=JSON.parse(process.argv[2]);"
            "process.stdout.write(JSON.stringify(a.findAlignment(input.dragged,input.targets,input.threshold)));"
        )
        completed = subprocess.run(
            [str(NODE), "-e", script, str(module), json.dumps({
                "dragged": dragged,
                "targets": targets,
                "threshold": threshold,
            })],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_free_drag_when_no_target_is_near(self):
        result = self.run_alignment(
            {"x": 31, "y": 47, "width": 100, "height": 80},
            [{"id": "target", "x": 400, "y": 300, "width": 100, "height": 80}],
        )
        self.assertEqual(result["x"], 31)
        self.assertEqual(result["y"], 47)
        self.assertEqual(result["guides"], [])

    def test_edges_and_centers_snap_independently(self):
        result = self.run_alignment(
            {"x": 154, "y": 196, "width": 100, "height": 80},
            [{"id": "target", "x": 100, "y": 100, "width": 100, "height": 100}],
        )
        self.assertEqual(result["x"], 150)
        self.assertEqual(result["y"], 200)
        self.assertEqual({guide["axis"] for guide in result["guides"]}, {"x", "y"})


if __name__ == "__main__":
    unittest.main()
