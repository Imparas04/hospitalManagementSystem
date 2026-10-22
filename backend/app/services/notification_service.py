"""Notifications: lab result ready, low medicine stock, medicine expiry, payment pending, patient discharge.

Two kinds (see models/notification.py):
  EVENT notifications  - created at the moment something happens (lab result entered, patient discharged).
  ALERT notifications  - describe a CONDITION that can be true or false (stock is low, a batch is about to
                         expire, a bill is unpaid). refresh_alerts() compares the conditions with the
                         existing alerts and: creates the missing ones, updates changed text, and marks
                         alerts resolved (hidden) once the condition is gone. It can be called any number
                         of times without creating duplicates, because each alert has a unique dedupe_key.

Event notifications are best-effort: if creating one fails, the real action (which already succeeded)
is never affected.
"""
import time
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.billing import BILL_PAID, Bill
from app.models.notification import Notification, NotificationRead
from app.models.pharmacy import MedicineBatch
from app.models.role import ROLE_ADMIN, ROLE_BILLING, ROLE_PHARMACIST, ROLE_RECEPTIONIST
from app.services import pharmacy_service
from app.utils.timeutils import local_today, utc_now_naive

_last_scan = 0.0


# ----------------------------------------------------------------------------
# EVENT notifications
# ----------------------------------------------------------------------------

def _safe_add(**fields):
    try:
        db.session.add(Notification(**fields))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not create notification")


def notify_user(user_id, type_, title, message, severity="info", entity_type=None, entity_id=None):
    _safe_add(type=type_, title=title, message=message[:500], severity=severity,
              target_user_id=user_id, entity_type=entity_type, entity_id=entity_id)


def notify_roles(roles, type_, title, message, severity="info", entity_type=None, entity_id=None):
    for role in roles:
        _safe_add(type=type_, title=title, message=message[:500], severity=severity,
                  target_role=role, entity_type=entity_type, entity_id=entity_id)


def notify_lab_result(order):
    """Tell the ordering doctor that a result is ready to review."""
    abnormal = order.result is not None and order.result.is_abnormal
    notify_user(
        order.doctor.user_id, "lab_result",
        "Lab result available" + (" - ABNORMAL" if abnormal else ""),
        f"{order.lab_test.name} result for {order.patient.full_name} ({order.patient.patient_code}) is ready for review.",
        severity="warning" if abnormal else "info", entity_type="LabOrder", entity_id=order.id)


def notify_discharge(admission):
    """Tell billing (final bill) and reception (paperwork) that a patient has left."""
    notify_roles(
        [ROLE_BILLING, ROLE_RECEPTIONIST], "patient_discharge", "Patient discharged",
        f"{admission.patient.full_name} ({admission.patient.patient_code}) was discharged from "
        f"{admission.bed.ward.name}, bed {admission.bed.bed_number}. Final bill and paperwork can be completed.",
        entity_type="Admission", entity_id=admission.id)


# ----------------------------------------------------------------------------
# ALERT notifications (conditions)
# ----------------------------------------------------------------------------

def _money(value):
    return f"{float(value):.2f}"


def _low_stock_alerts():
    alerts = {}
    for medicine, left in pharmacy_service.low_stock_medicines():
        out = left == 0
        alerts[f"low_stock:{medicine.id}"] = dict(
            type="low_stock", severity="critical" if out else "warning",
            title="Out of stock" if out else "Low medicine stock",
            message=(f"{medicine.name} is OUT OF STOCK (reorder level {medicine.reorder_level})." if out else
                     f"{medicine.name}: only {left} {medicine.unit}(s) left (reorder level {medicine.reorder_level})."),
            target_role=ROLE_PHARMACIST, entity_type="Medicine", entity_id=medicine.id)
    return alerts


