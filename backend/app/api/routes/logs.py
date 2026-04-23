from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import PublishLog
from app.schemas import PublishLogRead

router = APIRouter(prefix="/publish-logs", tags=["publish-logs"])


@router.get("", response_model=list[PublishLogRead])
def list_publish_logs(task_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[PublishLog]:
    statement = select(PublishLog)
    if task_id:
        statement = statement.where(PublishLog.task_id == task_id)
    statement = statement.order_by(desc(PublishLog.created_at))
    return list(db.scalars(statement).all())
