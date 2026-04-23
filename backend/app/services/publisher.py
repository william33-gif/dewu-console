import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import AccountDevice, DeviceStatus, MaterialBatch, PublishLog, PublishTask, TaskStatus

SUCCESS_MARKER = "PUBLISH_SUCCESS"
SCREENSHOT_MARKER = "PUBLISH_SCREENSHOT_URL="
REMOTE_CAMERA_DIR = "/sdcard/DCIM/Camera"
REMOTE_BATCH_MARKER = "DEWU_"
REMOTE_BATCH_PREFIX = "zzzz_DEWU_"
DEWU_APP_PACKAGE = "com.shizhuang.duapp"
MEDIA_SETTLE_SECONDS = 6
PUBLISH_EXECUTION_LOCK = Lock()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_log(task_id: str, step_name: str, result: str, detail: Optional[str] = None, screenshot: Optional[str] = None) -> None:
    with SessionLocal() as db:
        db.add(
            PublishLog(
                task_id=task_id,
                step_name=step_name,
                result=result,
                detail=detail,
                screenshot=screenshot,
            )
        )
        db.commit()


def get_material_image_paths(material: MaterialBatch) -> list[tuple[str, Path]]:
    raw_values = [
        ("image_1", material.image_1),
        ("image_2", material.image_2),
        ("image_3", material.image_3),
        ("image_4", material.image_4),
    ]
    paths: list[tuple[str, Path]] = []

    for index, (label, raw_value) in enumerate(raw_values, start=1):
        if not raw_value:
            raise RuntimeError(f"Material batch is missing image {index}.")

        path = Path(raw_value)
        if not path.exists():
            raise RuntimeError(f"Material image does not exist: {path}")
        paths.append((label, path))

    cover_path = Path(material.cover_image) if material.cover_image else paths[0][1]
    if not cover_path.exists():
        raise RuntimeError(f"Cover image does not exist: {cover_path}")

    cover_index = next((index for index, (_, path) in enumerate(paths) if path.resolve() == cover_path.resolve()), None)
    if cover_index is None:
        raise RuntimeError("Cover image must be one of image_1 to image_4.")

    cover_item = paths.pop(cover_index)
    paths.append(cover_item)
    return paths


