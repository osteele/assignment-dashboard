from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from . import app

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# for re-export
session = db.session
Base = db.Model
