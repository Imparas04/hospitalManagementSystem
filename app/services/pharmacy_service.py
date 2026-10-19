"""Medicine catalog, stock batches, and prescription issuing.

Python Advanced Logic: issuing a medicine automatically pulls from the
batch that expires SOONEST first (FEFO - First-Expiry-First-Out), never
touches an already-expired batch, and splits across multiple batches if
one alone doesn't have enough stock.
"""
from datetime import date

from app.extensions import db
from app.models.pharmacy import Medicine, MedicineBatch, Prescription, PrescriptionItem


def create_medicine(data):
    medicine = Medicine(name=data["name"].strip(), unit=data["unit"],
                         reorder_level=data.get("reorder_level", 10), unit_price=data.get("unit_price", 10))
    db.session.add(medicine)
    db.session.commit()
    return medicine


def stock_totals():
    """{medicine_id: units in stock that are NOT expired} in ONE grouped query.
    Used by the low-stock alerts, the dashboard and the pharmacy report."""
    from app.utils.timeutils import local_today
    rows = (db.session.query(MedicineBatch.medicine_id, db.func.sum(MedicineBatch.available_quantity))
            .filter(MedicineBatch.expiry_date >= local_today())
            .group_by(MedicineBatch.medicine_id).all())
    return {medicine_id: int(total or 0) for medicine_id, total in rows}


def low_stock_medicines():
    """[(Medicine, units_left), ...] for active medicines below their reorder level."""
    totals = stock_totals()
    return [(m, totals.get(m.id, 0)) for m in Medicine.query.filter_by(is_active=True).order_by(Medicine.name).all()
            if totals.get(m.id, 0) < m.reorder_level]


def search_medicines(query_params):
    q = Medicine.query.filter_by(is_active=True)
    search = (query_params.get("q") or "").strip()
    if search:
        q = q.filter(Medicine.name.like(f"%{search}%"))
    medicines = q.order_by(Medicine.name).all()
    if query_params.get("low_stock") == "true":
        medicines = [m for m in medicines if m.to_dict()["is_low_stock"]]
    return medicines


def add_batch(medicine, data):
    batch = MedicineBatch(
        medicine_id=medicine.id, batch_number=data["batch_number"].strip(),
        expiry_date=data["expiry_date"], purchase_quantity=data["purchase_quantity"],
        available_quantity=data["purchase_quantity"],
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def create_prescription(data, doctor_id):
    prescription = Prescription(patient_id=data["patient_id"], doctor_id=doctor_id,
                                 notes=(data.get("notes") or None))
    db.session.add(prescription)
    db.session.flush()  # get prescription.id before adding items
    for item in data["items"]:
        db.session.add(PrescriptionItem(
            prescription_id=prescription.id, medicine_id=item["medicine_id"],
            dosage=item["dosage"].strip(), quantity_prescribed=item["quantity"],
        ))
    db.session.commit()
    return prescription


def _issue_from_batches(medicine_id, quantity_needed):
    """FEFO allocation: earliest-expiring, non-expired, in-stock batches first.
    Returns the quantity actually issued (may be less than requested)."""
    batches = (
        MedicineBatch.query.filter(
            MedicineBatch.medicine_id == medicine_id,
            MedicineBatch.available_quantity > 0,
            MedicineBatch.expiry_date >= date.today(),  # never issue expired stock
        )
        .order_by(MedicineBatch.expiry_date.asc())
        .all()
    )
    remaining = quantity_needed
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch.available_quantity, remaining)
        batch.available_quantity -= take
        remaining -= take
    return quantity_needed - remaining  # how much was actually issued


def issue_prescription(prescription):
    """Issues every pending/partial item as far as stock allows. Returns a
    per-item breakdown so the pharmacist can see exactly what happened."""
    breakdown = []
    for item in prescription.items:
        still_needed = item.quantity_prescribed - item.quantity_issued
        if still_needed <= 0:
            breakdown.append({"medicine": item.medicine.name, "issued_now": 0, "shortfall": 0,
                               "reason": "already fully issued"})
            continue
        issued_now = _issue_from_batches(item.medicine_id, still_needed)
        item.quantity_issued += issued_now
        shortfall = still_needed - issued_now
        breakdown.append({
            "medicine": item.medicine.name, "issued_now": issued_now, "shortfall": shortfall,
            "reason": None if shortfall == 0 else "insufficient non-expired stock",
        })

    db.session.flush()
    all_issued = all(i.quantity_issued >= i.quantity_prescribed for i in prescription.items)
    any_issued = any(i.quantity_issued > 0 for i in prescription.items)
    prescription.status = "issued" if all_issued else ("partially_issued" if any_issued else "pending")
    db.session.commit()
    return breakdown
