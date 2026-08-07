"""Calendar API — real CRUD for calendar events."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.core.db import get_db
from app.models.calendar import CalendarEvent
from app.models.profile import User
from app.schemas.calendar import CalendarEventIn, CalendarEventOut, CalendarEventUpdate

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _out(ev: CalendarEvent) -> CalendarEventOut:
    return CalendarEventOut(
        id=str(ev.id),
        title=ev.title,
        description=ev.description,
        date=ev.date,
        time=ev.time,
        color=ev.color,
        type=ev.type.value,
        courseId=str(ev.course_id) if ev.course_id else None,
        reminderMinutesBefore=ev.reminder_minutes_before,
        completed=ev.completed,
        completedAt=int(ev.completed_at.timestamp() * 1000) if ev.completed_at else None,
        createdAt=int(ev.created_at.timestamp() * 1000) if ev.created_at else 0,
        updatedAt=int(ev.updated_at.timestamp() * 1000) if ev.updated_at else 0,
    )


@router.get("", response_model=list[CalendarEventOut])
def list_events(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarEventOut]:
    events = list(
        db.scalars(
            select(CalendarEvent)
            .where(CalendarEvent.owner_id == user.id)
            .order_by(CalendarEvent.date, CalendarEvent.time)
        ).all()
    )
    return [_out(e) for e in events]


@router.post("", response_model=CalendarEventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: CalendarEventIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventOut:
    event = CalendarEvent(
        owner_id=user.id,
        title=payload.title,
        description=payload.description,
        date=payload.date,
        time=payload.time,
        color=payload.color,
        type=payload.type,
        course_id=payload.courseId,
        reminder_minutes_before=payload.reminderMinutesBefore,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _out(event)


@router.patch("/{event_id}", response_model=CalendarEventOut)
def update_event(
    event_id: str,
    payload: CalendarEventUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventOut:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    require_owner(str(event.owner_id), str(user.id))

    data = payload.model_dump(exclude_unset=True)
    mapping = {
        "title": "title",
        "description": "description",
        "date": "date",
        "time": "time",
        "color": "color",
        "type": "type",
        "courseId": "course_id",
        "reminderMinutesBefore": "reminder_minutes_before",
        "completed": "completed",
    }
    for camel, snake in mapping.items():
        if camel in data:
            setattr(event, snake, data[camel])
    if "completed" in data:
        event.completed_at = datetime.utcnow() if data["completed"] else None
    db.commit()
    db.refresh(event)
    return _out(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    require_owner(str(event.owner_id), str(user.id))
    db.delete(event)
    db.commit()
