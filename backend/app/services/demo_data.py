"""Starter data so a brand-new database is usable straight away.

Everything here is SAFE TO RUN MANY TIMES: a record that already exists (same name / code) is skipped.
  seed_master_data()  -> departments, wards + beds, lab tests, medicines with stock   (no passwords involved)
  seed_demo_doctors() -> a few doctor accounts + doctor profiles + weekly schedules   (needs a password)
"""
from datetime import date, timedelta

from app.extensions import db
from app.models.bed import Bed, Ward
from app.models.doctor import Department, Doctor
from app.models.lab import LabTest
from app.models.pharmacy import Medicine, MedicineBatch
from app.models.role import ROLE_DOCTOR
from app.models.user import User
from app.services import doctor_service, user_service

DEPARTMENTS = [
    ("General Medicine", "Everyday illnesses, fever, infections, check-ups"),
    ("Cardiology", "Heart and blood-pressure problems"),
    ("Orthopedics", "Bones, joints and fractures"),
    ("Pediatrics", "Children's health"),
    ("Gynecology", "Women's health and maternity care"),
    ("Neurology", "Brain and nervous system"),
    ("Emergency Medicine", "Accident and emergency cases"),
    ("ENT", "Ear, nose and throat"),
]

# name, ward_type, gender_restriction, daily_charge, bed_type, bed prefix, number of beds
WARDS = [
    ("General Ward (Male)", "general", "male", 800, "general", "GM", 6),
    ("General Ward (Female)", "general", "female", 800, "general", "GF", 6),
    ("ICU", "icu", None, 5000, "icu", "ICU", 4),
    ("Isolation Ward", "isolation", None, 3000, "isolation", "ISO", 3),
    ("Maternity Ward", "maternity", "female", 2000, "general", "MAT", 4),
    ("Pediatric Ward", "pediatric", None, 1500, "general", "PED", 4),
]

# code, name, normal range, price
LAB_TESTS = [
    ("CBC", "Complete Blood Count", "WBC 4,000-11,000 per uL", 300),
    ("BSF", "Blood Sugar (Fasting)", "70-100 mg/dL", 100),
    ("HBA1C", "HbA1c", "Below 5.7 %", 550),
    ("LIPID", "Lipid Profile", "Total cholesterol below 200 mg/dL", 600),
    ("LFT", "Liver Function Test", "ALT 7-56 U/L", 700),
    ("KFT", "Kidney Function Test", "Creatinine 0.6-1.3 mg/dL", 650),
    ("TSH", "Thyroid (TSH)", "0.4-4.0 mIU/L", 500),
    ("CRP", "C-Reactive Protein", "Below 10 mg/L", 450),
    ("URINE", "Urine Routine", "No sugar, no protein", 150),
]

# name, unit, price per unit, reorder level, opening stock
MEDICINES = [
    ("Paracetamol 500mg", "tablet", 2, 100, 500),
    ("Amoxicillin 500mg", "tablet", 8, 80, 300),
    ("Cetirizine 10mg", "tablet", 3, 60, 250),
    ("Pantoprazole 40mg", "tablet", 6, 60, 250),
    ("Metformin 500mg", "tablet", 4, 80, 300),
    ("Amlodipine 5mg", "tablet", 5, 60, 250),
    ("Cough Syrup 100ml", "syrup", 85, 20, 60),
    ("Ceftriaxone 1g", "injection", 120, 20, 80),
    ("Diclofenac Gel 30g", "ointment", 95, 15, 40),
    ("Eye Drops 10ml", "drops", 70, 15, 40),
]

# username, full name, department, specialization, fee
DOCTORS = [
    ("dr_sharma", "Dr. Anil Sharma", "General Medicine", "General Physician", 400),
    ("dr_mehta", "Dr. Kavita Mehta", "Cardiology", "Cardiologist", 800),
    ("dr_patil", "Dr. Rahul Patil", "Orthopedics", "Orthopedic Surgeon", 700),
    ("dr_iyer", "Dr. Sunita Iyer", "Pediatrics", "Pediatrician", 500),
    ("dr_khan", "Dr. Imran Khan", "Emergency Medicine", "Emergency Physician", 600),
]


