from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import AccountDevice
from app.schemas import AccountDeviceCreate, AccountDeviceRead, AccountDeviceUpdate

router = APIRouter(prefix="/account-devices", tags=["account-devices"])


@router.get("", response_model=list[AccountDeviceRead])
def list_account_devices(db: Session = Depends(get_db)) -> list[AccountDevice]:
    return list(db.scalars(select(AccountDevice).order_by(desc(AccountDevice.updated_at))).all())


@router.post("", response_model=AccountDeviceRead, status_code=status.HTTP_201_CREATED)
def create_account_device(payload: AccountDeviceCreate, db: Session = Depends(get_db)) -> AccountDevice:
    device = AccountDevice(
        account_id=payload.account_id,
        account_name=payload.account_name,
        platform=payload.platform,
        device_id=payload.device_id,
        device_name=payload.device_name,
        adb_serial=payload.adb_serial,
        appium_url=payload.appium_url,
        status=payload.status.value,
        remark=payload.remark,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.patch("/{device_id}", response_model=AccountDeviceRead)
def update_account_device(device_id: str, payload: AccountDeviceUpdate, db: Session = Depends(get_db)) -> AccountDevice:
    device = db.scalar(select(AccountDevice).where(AccountDevice.device_id == device_id))
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号设备不存在。")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, field, getattr(value, "value", value))

    db.commit()
    db.refresh(device)
    return device
