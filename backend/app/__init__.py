"""Application factory: builds and configures the Flask app."""
import os

from flask import Flask

from app.config import Config
from app.extensions import cors, db, jwt


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False  # keep JSON keys in the order we write them

    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY is not set. Copy .env.example to .env and fill it in.")

    # Attach extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # Models must be imported so tables are known
    from app import models  # noqa: F401

    # Routes (blueprints)
    from app.routes import (admissions, appointments, audit, auth, billing, dashboard, discharge, doctors, health,
                            lab, notifications, patients, pharmacy, reports, triage, users)
    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(patients.bp)
    app.register_blueprint(doctors.bp)
    app.register_blueprint(appointments.bp)
    app.register_blueprint(admissions.bp)
    app.register_blueprint(triage.bp)
    app.register_blueprint(lab.bp)
    app.register_blueprint(pharmacy.bp)
    app.register_blueprint(billing.bp)
    app.register_blueprint(discharge.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(audit.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(reports.bp)

    from app.middleware.error_handlers import register_error_handlers
    register_error_handlers(app)

    from app.middleware.audit import register_audit
    register_audit(app)

    from app.cli import register_cli
    register_cli(app)

    return app
