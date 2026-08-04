import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


INSTALLER_SCRIPT = Path(__file__).resolve().parents[1] / "build" / "windows" / "InfiniteCanvas.iss"
INSTALLER_SMOKE_SCRIPT = (
    Path(__file__).resolve().parents[1] / "build" / "windows" / "test_installer_upgrade.ps1"
)
PYINSTALLER_SPEC = Path(__file__).resolve().parents[1] / "build" / "windows" / "InfiniteCanvas.spec"


class InstallerDefinitionTests(unittest.TestCase):
    def test_installer_preserves_local_app_data(self):
        script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")

        self.assertIn("AppId={{61D4D665-79A6-4C85-A5D0-FE262538F79C}", script)
        self.assertIn("PrivilegesRequired=lowest", script)
        self.assertNotIn("%LOCALAPPDATA%", script)
        self.assertNotIn("uninsdelete", script.lower())
        self.assertIn("OutputBaseFilename=InfiniteCanvas-Setup-{#AppVersion}", script)

    def test_upgrade_removes_only_old_runtime_before_copy(self):
        script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")

        self.assertIn("function PrepareToInstall(var NeedsRestart: Boolean): String;", script)
        self.assertIn("RuntimeDir := ExpandConstant('{app}\\_internal');", script)
        self.assertIn("ExecutablePath := ExpandConstant('{app}\\InfiniteCanvas.exe');", script)
        self.assertIn("if DirExists(RuntimeDir)", script)
        self.assertIn("DelTree(RuntimeDir, True, True, True)", script)
        self.assertIn("if FileExists(ExecutablePath)", script)
        self.assertIn("DeleteFile(ExecutablePath)", script)
        self.assertIn("Result := 'The previous InfiniteCanvas runtime could not be removed.'", script)
        self.assertIn("Result := 'The previous InfiniteCanvas executable could not be removed.'", script)

    def test_cleanup_does_not_target_user_data_or_whole_app_directory(self):
        script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")
        cleanup = script.split("function PrepareToInstall", 1)[1]

        self.assertNotIn("localappdata", cleanup.lower())
        self.assertNotIn("DelTree(ExpandConstant('{app}')", cleanup)

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
        self.assertIn("UsePreviousAppDir=no", script)
        self.assertIn("#ifndef SmokeTestRoot", script)

    def test_upgrade_smoke_script_covers_clean_install_and_legacy_residue(self):
        script = INSTALLER_SMOKE_SCRIPT.read_text(encoding="utf-8-sig")

        self.assertIn('"/DSmokeTestRoot=$installRoot"', script)
        self.assertIn("legacy-speedups.cp310-win_amd64.pyd", script)
        self.assertIn("websockets-16.1.1.dist-info", script)
        self.assertIn('"/VERYSILENT"', script)
        self.assertIn("InfiniteCanvas.exe", script)
        self.assertIn("Assert-WithinTestRoot", script)
        self.assertIn("Start-Process -FilePath $Installer -ArgumentList $Arguments -Wait -PassThru", script)

    def test_pyinstaller_excludes_generated_tool_caches(self):
        spec = PYINSTALLER_SPEC.read_text(encoding="utf-8-sig")

        self.assertIn('Tree(', spec)
        self.assertIn('prefix="tools"', spec)
        self.assertIn('excludes=["__pycache__", "*.pyc", "*.pyo"]', spec)


if __name__ == "__main__":
    unittest.main()
