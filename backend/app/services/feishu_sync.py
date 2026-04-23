import ast
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import AccountDevice, MaterialBatch, PublishTask, TaskStatus
from app.schemas import FeishuSyncItem, FeishuSyncResponse
from app.services.publisher import add_log


def _safe_name(name: str) -> str:
    sanitized = re.sub(r"[\\\\/:*?\"<>|]+", "_", name).strip()
    return sanitized or f"file-{uuid4().hex[:8]}"


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple | set):
        combined = "".join(filter(None, (_normalize_text(item) for item in value)))
        cleaned = combined.strip()
        return cleaned or None
    if isinstance(value, dict):
        if "text" in value:
            return _normalize_text(value.get("text"))
        if "content" in value:
            return _normalize_text(value.get("content"))
        combined = "".join(
            filter(
                None,
                (
                    _normalize_text(item)
                    for key, item in value.items()
                    if key not in {"type", "token", "url", "link", "mentionType", "text_element_style"}
                ),
            )
        )
        cleaned = combined.strip()
        return cleaned or None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        parsed = _parse_structured_text(cleaned)
        if parsed is not None and parsed != value:
            normalized = _normalize_text(parsed)
            if normalized:
                return normalized
        return cleaned
    return str(value).strip() or None


def _parse_structured_text(value: str) -> object | None:
    candidate = value.strip()
    if not candidate:
        return None

    for loader in (json.loads, ast.literal_eval):
        try:
            parsed = loader(candidate)
        except Exception:  # noqa: BLE001
            continue
        if parsed == value:
            continue
        if isinstance(parsed, str) and parsed.strip() != value:
            nested = _parse_structured_text(parsed)
            return nested if nested is not None else parsed
        return parsed

    return None


def _first_present(fields: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _normalize_text(fields.get(key))
        if value:
            return value
    return None


def _parse_datetime(value: object | None) -> datetime | None:
    if value in (None, ""):
        return None

    local_tz = ZoneInfo(get_settings().app_timezone)

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=local_tz)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    return None


def _post_json(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, headers: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_binary(url: str, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _get_tenant_access_token() -> str:
    settings = get_settings()
    if not settings.feishu_configured:
        raise RuntimeError("飞书配置不完整。")

    payload = _post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {
            "app_id": settings.feishu_app_id,
            "app_secret": settings.feishu_app_secret,
        },
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"获取飞书 tenant_access_token 失败：{payload.get('msg')}")
    token = payload.get("tenant_access_token")
    if not token:
        raise RuntimeError("飞书返回中缺少 tenant_access_token。")
    return str(token)


def _iter_records(token: str) -> list[dict[str, object]]:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {token}"}

    page_token: str | None = None
    collected: list[dict[str, object]] = []

    while True:
        query = {"page_size": "50"}
        if settings.feishu_view_id:
            query["view_id"] = settings.feishu_view_id
        if page_token:
            query["page_token"] = page_token

        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{settings.feishu_app_token}/tables/{settings.feishu_table_id}/records?"
            f"{urllib.parse.urlencode(query)}"
        )
        payload = _get_json(url, headers)
        if payload.get("code") != 0:
            raise RuntimeError(f"读取飞书多维表格失败：{payload.get('msg')}")

        data = payload.get("data") or {}
        items = data.get("items") or []
        collected.extend(item for item in items if isinstance(item, dict))

        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break

    return collected


def _download_attachments(record_id: str, attachments: list[dict[str, object]], token: str) -> list[str]:
    settings = get_settings()
    base_dir = settings.resolved_material_storage_dir / record_id
    base_dir.mkdir(parents=True, exist_ok=True)

    headers = {"Authorization": f"Bearer {token}"}
    local_paths: list[str] = []

    for index, attachment in enumerate(attachments[:4], start=1):
        file_token = _normalize_text(attachment.get("file_token")) or f"token-{index}"
        file_name = _safe_name(str(attachment.get("name") or f"image_{index}.bin"))
        target_path = base_dir / f"{index:02d}-{file_token}-{file_name}"

        if not target_path.exists():
            download_url = str(attachment.get("url") or "")
            if not download_url:
                raise RuntimeError(f"飞书记录 {record_id} 的附件缺少下载地址。")
            content = _download_binary(download_url, headers)
            target_path.write_bytes(content)

        local_paths.append(str(target_path))

    return local_paths


def _build_title(fields: dict[str, object]) -> str:
    return _normalize_text(fields.get("标题文案")) or "未生成标题"


def _build_content(fields: dict[str, object]) -> str | None:
    return _normalize_text(fields.get("正文文案"))


def _build_tags(fields: dict[str, object]) -> str | None:
    parts = []
    color = _normalize_text(fields.get("色号"))
    if color:
        parts.append(color)
    platform = _normalize_text(fields.get("平台使用"))
    if platform:
        parts.append(platform)
    return " / ".join(parts) if parts else None


