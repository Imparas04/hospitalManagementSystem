"""Notifications for the logged-in user (sent to them, or to their role)."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import login_required, roles_required
from app.models.notification import NOTIFICATION_TYPES, Notification
from app.models.role import ROLE_ADMIN
from app.services import notification_service
from app.utils.responses import error_response, success_response

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@login_required
def list_notifications():
    """Query: unread=true, type=<lab_result|low_stock|medicine_expiry|payment_pending|patient_discharge>,
    severity, page, per_page. Newest first. Alerts (stock/expiry/payment) are refreshed first."""
    notification_service.refresh_alerts()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    if page < 1 or per_page < 1:
        return error_response("page and per_page must be positive numbers", status=400)
    type_ = request.args.get("type")
    if type_ and type_ not in NOTIFICATION_TYPES:
        return error_response("Validation failed", {"type": f"type must be one of: {', '.join(NOTIFICATION_TYPES)}"}, 400)

    user = g.current_user
    q = notification_service.visible_to(user)
    read = notification_service.read_ids(user)
    if request.args.get("unread") == "true" and read:
        q = q.filter(~Notification.id.in_(read))
    if type_:
        q = q.filter(Notification.type == type_)
    if request.args.get("severity"):
        q = q.filter(Notification.severity == request.args["severity"])

    result = q.order_by(Notification.created_at.desc(), Notification.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return success_response("Notifications fetched", {
        "items": [n.to_dict(is_read=n.id in read) for n in result.items],
        "page": result.page, "per_page": result.per_page, "total": result.total, "pages": result.pages,
        "unread_count": notification_service.unread_count(user)})


@bp.get("/unread-count")
@login_required
def unread_count():
    """Cheap endpoint for the bell badge - safe to poll every 30-60 seconds."""
    notification_service.refresh_alerts()
    return success_response("Unread count", {"unread_count": notification_service.unread_count(g.current_user)})


def _visible_or_404(notification_id):
    note = notification_service.visible_to(g.current_user).filter(Notification.id == notification_id).first()
    if not note:
        return None, error_response("Notification not found", status=404)
    return note, None


@bp.post("/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    note, err = _visible_or_404(notification_id)
    if err:
        return err
    notification_service.mark_read(note, g.current_user)
    return success_response("Marked as read", note.to_dict(is_read=True))


@bp.post("/read-all")
@login_required
def mark_all_read():
    user = g.current_user
    read = notification_service.read_ids(user)
    count = 0
    for note in notification_service.visible_to(user).all():
        if note.id not in read:
            notification_service.mark_read(note, user)
            count += 1
    return success_response("All notifications marked as read", {"marked": count})


@bp.post("/refresh")
@roles_required(ROLE_ADMIN)
def refresh():
    """Admin: re-check stock, expiry and payment alerts right now (normally automatic)."""
    return success_response("Alerts refreshed", notification_service.refresh_alerts(force=True))
