import os

from flask import Flask

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change me in production')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if 'GITHUB_CLIENT_ID' in os.environ:
    app.config['REQUIRE_LOGIN'] = True
    app.config['GITHUB_CLIENT_ID'] = os.environ['GITHUB_CLIENT_ID']
    app.config['GITHUB_CLIENT_SECRET'] = os.environ['GITHUB_CLIENT_SECRET']
else:
    app.config['REQUIRE_LOGIN'] = False
