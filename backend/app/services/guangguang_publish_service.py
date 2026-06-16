from enum import Enum
import json
import logging
from pathlib import Path
import re

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    GuangguangPCPublishLog,
    GuangguangPCPublishStatus,
    GuangguangPCPublishTask,
    GuangguangPublishLog,
    GuangguangPublishTask,
)
from app.schemas import GuangguangPublishLogCreate, GuangguangPublishTaskCreate, GuangguangPublishTaskUpdate
from app.services.ai_buyer_show_asset_service import (
    _attachment_extension,
    download_feishu_attachment,
    extract_first_attachment_ref,
)
from app.services.feishu_sync import (
    _field_text_candidates,
    _first_present,
    _get_tenant_access_token,
    _iter_records,
    _normalize_text,
    _parse_datetime,
)

logger = logging.getLogger("uvicorn.error")
MAX_GUANGGUANG_IMAGES = 9
MAX_GUANGGUANG_IMAGE_BYTES = 20 * 1024 * 1024


def _payload_data(payload: GuangguangPublishTaskCreate | GuangguangPublishTaskUpdate | GuangguangPublishLogCreate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    return {field: value.value if isinstance(value, Enum) else value for field, value in data.items()}


def list_publish_tasks(db: Session) -> list[GuangguangPublishTask]:
    return list(db.scalars(select(GuangguangPublishTask).order_by(desc(GuangguangPublishTask.created_at))).all())


def get_publish_task(db: Session, task_id: int) -> GuangguangPublishTask | None:
    return db.get(GuangguangPublishTask, task_id)


def create_publish_task(db: Session, payload: GuangguangPublishTaskCreate) -> GuangguangPublishTask:
    task = GuangguangPublishTask(**_payload_data(payload))
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_publish_task(
    db: Session,
    task: GuangguangPublishTask,
    payload: GuangguangPublishTaskUpdate,
) -> GuangguangPublishTask:
    for field, value in _payload_data(payload).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


def list_publish_logs(db: Session, task_id: int) -> list[GuangguangPublishLog]:
    statement = select(GuangguangPublishLog).where(GuangguangPublishLog.task_id == task_id)
    return list(db.scalars(statement.order_by(desc(GuangguangPublishLog.created_at))).all())


def create_publish_log(db: Session, task_id: int, payload: GuangguangPublishLogCreate) -> GuangguangPublishLog:
    log = GuangguangPublishLog(task_id=task_id, **_payload_data(payload))
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_pc_publish_task(db: Session, task_id: int) -> GuangguangPCPublishTask | None:
    return db.get(GuangguangPCPublishTask, task_id)


def list_pc_publish_tasks(db: Session) -> list[GuangguangPCPublishTask]:
    statement = select(GuangguangPCPublishTask).order_by(desc(GuangguangPCPublishTask.created_at))
    return list(db.scalars(statement).all())


def add_pc_publish_log(
    db: Session,
    task_id: int,
    step_name: str,
    result: str,
    detail: str | None = None,
    screenshot: str | None = None,
) -> GuangguangPCPublishLog:
    log = GuangguangPCPublishLog(
        task_id=task_id,
        step_name=step_name,
        result=result,
        detail=detail,
        screenshot=screenshot,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def set_pc_task_state(
    db: Session,
    task: GuangguangPCPublishTask,
    status: GuangguangPCPublishStatus,
    *,
    error_message: str | None = None,
    screenshot_path: str | None = None,
) -> GuangguangPCPublishTask:
    task.status = status.value
    task.error_message = error_message
    if screenshot_path is not None:
        task.screenshot_path = screenshot_path
    db.commit()
    db.refresh(task)
    return task


def _normalize_field_key(name: str) -> str:
    """Strip all whitespace and lowercase so field names match tolerantly."""
    return re.sub(r"\s+", "", str(name)).lower()


def _lookup_field(fields: dict[str, object], *names: str) -> str | None:
    """Read a field by name, tolerating case and whitespace differences in the key."""
    for name in names:
        value = _normalize_text(fields.get(name))
        if value:
            return value

    wanted = {_normalize_field_key(name) for name in names}
    for key, raw in fields.items():
        if _normalize_field_key(key) in wanted:
            value = _normalize_text(raw)
            if value:
                return value
    return None


# Field-name candidates for the Taobao product id, in priority order.
TAOBAO_ID_FIELD_NAMES = ("淘宝id", "淘宝ID", "款号ID")


def resolve_sku_id_from_feishu(db: Session, task: GuangguangPCPublishTask) -> str | None:
    """Re-read 淘宝id from Feishu for an existing task whose sku_id is missing.

    Tasks synced by older code may have a NULL sku_id even though the Feishu
    record now carries the value. This backfills it on demand so binding does
    not fail just because the row predates the field-reading logic.
    """
    if not (task.feishu_record_id or "").strip():
        return None

    token = _get_tenant_access_token()
    for record in _iter_records(token):
        record_id = str(record.get("record_id") or record.get("id") or "").strip()
        if record_id != task.feishu_record_id:
            continue
        fields = record.get("fields")
        if not isinstance(fields, dict):
            return None
        sku_id = _lookup_field(fields, *TAOBAO_ID_FIELD_NAMES)
        if sku_id and sku_id != task.sku_id:
            task.sku_id = sku_id
            db.commit()
            db.refresh(task)
        return sku_id
    return None


def _manual_review_is_approved(fields: dict[str, object]) -> tuple[bool, str | None]:
    candidates = [
        candidate.strip()
        for candidate in _field_text_candidates(fields.get("人工审核"))
        if candidate.strip()
    ]
    review_text = " ".join(dict.fromkeys(candidates)) or None
    return any(candidate == "通过" for candidate in candidates), review_text


def _serialize_attachments(value: object | None) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    attachments = [item for item in value if isinstance(item, dict)]
    if not attachments:
        return None
    return json.dumps(attachments, ensure_ascii=False, default=str)


def _apply_feishu_fields(
    task: GuangguangPCPublishTask,
    *,
    fields: dict[str, object],
    scheduled_at: object,
    review_text: str | None,
) -> None:
    serialized_materials = _serialize_attachments(fields.get("素材"))
    if task.feishu_materials != serialized_materials:
        task.local_image_paths = None
    task.sku = _first_present(fields, "款号", "货号")
    task.color = _normalize_text(fields.get("色号"))
    task.sku_id = _lookup_field(fields, *TAOBAO_ID_FIELD_NAMES)
    task.device_id = _normalize_text(fields.get("设备ID"))
    task.manual_review = review_text
    task.scheduled_at = scheduled_at
    task.title = _normalize_text(fields.get("淘宝版本标题"))
    task.content = _normalize_text(fields.get("淘宝版本文案"))
    task.feishu_materials = serialized_materials


def sync_pc_tasks_from_feishu(db: Session) -> dict[str, object]:
    logger.info("GUANGGUANG_FEISHU_SYNC_START")
    token = _get_tenant_access_token()
    records = _iter_records(token)
    result: dict[str, object] = {
        "total_records": len(records),
        "synced": 0,
        "skipped": 0,
        "failed": 0,
        "items": [],
    }
    items = result["items"]
    assert isinstance(items, list)

    for record in records:
        record_id = str(record.get("record_id") or record.get("id") or "").strip()
        fields = record.get("fields")
        if not record_id or not isinstance(fields, dict):
            result["failed"] = int(result["failed"]) + 1
            items.append(
                {
                    "record_id": record_id or "unknown",
                    "task_id": None,
                    "status": "failed",
                    "detail": "飞书记录缺少 record_id 或 fields。",
                }
            )
            continue

        try:
            review_approved, review_text = _manual_review_is_approved(fields)
            scheduled_at = _parse_datetime(fields.get("逛逛计划发布时间"))
            qualifies = review_approved and scheduled_at is not None
            task = db.scalar(
                select(GuangguangPCPublishTask).where(
                    GuangguangPCPublishTask.feishu_record_id == record_id
                )
            )

            if task is not None and task.status == GuangguangPCPublishStatus.PUBLISHED.value:
                result["skipped"] = int(result["skipped"]) + 1
                items.append(
                    {
                        "record_id": record_id,
                        "task_id": task.id,
                        "status": "skipped_published",
                        "detail": "逛逛任务已发布，飞书同步未覆盖。",
                    }
                )
                continue

            if task is None and not qualifies:
                result["skipped"] = int(result["skipped"]) + 1
                reason = (
                    "人工审核不是“通过”"
                    if not review_approved
                    else "逛逛计划发布时间为空"
                )
                items.append(
                    {
                        "record_id": record_id,
                        "task_id": None,
                        "status": "skipped",
                        "detail": f"未生成逛逛任务：{reason}。",
                    }
                )
                continue

            action = "updated"
            if task is None:
                action = "created"
                task = GuangguangPCPublishTask(
                    source_type="feishu",
                    feishu_record_id=record_id,
                    status=GuangguangPCPublishStatus.PENDING.value,
                )
                db.add(task)

            _apply_feishu_fields(
                task,
                fields=fields,
                scheduled_at=scheduled_at,
                review_text=review_text,
            )
            db.commit()
            db.refresh(task)
            result["synced"] = int(result["synced"]) + 1
            active_detail = (
                "已进入逛逛待发布任务。"
                if qualifies
                else "计划时间或人工审核条件已不满足，任务保留但不进入待发布。"
            )
            items.append(
                {
                    "record_id": record_id,
                    "task_id": task.id,
                    "status": action if qualifies else "updated_inactive",
                    "detail": active_detail,
                }
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("GUANGGUANG_FEISHU_SYNC_RECORD_FAILED record_id=%s", record_id)
            result["failed"] = int(result["failed"]) + 1
            items.append(
                {
                    "record_id": record_id,
                    "task_id": None,
                    "status": "failed",
                    "detail": str(exc),
                }
            )

    logger.info(
        "GUANGGUANG_FEISHU_SYNC_DONE synced=%s skipped=%s failed=%s",
        result["synced"],
        result["skipped"],
        result["failed"],
    )
    return result


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip()
    return cleaned or "image"


def parse_feishu_materials(task: GuangguangPCPublishTask) -> list[dict[str, object]]:
    if not task.feishu_materials:
        return []
    try:
        value = json.loads(task.feishu_materials)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("素材字段格式无效") from exc
    if not isinstance(value, list):
        raise ValueError("素材字段格式无效")
    return [item for item in value if isinstance(item, dict)]


def prepare_local_images(task: GuangguangPCPublishTask) -> list[Path]:
    attachments = parse_feishu_materials(task)
    if not attachments:
        raise ValueError("素材为空")
    if len(attachments) > MAX_GUANGGUANG_IMAGES:
        raise ValueError("逛逛最多支持 9 张图片")

    for attachment in attachments:
        raw_size = attachment.get("size")
        try:
            attachment_size = int(raw_size) if raw_size is not None else 0
        except (TypeError, ValueError):
            attachment_size = 0
        if attachment_size > MAX_GUANGGUANG_IMAGE_BYTES:
            raise ValueError(
                f"逛逛单张图片不能超过 20MB：{attachment.get('name') or '未命名图片'}"
            )

    token = _get_tenant_access_token()
    settings = get_settings()
    image_dir = (
        settings.resolved_project_root
        / "storage"
        / "guangguang_tasks"
        / str(task.id)
        / "images"
    )
    image_dir.mkdir(parents=True, exist_ok=True)
    local_paths: list[Path] = []

    for index, attachment in enumerate(attachments, start=1):
        attachment_ref = extract_first_attachment_ref(attachment)
        if attachment_ref is None:
            raise ValueError(f"素材附件缺少下载信息：第 {index} 张")
        extension = _attachment_extension(attachment_ref)
        original_name = _safe_file_name(str(attachment.get("name") or f"image_{index}{extension}"))
        if not Path(original_name).suffix:
            original_name = f"{original_name}{extension}"
        target_path = image_dir / f"{index:02d}_{original_name}"
        downloaded_path = Path(
            download_feishu_attachment(
                attachment_ref,
                target_path,
                tenant_access_token=token,
            )
        )
        if not downloaded_path.is_file() or downloaded_path.stat().st_size <= 0:
            raise ValueError(f"本地图片不存在：{downloaded_path}")
        if downloaded_path.stat().st_size > MAX_GUANGGUANG_IMAGE_BYTES:
            raise ValueError(f"逛逛单张图片不能超过 20MB：{downloaded_path.name}")
        local_paths.append(downloaded_path.resolve())

    return local_paths


def save_local_image_paths(
    db: Session,
    task: GuangguangPCPublishTask,
    paths: list[Path],
) -> GuangguangPCPublishTask:
    task.local_image_paths = json.dumps([str(path) for path in paths], ensure_ascii=False)
    db.commit()
    db.refresh(task)
    return task
