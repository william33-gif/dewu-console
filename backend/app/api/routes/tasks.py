from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import AccountDevice, DeviceStatus, MaterialBatch, PublishLog, PublishTask, TaskStatus
from app.schemas import TaskBatchPublishRequest, TaskCreate, TaskDetailRead, TaskListRead, TaskRead, TaskUpdate
from app.services.publisher import add_log, run_batch_publish_job, run_publish_job

router = APIRouter(prefix="/tasks", tags=["tasks"])


def build_task_detail(db: Session, task: PublishTask) -> TaskDetailRead:
    material = None
    device = None
    if task.material_batch_id:
        material = db.scalar(select(MaterialBatch).where(MaterialBatch.batch_id == task.material_batch_id))
    if task.device_id:
        device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id))
    logs = db.scalars(select(PublishLog).where(PublishLog.task_id == task.task_id).order_by(desc(PublishLog.created_at))).all()

    return TaskDetailRead.model_validate(
        {
            **TaskRead.model_validate(task).model_dump(),
            "material_batch": material,
            "account_device": device,
            "logs": logs,
        }
    )


def get_task_readiness_issue(db: Session, task: PublishTask) -> str | None:
    if not task.material_batch_id:
        return "Task has no material batch."

    material = db.scalar(select(MaterialBatch).where(MaterialBatch.batch_id == task.material_batch_id))
    if not material:
        return "Material batch does not exist."

    images = [material.image_1, material.image_2, material.image_3, material.image_4]
    if any(not image for image in images):
        return "Material batch needs 4 images."

    if not task.account_id:
        return "Task has no account."

    if not task.device_id:
        return "Task has no device."

    device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id))
    if not device:
        return "Bound device does not exist."

    if device.account_id != task.account_id:
        return "Task account and device binding do not match."

    return None


@router.get("", response_model=list[TaskListRead])
def list_tasks(db: Session = Depends(get_db)) -> list[TaskListRead]:
    tasks = db.scalars(select(PublishTask).order_by(desc(PublishTask.created_at))).all()
    items: list[TaskListRead] = []
    for task in tasks:
        device = None
        if task.device_id:
            device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id))
        items.append(
            TaskListRead.model_validate(
                {
                    **TaskRead.model_validate(task).model_dump(),
                    "account_device": device,
                }
            )
        )
    return items


@router.post("/batch/publish", status_code=status.HTTP_202_ACCEPTED)
def publish_tasks_in_batch(
    payload: TaskBatchPublishRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ordered_task_ids = list(dict.fromkeys(task_id.strip() for task_id in payload.task_ids if task_id and task_id.strip()))
    if not ordered_task_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please select at least one task.")

    tasks = db.scalars(select(PublishTask).where(PublishTask.task_id.in_(ordered_task_ids))).all()
    task_map = {task.task_id: task for task in tasks}
    missing = [task_id for task_id in ordered_task_ids if task_id not in task_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tasks not found: {', '.join(missing)}")

    queued_tasks: list[PublishTask] = []
    for task_id in ordered_task_ids:
        task = task_map[task_id]
        if task.status != TaskStatus.READY.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only ready tasks can join batch publish. Invalid task: {task.task_id}",
            )

        issue = get_task_readiness_issue(db, task)
        if issue:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{task.task_id}: {issue}")

        queued_tasks.append(task)

    total = len(queued_tasks)
    for index, task in enumerate(queued_tasks, start=1):
        task.status = TaskStatus.PUBLISHING.value
        task.current_step = f"Batch queued {index}/{total}"
        task.error_message = None
        task.result_screenshot = None

    db.commit()

    for index, task in enumerate(queued_tasks, start=1):
        add_log(task.task_id, "Batch queued", "running", f"Queued as batch item {index}/{total}.")

    background_tasks.add_task(run_batch_publish_job, ordered_task_ids)
    return {"message": f"{total} tasks entered the batch publish queue."}


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> PublishTask:
    task = PublishTask(
        task_id=payload.task_id or f"TASK-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        platform=payload.platform,
        sku_code=payload.sku_code,
        account_id=payload.account_id,
        device_id=payload.device_id,
        material_batch_id=payload.material_batch_id,
        title=payload.title,
        content=payload.content,
        topics=payload.topics,
        status=payload.status.value,
        plan_publish_time=payload.plan_publish_time,
        current_step="Draft",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    add_log(task.task_id, "Create task", "success", "Task created.")
    return task


@router.get("/{task_id}", response_model=TaskDetailRead)
def get_task(task_id: str, db: Session = Depends(get_db)) -> TaskDetailRead:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return build_task_detail(db, task)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: str, payload: TaskUpdate, db: Session = Depends(get_db)) -> PublishTask:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value.value if isinstance(value, TaskStatus) else value)

    db.commit()
    db.refresh(task)
    add_log(task.task_id, "Update task", "success", "Task updated.")
    return task


