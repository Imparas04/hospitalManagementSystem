"""Appointment booking, rescheduling, cancellation and the waiting list."""
from datetime import datetime

from app.extensions import db
from app.models.appointment import (
    STATUS_CANCELLED, STATUS_COMPLETED, STATUS_NO_SHOW, STATUS_SCHEDULED,
    STATUS_WAITLISTED, Appointment,
)
from app.models.doctor import Doctor
from app.services.doctor_service import is_slot_available


def book_appointment(data, created_by_id):
    """Books into the requested slot if free, otherwise waitlists it (unless
    the caller explicitly forbids that with allow_waitlist=False).

    Returns (appointment, was_waitlisted).
    """
    doctor = db.session.get(Doctor, data["doctor_id"])
    appt_date = datetime.strptime(data["appointment_date"], "%Y-%m-%d").date()
    appt_time = datetime.strptime(data["appointment_time"], "%H:%M").time()
    allow_waitlist = data.get("allow_waitlist", True)

    slot_free = is_slot_available(doctor.id, appt_date, appt_time)
    if not slot_free and not allow_waitlist:
        return None, None  # caller turns this into a 409

    appointment = Appointment(
        patient_id=data["patient_id"],
        doctor_id=doctor.id,
        department_id=doctor.department_id,
        appointment_date=appt_date,
        appointment_time=appt_time,
        status=STATUS_SCHEDULED if slot_free else STATUS_WAITLISTED,
        reason=data["reason"].strip(),
        notes=(data.get("notes") or None),
        created_by_id=created_by_id,
    )
    db.session.add(appointment)
    db.session.commit()
    return appointment, not slot_free


def reschedule_appointment(appointment, data):
    """Change date/time (and optionally doctor). Re-checks slot availability."""
    doctor_id = data.get("doctor_id", appointment.doctor_id)
    appt_date = datetime.strptime(data["appointment_date"], "%Y-%m-%d").date() \
        if "appointment_date" in data else appointment.appointment_date
    appt_time = datetime.strptime(data["appointment_time"], "%H:%M").time() \
        if "appointment_time" in data else appointment.appointment_time

    slot_free = is_slot_available(doctor_id, appt_date, appt_time, exclude_appointment_id=appointment.id)
    if not slot_free:
        return None

    doctor = db.session.get(Doctor, doctor_id)
    appointment.doctor_id = doctor.id
    appointment.department_id = doctor.department_id
    appointment.appointment_date = appt_date
    appointment.appointment_time = appt_time
    appointment.status = STATUS_SCHEDULED
    db.session.commit()
    return appointment


def set_status(appointment, new_status):
    appointment.status = new_status
    db.session.commit()
    return appointment


def search_appointments(query_params):
    q = Appointment.query
    for field, column in (("doctor_id", Appointment.doctor_id), ("patient_id", Appointment.patient_id),
                          ("department_id", Appointment.department_id)):
        val = query_params.get(field)
        if val:
            q = q.filter(column == int(val))
    status = query_params.get("status")
    if status:
        q = q.filter(Appointment.status == status)
    appt_date = query_params.get("date")
    if appt_date:
        q = q.filter(Appointment.appointment_date == datetime.strptime(appt_date, "%Y-%m-%d").date())
    return q.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())


def promote_from_waitlist(appointment):
    """Try to move a waitlisted appointment into its originally requested slot."""
    if is_slot_available(appointment.doctor_id, appointment.appointment_date, appointment.appointment_time,
                          exclude_appointment_id=appointment.id):
        appointment.status = STATUS_SCHEDULED
        db.session.commit()
        return True
    return False
