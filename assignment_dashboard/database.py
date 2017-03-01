import os

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from . import app

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/database.db'))
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + DB_PATH)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_ECHO'] = os.environ.get('SQLALCHEMY_ECHO', None)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# for re-export
session = db.session
Base = db.Model