@router.post("/{task_id}/approve", response_model=TaskRead)
def approve_task(task_id: str, db: Session = Depends(get_db)) -> PublishTask:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    issue = get_task_readiness_issue(db, task)
    if issue:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=issue)

    task.status = TaskStatus.READY.value
    task.current_step = "Ready"
    db.commit()
    db.refresh(task)
    add_log(task.task_id, "Approve task", "success", "Task moved to ready.")
    return task


@router.post("/{task_id}/review-rollback", response_model=TaskRead)
def review_rollback_task(task_id: str, db: Session = Depends(get_db)) -> PublishTask:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    if task.status in {TaskStatus.DRAFT.value, TaskStatus.PENDING_REVIEW.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is already waiting for review.")

    if task.status == TaskStatus.PUBLISHING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Publishing task cannot be moved back to review.")

    device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id)) if task.device_id else None

    task.status = TaskStatus.PENDING_REVIEW.value
    task.current_step = "Pending review again"
    task.actual_publish_time = None
    task.execution_started_at = None
    task.execution_finished_at = None
    task.error_message = None
    task.publish_url = None
    task.result_screenshot = None
    if device:
        device.status = DeviceStatus.IDLE.value

    db.commit()
    db.refresh(task)
    add_log(task.task_id, "Review rollback", "success", "Task moved back to pending review.")
    return task


@router.post("/{task_id}/retry", response_model=TaskRead)
def retry_task(task_id: str, db: Session = Depends(get_db)) -> PublishTask:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    task.status = TaskStatus.READY.value
    task.current_step = "Retry ready"
    task.retry_count += 1
    task.error_message = None
    task.result_screenshot = None
    db.commit()
    db.refresh(task)
    add_log(task.task_id, "Retry task", "success", f"Retry count is now {task.retry_count}.")
    return task


@router.post("/{task_id}/rollback", response_model=TaskRead)
def rollback_task(task_id: str, db: Session = Depends(get_db)) -> PublishTask:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.status != TaskStatus.PUBLISHED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only published tasks can be rolled back.")

    device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == task.device_id)) if task.device_id else None

    task.status = TaskStatus.READY.value
    task.current_step = "Ready again"
    task.actual_publish_time = None
    task.execution_started_at = None
    task.execution_finished_at = None
    task.error_message = None
    task.publish_url = None
    task.result_screenshot = None
    if device:
        device.status = DeviceStatus.IDLE.value

    db.commit()
    db.refresh(task)
    add_log(task.task_id, "Rollback task", "success", "Published task rolled back to ready.")
    return task


@router.post("/{task_id}/publish", status_code=status.HTTP_202_ACCEPTED)
def publish_task(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, str]:
    task = db.scalar(select(PublishTask).where(PublishTask.task_id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.status not in {TaskStatus.READY.value, TaskStatus.FAILED.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current status cannot start publishing.")

    task.status = TaskStatus.PUBLISHING.value
    task.result_screenshot = None
    task.current_step = "Queued"
    db.commit()

    background_tasks.add_task(run_publish_job, task.task_id)
    add_log(task.task_id, "Start publish", "running", "Publish request entered the background queue.")
    return {"message": f"Task {task.task_id} entered the publish queue."}
