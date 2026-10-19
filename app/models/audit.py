from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AuditLog(db.Model):
    """Append-only record of who did what. There is deliberately NO update or delete
    API for this table - a log that can be edited is not an audit trail.

    username and role are COPIED into the row (not just linked) so the history stays
    correct even if the user is later renamed or given another role."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)   # NULL for a failed login
    username = db.Column(db.String(50))
    role = db.Column(db.String(30))
    action = db.Column(db.String(50), nullable=False, index=True)            # e.g. patient.create
    entity_type = db.Column(db.String(30))                                    # e.g. Patient
    entity_id = db.Column(db.Integer)
    description = db.Column(db.String(500), nullable=False)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=_now, index=True)

    __table_args__ = (db.Index("ix_audit_entity", "entity_type", "entity_id"),)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id, "username": self.username, "role": self.role,
            "action": self.action, "entity_type": self.entity_type, "entity_id": self.entity_id,
            "description": self.description, "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
