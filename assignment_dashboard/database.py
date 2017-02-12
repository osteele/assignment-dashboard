import os

from flask_sqlalchemy import SQLAlchemy

from . import app

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///../database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

db = SQLAlchemy(app)

# for re-export
session = db.session
Base = db.Model
