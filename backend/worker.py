import time

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import PublishTask, TaskStatus
from app.services.publisher import run_publish_job


def main() -> None:
    while True:
        with SessionLocal() as db:
            task = db.scalar(
                select(PublishTask).where(PublishTask.status == TaskStatus.READY.value).order_by(PublishTask.created_at)
            )
            task_id = task.task_id if task else None

        if task_id:
            run_publish_job(task_id)
        else:
            time.sleep(3)


if __name__ == "__main__":
    main()
