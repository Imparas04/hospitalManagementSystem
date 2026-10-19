"""Role-based dashboards + Chart.js-ready analytics."""
from flask import Blueprint, g, request

from app.middleware.auth import login_required, permission_required
from app.services import stats_service
from app.utils.responses import error_response, success_response

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
@login_required
def dashboard():
    """One endpoint, a DIFFERENT dashboard per role (decided on the server from the token - the
    frontend cannot ask for another role's numbers). Response: role, date, cards[], stats{}.
    `cards` is a ready list [{key, label, value, format}] so one generic UI can render any role."""
    return success_response("Dashboard fetched", stats_service.dashboard_for(g.current_user))


def _int_arg(name, default, low, high):
    """Reads ?name=<int> and checks the range. Returns (value, error_response_or_None)."""
    raw = request.args.get(name)
    if raw is None:
        return default, None
    if not raw.lstrip("-").isdigit() or not low <= int(raw) <= high:
        return None, error_response("Validation failed", {name: f"{name} must be a whole number from {low} to {high}"}, 400)
    return int(raw), None


@bp.get("/analytics/patient-registrations")
@permission_required("analytics:registrations")
def chart_registrations():
    days, err = _int_arg("days", 30, 1, 365)
    return err or success_response("Chart data fetched", stats_service.patient_registration_trend(days))


@bp.get("/analytics/department-patients")
@permission_required("analytics:departments")
def chart_departments():
    return success_response("Chart data fetched", stats_service.department_wise_patients())


@bp.get("/analytics/bed-occupancy")
@permission_required("analytics:beds")
def chart_beds():
    return success_response("Chart data fetched", stats_service.bed_occupancy())


@bp.get("/analytics/emergency-cases")
@permission_required("analytics:emergency")
def chart_emergency():
    days, err = _int_arg("days", 30, 1, 365)
    return err or success_response("Chart data fetched", stats_service.emergency_cases(days))


@bp.get("/analytics/monthly-revenue")
@permission_required("analytics:revenue")
def chart_revenue():
    months, err = _int_arg("months", 12, 1, 24)
    return err or success_response("Chart data fetched", stats_service.monthly_revenue(months))


@bp.get("/analytics/lab-statistics")
@permission_required("analytics:lab")
def chart_lab():
    days, err = _int_arg("days", 30, 1, 365)
    return err or success_response("Chart data fetched", stats_service.lab_test_statistics(days))


@bp.get("/analytics/medicine-consumption")
@permission_required("analytics:medicine")
def chart_medicine():
    days, err = _int_arg("days", 30, 1, 365)
    if err:
        return err
    limit, err = _int_arg("limit", 10, 1, 50)
    return err or success_response("Chart data fetched", stats_service.medicine_consumption(days, limit))
