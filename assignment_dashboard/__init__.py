from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

import assignment_dashboard.commands  # isort:skip
import assignment_dashboard.views  # isort:skip
