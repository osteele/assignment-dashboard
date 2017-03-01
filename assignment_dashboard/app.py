import os

from flask import Flask

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change me in production')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if os.environ.get('GITHUB_CLIENT_ID'):
    app.config['GITHUB_CLIENT_ID'] = os.environ['GITHUB_CLIENT_ID']
    app.config['GITHUB_CLIENT_SECRET'] = os.environ['GITHUB_CLIENT_SECRET']
