import os
import re
from collections import defaultdict

import click
import pandas as pd

from . import app
from .database import db, session
from .models import Assignment, User


@app.cli.command()
def initdb():
    click.echo("Initializing the database.")
    db.drop_all()
    db.create_all()


@app.cli.command()
@click.option('--repo-limit', help="Limit the number of repos.")
@click.option('--commit-limit', help="Limit the number of commits.")
@click.option('--repo', help="The name of the repo in org/name format")
@click.option('--reprocess', is_flag=True, help="Reprocess previously-seen commits")
@click.option('--users', help="Restrict to logins in this comma-separated list")
def updatedb(**kwargs):
    click.echo("Updating the database.")
    # TODO modify update_database() to take kwargs. currently the module reads environs
    for k, v in kwargs.items():
        k = {'users': 'user_filter'}.get(k, k)
        if v is not None:
            os.environ[k.upper()] = str(v)
    # do the import after the environs have been set
    from .update_database import update_db  # noqa: F401
    update_db()


@app.cli.command()
def delete_assignments_cache():
    q = Assignment.query
    click.echo("Deleting %d assignment caches." % q.count())
    q.delete()
    session.commit()


@app.cli.command()
@click.argument('csv_filename')
def set_usernames(csv_filename):
    df = pd.DataFrame.from_csv(csv_filename, index_col=None)
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
    print(";".join("%d records %s" % (v, k) for k, v in counts.items()))
