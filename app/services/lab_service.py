"""Lab test catalog + order workflow: ordered -> sample_collected -> processing
-> result_entered -> reviewed."""
from app.extensions import db
from app.models.lab import LabOrder, LabResult, LabTest


def create_test_type(data):
    test = LabTest(name=data["name"].strip(), code=data["code"].strip().upper(),
                    normal_range=(data.get("normal_range") or None), price=data.get("price", 300))
    db.session.add(test)
    db.session.commit()
    return test


def create_order(data, doctor_id):
    order = LabOrder(
        patient_id=data["patient_id"], doctor_id=doctor_id, lab_test_id=data["lab_test_id"],
        notes=(data.get("notes") or None),
    )
    db.session.add(order)
    db.session.commit()
    return order


def search_orders(query_params):
    q = LabOrder.query
    for field, column in (("patient_id", LabOrder.patient_id), ("doctor_id", LabOrder.doctor_id)):
        val = query_params.get(field)
        if val:
            q = q.filter(column == int(val))
    status = query_params.get("status")
    if status:
        q = q.filter(LabOrder.status == status)
    return q.order_by(LabOrder.ordered_at.desc())


def advance_status(order, new_status):
    order.status = new_status
    db.session.commit()
    return order


def enter_result(order, data, entered_by_id):
    result = LabResult(
        lab_order_id=order.id, result_value=data["result_value"].strip(),
        is_abnormal=bool(data.get("is_abnormal", False)), entered_by_id=entered_by_id,
    )
    db.session.add(result)
    order.status = "result_entered"
    db.session.commit()
    from app.services import notification_service  # local import avoids a circular import
    notification_service.notify_lab_result(order)
    return result


def review_result(order, reviewer_notes, reviewed_by_id):
    from datetime import datetime, timezone
    order.result.reviewer_notes = (reviewer_notes or None)
    order.result.reviewed_by_id = reviewed_by_id
    order.result.reviewed_at = datetime.now(timezone.utc)
    order.status = "reviewed"
    db.session.commit()
    return order