def _build_task_status(account_id: str | None, device_id: str | None, image_count: int) -> str:
    if account_id and device_id and image_count >= 4:
        return TaskStatus.READY.value
    return TaskStatus.DRAFT.value


def _resolve_account_reference(db: Session, reference: str | None) -> tuple[AccountDevice | None, str | None]:
    if not reference:
        return None, None

    matched = db.scalar(select(AccountDevice).where(AccountDevice.account_id == reference))
    if matched:
        return matched, f"账号引用 {reference} 已按账号ID匹配。"

    matches = db.scalars(select(AccountDevice).where(AccountDevice.account_name == reference)).all()
    if len(matches) == 1:
        return matches[0], f"账号引用 {reference} 已按账号名称匹配到账号ID {matches[0].account_id}。"
    if len(matches) > 1:
        raise RuntimeError(f"账号名称 {reference} 匹配到多条本地账号记录，请改填账号ID或确保名称唯一。")

    return None, None


def _resolve_device_reference(db: Session, reference: str | None) -> tuple[AccountDevice | None, str | None]:
    if not reference:
        return None, None

    matched = db.scalar(select(AccountDevice).where(AccountDevice.device_id == reference))
    if matched:
        return matched, f"设备引用 {reference} 已按设备ID匹配。"

    matches = db.scalars(select(AccountDevice).where(AccountDevice.device_name == reference)).all()
    if len(matches) == 1:
        return matches[0], f"设备引用 {reference} 已按设备名称匹配到设备ID {matches[0].device_id}。"
    if len(matches) > 1:
        raise RuntimeError(f"设备名称 {reference} 匹配到多条本地设备记录，请改填设备ID或确保名称唯一。")

    return None, None


def _resolve_assignment(
    db: Session,
    account_reference: str | None,
    device_reference: str | None,
    image_count: int,
) -> tuple[str | None, str | None, str, str, str]:
    if image_count < 4:
        return (
            account_reference,
            device_reference,
            TaskStatus.DRAFT.value,
            "待补充素材",
            "附件字段少于 4 张图，暂时不能发布。",
        )

    account_binding, account_hint = _resolve_account_reference(db, account_reference)
    device_binding, device_hint = _resolve_device_reference(db, device_reference)

    if account_binding and not device_reference:
        device_reference = account_binding.device_id
        device_binding = account_binding

    if device_binding and not account_reference:
        account_reference = device_binding.account_id
        account_binding = device_binding

    detail_parts = [part for part in (account_hint, device_hint) if part]

    if not account_reference and not device_reference:
        return None, None, TaskStatus.DRAFT.value, "待补充账号设备", "飞书未填写账号ID和设备ID。"

    if account_reference and not account_binding:
        return (
            None,
            device_binding.device_id if device_binding else None,
            TaskStatus.DRAFT.value,
            "账号未登记",
            f"未找到账号引用 {account_reference}，请在本地账号设备表登记对应账号ID或账号名称。",
        )

    if device_reference and not device_binding:
        return (
            account_binding.account_id if account_binding else None,
            None,
            TaskStatus.DRAFT.value,
            "设备未登记",
            f"未找到设备引用 {device_reference}，请在本地账号设备表登记对应设备ID或设备名称。",
        )

    if not account_reference:
        return None, device_binding.device_id if device_binding else None, TaskStatus.DRAFT.value, "待补充账号信息", "飞书未填写账号信息。"

    if not device_reference:
        return (
            account_binding.account_id if account_binding else None,
            None,
            TaskStatus.DRAFT.value,
            "待补充设备信息",
            "飞书未填写设备信息。",
        )

    if account_binding.id != device_binding.id:
        return (
            account_binding.account_id,
            device_binding.device_id,
            TaskStatus.DRAFT.value,
            "账号设备不匹配",
            (
                f"账号引用 {account_reference} 和设备引用 {device_reference} "
                "在本地并非同一组绑定关系。"
            ),
        )

    success_detail = " ".join(detail_parts) if detail_parts else "账号设备已匹配，图文已同步，等待人工审核。"
    return account_binding.account_id, device_binding.device_id, TaskStatus.PENDING_REVIEW.value, "待审核", success_detail


def _upsert_material_batch(
    db: Session,
    batch_id: str,
    sku_code: str,
    local_paths: list[str],
    tags: str | None,
) -> MaterialBatch:
    material_batch = db.scalar(select(MaterialBatch).where(MaterialBatch.batch_id == batch_id))
    if not material_batch:
        material_batch = MaterialBatch(batch_id=batch_id, sku_code=sku_code)
        db.add(material_batch)

    material_batch.sku_code = sku_code
    material_batch.image_1 = local_paths[0] if len(local_paths) > 0 else None
    material_batch.image_2 = local_paths[1] if len(local_paths) > 1 else None
    material_batch.image_3 = local_paths[2] if len(local_paths) > 2 else None
    material_batch.image_4 = local_paths[3] if len(local_paths) > 3 else None
    material_batch.cover_image = local_paths[0] if local_paths else None
    material_batch.tags = tags
    return material_batch


