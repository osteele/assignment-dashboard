import os
import sys

import click

from alembic import command
from alembic.config import Config

from . import app, update_database
from .database import db, session
from .model_helpers import update_names_from_csv
from .models import Assignment, Repo, User


def assert_github_token():
    token_name = 'GITHUB_API_TOKEN'
    if token_name not in os.environ:
        print("Error: %s isn't set." % token_name, file=sys.stderr)
        print("Visit https://github.com/settings/tokens/new to create a GitHub personal access token", file=sys.stderr)
        print("and set the %s environment variable to it." % token_name, file=sys.stderr)
        sys.exit(1)


@app.cli.command()
def initdb():
    """Initialize the database."""
    db.drop_all()
    db.create_all()
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "../migrations/alembic.ini"))
    command.stamp(alembic_cfg, "head")


@app.cli.command()
@click.argument('repo_name')
def add_repo(repo_name):
    """Add a repository to the database."""
    assert_github_token()
    update_database.epo(repo_name)


@app.cli.command()
@click.option('--repo-limit', type=click.INT, help="Limit the number of repos.")
@click.option('--commit-limit', type=click.INT, help="Limit the number of commits.")
@click.option('--reprocess', is_flag=True, help="Reprocess previously-seen commits")
@click.option('--oldest-first', is_flag=True, help="Oldest repos first")
@click.option('--users', help="Restrict to logins in this comma-separated list")
@click.option('--update-users/--skip-update-users', default=True, help="Update user list")
def updatedb(**options):
    """Update the database from GitHub."""
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "../migrations/alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    assert_github_token()
    repos = session.query(Repo).filter(Repo.source_id.is_(None)).all()
    if not repos:
        print("Error: REPO_NAME not specified")
        print("Run add_repo to add an assignment repository.")
        sys.exit(1)

    # do the import after the environs have been set
    if options['users']:
        options['users'] = list(filter(None, options['users'].split(',')))
    for repo in repos:
        print("Updating %s" % repo.full_name)
        update_database.update_db(repo.full_name, options)


@app.cli.command()
def delete_assignments_cache():
    """Delete the assignments cache."""
    q = Assignment.query
    click.echo("Deleting %d assignment caches." % q.count())
    q.delete()
    session.commit()


@app.cli.command()
@click.argument('csv_filename', type=click.Path(exists=True))
def set_usernames(csv_filename):
    """Set usernames to values from a CSV file."""
    print(update_names_from_csv(click.format_filename(csv_filename)))


@app.cli.command()
@click.option('--clear', is_flag=True, help="Unset user names")
def set_fake_usernames(clear):
    """Set usernames to values from a fake."""
    try:
        from faker import Faker
    except ModuleNotFoundError as e:
        print("%s: pip install Faker" % e, file=sys.stderr)
        sys.exit(1)
    fake = Faker()
    for user in session.query(User).filter(User.role == 'student').all():
        user.fullname = fake.name()
    session.commit()
