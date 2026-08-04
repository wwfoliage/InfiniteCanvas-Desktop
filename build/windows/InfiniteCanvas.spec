# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]
webview_datas, webview_binaries, webview_hidden = collect_all("webview")

datas = [
    (str(project_root / "static"), "static"),
    (str(project_root / "workflows"), "workflows"),
    (str(project_root / "CLI"), "CLI"),
    (str(project_root / "tools"), "tools"),
    (str(project_root / "VERSION"), "."),
    (str(project_root / "LICENSE"), "."),
] + webview_datas

hidden_imports = sorted(set(
    webview_hidden
    + collect_submodules("uvicorn")
    + collect_submodules("webview")
    + ["canvas_media_tasks"]
))

a = Analysis(
    [str(project_root / "desktop_app.py")],
    pathex=[str(project_root)],
    binaries=webview_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InfiniteCanvas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "build" / "windows" / "InfiniteCanvas.ico"),
    version=str(project_root / "build" / "windows" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="InfiniteCanvas",
)
