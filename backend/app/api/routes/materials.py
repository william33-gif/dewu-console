from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import MaterialBatch
from app.schemas import MaterialBatchCreate, MaterialBatchRead

router = APIRouter(prefix="/material-batches", tags=["material-batches"])


@router.get("", response_model=list[MaterialBatchRead])
def list_material_batches(db: Session = Depends(get_db)) -> list[MaterialBatch]:
    return list(db.scalars(select(MaterialBatch).order_by(desc(MaterialBatch.created_at))).all())


@router.post("", response_model=MaterialBatchRead, status_code=status.HTTP_201_CREATED)
def create_material_batch(payload: MaterialBatchCreate, db: Session = Depends(get_db)) -> MaterialBatch:
    batch = MaterialBatch(
        batch_id=payload.batch_id or f"MAT-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        sku_code=payload.sku_code,
        image_1=payload.image_1,
        image_2=payload.image_2,
        image_3=payload.image_3,
        image_4=payload.image_4,
        cover_image=payload.cover_image,
        tags=payload.tags,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/{batch_id}", response_model=MaterialBatchRead)
def get_material_batch(batch_id: str, db: Session = Depends(get_db)) -> MaterialBatch:
    batch = db.scalar(select(MaterialBatch).where(MaterialBatch.batch_id == batch_id))
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材批次不存在。")
    return batch