def run_adb_command(adb_path: Path, serial: str, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(adb_path), "-s", serial, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def cleanup_previous_pushed_images(task_id: str, adb_path: Path, serial: str) -> None:
    cleanup_result = run_adb_command(
        adb_path,
        serial,
        ["shell", f"find {REMOTE_CAMERA_DIR} -maxdepth 1 -name '*{REMOTE_BATCH_MARKER}*' -delete"],
        timeout=30,
    )
    if cleanup_result.returncode != 0:
        detail = (cleanup_result.stderr or cleanup_result.stdout or "").strip()
        add_log(
            task_id,
            "Clean remote temp images",
            "failed",
            detail or "Failed to remove old DEWU temp images. Continuing with publish.",
        )
        return

    add_log(
        task_id,
        "Clean remote temp images",
        "success",
        "Removed old DEWU temp images from the device camera directory.",
    )


def wait_for_media_library(task_id: str, step_name: str, seconds: int = MEDIA_SETTLE_SECONDS) -> None:
    add_log(task_id, step_name, "running", f"Waiting {seconds}s for the media library to refresh.")
    time.sleep(seconds)


def force_stop_dewu_app(task_id: str, adb_path: Path, serial: str) -> None:
    result = run_adb_command(adb_path, serial, ["shell", "am", "force-stop", DEWU_APP_PACKAGE], timeout=30)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        add_log(
            task_id,
            "Force stop Dewu",
            "failed",
            detail or "Failed to force stop Dewu. Continuing with publish.",
        )
        return

    add_log(task_id, "Force stop Dewu", "success", "Dewu was force stopped before the task started. The next script run will cold start the app.")


def set_remote_image_timestamp(task_id: str, adb_path: Path, serial: str, remote_path: str, timestamp: datetime) -> None:
    time_token = timestamp.strftime("%Y%m%d%H%M.%S")
    touch_result = run_adb_command(
        adb_path,
        serial,
        ["shell", "touch", "-t", time_token, remote_path],
        timeout=30,
    )
    if touch_result.returncode != 0:
        detail = (touch_result.stderr or touch_result.stdout or "").strip()
        raise RuntimeError(f"Failed to set image timestamp for {remote_path}: {detail or 'touch returned non-zero'}")

    add_log(task_id, "Rewrite image timestamp", "success", f"{remote_path} -> {time_token}")


def push_material_images_to_device(task_id: str, material: MaterialBatch, device: AccountDevice) -> list[str]:
    settings = get_settings()
    adb_path = settings.resolved_adb_path
    serial = device.adb_serial or device.device_id
    upload_items = get_material_image_paths(material)
    remote_paths: list[str] = []
    now = datetime.now()
    batch_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    try:
        mkdir_result = run_adb_command(adb_path, serial, ["shell", "mkdir", "-p", REMOTE_CAMERA_DIR], timeout=30)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ADB was not found. Current resolved path: {adb_path}") from exc

    if mkdir_result.returncode != 0:
        detail = (mkdir_result.stderr or mkdir_result.stdout or "").strip()
        raise RuntimeError(f"Failed to create remote camera directory: {detail or REMOTE_CAMERA_DIR}")

    cleanup_previous_pushed_images(task_id, adb_path, serial)
    wait_for_media_library(task_id, "Wait for old images cleanup")

    total_items = len(upload_items)
    for upload_index, (label, local_path) in enumerate(upload_items, start=1):
        suffix = local_path.suffix.lower() or ".jpg"
        sort_index = total_items - upload_index + 1
        remote_name = f"{REMOTE_BATCH_PREFIX}{batch_stamp}_{task_id}_{sort_index:02d}_{label}{suffix}"
        remote_path = f"{REMOTE_CAMERA_DIR}/{remote_name}"

        push_result = run_adb_command(adb_path, serial, ["push", str(local_path), remote_path], timeout=180)
        if push_result.returncode != 0:
            detail = (push_result.stderr or push_result.stdout or "").strip()
            raise RuntimeError(f"Failed to push {local_path.name}: {detail or 'adb push returned non-zero'}")

        target_time = now + timedelta(seconds=total_items - upload_index + 1)
        set_remote_image_timestamp(task_id, adb_path, serial, remote_path, target_time)

        scan_result = run_adb_command(
            adb_path,
            serial,
            [
                "shell",
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                f"file://{remote_path}",
            ],
            timeout=30,
        )
        if scan_result.returncode != 0:
            add_log(
                task_id,
                "Refresh media library",
                "failed",
                f"Media scan returned non-zero for {remote_path}. Dewu may not see the image immediately.",
            )

        remote_paths.append(remote_path)
        time.sleep(1)

    wait_for_media_library(task_id, "Wait for new images to appear", seconds=4)
    return remote_paths


def mark_failed(task_id: str, detail: str, result_screenshot: str | None = None) -> None:
    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        if not task:
            return

        device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id)) if task.device_id else None
        task.status = TaskStatus.FAILED.value
        task.error_message = detail
        task.current_step = "Publish failed"
        if result_screenshot:
            task.result_screenshot = result_screenshot
        task.execution_finished_at = utcnow()
        if device:
            device.status = DeviceStatus.ERROR.value
            device.last_heartbeat = utcnow()
        db.commit()

    add_log(task_id, "Publish failed", "failed", detail, screenshot=result_screenshot)


def extract_stdout_marker(output: str, marker: str) -> str | None:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped.startswith(marker):
            value = stripped[len(marker) :].strip()
            return value or None
    return None


