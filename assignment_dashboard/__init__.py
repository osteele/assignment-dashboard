# flake8: noqa

from assignment_dashboard.app import app
import assignment_dashboard.commands  # isort:skip
import assignment_dashboard.views  # isort:skip
import os

if os.environ.get('GITHUB_CLIENT_ID'):
    import assignment_dashboard.oauth
