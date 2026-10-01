"""Create / update users. Keeps route files short and easy to read."""
from app.extensions import db
from app.models.role import Role
from app.models.user import User


def username_or_email_taken(username=None, email=None, exclude_id=None):
    """Return {field: message} for duplicates (case-insensitive)."""
    errors = {}
    if username:
        q = User.query.filter(db.func.lower(User.username) == username.lower())
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        if q.first():
            errors["username"] = "Username already exists"
    if email:
        q = User.query.filter(db.func.lower(User.email) == email.lower())
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        if q.first():
            errors["email"] = "Email already registered"
    return errors


def create_user(data):
    role = Role.query.filter_by(name=data["role"]).first()
    user = User(
        username=data["username"].strip(),
        email=data["email"].strip().lower(),
        full_name=data["full_name"].strip(),
        phone=(data.get("phone") or None),
        role_id=role.id,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user, data):
    if "username" in data:
        user.username = data["username"].strip()
    if "email" in data:
        user.email = data["email"].strip().lower()
    if "full_name" in data:
        user.full_name = data["full_name"].strip()
    if "phone" in data:
        user.phone = data["phone"] or None
    if "role" in data:
        user.role_id = Role.query.filter_by(name=data["role"]).first().id
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    db.session.commit()
    return user
