"""Command-line helpers:
  flask init-db | seed-roles | create-admin | seed-demo-users | seed-demo-data | seed-demo-doctors"""
import os

import click
from flask import current_app

from app.extensions import db
from app.models.role import ALL_ROLES, ROLE_ADMIN, ROLE_DESCRIPTIONS, Role
from app.models.user import User
from app.services import user_service
from app.utils.validators import validate_password


def seed_roles():
    """Insert the 7 roles if they are missing. Safe to run many times."""
    added = 0
    for name in ALL_ROLES:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=ROLE_DESCRIPTIONS[name]))
            added += 1
    db.session.commit()
    return added


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables from the models (alternative to running database/schema.sql)."""
        db.create_all()
        click.echo("Tables created.")

    @app.cli.command("seed-roles")
    def seed_roles_cmd():
        """Insert the 7 roles."""
        click.echo(f"Roles added: {seed_roles()}")

    @app.cli.command("create-admin")
    def create_admin():
        """Create the first admin using ADMIN_* values from .env (password is never hardcoded)."""
        seed_roles()
        username = os.getenv("ADMIN_USERNAME")
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")
        full_name = os.getenv("ADMIN_FULL_NAME", "System Administrator")
        if not (username and email and password):
            raise click.ClickException("Set ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD in .env")
        pw_error = validate_password(password)
        if pw_error:
            raise click.ClickException(pw_error)
        if user_service.username_or_email_taken(username, email):
            raise click.ClickException("An admin/user with this username or email already exists")
        user_service.create_user({"username": username, "email": email, "password": password,
                                  "full_name": full_name, "role": ROLE_ADMIN})
        click.echo(f"Admin '{username}' created.")

    @app.cli.command("seed-demo-users")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
                  help="Password given to ALL demo users (for local testing only).")
    def seed_demo_users(password):
        """Create one demo user per role (demo_doctor, demo_nurse, ...) for testing/demo."""
        seed_roles()
        pw_error = validate_password(password)
        if pw_error:
            raise click.ClickException(pw_error)
        created = 0
        for role in ALL_ROLES:
            if role == ROLE_ADMIN:
                continue
            username = f"demo_{role}"
            if User.query.filter_by(username=username).first():
                continue
            user_service.create_user({
                "username": username, "email": f"{username}@hospital.local", "password": password,
                "full_name": f"Demo {role.replace('_', ' ').title()}", "role": role})
            created += 1
        click.echo(f"Demo users created: {created}")

    @app.cli.command("seed-demo-data")
    def seed_demo_data_cmd():
        """Add starter departments, wards + beds, lab tests and medicines (safe to run again)."""
        from app.services import demo_data
        added = demo_data.seed_master_data()
        click.echo("Added: " + ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in added.items()))

    @app.cli.command("seed-demo-doctors")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
                  help="Password given to the demo doctor accounts (for local testing only).")
    def seed_demo_doctors_cmd(password):
        """Create demo doctors (dr_sharma, dr_mehta, ...) with profiles and weekly timetables."""
        from app.services import demo_data
        pw_error = validate_password(password)
        if pw_error:
            raise click.ClickException(pw_error)
        seed_roles()
        click.echo(f"Doctor profiles added: {demo_data.seed_demo_doctors(password)}")
