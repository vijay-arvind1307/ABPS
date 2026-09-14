from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models.models import User, Notification
from app.schemas.schemas import NotificationResponse
from app.routers.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["System Operational Notifications"])


@router.get("", response_model=List[NotificationResponse])
@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns recent notifications relevant to user's role and department."""
    query = db.query(Notification)

    if current_user.role == "department_user" and current_user.department_id:
        query = query.filter(
            or_(
                Notification.department_id == current_user.department_id,
                Notification.user_id == current_user.id,
                Notification.department_id == None
            )
        )
    elif current_user.role == "railway_planner":
        query = query.filter(
            or_(
                Notification.user_id == current_user.id,
                Notification.department_id == current_user.department_id,
                Notification.notification_type.in_(["CHANGE_REQUESTED", "EXECUTION_ALERT", "DISTURBANCE_DETECTED", "INFO"]),
                Notification.department_id == None
            )
        )

    return query.order_by(Notification.id.desc()).limit(limit).all()


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns count of unread notifications for badge display."""
    query = db.query(Notification).filter(Notification.is_read == False)
    if current_user.role == "department_user" and current_user.department_id:
        query = query.filter(
            or_(
                Notification.department_id == current_user.department_id,
                Notification.user_id == current_user.id,
                Notification.department_id == None
            )
        )
    return {"unread_count": query.count()}


@router.post("/{id}/read")
def mark_notification_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marks single notification as read."""
    notif = db.query(Notification).filter(Notification.id == id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notif.is_read = True
    db.commit()
    return {"success": True, "id": id, "is_read": True}


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marks all notifications as read."""
    query = db.query(Notification).filter(Notification.is_read == False)
    if current_user.role == "department_user" and current_user.department_id:
        query = query.filter(
            or_(
                Notification.department_id == current_user.department_id,
                Notification.user_id == current_user.id,
                Notification.department_id == None
            )
        )
    query.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"success": True, "message": "All notifications marked as read."}