def _upsert_task(
    db: Session,
    task_id: str,
    batch_id: str,
    sku_code: str,
    title: str,
    content: str | None,
    topics: str | None,
    account_id: str | None,
    device_id: str | None,
    plan_publish_time: datetime | None,
    status: str,
    current_step: str,
    detail: str,
) -> tuple[PublishTask, str]:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    action = "created"

    if not task:
        task = PublishTask(task_id=task_id, platform="dewu", sku_code=sku_code, title=title)
        db.add(task)
    else:
        action = "updated"

    task.sku_code = sku_code
    task.account_id = account_id
    task.device_id = device_id
    task.material_batch_id = batch_id
    task.title = title
    task.content = content
    task.topics = topics
    task.plan_publish_time = plan_publish_time

    preserved_statuses = {
        TaskStatus.READY.value,
        TaskStatus.PUBLISHING.value,
        TaskStatus.PUBLISHED.value,
        TaskStatus.FAILED.value,
    }
    if task.status not in preserved_statuses:
        task.status = status
        task.current_step = current_step
        task.error_message = None if status != TaskStatus.FAILED.value else detail

    return task, action


def sync_feishu_records() -> FeishuSyncResponse:
    token = _get_tenant_access_token()
    records = _iter_records(token)

    result = FeishuSyncResponse(synced=0, skipped=0, failed=0, items=[])

    for record in records:
        record_id = str(record.get("record_id") or record.get("id") or "").strip()
        fields = record.get("fields") or {}
        if not record_id or not isinstance(fields, dict):
            result.failed += 1
            result.items.append(
                FeishuSyncItem(
                    record_id=record_id or "unknown",
                    sku_code="unknown",
                    status="failed",
                    detail="飞书记录缺少 record_id 或 fields。",
                )
            )
            continue

        sku_code = _normalize_text(fields.get("款号")) or "UNKNOWN"
        attachments_raw = fields.get("素材")
        attachments = attachments_raw if isinstance(attachments_raw, list) else []
        task_id = f"FS-{record_id}"
        batch_id = f"FSM-{record_id}"

        try:
            with SessionLocal() as db:
                if len(attachments) < 4:
                    raise RuntimeError("附件字段少于 4 张图，无法生成素材批次。")

                local_paths = _download_attachments(record_id, attachments, token)

                account_reference = _first_present(fields, "账号ID", "账号名称", "账号", "账号名")
                device_reference = _first_present(fields, "设备ID", "设备名称", "设备", "手机", "手机名称")
                plan_publish_time = _parse_datetime(fields.get("计划发布时间"))
                account_id, device_id, status, current_step, detail = _resolve_assignment(
                    db=db,
                    account_reference=account_reference,
                    device_reference=device_reference,
                    image_count=len(local_paths),
                )

                _upsert_material_batch(
                    db=db,
                    batch_id=batch_id,
                    sku_code=sku_code,
                    local_paths=local_paths,
                    tags=_build_tags(fields),
                )
                task, action = _upsert_task(
                    db=db,
                    task_id=task_id,
                    batch_id=batch_id,
                    sku_code=sku_code,
                    title=_build_title(fields),
                    content=_build_content(fields),
                    topics=_normalize_text(fields.get("话题")),
                    account_id=account_id,
                    device_id=device_id,
                    plan_publish_time=plan_publish_time,
                    status=status,
                    current_step=current_step,
                    detail=detail,
                )
                db.commit()

            log_step = "飞书同步创建" if action == "created" else "飞书同步更新"
            add_log(task_id, log_step, "success", f"来源记录 {record_id} 已同步到本地任务。{detail}")
            result.synced += 1
            result.items.append(
                FeishuSyncItem(
                    record_id=record_id,
                    sku_code=sku_code,
                    task_id=task_id,
                    batch_id=batch_id,
                    status=action,
                    detail=detail,
                )
            )
        except urllib.error.HTTPError as exc:
            result.failed += 1
            result.items.append(
                FeishuSyncItem(
                    record_id=record_id,
                    sku_code=sku_code,
                    task_id=task_id,
                    batch_id=batch_id,
                    status="failed",
                    detail=f"飞书文件下载失败：HTTP {exc.code}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            result.failed += 1
            result.items.append(
                FeishuSyncItem(
                    record_id=record_id,
                    sku_code=sku_code,
                    task_id=task_id,
                    batch_id=batch_id,
                    status="failed",
                    detail=str(exc),
                )
            )

    return result
