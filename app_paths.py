from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    resource_dir: Path
    data_dir: Path

    @property
    def static_dir(self) -> Path:
        return self.resource_dir / "static"

    @property
    def workflow_dir(self) -> Path:
        return self.resource_dir / "workflows"

    @property
    def cli_dir(self) -> Path:
        return self.resource_dir / "CLI"

    @property
    def tools_dir(self) -> Path:
        return self.resource_dir / "tools"

    @property
    def version_file(self) -> Path:
        return self.resource_dir / "VERSION"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def asset_input_dir(self) -> Path:
        return self.assets_dir / "input"

    @property
    def asset_output_dir(self) -> Path:
        return self.assets_dir / "output"

    @property
    def asset_library_dir(self) -> Path:
        return self.assets_dir / "library"

    @property
    def local_upload_dir(self) -> Path:
        return self.assets_dir / "uploads"

    @property
    def history_file(self) -> Path:
        return self.data_dir / "history.json"

    @property
    def api_env_file(self) -> Path:
        return self.data_dir / "API" / ".env"

    @property
    def runtime_data_dir(self) -> Path:
        return self.data_dir / "data"

    @property
    def conversation_dir(self) -> Path:
        return self.runtime_data_dir / "conversations"

    @property
    def canvas_dir(self) -> Path:
        return self.runtime_data_dir / "canvases"

    @property
    def media_preview_dir(self) -> Path:
        return self.runtime_data_dir / "media_previews"

    @property
    def asset_library_file(self) -> Path:
        return self.runtime_data_dir / "asset_library.json"

    @property
    def prompt_library_file(self) -> Path:
        return self.runtime_data_dir / "prompt_libraries.json"

    @property
    def api_providers_file(self) -> Path:
        return self.runtime_data_dir / "api_providers.json"

    @property
    def runninghub_workflow_store_file(self) -> Path:
        return self.runtime_data_dir / "runninghub_workflows.json"

    @property
    def shared_folders_file(self) -> Path:
        return self.runtime_data_dir / "shared_folders.json"

    @property
    def storage_settings_file(self) -> Path:
        return self.runtime_data_dir / "storage_settings.json"

    @property
    def mediakit_settings_file(self) -> Path:
        return self.runtime_data_dir / "mediakit_settings.json"

    @property
    def mediakit_tasks_file(self) -> Path:
        return self.runtime_data_dir / "mediakit_tasks.json"

    @property
    def canvas_media_tasks_file(self) -> Path:
        return self.runtime_data_dir / "canvas_media_tasks.json"

    @property
    def projects_file(self) -> Path:
        return self.runtime_data_dir / "projects.json"

    @property
    def asset_classification_prompt_file(self) -> Path:
        return self.runtime_data_dir / "asset_classification_prompt.txt"

    @property
    def global_config_file(self) -> Path:
        return self.data_dir / "global_config.json"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def webview_data_dir(self) -> Path:
        return self.data_dir / "webview"


def _default_local_app_data() -> Path:
    configured = os.environ.get("LOCALAPPDATA", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "AppData" / "Local"


def resolve_app_paths(
    resource_dir: Path | str | None = None,
    data_dir: Path | str | None = None,
    frozen: bool | None = None,
) -> AppPaths:
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if resource_dir is None:
        if packaged:
            resource_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
        else:
            resource_root = Path(__file__).resolve().parent
    else:
        resource_root = Path(resource_dir).expanduser().resolve()

    if data_dir is not None:
        data_root = Path(data_dir).expanduser().resolve()
    else:
        configured = os.environ.get("INFINITE_CANVAS_DATA_DIR", "").strip()
        if configured:
            data_root = Path(configured).expanduser().resolve()
        elif packaged:
            data_root = (_default_local_app_data() / "InfiniteCanvas").resolve()
        else:
            data_root = resource_root

    return AppPaths(resource_dir=resource_root, data_dir=data_root)


def ensure_user_directories(paths: AppPaths) -> None:
    directories = (
        paths.api_env_file.parent,
        paths.output_dir,
        paths.asset_input_dir,
        paths.asset_output_dir,
        paths.asset_library_dir,
        paths.local_upload_dir,
        paths.runtime_data_dir,
        paths.conversation_dir,
        paths.canvas_dir,
        paths.media_preview_dir,
        paths.logs_dir,
        paths.webview_data_dir,
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
