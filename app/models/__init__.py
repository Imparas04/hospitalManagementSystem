"""Import every model here so SQLAlchemy knows about all tables."""
from app.models.role import Role  # noqa: F401
from app.models.user import User  # noqa: F401
