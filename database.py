import os
from app import app

from flask_sqlalchemy import SQLAlchemy

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

db = SQLAlchemy(app)

# for re-export
session = db.session
Base = db.Model
