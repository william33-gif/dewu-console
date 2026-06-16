import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import GuangguangPCPublishStatus, GuangguangPCPublishTask
from app.schemas import (
    GuangguangBindProductRead,
    GuangguangFillContentRead,
    GuangguangPCPublishTaskRead,
    GuangguangPreparePublishRead,
    GuangguangSyncRead,
    GuangguangUploadImagesRead,
)
from app.services import guangguang_publish_service
from app.services.guangguang_pc_publisher import (
    GuangguangBrowserAutomationError,
    publisher,
)


logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/guangguang-publish", tags=["guangguang-publish"])


def _task_or_404(db: Session, task_id: int) -> GuangguangPCPublishTask:
    task = guangguang_publish_service.get_pc_publish_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"逛逛发布任务不存在：{task_id}",
        )
    return task


def _mark_failed(
    db: Session,
    task: GuangguangPCPublishTask,
    *,
    step_name: str,
    error_message: str,
) -> None:
    guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.FAILED,
        error_message=error_message,
    )
    guangguang_publish_service.add_pc_publish_log(
        db,
        task.id,
        step_name,
        "failed",
        error_message,
    )


@router.get("/tasks", response_model=list[GuangguangPCPublishTaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list[GuangguangPCPublishTask]:
    return guangguang_publish_service.list_pc_publish_tasks(db)


@router.post("/sync-from-feishu", response_model=GuangguangSyncRead)
def sync_from_feishu(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return guangguang_publish_service.sync_pc_tasks_from_feishu(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("GUANGGUANG_FEISHU_SYNC_FAILED")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"逛逛飞书同步失败：{exc}",
        ) from exc


@router.post(
    "/prepare-publish/{task_id}",
    response_model=GuangguangPreparePublishRead,
)
async def prepare_publish(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = _task_or_404(db, task_id)
    try:
        result = await publisher.prepare_publish(task)
    except GuangguangBrowserAutomationError as exc:
        _mark_failed(
            db,
            task,
            step_name="Prepare publish",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        _mark_failed(
            db,
            task,
            step_name="Prepare publish",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    task = guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.BROWSER_READY,
        screenshot_path=str(result["screenshot_path"]),
    )
    guangguang_publish_service.add_pc_publish_log(
        db,
        task.id,
        "Prepare publish",
        "success",
        f"url={result['current_url']}",
        str(result["screenshot_path"]),
    )
    return result


@router.post(
    "/test-bind-product/{task_id}",
    response_model=GuangguangBindProductRead,
)
async def test_bind_product(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = _task_or_404(db, task_id)
    if not (task.sku_id or "").strip():
        try:
            resolved_sku_id = guangguang_publish_service.resolve_sku_id_from_feishu(db, task)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GUANGGUANG_BIND_SKU_ID_BACKFILL_FAILED task_id=%s error=%r", task.id, exc)
            resolved_sku_id = None
        if not resolved_sku_id:
            error_message = "淘宝id为空，且无法从飞书回读，请检查飞书记录的“淘宝id”字段后重新同步"
            _mark_failed(db, task, step_name="Test bind product", error_message=error_message)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.UPLOADING,
    )
    try:
        image_paths = guangguang_publish_service.prepare_local_images(task)
        guangguang_publish_service.save_local_image_paths(db, task, image_paths)
        result = await publisher.test_bind_product(task, image_paths)
    except GuangguangBrowserAutomationError as exc:
        _mark_failed(
            db,
            task,
            step_name="Test bind product",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ValueError, RuntimeError) as exc:
        _mark_failed(
            db,
            task,
            step_name="Test bind product",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("GUANGGUANG_TEST_BIND_PRODUCT_FAILED task_id=%s", task.id)
        _mark_failed(
            db,
            task,
            step_name="Test bind product",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    task = guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.PRODUCT_BOUND,
        screenshot_path=str(result["screenshot_path"]),
    )
    guangguang_publish_service.add_pc_publish_log(
        db,
        task.id,
        "Test bind product",
        "success",
        (
            f"uploaded_count={result['uploaded_count']}; "
            f"title_filled={result['title_filled']}; "
            f"content_filled={result['content_filled']}; "
            f"taobao_id={result['taobao_id']}; "
            f"product_bound={result['product_bound']}; "
            f"url={result['current_url']}"
        ),
        str(result["screenshot_path"]),
    )
    return result


@router.post(
    "/test-upload-images/{task_id}",
    response_model=GuangguangUploadImagesRead,
)
async def test_upload_images(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = _task_or_404(db, task_id)
    guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.UPLOADING,
    )
    try:
        image_paths = guangguang_publish_service.prepare_local_images(task)
        guangguang_publish_service.save_local_image_paths(db, task, image_paths)
        result = await publisher.test_upload_images(task, image_paths)
    except GuangguangBrowserAutomationError as exc:
        _mark_failed(
            db,
            task,
            step_name="Test upload images",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ValueError, RuntimeError) as exc:
        _mark_failed(
            db,
            task,
            step_name="Test upload images",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("GUANGGUANG_TEST_UPLOAD_FAILED task_id=%s", task.id)
        _mark_failed(
            db,
            task,
            step_name="Test upload images",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    task = guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.IMAGES_UPLOADED,
        screenshot_path=str(result["screenshot_path"]),
    )
    guangguang_publish_service.add_pc_publish_log(
        db,
        task.id,
        "Test upload images",
        "success",
        f"uploaded_count={result['uploaded_count']}; url={result['current_url']}",
        str(result["screenshot_path"]),
    )
    return result


@router.post(
    "/test-fill-content/{task_id}",
    response_model=GuangguangFillContentRead,
)
async def test_fill_content(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = _task_or_404(db, task_id)
    guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.UPLOADING,
    )
    try:
        image_paths = guangguang_publish_service.prepare_local_images(task)
        guangguang_publish_service.save_local_image_paths(db, task, image_paths)
        result = await publisher.test_fill_content(task, image_paths)
    except GuangguangBrowserAutomationError as exc:
        _mark_failed(
            db,
            task,
            step_name="Test fill content",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ValueError, RuntimeError) as exc:
        _mark_failed(
            db,
            task,
            step_name="Test fill content",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("GUANGGUANG_TEST_FILL_CONTENT_FAILED task_id=%s", task.id)
        _mark_failed(
            db,
            task,
            step_name="Test fill content",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    task = guangguang_publish_service.set_pc_task_state(
        db,
        task,
        GuangguangPCPublishStatus.CONTENT_FILLED,
        screenshot_path=str(result["screenshot_path"]),
    )
    guangguang_publish_service.add_pc_publish_log(
        db,
        task.id,
        "Test fill content",
        "success",
        (
            f"uploaded_count={result['uploaded_count']}; "
            f"title_filled={result['title_filled']}; "
            f"content_filled={result['content_filled']}; "
            f"url={result['current_url']}"
        ),
        str(result["screenshot_path"]),
    )
    return result