def _expiry_alerts():
    today = local_today()
    limit = today + timedelta(days=current_app.config["EXPIRY_ALERT_DAYS"])
    batches = (MedicineBatch.query.filter(MedicineBatch.available_quantity > 0, MedicineBatch.expiry_date <= limit)
               .order_by(MedicineBatch.expiry_date).all())
    alerts = {}
    for b in batches:
        days_left = (b.expiry_date - today).days
        if days_left < 0:
            title, severity = "Medicine EXPIRED", "critical"
            message = (f"{b.medicine.name}, batch {b.batch_number}: {b.available_quantity} unit(s) expired on "
                       f"{b.expiry_date} - remove from stock. (Expired stock is never issued.)")
        else:
            title, severity = "Medicine expiring soon", "critical" if days_left <= 7 else "warning"
            message = (f"{b.medicine.name}, batch {b.batch_number}: {b.available_quantity} unit(s) expire in "
                       f"{days_left} day(s) on {b.expiry_date}.")
        alerts[f"expiry:{b.id}"] = dict(type="medicine_expiry", severity=severity, title=title, message=message,
                                        target_role=ROLE_PHARMACIST, entity_type="MedicineBatch", entity_id=b.id)
    return alerts


def _payment_alerts():
    cutoff = utc_now_naive() - timedelta(days=current_app.config["PAYMENT_PENDING_AFTER_DAYS"])
    bills = Bill.query.filter(Bill.status != BILL_PAID, Bill.created_at <= cutoff).order_by(Bill.id).all()
    alerts = {}
    for bill in bills:
        age_days = (utc_now_naive() - bill.created_at).days
        alerts[f"payment_pending:{bill.id}"] = dict(
            type="payment_pending", severity="warning" if age_days >= 7 else "info", title="Payment pending",
            message=(f"Bill {bill.bill_number} for {bill.patient.full_name}: Rs. {bill.outstanding:.2f} outstanding "
                     f"of Rs. {_money(bill.total_amount)}."),
            target_role=ROLE_BILLING, entity_type="Bill", entity_id=bill.id)
    return alerts


def refresh_alerts(force=False):
    """Sync alert notifications with reality. Returns {'created','updated','resolved'} or None if skipped
    (alerts are re-checked at most once per NOTIFICATION_SCAN_INTERVAL_SECONDS unless force=True)."""
    global _last_scan
    interval = current_app.config["NOTIFICATION_SCAN_INTERVAL_SECONDS"]
    now = time.monotonic()
    if not force and interval > 0 and now - _last_scan < interval:
        return None
    _last_scan = now

    desired = {}
    desired.update(_low_stock_alerts())
    desired.update(_expiry_alerts())
    desired.update(_payment_alerts())

    existing = {n.dedupe_key: n for n in Notification.query.filter(Notification.dedupe_key.isnot(None)).all()}
    created = updated = resolved = 0
    stamp = utc_now_naive()

    for key, fields in desired.items():
        note = existing.get(key)
        if note is None:
            db.session.add(Notification(dedupe_key=key, **fields))
            created += 1
        elif note.resolved_at is not None:
            # The condition came back (e.g. restocked, then low again): notify everyone again.
            NotificationRead.query.filter_by(notification_id=note.id).delete()
            for name, value in fields.items():
                setattr(note, name, value)
            note.resolved_at, note.created_at = None, stamp
            created += 1
        elif note.message != fields["message"] or note.severity != fields["severity"] or note.title != fields["title"]:
            note.message, note.severity, note.title = fields["message"], fields["severity"], fields["title"]
            updated += 1

    for key, note in existing.items():
        if key not in desired and note.resolved_at is None:
            note.resolved_at = stamp
            resolved += 1

    try:
        db.session.commit()
    except IntegrityError:
        # Two requests ran the scan at the same moment; the other one created the row first. Harmless.
        db.session.rollback()
        return {"created": 0, "updated": 0, "resolved": 0}
    return {"created": created, "updated": updated, "resolved": resolved}


# ----------------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------------

def visible_to(user):
    """Notifications this user may see: sent to them personally, or to their role. Admin sees all."""
    q = Notification.query.filter(Notification.resolved_at.is_(None))
    if user.role.name != ROLE_ADMIN:
        q = q.filter(db.or_(
            Notification.target_user_id == user.id,
            db.and_(Notification.target_user_id.is_(None), Notification.target_role == user.role.name)))
    return q


def read_ids(user):
    return {r[0] for r in db.session.query(NotificationRead.notification_id).filter_by(user_id=user.id).all()}


def unread_count(user):
    q = visible_to(user)
    ids = read_ids(user)
    if ids:
        q = q.filter(~Notification.id.in_(ids))
    return q.count()


def mark_read(note, user):
    if not NotificationRead.query.filter_by(notification_id=note.id, user_id=user.id).first():
        db.session.add(NotificationRead(notification_id=note.id, user_id=user.id))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # already marked by a double click
