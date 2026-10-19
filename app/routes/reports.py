"""Reports: daily, weekly, monthly, department, doctor performance, revenue, pharmacy.
Each can be returned as JSON (default), CSV, Excel (.xlsx) or PDF with ?format=...

Like the other PDF endpoints, files need the JWT header, so the frontend must fetch() them and
turn the response into a blob (see docs/API_Phase_07.md).  Exporting is written to the audit log."""
from flask import Blueprint, Response, g, request

from app.middleware.auth import login_required
from app.services import pdf_service, report_service
from app.utils.permissions import has_permission
from app.utils.responses import error_response, success_response

bp = Blueprint("reports", __name__, url_prefix="/api")

FORMATS = {
    "csv": ("text/csv; charset=utf-8", "csv"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "pdf": ("application/pdf", "pdf"),
}


def _allowed(report_type):
    return has_permission(g.current_user.role.name, report_service.REPORTS[report_type][2])


@bp.get("/reports")
@login_required
def list_reports():
    """The reports THIS role may run, with the parameters each accepts."""
    items = [{"type": t, "title": title, "parameters": params, "formats": ["json", *FORMATS]}
             for t, (title, params, _perm) in report_service.REPORTS.items() if _allowed(t)]
    return success_response("Reports fetched", items)


@bp.get("/reports/<report_type>")
@login_required
def get_report(report_type):
    """Query: format=json|csv|xlsx|pdf (default json).
      daily:   date=YYYY-MM-DD            weekly: date=<any day in the week> (Monday-Sunday)
      monthly: month=YYYY-MM              others: from=YYYY-MM-DD&to=YYYY-MM-DD (default: last 30 days)
      csv only: table=<table name>  (CSV holds one table; default is the first)"""
    if report_type not in report_service.REPORTS:
        return error_response("Report not found", {"report_type": f"must be one of: {', '.join(report_service.REPORTS)}"}, 404)
    if not _allowed(report_type):
        return error_response("You do not have permission to perform this action", status=403)

    fmt = request.args.get("format", "json")
    if fmt != "json" and fmt not in FORMATS:
        return error_response("Validation failed", {"format": "format must be one of: json, csv, xlsx, pdf"}, 400)

    first, last, errors = report_service.resolve_period(report_type, request.args)
    if errors:
        return error_response("Validation failed", errors, 400)

    report = report_service.build_report(report_type, first, last)
    if fmt == "json":
        return success_response("Report generated", report)

    if fmt == "csv":
        table = request.args.get("table")
        if table and table not in report_service.table_names(report):
            return error_response("Validation failed", {"table": f"table must be one of: {', '.join(report_service.table_names(report))}"}, 400)
        body = report_service.export_csv(report, table)
    elif fmt == "xlsx":
        body = report_service.export_xlsx(report)
    else:
        body = pdf_service.report_pdf(report)

    mimetype, ext = FORMATS[fmt]
    disposition = "inline" if fmt == "pdf" else "attachment"
    return Response(body, mimetype=mimetype, headers={
        "Content-Disposition": f'{disposition}; filename="{report_type}_{first}_{last}.{ext}"'})
