"""Notifications API — real notification feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.calendar import Notification
from app.models.profile import User
from app.schemas.calendar import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=str(n.id),
        kind=n.kind.value,
        title=n.title,
        body=n.body,
        icon=n.icon,
        link=n.link,
        read=n.read,
        createdAt=int(n.created_at.timestamp() * 1000) if n.created_at else 0,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    items = list(
        db.scalars(
            select(Notification)
            .where(Notification.recipient_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        ).all()
    )
    return [_out(n) for n in items]


@router.get("/unread-count")
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from sqlalchemy import func

    count = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_id == user.id, Notification.read.is_(False)
        )
    ) or 0
    return {"count": count}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    item = db.get(Notification, notification_id)
    if item is None or item.recipient_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
    item.read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from sqlalchemy import update

    db.execute(
        update(Notification)
        .where(Notification.recipient_id == user.id)
        .values(read=True)
    )
    db.commit()
    return {"ok": True}
