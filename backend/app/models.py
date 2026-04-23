from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class TaskStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class DeviceStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class PublishTask(Base):
    __tablename__ = "publish_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="dewu")
    sku_code: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    material_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.DRAFT.value, index=True)
    current_step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan_publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_screenshot: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )


class MaterialBatch(Base):
    __tablename__ = "material_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    sku_code: Mapped[str] = mapped_column(String(64), index=True)
    image_1: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_2: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_3: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_4: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())


class AccountDevice(Base):
    __tablename__ = "account_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_name: Mapped[str] = mapped_column(String(128))
    platform: Mapped[str] = mapped_column(String(32), default="dewu")
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    adb_serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    appium_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=DeviceStatus.IDLE.value, index=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )


class PublishLog(Base):
    __tablename__ = "publish_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("publish_tasks.task_id", ondelete="CASCADE"), index=True)
    step_name: Mapped[str] = mapped_column(String(128))
    result: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
