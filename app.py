import os
import re
from collections import namedtuple

import arrow
from flask import Flask, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from models import FileCommit, Repo, Session, User

app = Flask(__name__)

AssignmentData = namedtuple('AssignmentData', 'source_repo assignment_names assignment_paths responses')


def get_assignment_data():
    session = Session()
    source_repo = session.query(Repo).filter(Repo.source_id.is_(None)).first()
    users = session.query(User).all()

    assignment_paths = sorted(
        {file.path for file in source_repo.files if file.path.endswith('.ipynb')})
    assignment_names = [re.sub(r'day(\d+)_reading_journal\.ipynb', r'Journal #\1', path) for path in assignment_paths]

    files = session.query(FileCommit).filter(FileCommit.path.in_(assignment_paths)).options(joinedload(FileCommit.repo)).all()
    user_path_files = {(file.repo.owner_id, file.path): file for file in files}

    def file_presentation(file, path):
        if not file:
            return dict(css_class='danger', path=path, mod_time='missing')
        return dict(
            css_class='unchanged' if file.sha == user_path_files[
                source_repo.owner.id, file.path].sha else None,
            mod_time=arrow.get(file.mod_time).humanize(),
            path=path
        )

    responses = [dict(login=user.login,
                      fullname=user.fullname,
                      repo_url="https://github.com/%s/%s" % (
                          user.login, source_repo.name),
                      responses=[file_presentation(user_path_files.get((user.id, path), None), path)
                                 for path in assignment_paths]
                      )
                 for user in sorted(users, key=lambda u: (u.fullname or u.login).lower())
                 if user != source_repo.owner]

    return AssignmentData(source_repo=source_repo, assignment_names=assignment_names, assignment_paths=assignment_paths, responses=responses)


@app.route('/')
def home_page():
    data = get_assignment_data()
    return render_template('index.html',
                           org_fullname=data.source_repo.owner.fullname,
                           org_login=data.source_repo.owner.login,
                           repo_name=data.source_repo.name,
                           assignment_names=data.assignment_names,
                           col_keys=data.assignment_paths,
                           rows=data.responses)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = 'PORT' not in os.environ
    app.run(host='127.0.0.1' if debug else '0.0.0.0', debug=debug, port=port)
