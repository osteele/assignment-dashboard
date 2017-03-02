# flake8: noqa

import os
from assignment_dashboard.app import app
import assignment_dashboard.commands
import assignment_dashboard.views

if 'GITHUB_CLIENT_ID' in os.environ:
    import assignment_dashboard.oauth
