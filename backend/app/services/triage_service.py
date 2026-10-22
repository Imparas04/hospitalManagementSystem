"""Two algorithms required by the project document:

1. calculate_priority()  - vital signs -> emergency priority level
2. allocate_bed_for_triage() - triage requirements -> best available bed

Both are kept in this one file, deliberately simple and rule-based, so they
are easy to explain and demo in viva.
"""
from app.extensions import db
from app.models.bed import Bed
from app.models.triage import (
    PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM, STATUS_BED_ASSIGNED,
    STATUS_WAITING, TriageRecord,
)

# --------------------------------------------------------------------------
# 1. EMERGENCY PRIORITY CALCULATION
# --------------------------------------------------------------------------
# Each abnormal vital sign adds points. More points = more urgent.
# This is a simple, explainable scoring model (not a real clinical triage
# protocol) - good enough for a demo, and easy to extend with new rules.
#
#   Vital               Normal range        Points if abnormal
#   -------------------------------------------------------------
#   Oxygen level (SpO2)  >= 95%              +4 if < 90, +2 if 90-94
#   Heart rate            60-100 bpm         +4 if <40 or >130, +2 if 40-59 or 101-130
#   Blood pressure (sys)  90-140 mmHg        +3 if <90 or >180, +1 if 141-180
#   Temperature            97-99 F           +2 if > 104, +1 if 100.4-104
#
#   Score  ->  Priority
#   >= 7   ->  critical
#   4-6    ->  high
#   2-3    ->  medium
#   0-1    ->  low


def _score_oxygen(spo2):
    if spo2 < 90:
        return 4
    if spo2 < 95:
        return 2
    return 0


def _score_heart_rate(hr):
    if hr < 40 or hr > 130:
        return 4
    if hr < 60 or hr > 100:
        return 2
    return 0


def _score_blood_pressure(systolic):
    if systolic < 90 or systolic > 180:
        return 3
    if systolic > 140:
        return 1
    return 0


def _score_temperature(temp_f):
    if temp_f > 104:
        return 2
    if temp_f >= 100.4:
        return 1
    return 0


def calculate_priority(vitals):
    """vitals: dict with blood_pressure_systolic, heart_rate, oxygen_level, temperature.
    Returns (priority_level, priority_score)."""
    score = (
        _score_oxygen(vitals["oxygen_level"])
        + _score_heart_rate(vitals["heart_rate"])
        + _score_blood_pressure(vitals["blood_pressure_systolic"])
        + _score_temperature(vitals["temperature"])
    )
    if score >= 7:
        level = PRIORITY_CRITICAL
    elif score >= 4:
        level = PRIORITY_HIGH
    elif score >= 2:
        level = PRIORITY_MEDIUM
    else:
        level = PRIORITY_LOW
    return level, score


def create_triage_record(data, recorded_by_id):
    level, score = calculate_priority(data)
    record = TriageRecord(
        patient_id=data["patient_id"],
        blood_pressure_systolic=data["blood_pressure_systolic"],
        blood_pressure_diastolic=data["blood_pressure_diastolic"],
        heart_rate=data["heart_rate"],
        oxygen_level=data["oxygen_level"],
        temperature=data["temperature"],
        symptoms=data["symptoms"].strip(),
        emergency_condition=(data.get("emergency_condition") or None),
        icu_required=bool(data.get("icu_required", False)),
        isolation_required=bool(data.get("isolation_required", False)),
        priority_level=level,
        priority_score=score,
        recorded_by_id=recorded_by_id,
    )
    db.session.add(record)
    db.session.commit()
    return record


def emergency_queue():
    """Waiting patients, most urgent first (by priority, then who arrived earlier)."""
    waiting = TriageRecord.query.filter_by(status=STATUS_WAITING).all()
    return sorted(waiting, key=lambda r: (-r.priority_score, r.recorded_at))


# --------------------------------------------------------------------------
# 2. AUTOMATIC BED ALLOCATION
# --------------------------------------------------------------------------
# Patient requirement -> search available beds -> apply rules -> select bed -> allocate
#
# Rules applied, in order:
#   1. Bed type must match requirement: icu_required -> 'icu' bed,
#      isolation_required -> 'isolation' bed, otherwise 'general' bed.
#      (icu_required wins if both flags are set - ICU care takes priority.)
#   2. Bed must be in a ward whose gender_restriction is either NULL (mixed)
#      or equal to the patient's gender.
#   3. Bed must currently be 'available'.
#   4. Among matches, the bed from the ward with the FEWEST free beds is
#      picked first - this keeps bigger wards' spare capacity free for
#      larger/urgent batches of patients instead of using them up on singles.


def _required_bed_type(triage):
    if triage.icu_required:
        return "icu"
    if triage.isolation_required:
        return "isolation"
    return "general"


def find_bed_for_triage(triage):
    """Returns the best matching available Bed, or None if nothing fits."""
    bed_type = _required_bed_type(triage)
    patient_gender = triage.patient.gender

    candidates = (
        Bed.query.join(Bed.ward)
        .filter(
            Bed.bed_type == bed_type,
            Bed.status == "available",
            db.or_(db.text("wards.gender_restriction IS NULL"), db.text("wards.gender_restriction = :g")),
        )
        .params(g=patient_gender)
        .all()
    )
    if not candidates:
        return None

    # Rule 4: prefer the ward with the fewest free beds (tightest fit first).
    def free_beds_in_ward(bed):
        return sum(1 for b in bed.ward.beds if b.status == "available")

    candidates.sort(key=free_beds_in_ward)
    return candidates[0]


def allocate_bed_for_triage(triage, doctor_id, admitted_by_id):
    """Finds a bed, admits the patient into it, links the admission back to
    the triage record, and marks the triage status 'bed_assigned'.
    Returns (admission, error_message)."""
    from app.services.admission_service import admit_patient  # local import avoids a circular import

    bed = find_bed_for_triage(triage)
    if bed is None:
        return None, f"No available '{_required_bed_type(triage)}' bed found for this patient"

    admission, err = admit_patient({
        "patient_id": triage.patient_id, "bed_id": bed.id, "doctor_id": doctor_id,
        "reason": f"Emergency admission - {triage.emergency_condition or triage.symptoms[:50]}",
    }, admitted_by_id)
    if err:
        return None, err

    triage.admission_id = admission.id
    triage.status = STATUS_BED_ASSIGNED
    db.session.commit()
    return admission, None