def _run_publish_job_impl(task_id: str) -> None:
    settings = get_settings()

    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        if not task:
            return

        material = db.scalar(select(MaterialBatch).where(MaterialBatch.batch_id == task.material_batch_id)) if task.material_batch_id else None
        device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id)) if task.device_id else None

        task.status = TaskStatus.PUBLISHING.value
        task.current_step = "Lock task"
        task.error_message = None
        task.result_screenshot = None
        task.execution_started_at = utcnow()
        task.execution_finished_at = None
        if device:
            device.status = DeviceStatus.BUSY.value
        db.commit()

    add_log(task_id, "Task locked", "success", "Task moved to publishing.")

    if not material:
        mark_failed(task_id, "No material batch is bound to the task.")
        return

    if not device:
        mark_failed(task_id, "No device is bound to the task.")
        return

    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        if task:
            task.current_step = "Push images to device"
            db.commit()

    try:
        remote_paths = push_material_images_to_device(task_id, material, device)
    except Exception as exc:  # noqa: BLE001
        mark_failed(task_id, f"Failed to push images to device: {exc}")
        return

    remote_summary = "\n".join(f"image_{index + 1}: {remote_path}" for index, remote_path in enumerate(remote_paths))
    add_log(
        task_id,
        "Push images to device",
        "success",
        f"Batch {material.batch_id} was pushed to device {device.device_id}.\n{remote_summary}",
    )

    force_stop_dewu_app(task_id, settings.resolved_adb_path, device.adb_serial or device.device_id)

    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        if task:
            task.current_step = "Run Appium script"
            db.commit()

    script_path = settings.resolved_appium_script_path
    script_env = os.environ.copy()
    script_env.update(
        {
            "DEWU_UDID": device.adb_serial or device.device_id,
            "DEWU_ADB_PATH": str(settings.resolved_adb_path),
            "DEWU_APPIUM_URL": device.appium_url or "http://127.0.0.1:4723",
            "DEWU_TASK_ID": task_id,
            "DEWU_MATERIAL_BATCH_ID": material.batch_id,
            "DEWU_PUSHED_IMAGES": "|".join(remote_paths),
            "DEWU_TITLE": task.title or "",
            "DEWU_CONTENT": task.content or "",
            "DEWU_TOPICS": task.topics or "",
            "DEWU_RESULT_DIR": str(settings.resolved_result_storage_dir),
            "DEWU_RESULT_URL_PREFIX": "/media/results",
            "DEWU_PUBLISH_RESULT_WAIT_SECONDS": "1.0",
        }
    )
    add_log(task_id, "Start auto publish", "running", f"Executing script: {script_path}")

    try:
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(settings.resolved_project_root),
            capture_output=True,
            text=True,
            env=script_env,
            timeout=settings.publish_timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        mark_failed(task_id, f"Publish script was not found: {script_path}")
        return
    except subprocess.TimeoutExpired:
        mark_failed(task_id, f"Publish script timed out after {settings.publish_timeout_seconds}s.")
        return
    except Exception as exc:  # noqa: BLE001
        mark_failed(task_id, f"Running the publish script raised an exception: {exc}")
        return

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    result_screenshot = extract_stdout_marker(stdout, SCREENSHOT_MARKER)

    if stdout:
        add_log(task_id, "Script stdout", "success", stdout[:5000], screenshot=result_screenshot)
    if stderr:
        add_log(task_id, "Script stderr", "failed", stderr[:5000])

    if completed.returncode != 0:
        mark_failed(task_id, f"Publish script exited with code {completed.returncode}.", result_screenshot=result_screenshot)
        return

    if SUCCESS_MARKER not in stdout:
        mark_failed(task_id, "Publish script finished but the success marker was not found.", result_screenshot=result_screenshot)
        return

    if result_screenshot:
        add_log(
            task_id,
            "Publish result screenshot",
            "success",
            "Captured a confirmation screenshot 1 second after tapping publish.",
            screenshot=result_screenshot,
        )

    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id)) if task else None
        if not task:
            return

        task.status = TaskStatus.PUBLISHED.value
        task.current_step = "Publish complete"
        task.actual_publish_time = utcnow()
        task.execution_finished_at = utcnow()
        task.publish_url = task.publish_url or f"dewu://publish/{task.task_id}"
        task.result_screenshot = result_screenshot
        if device:
            device.status = DeviceStatus.IDLE.value
            device.last_heartbeat = utcnow()
        db.commit()

    add_log(
        task_id,
        "Publish complete",
        "success",
        "Appium script completed and the task was marked as published.",
        screenshot=result_screenshot,
    )


def run_publish_job(task_id: str) -> None:
    with PUBLISH_EXECUTION_LOCK:
        _run_publish_job_impl(task_id)


def run_batch_publish_job(task_ids: list[str]) -> None:
    total = len(task_ids)
    if total == 0:
        return

    for index, task_id in enumerate(task_ids, start=1):
        with SessionLocal() as db:
            task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
            if not task:
                continue
            task.current_step = f"Batch item {index}/{total}"
            db.commit()

        add_log(task_id, "Batch publish", "running", f"Starting batch item {index}/{total}.")

        try:
            run_publish_job(task_id)
        except Exception as exc:  # noqa: BLE001
            mark_failed(task_id, f"Batch publish raised an exception: {exc}")
