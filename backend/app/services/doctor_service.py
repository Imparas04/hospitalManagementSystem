"""Department, Doctor and DoctorSchedule logic, plus the free-slot calculator
used by appointment booking."""
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models.appointment import STATUS_CANCELLED, STATUS_NO_SHOW, Appointment
from app.models.doctor import Department, Doctor, DoctorSchedule
from app.models.role import ROLE_DOCTOR
from app.models.user import User


def create_department(data):
    dept = Department(name=data["name"].strip(), description=(data.get("description") or None))
    db.session.add(dept)
    db.session.commit()
    return dept


def update_department(dept, data):
    if "name" in data:
        dept.name = data["name"].strip()
    if "description" in data:
        dept.description = data["description"] or None
    if "is_active" in data:
        dept.is_active = bool(data["is_active"])
    db.session.commit()
    return dept


def create_doctor(data):
    doctor = Doctor(
        user_id=data["user_id"],
        department_id=data["department_id"],
        specialization=data["specialization"].strip(),
        is_on_emergency_duty=bool(data.get("is_on_emergency_duty", False)),
        consultation_fee=data.get("consultation_fee", 500),
    )
    db.session.add(doctor)
    db.session.commit()
    return doctor


def update_doctor(doctor, data):
    if "department_id" in data:
        doctor.department_id = data["department_id"]
    if "specialization" in data:
        doctor.specialization = data["specialization"].strip()
    if "is_on_emergency_duty" in data:
        doctor.is_on_emergency_duty = bool(data["is_on_emergency_duty"])
    if "consultation_fee" in data:
        doctor.consultation_fee = data["consultation_fee"]
    if "is_active" in data:
        doctor.is_active = bool(data["is_active"])
    db.session.commit()
    return doctor


def search_doctors(query_params):
    q = Doctor.query.join(User)
    is_active = query_params.get("is_active", "true")
    if is_active in ("true", "false"):
        q = q.filter(Doctor.is_active == (is_active == "true"))
    department_id = query_params.get("department_id")
    if department_id:
        q = q.filter(Doctor.department_id == int(department_id))
    specialization = query_params.get("specialization")
    if specialization:
        q = q.filter(Doctor.specialization.like(f"%{specialization}%"))
    if query_params.get("emergency_duty") == "true":
        q = q.filter(Doctor.is_on_emergency_duty.is_(True))
    search = (query_params.get("q") or "").strip()
    if search:
        q = q.filter(User.full_name.like(f"%{search}%"))
    return q.order_by(Doctor.id)


def add_schedule(doctor, data):
    schedule = DoctorSchedule(
        doctor_id=doctor.id,
        day_of_week=data["day_of_week"],
        start_time=datetime.strptime(data["start_time"], "%H:%M").time(),
        end_time=datetime.strptime(data["end_time"], "%H:%M").time(),
        slot_minutes=data.get("slot_minutes", 15),
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


def _time_slots(start_time, end_time, slot_minutes):
    """Yield every slot start time between start_time and end_time."""
    cursor = datetime.combine(date.today(), start_time)
    end = datetime.combine(date.today(), end_time)
    step = timedelta(minutes=slot_minutes)
    while cursor + step <= end:
        yield cursor.time()
        cursor += step


def available_slots(doctor_id, target_date, exclude_appointment_id=None):
    """All free appointment slots for a doctor on a given date.

    Algorithm: weekday -> doctor's schedule rows for that weekday -> generate
    every slot_minutes-sized slot -> remove slots already booked (excluding
    cancelled/no-show appointments, which free up the slot again).

    `exclude_appointment_id` leaves one specific appointment's own row out of
    the "booked" set - used when rescheduling/promoting that same appointment,
    so it does not block itself from re-claiming its own slot.
    """
    weekday = target_date.weekday()
    schedules = DoctorSchedule.query.filter_by(doctor_id=doctor_id, day_of_week=weekday).all()
    if not schedules:
        return []

    booked_query = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == target_date,
        Appointment.status.notin_([STATUS_CANCELLED, STATUS_NO_SHOW]),
    )
    if exclude_appointment_id:
        booked_query = booked_query.filter(Appointment.id != exclude_appointment_id)
    booked = {a.appointment_time for a in booked_query.all()}

    slots = []
    for sched in schedules:
        for t in _time_slots(sched.start_time, sched.end_time, sched.slot_minutes):
            if t not in booked:
                slots.append(t.strftime("%H:%M"))
    return sorted(set(slots))


def is_slot_available(doctor_id, target_date, target_time, exclude_appointment_id=None):
    return target_time.strftime("%H:%M") in available_slots(doctor_id, target_date, exclude_appointment_id)
