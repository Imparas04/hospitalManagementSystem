"""Login logic: check credentials and build a JWT."""
from datetime import datetime, timezone

from flask_jwt_extended import create_access_token
from sqlalchemy import or_

from app.extensions import db
from app.models.user import User


def authenticate(login_id, password):
    """Return the User if credentials are correct and account is active, else None.

    `login_id` can be the username or the email.
    """
    user = User.query.filter(or_(User.username == login_id, User.email == login_id.lower())).first()
    if user is None or not user.check_password(password):
        return None
    if not user.is_active:
        return None
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    return user


def make_token(user):
    """JWT identity = user id (as string). Role is added as an extra claim for the frontend's convenience.

    NOTE: the server never trusts this claim for authorization - it re-reads the role from the DB.
    """
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role.name})
