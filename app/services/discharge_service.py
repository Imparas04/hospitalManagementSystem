"""Discharge: free the bed, save the doctor's summary, create the final bill, and
collect everything needed for the printed discharge summary."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.billing import BillItem, DischargeSummary
from app.models.lab import LabOrder
from app.models.pharmacy import Prescription
from app.services import admission_service, billing_service


def discharge_with_summary(admission, data, user_id):
    """1) discharge the patient if still admitted (frees the bed), 2) save the summary,
    3) create the final bill for everything not billed yet. Returns the summary."""
    if admission.status == "admitted":
        admission_service.discharge_patient(admission)

    follow_up = data.get("follow_up_date")
    summary = DischargeSummary(
        admission_id=admission.id,
        diagnosis=data["diagnosis"].strip(),
        treatment_summary=data["treatment_summary"].strip(),
        doctor_instructions=(data.get("doctor_instructions") or None),
        follow_up_date=datetime.strptime(follow_up, "%Y-%m-%d").date() if follow_up else None,
        created_by_id=user_id,
    )
    db.session.add(summary)
    db.session.commit()

    # Final bill. Returns None when there is truly nothing left to bill - that is fine.
    billing_service.generate_bill(admission.patient, created_by_id=user_id)
    return summary


def build_summary_data(summary):
    """One dict used by BOTH the JSON API and the PDF, so they can never disagree."""
    admission = summary.admission
    patient, doctor = admission.patient, admission.doctor

    # "During the stay" window. A few seconds of grace at the start because MySQL
    # rounds timestamps to whole seconds.
    start = admission.admission_date - timedelta(seconds=5)
    end = admission.discharge_date or datetime.now(timezone.utc).replace(tzinfo=None)

    lab_orders = (LabOrder.query.filter(LabOrder.patient_id == patient.id, LabOrder.ordered_at >= start,
                                        LabOrder.ordered_at <= end + timedelta(seconds=5)).order_by(LabOrder.id).all())
    prescriptions = (Prescription.query.filter(Prescription.patient_id == patient.id, Prescription.created_at >= start,
                                               Prescription.created_at <= end + timedelta(seconds=5))
                     .order_by(Prescription.id).all())

    lab_reports = [{
        "test": o.lab_test.name, "code": o.lab_test.code, "status": o.status,
        "result": o.result.result_value if o.result else None,
        "is_abnormal": o.result.is_abnormal if o.result else None,
        "reviewer_notes": o.result.reviewer_notes if o.result else None,
    } for o in lab_orders]

    medicines = [{
        "medicine": i.medicine.name, "unit": i.medicine.unit, "dosage": i.dosage,
        "quantity_prescribed": i.quantity_prescribed, "quantity_issued": i.quantity_issued,
    } for p in prescriptions for i in p.items]

    # The final bill is the one that carries this admission's bed charge.
    bill_item = BillItem.query.filter_by(source_key=f"admission:{admission.id}").first()
    bill = bill_item.bill.to_dict(include_details=True) if bill_item else None

    return {
        "admission_id": admission.id,
        "patient": {
            "id": patient.id, "patient_code": patient.patient_code, "full_name": patient.full_name,
            "age": patient.age, "gender": patient.gender, "blood_group": patient.blood_group, "phone": patient.phone,
        },
        "doctor": {"id": doctor.id, "full_name": doctor.user.full_name, "specialization": doctor.specialization,
                   "department": doctor.department.name},
        "admission": {
            "ward": admission.bed.ward.name, "bed_number": admission.bed.bed_number, "reason": admission.reason,
            "admission_date": admission.admission_date.isoformat(),
            "discharge_date": admission.discharge_date.isoformat() if admission.discharge_date else None,
        },
        "diagnosis": summary.diagnosis,
        "treatment_summary": summary.treatment_summary,
        "lab_reports": lab_reports,
        "medicines": medicines,
        "doctor_instructions": summary.doctor_instructions,
        "follow_up_date": summary.follow_up_date.isoformat() if summary.follow_up_date else None,
        "final_bill": bill,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
    }
