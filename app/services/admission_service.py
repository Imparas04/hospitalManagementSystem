"""Ward/Bed setup and patient admission/discharge (manual bed selection -
the automatic *smart* bed allocation algorithm is built in Phase 4)."""
from datetime import datetime, timezone

from app.extensions import db
from app.models.bed import Admission, Bed, Ward


def create_ward(data):
    ward = Ward(name=data["name"].strip(), ward_type=data["ward_type"])
    db.session.add(ward)
    db.session.commit()
    return ward


def add_bed(ward, data):
    bed = Bed(ward_id=ward.id, bed_number=data["bed_number"].strip(), bed_type=data["bed_type"])
    db.session.add(bed)
    db.session.commit()
    return bed


def update_bed_status(bed, status):
    bed.status = status
    db.session.commit()
    return bed


def search_beds(query_params):
    q = Bed.query
    ward_id = query_params.get("ward_id")
    if ward_id:
        q = q.filter(Bed.ward_id == int(ward_id))
    status = query_params.get("status")
    if status:
        q = q.filter(Bed.status == status)
    bed_type = query_params.get("bed_type")
    if bed_type:
        q = q.filter(Bed.bed_type == bed_type)
    return q.order_by(Bed.ward_id, Bed.bed_number)


def admit_patient(data, admitted_by_id):
    """Returns (admission, error_message). error_message is set if the bed isn't available."""
    bed = db.session.get(Bed, data["bed_id"])
    if bed is None or bed.status != "available":
        return None, "Selected bed is not available"

    admission = Admission(
        patient_id=data["patient_id"],
        bed_id=bed.id,
        doctor_id=data["doctor_id"],
        reason=data["reason"].strip(),
        admitted_by_id=admitted_by_id,
    )
    bed.status = "occupied"
    db.session.add(admission)
    db.session.commit()
    return admission, None


def discharge_patient(admission):
    admission.status = "discharged"
    admission.discharge_date = datetime.now(timezone.utc)
    admission.bed.status = "available"
    db.session.commit()
    return admission


def search_admissions(query_params):
    q = Admission.query
    patient_id = query_params.get("patient_id")
    if patient_id:
        q = q.filter(Admission.patient_id == int(patient_id))
    status = query_params.get("status")
    if status:
        q = q.filter(Admission.status == status)
    ward_id = query_params.get("ward_id")
    if ward_id:
        q = q.join(Bed).filter(Bed.ward_id == int(ward_id))
    return q.order_by(Admission.id.desc())
