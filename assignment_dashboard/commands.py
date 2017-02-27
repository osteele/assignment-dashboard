import os
import re
import sys
from collections import defaultdict

import click
import pandas as pd

from . import app
from .database import db, session
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

@app.cli.command()
@click.argument('repo_name')
def add_repo(repo_name):
    """Add a repository to the database."""
    assert_github_token()
    from .update_database import add_repo  # noqa: F401
    add_repo(repo_name)


@app.cli.command()
@click.option('--repo-limit', help="Limit the number of repos.")
@click.option('--commit-limit', help="Limit the number of commits.")
@click.option('--reprocess', is_flag=True, help="Reprocess previously-seen commits")
@click.option('--users', help="Restrict to logins in this comma-separated list")
def updatedb(**kwargs):
    """Update the database from GitHub."""
    assert_github_token()
    repos = session.query(Repo).filter(Repo.source_id.is_(None)).all()
    if not repos:
        print("Error: REPO_NAME not specified")
        print("Run add_repo to add an assignment repository.")
        sys.exit(1)

    # TODO modify update_database() to take kwargs. currently the module reads environs
    for k, v in kwargs.items():
        k = {'users': 'user_filter'}.get(k, k)
        if v is not None:
            os.environ[k.upper()] = str(v)
    # do the import after the environs have been set
    from .update_database import update_db  # noqa: F401
    for repo in repos:
        print("Updating %s" % repo.full_name)
        update_db(repo.full_name)


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
    df = pd.DataFrame.from_csv(click.format_filename(csv_filename), index_col=None)
    name_col = next(col for col in df.columns if re.match(r'(user ?)?names?', col, re.I))
    github_col = next(col for col in df.columns if re.search(r'git', col, re.I))
    logins = set(df[github_col])
    users = {u.login: u for u in session.query(User).filter(User.login.in_(logins))}

    unknown = logins - set(users.keys())
    if unknown:
        print('not in the database:', unknown)

    counts = defaultdict(lambda: 0)
    for _, row in df.iterrows():
        login, name = row[github_col], row[name_col]
        if login not in users:
            counts['not in the database'] += 1
        elif users[login].fullname == name:
            counts['unchanged'] += 1
        else:
            users[login].fullname = name
            counts['updated'] += 1
    session.commit()
    print("; ".join("%d records %s" % (v, k) for k, v in counts.items()))


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