def seed_master_data():
    """Returns a dict with how many NEW records were added of each kind."""
    added = {"departments": 0, "wards": 0, "beds": 0, "lab_tests": 0, "medicines": 0, "batches": 0}

    for name, description in DEPARTMENTS:
        if not Department.query.filter_by(name=name).first():
            doctor_service.create_department({"name": name, "description": description})
            added["departments"] += 1

    for name, ward_type, gender, charge, bed_type, prefix, count in WARDS:
        ward = Ward.query.filter_by(name=name).first()
        if ward is None:
            ward = Ward(name=name, ward_type=ward_type, gender_restriction=gender, daily_charge=charge)
            db.session.add(ward)
            db.session.commit()
            added["wards"] += 1
        existing = {b.bed_number for b in ward.beds}
        for i in range(1, count + 1):
            number = f"{prefix}-{i:02d}"
            if number not in existing:
                db.session.add(Bed(ward_id=ward.id, bed_number=number, bed_type=bed_type))
                added["beds"] += 1
        db.session.commit()

    for code, name, normal_range, price in LAB_TESTS:
        if not LabTest.query.filter_by(code=code).first():
            db.session.add(LabTest(name=name, code=code, normal_range=normal_range, price=price))
            added["lab_tests"] += 1
    db.session.commit()

    expiry = date.today() + timedelta(days=540)   # about 18 months from today
    for name, unit, price, reorder, stock in MEDICINES:
        if Medicine.query.filter_by(name=name).first():
            continue
        medicine = Medicine(name=name, unit=unit, unit_price=price, reorder_level=reorder)
        db.session.add(medicine)
        db.session.commit()
        db.session.add(MedicineBatch(medicine_id=medicine.id, batch_number=f"B-{medicine.id:03d}-A",
                                     expiry_date=expiry, purchase_quantity=stock, available_quantity=stock))
        db.session.commit()
        added["medicines"] += 1
        added["batches"] += 1
    return added


def seed_demo_doctors(password):
    """Create doctor accounts + profiles + a Monday-Saturday timetable. Also gives the 'demo_doctor'
    account (from seed-demo-users) a profile if it has none. Returns how many doctor profiles were added."""
    seed_master_data()
    created = 0
    people = [(u, n, d, s, f) for u, n, d, s, f in DOCTORS]
    for username, full_name, dept_name, specialization, fee in people:
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = user_service.create_user({
                "username": username, "email": f"{username}@hospital.local", "password": password,
                "full_name": full_name, "role": ROLE_DOCTOR})
        created += _ensure_profile(user, dept_name, specialization, fee)

    demo = User.query.filter_by(username="demo_doctor").first()
    if demo is not None:
        created += _ensure_profile(demo, "General Medicine", "General Physician", 400)
    return created


def _ensure_profile(user, dept_name, specialization, fee):
    if Doctor.query.filter_by(user_id=user.id).first():
        return 0
    dept = Department.query.filter_by(name=dept_name).first()
    doctor = doctor_service.create_doctor({
        "user_id": user.id, "department_id": dept.id, "specialization": specialization,
        "consultation_fee": fee, "is_on_emergency_duty": dept_name == "Emergency Medicine"})
    for day in range(0, 6):   # Monday .. Saturday
        doctor_service.add_schedule(doctor, {"day_of_week": day, "start_time": "09:00",
                                             "end_time": "13:00", "slot_minutes": 15})
        doctor_service.add_schedule(doctor, {"day_of_week": day, "start_time": "16:00",
                                             "end_time": "19:00", "slot_minutes": 15})
    return 1
