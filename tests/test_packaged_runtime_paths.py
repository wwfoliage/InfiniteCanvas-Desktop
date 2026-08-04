import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PackagedRuntimePathTests(unittest.TestCase):
    def test_main_uses_overridden_user_data_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            env = os.environ.copy()
            env["INFINITE_CANVAS_DATA_DIR"] = str(user_root)
            code = (
                "import sys; "
                f"sys.path.insert(0, {str(PROJECT_ROOT)!r}); "
                "import main; "
                "print('DATA=' + main.DATA_DIR); "
                "print('STATIC=' + main.STATIC_DIR)"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn(f"DATA={user_root / 'data'}", result.stdout)
            self.assertIn(f"STATIC={PROJECT_ROOT / 'static'}", result.stdout)
            self.assertTrue((user_root / "API").is_dir())
            self.assertTrue((user_root / "assets" / "output").is_dir())


if __name__ == "__main__":
    unittest.main()
