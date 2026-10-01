"""Turn every error into our standard JSON format (never an HTML error page)."""
from werkzeug.exceptions import HTTPException

from app.extensions import db, jwt
from app.utils.responses import error_response


def register_error_handlers(app):
    # ---- JWT problems -> 401 ----
    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response("Authorization token is missing", {"token": reason}, 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response("Invalid token", {"token": reason}, 401)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response("Token has expired, please log in again", status=401)

    # ---- Generic errors ----
    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return error_response(err.description or err.name, status=err.code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        db.session.rollback()
        app.logger.exception("Unhandled error: %s", err)
        return error_response("Internal server error", status=500)
