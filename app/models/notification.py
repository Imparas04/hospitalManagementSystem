from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


NOTIFICATION_TYPES = ("lab_result", "low_stock", "medicine_expiry", "payment_pending", "patient_discharge")
SEVERITIES = ("info", "warning", "critical")


class Notification(db.Model):
    """One message for a person (target_user_id) or for everyone with a role (target_role).
    Who has READ it is stored per user in NotificationRead, so two pharmacists do not share one 'read' flag.

    Two kinds:
      * event notifications (lab result ready, patient discharged): created at the moment it happens
      * alert notifications (low stock, expiry, payment pending): describe a CONDITION. They carry a
        unique dedupe_key like 'low_stock:7' so the same alert is never created twice, and are marked
        resolved (hidden) automatically when the condition goes away."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    severity = db.Column(db.String(10), nullable=False, default="info")
    target_role = db.Column(db.String(30), index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    entity_type = db.Column(db.String(30))
    entity_id = db.Column(db.Integer)
    dedupe_key = db.Column(db.String(60), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now, index=True)
    resolved_at = db.Column(db.DateTime)

    def to_dict(self, is_read=False):
        return {
            "id": self.id, "type": self.type, "title": self.title, "message": self.message,
            "severity": self.severity, "entity_type": self.entity_type, "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_read": is_read,
        }


class NotificationRead(db.Model):
    __tablename__ = "notification_reads"

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey("notifications.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    read_at = db.Column(db.DateTime, nullable=False, default=_now)

    __table_args__ = (db.UniqueConstraint("notification_id", "user_id", name="uq_notification_reader"),)
