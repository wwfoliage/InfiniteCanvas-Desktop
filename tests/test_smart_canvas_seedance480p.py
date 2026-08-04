import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMART_CANVAS_JS = ROOT / "static" / "js" / "smart-canvas.js"


class SmartCanvasSeedance480pTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SMART_CANVAS_JS.read_text(encoding="utf-8")

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the JavaScript helper test")
    def test_common_seedance_2_model_names(self):
        match = re.search(
            r"function isSeedance2VideoModel\(model\)\{\s*.*?\n\}",
            self.source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "isSeedance2VideoModel() was not found")

        positives = [
            "seedance2.0",
            "Seedance2.0Fast",
            "seedance-2.0",
            "seedance_2.0",
            "seedance-2-0",
            "seedance_2_0",
            "seedance 2 0",
            "seedance20",
            "seedance2.0_vip",
            "doubao-seedance-2-0-260128",
            "dreamina-video-seedance-2.0-fast",
            "bytedance/seedance-2.0-global/image-to-video",
        ]
        negatives = [
            "",
            "seedance",
            "seedance-1.5-pro",
            "seedance-2.1",
            "seedance-2-00",
            "seedance-20.0",
            "veo3-fast",
            "sora",
        ]
        script = f"""
{match.group(0)}
const positives = {json.dumps(positives)};
const negatives = {json.dumps(negatives)};
const failures = [];
for (const value of positives) {{
    if (!isSeedance2VideoModel(value)) failures.push(`expected true: ${{value}}`);
}}
for (const value of negatives) {{
    if (isSeedance2VideoModel(value)) failures.push(`expected false: ${{value}}`);
}}
if (failures.length) {{
    console.error(failures.join('\\n'));
    process.exit(1);
}}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_480p_menu_and_request_wiring_remain_enabled(self):
        self.assertIn(
            "if(supportsSeedance2Video480p(settings)) options.push(['480p','480P']);",
            self.source,
        )
        self.assertIn(
            "resolution: runSettings.videoResolution || ''",
            self.source,
        )
        self.assertIn(
            "if(engine !== 'api' || isJimengProviderId(provider) || isTudouVideoProvider(provider)) return false;",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
