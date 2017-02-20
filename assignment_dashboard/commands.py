import os

import click

from . import app
from .database import db, session
from .models import Assignment


@app.cli.command()
def initdb():
    # click.echo("Initializing the database.")
    db.drop_all()
    db.create_all()


@app.cli.command()
@click.option('--repo-limit', help="Limit the number of repos.")
@click.option('--commit-limit', help="Limit the number of commits.")
@click.option('--repo', help="The name of the repo in org/name format")
@click.option('--reprocess-commits', is_flag=True, help="Reprocess previously-seen commits")
def updatedb(**kwargs):
    click.echo("Updating the database.")
    for k, v in kwargs.items():
        if v is not None:
            os.environ[k.upper()] = str(v)
    # TODO turn update_database.py into a module function, and call that instead
    import assignment_dashboard.update_database  # noqa: F401


@app.cli.command()
def delete_assignments_cache():
    q = Assignment.query
    click.echo("Deleting %d assignment caches." % q.count())
    q.delete()
    session.commit()
