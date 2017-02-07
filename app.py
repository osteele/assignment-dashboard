import os
import re
from collections import namedtuple

import arrow
import nbformat
from flask import Flask, make_response, render_template, url_for
from nbconvert import HTMLExporter
from sqlalchemy.orm import joinedload

from models import FileCommit, Repo, Session, User
from nb_combine import nb_combine, safe_read_notebook

PYNB_MIME_TYPE = 'application/x-ipynb+json'

app = Flask(__name__)

AssignmentData = namedtuple('AssignmentData', 'source_repo assignment_names assignment_paths responses')


def get_assignment_data(session=None):
    session = session or Session()
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


def get_combined_notebook(assignment_id):
    session = Session()
    data = get_assignment_data(session)
    assignment_path = data.assignment_paths[int(assignment_id)]

    files = session.query(FileCommit).filter(FileCommit.path == assignment_path).options(joinedload(FileCommit.repo)).all()
    nbs = {file.repo.owner.login: safe_read_notebook(file.file_content.content.decode(), clear_outputs=True)
           for file in files
           if file.file_content}
    owner_nb = nbs[data.source_repo.owner.login]
    student_nbs = {owner: nb for owner, nb in nbs.items() if owner != data.source_repo.owner.login and nb}
    return nb_combine(owner_nb, student_nbs)


@app.route('/')
def home_page():
    data = get_assignment_data()
    return render_template(
        'index.html',
        org_fullname=data.source_repo.owner.fullname,
        org_login=data.source_repo.owner.login,
        repo_name=data.source_repo.name,
        assignments=enumerate(data.assignment_names),
        col_keys=data.assignment_paths,
        rows=data.responses)


# under development
@app.route('/assignment/<assignment_id>')
def assignment(assignment_id):
    data = get_assignment_data()
    assignment_name = data.assignment_names[int(assignment_id)]
    assignment_path = data.assignment_paths[int(assignment_id)]
    # missing = [owner for owner, nb in nbs.items() if not nb]
    return render_template(
        'assignment.html',
        classroom_repo=data.source_repo,
        classroom_owner=data.source_repo.owner,
        assignment_name=assignment_name,
        assignment_path=assignment_path,
        collated_html_url=url_for('combined_assignment', assignment_id=assignment_id),
        collated_nb_download_url=url_for('download_combined_assignment', assignment_id=assignment_id),
    )


@app.route('/assignment/<assignment_id>/combined')
def combined_assignment(assignment_id):
    combined_nb = get_combined_notebook(assignment_id)
    return HTMLExporter().from_notebook_node(combined_nb)


@app.route('/assignment/<assignment_id>/combined.ipynb')
def download_combined_assignment(assignment_id):
    combined_nb = get_combined_notebook(assignment_id)
    response = make_response(nbformat.writes(combined_nb))
    response.headers['Content-Disposition'] = 'attachment; filename=assignment-combined.ipynb'
    response.headers['Content-Type'] = PYNB_MIME_TYPE
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = 'PORT' not in os.environ
    app.run(host='127.0.0.1' if debug else '0.0.0.0', debug=debug, port=port)
