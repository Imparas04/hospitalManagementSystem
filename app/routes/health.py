from flask import Blueprint
from sqlalchemy import text

from app.extensions import db
from app.utils.responses import error_response, success_response

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    """Public endpoint: is the API up and is the database reachable?"""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        return error_response("Database not reachable", status=503)
    return success_response("API is running", {"status": "ok"})
