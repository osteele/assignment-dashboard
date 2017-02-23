import os

from flask_sqlalchemy import SQLAlchemy

from . import app

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/database.db'))
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + DB_PATH)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

db = SQLAlchemy(app)

# for re-export
session = db.session
Base = db.Model
