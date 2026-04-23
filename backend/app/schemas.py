from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import DeviceStatus, TaskStatus


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MaterialBatchBase(BaseModel):
    sku_code: str
    image_1: Optional[str] = None
    image_2: Optional[str] = None
    image_3: Optional[str] = None
    image_4: Optional[str] = None
    cover_image: Optional[str] = None
    tags: Optional[str] = None


class MaterialBatchCreate(MaterialBatchBase):
    batch_id: Optional[str] = None


class MaterialBatchRead(APIModel, MaterialBatchBase):
    id: int
    batch_id: str
    created_at: datetime


class AccountDeviceBase(BaseModel):
    account_name: str
    platform: str = "dewu"
    device_name: Optional[str] = None
    adb_serial: Optional[str] = None
    appium_url: Optional[str] = None
    remark: Optional[str] = None


class AccountDeviceCreate(AccountDeviceBase):
    account_id: str
    device_id: str
    status: DeviceStatus = DeviceStatus.IDLE


class AccountDeviceUpdate(BaseModel):
    account_name: Optional[str] = None
    platform: Optional[str] = None
    device_name: Optional[str] = None
    adb_serial: Optional[str] = None
    appium_url: Optional[str] = None
    status: Optional[DeviceStatus] = None
    remark: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


class AccountDeviceRead(APIModel, AccountDeviceBase):
    id: int
    account_id: str
    device_id: str
    status: str
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PublishLogRead(APIModel):
    id: int
    task_id: str
    step_name: str
    result: str
    detail: Optional[str] = None
    screenshot: Optional[str] = None
    created_at: datetime


class TaskBase(BaseModel):
    platform: str = "dewu"
    sku_code: str
    account_id: Optional[str] = None
    device_id: Optional[str] = None
    material_batch_id: Optional[str] = None
    title: str
    content: Optional[str] = None
    topics: Optional[str] = None
    plan_publish_time: Optional[datetime] = None


class TaskCreate(TaskBase):
    task_id: Optional[str] = None
    status: TaskStatus = TaskStatus.DRAFT


class TaskUpdate(BaseModel):
    sku_code: Optional[str] = None
    account_id: Optional[str] = None
    device_id: Optional[str] = None
    material_batch_id: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    topics: Optional[str] = None
    status: Optional[TaskStatus] = None
    plan_publish_time: Optional[datetime] = None
    error_message: Optional[str] = None
    publish_url: Optional[str] = None
    result_screenshot: Optional[str] = None


class TaskBatchPublishRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list)


class TaskRead(APIModel, TaskBase):
    id: int
    task_id: str
    status: str
    current_step: Optional[str] = None
    actual_publish_time: Optional[datetime] = None
    execution_started_at: Optional[datetime] = None
    execution_finished_at: Optional[datetime] = None
    retry_count: int
    error_message: Optional[str] = None
    publish_url: Optional[str] = None
    result_screenshot: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskListRead(TaskRead):
    account_device: Optional[AccountDeviceRead] = None


class TaskDetailRead(TaskRead):
    material_batch: Optional[MaterialBatchRead] = None
    account_device: Optional[AccountDeviceRead] = None
    logs: list[PublishLogRead] = Field(default_factory=list)


class FeishuSyncItem(BaseModel):
    record_id: str
    sku_code: str
    task_id: Optional[str] = None
    batch_id: Optional[str] = None
    status: str
    detail: str


class FeishuSyncResponse(BaseModel):
    synced: int
    skipped: int
    failed: int
    items: list[FeishuSyncItem] = Field(default_factory=list)
