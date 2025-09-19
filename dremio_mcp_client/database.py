from os import environ
from os.path import isfile

from .models import db

# Register a database by URI,
# Passed as a secret file or environment variable.


def register_database(app):
    db_uri_file = environ.get("DB_URI_FILE", "secrets/db_uri")

    db_uri = environ.get("DB_URI", "sqlite:///database.sqlite")
    if isfile(db_uri_file):
        with open(db_uri_file, "r") as f:
            db_uri = f.read().strip()

    if db_uri:
        app.config.update({"SQLALCHEMY_DATABASE_URI": db_uri})

    db.init_app(app)

    # If necessary, create missing tables from the schema.
    # Requires write permissions, and **does not migrate modified tables or data.**
    with app.app_context():
        db.create_all()
