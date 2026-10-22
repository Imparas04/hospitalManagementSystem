"""Discharge management: the doctor discharges the patient with a summary; the bed is freed,
the final bill is generated, and the summary can be viewed as JSON or downloaded as PDF."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required
from app.models.bed import Admission
from app.models.billing import DischargeSummary
from app.routes.billing import pdf_response
from app.services import discharge_service, pdf_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_discharge_payload

bp = Blueprint("discharge", __name__, url_prefix="/api/discharge")


@bp.post("/<int:admission_id>")
@permission_required("discharge:create")
def discharge(admission_id):
    """Discharge a patient (if still admitted), save the summary, create the final bill.
    Also works if a nurse already discharged the patient with POST /api/admissions/<id>/discharge."""
    admission = db.session.get(Admission, admission_id)
    if not admission:
        return error_response("Admission not found", status=404)
    if DischargeSummary.query.filter_by(admission_id=admission.id).first():
        return error_response("A discharge summary already exists for this admission", status=409)

    data = request.get_json(silent=True) or {}
    errors = validate_discharge_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)

    summary = discharge_service.discharge_with_summary(admission, data, user_id=g.current_user.id)
    return success_response("Patient discharged successfully", discharge_service.build_summary_data(summary), 201)


def _summary_or_404(admission_id):
    summary = DischargeSummary.query.filter_by(admission_id=admission_id).first()
    if not summary:
        return None, error_response("Discharge summary not found", status=404)
    return summary, None


@bp.get("/<int:admission_id>")
@permission_required("discharge:read")
def get_summary(admission_id):
    summary, err = _summary_or_404(admission_id)
    if err:
        return err
    return success_response("Discharge summary fetched", discharge_service.build_summary_data(summary))


@bp.get("/<int:admission_id>/pdf")
@permission_required("discharge:read")
def summary_pdf(admission_id):
    summary, err = _summary_or_404(admission_id)
    if err:
        return err
    data = discharge_service.build_summary_data(summary)
    return pdf_response(pdf_service.discharge_pdf(data), f"discharge-{data['patient']['patient_code']}.pdf")
