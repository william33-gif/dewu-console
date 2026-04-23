import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "得物自动发布控制台 API"
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/dewu_console"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    app_timezone: str = "Asia/Shanghai"
    project_root: Path = Path("..")
    appium_script_path: Path = Path("test_dewu.py")
    adb_path: Path | None = None
    publish_timeout_seconds: int = 300
    schedule_enabled: bool = True
    schedule_poll_seconds: int = 30
    material_storage_dir: Path = Path("storage/materials")
    result_storage_dir: Path = Path("storage/results")
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_app_token: str | None = None
    feishu_table_id: str | None = None
    feishu_view_id: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_project_root(self) -> Path:
        return self.project_root.resolve()

    @property
    def resolved_appium_script_path(self) -> Path:
        return (self.resolved_project_root / self.appium_script_path).resolve()

    @property
    def resolved_adb_path(self) -> Path:
        if self.adb_path:
            return Path(self.adb_path).expanduser().resolve()

        candidates: list[str | Path | None] = [
            shutil.which("adb"),
            Path(os.environ.get("ANDROID_SDK_ROOT", "")) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if os.environ.get("ANDROID_SDK_ROOT")
            else None,
            Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if os.environ.get("ANDROID_HOME")
            else None,
            Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        ]

        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists():
                return path.resolve()

        fallback = "adb.exe" if os.name == "nt" else "adb"
        return Path(fallback)

    @property
    def resolved_material_storage_dir(self) -> Path:
        return (self.resolved_project_root / self.material_storage_dir).resolve()

    @property
    def resolved_result_storage_dir(self) -> Path:
        return (self.resolved_project_root / self.result_storage_dir).resolve()

    @property
    def feishu_configured(self) -> bool:
        return all(
            [
                self.feishu_app_id,
                self.feishu_app_secret,
                self.feishu_app_token,
                self.feishu_table_id,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
