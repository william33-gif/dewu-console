from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.schemas import FeishuSyncResponse
from app.services.feishu_sync import sync_feishu_records

router = APIRouter(prefix="/feishu", tags=["feishu"])


@router.post("/sync", response_model=FeishuSyncResponse, status_code=status.HTTP_200_OK)
def sync_feishu() -> FeishuSyncResponse:
    settings = get_settings()
    if not settings.feishu_configured:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="飞书配置未完成。")

    try:
        return sync_feishu_records()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
