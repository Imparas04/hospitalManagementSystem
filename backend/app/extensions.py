"""Extension objects are created here (without an app) and attached in create_app().

This avoids circular imports: any file can `from app.extensions import db`.
"""
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
