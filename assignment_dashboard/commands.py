import os

import click

from . import app
from .database import db


@app.cli.command()
def initdb():
    click.echo('Initialize the database.')
    db.drop_all()
    db.create_all()


@app.cli.command()
@click.option('--repo-limit', help='Limit the number of repos.')
@click.option('--commit-limit', help='Limit the number of commits.')
@click.option('--repo', help='The name of the repo in org/name format')
def updatedb(**kwargs):
    click.echo('Update database.')
    for k, v in kwargs.items():
        if v is not None:
            os.environ[k.upper()] = v
    # TODO turn update_database.py into a module function, and call that instead
    import assignment_dashboard.update_database  # noqa: F401
