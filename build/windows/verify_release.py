from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable


FORBIDDEN_FILE_NAMES = {
    ".env",
    "history.json",
    "global_config.json",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".log", ".lnk"}
FORBIDDEN_DIRECTORY_NAMES = {
    "__pycache__",
    ".pytest_cache",
    "canvases",
    "conversations",
    "media_previews",
    "logs",
}
SENSITIVE_JSON_KEYS = {
    "api_key",
    "apikey",
    "access_key",
    "access_token",
    "authorization",
    "password",
    "secret",
    "secret_key",
}


def _normalized_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _json_secret_findings(value: Any, relative_path: str, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            field = f"{prefix}.{key}" if prefix else str(key)
            normalized = _normalized_key(key)
            if normalized in SENSITIVE_JSON_KEYS and isinstance(item, str) and item.strip():
                findings.append(f"{relative_path}: sensitive JSON field {field} is non-empty")
            findings.extend(_json_secret_findings(item, relative_path, field))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_json_secret_findings(item, relative_path, f"{prefix}[{index}]"))
    return findings


def scan_tree(root: Path | str, forbidden_values: Iterable[str]) -> list[str]:
    root_path = Path(root).resolve()
    secrets = [value.encode("utf-8") for value in forbidden_values if len(str(value).strip()) >= 6]
    findings: list[str] = []
    if not root_path.is_dir():
        return [f"release root is missing: {root_path}"]

    for path in sorted(item for item in root_path.rglob("*") if item.is_file()):
        relative = path.relative_to(root_path).as_posix()
        lower_parts = [part.lower() for part in path.relative_to(root_path).parts]
        lower_name = path.name.lower()
        if lower_name in FORBIDDEN_FILE_NAMES or lower_name.endswith(".env"):
            findings.append(f"{relative}: forbidden runtime/configuration file")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"{relative}: forbidden generated file type")
        if any(part in FORBIDDEN_DIRECTORY_NAMES for part in lower_parts[:-1]):
            findings.append(f"{relative}: forbidden personal/runtime directory")

        try:
            content = path.read_bytes()
        except OSError as exc:
            findings.append(f"{relative}: cannot be read ({exc.__class__.__name__})")
            continue

        if any(secret in content for secret in secrets):
            findings.append(f"{relative}: contains a known secret value")

        if path.suffix.lower() == ".json" and len(content) <= 20 * 1024 * 1024:
            try:
                parsed = json.loads(content.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            findings.extend(_json_secret_findings(parsed, relative))

    return sorted(set(findings))


def load_env_secret_values(path: Path | str | None) -> list[str]:
    if not path:
        return []
    source = Path(path)
    if not source.is_file():
        return []
    values: list[str] = []
    for raw_line in source.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        value = line.split("=", 1)[1].strip().strip('"').strip("'")
        if len(value) >= 6:
            values.append(value)
    return values


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, version: str) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return {"version": version, "files": files}


def verify_required_files(root: Path, version: str) -> list[str]:
    findings = []
    required = (
        root / "InfiniteCanvas.exe",
        root / "_internal" / "static" / "index.html",
        root / "_internal" / "VERSION",
        root / "_internal" / "LICENSE",
    )
    for path in required:
        if not path.is_file():
            findings.append(f"missing required packaged file: {path.relative_to(root).as_posix()}")
    packaged_version = root / "_internal" / "VERSION"
    if packaged_version.is_file() and packaged_version.read_text(encoding="utf-8-sig").strip() != version:
        findings.append("packaged VERSION does not match the requested version")
    return findings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify an InfiniteCanvas desktop release tree")
    parser.add_argument("root", type=Path)
    parser.add_argument("--version-file", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    version = args.version_file.read_text(encoding="utf-8-sig").strip()
    secrets = load_env_secret_values(args.secret_file)
    findings = scan_tree(root, secrets)
    findings.extend(verify_required_files(root, version))
    if findings:
        for finding in sorted(set(findings)):
            print(f"ERROR: {finding}", file=sys.stderr)
        return 1

    manifest = build_manifest(root, version)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + os.linesep,
        encoding="utf-8",
    )
    print(f"Verified {len(manifest['files'])} files for InfiniteCanvas {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
