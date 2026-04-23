import random
import threading
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import PublishTask, TaskStatus
from app.services.publisher import add_log, run_publish_job

_scheduler_lock = threading.Lock()
_scheduler_thread: threading.Thread | None = None
_scheduler_stop_event = threading.Event()


def _normalize_plan_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        local_tz = ZoneInfo(get_settings().app_timezone)
        value = value.replace(tzinfo=local_tz)

    return value.astimezone(timezone.utc)


def _collect_due_ready_task_ids() -> list[str]:
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        tasks = db.scalars(
            select(PublishTask).where(
                PublishTask.status == TaskStatus.READY.value,
                PublishTask.plan_publish_time.is_not(None),
            )
        ).all()

    due_groups: dict[datetime, list[PublishTask]] = defaultdict(list)
    for task in tasks:
        normalized = _normalize_plan_time(task.plan_publish_time)
        if normalized and normalized <= now:
            due_groups[normalized].append(task)

    ordered_task_ids: list[str] = []
    for plan_time in sorted(due_groups):
        same_time_tasks = due_groups[plan_time]
        random.shuffle(same_time_tasks)
        ordered_task_ids.extend(task.task_id for task in same_time_tasks)

    return ordered_task_ids


def _is_task_still_due_and_ready(task_id: str) -> bool:
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        if not task or task.status != TaskStatus.READY.value:
            return False

        normalized = _normalize_plan_time(task.plan_publish_time)
        return bool(normalized and normalized <= now)


def _mark_scheduled_queue(task_id: str) -> None:
    with SessionLocal() as db:
        task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
        if not task:
            return
        task.current_step = "Scheduled publish"
        db.commit()


def _scheduler_loop() -> None:
    settings = get_settings()
    poll_seconds = max(5, settings.schedule_poll_seconds)

    while not _scheduler_stop_event.is_set():
        due_task_ids = _collect_due_ready_task_ids()
        for task_id in due_task_ids:
            if _scheduler_stop_event.is_set():
                break
            if not _is_task_still_due_and_ready(task_id):
                continue

            _mark_scheduled_queue(task_id)
            add_log(task_id, "Scheduled publish", "running", "Task reached planned publish time and entered the automatic publish queue.")
            run_publish_job(task_id)

        _scheduler_stop_event.wait(poll_seconds)


def start_publish_scheduler() -> None:
    settings = get_settings()
    if not settings.schedule_enabled:
        return

    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return

        _scheduler_stop_event.clear()
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name="publish-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()


def stop_publish_scheduler() -> None:
    global _scheduler_thread
    _scheduler_stop_event.set()
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=2)
        _scheduler_thread = None
