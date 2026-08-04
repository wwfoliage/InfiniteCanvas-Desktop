import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


INSTALLER_SCRIPT = Path(__file__).resolve().parents[1] / "build" / "windows" / "InfiniteCanvas.iss"
PYINSTALLER_SPEC = Path(__file__).resolve().parents[1] / "build" / "windows" / "InfiniteCanvas.spec"


class InstallerDefinitionTests(unittest.TestCase):
    def test_installer_preserves_local_app_data(self):
        script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")

        self.assertIn("AppId={{", script)
        self.assertIn("PrivilegesRequired=lowest", script)
        self.assertNotIn("%LOCALAPPDATA%", script)
        self.assertNotIn("uninsdelete", script.lower())
        self.assertIn("OutputBaseFilename=InfiniteCanvas-Setup-{#AppVersion}", script)

    def test_installer_is_per_user_and_supports_upgrade(self):
        script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")

        self.assertIn("DefaultDirName={localappdata}\\Programs\\InfiniteCanvas", script)
        self.assertIn("ArchitecturesAllowed=x64", script)
        self.assertIn("CloseApplications=yes", script)
        self.assertIn("Source: \"{#SourceDir}\\*\"", script)

    def test_smoke_build_avoids_sandbox_registry_writes(self):
        script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")

        self.assertIn("#ifdef SmokeTestRoot", script)
        self.assertIn("Uninstallable=no", script)
        self.assertIn("#ifndef SmokeTestRoot", script)

    def test_pyinstaller_excludes_generated_tool_caches(self):
        spec = PYINSTALLER_SPEC.read_text(encoding="utf-8-sig")

        self.assertIn('Tree(', spec)
        self.assertIn('prefix="tools"', spec)
        self.assertIn('excludes=["__pycache__", "*.pyc", "*.pyo"]', spec)


if __name__ == "__main__":
    unittest.main()
