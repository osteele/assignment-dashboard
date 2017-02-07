"""
Implements the View-Model of an MVVM architecture.
"""

import re
from collections import namedtuple

import arrow
from sqlalchemy.orm import joinedload

from models import FileCommit, Repo, Session
from nb_combine import nb_combine, safe_read_notebook

RepoForksModel = namedtuple('RepoForksModel', 'source_repo assignment_names assignment_paths responses')
AssignmentModel = namedtuple('AssignmentModel', 'assignment_path collated_nb')


def get_repo_forks_model(session=None):
    session = session or Session()
    source_repo = session.query(Repo).filter(Repo.source_id.is_(None)).first()

    # source_repo.fork(lazy='joined') doesn't work :-()
    repos = session.query(Repo).options(joinedload(Repo.owner)).filter(Repo.source_id.is_(source_repo.id)).all()

    assignment_paths = sorted({file.path for file in source_repo.files if file.path.endswith('.ipynb')})
    assignment_names = [re.sub(r'day(\d+)_reading_journal\.ipynb', r'Journal #\1', path) for path in assignment_paths]

    # instead of repo.files, to avoid 1 + N
    files = session.query(FileCommit).filter(FileCommit.path.in_(assignment_paths)).all()
    user_path_files = {(file.repo.owner_id, file.path): file for file in files}

    def file_presentation(file, path):
        if not file:
            return dict(css_class='danger', path=path, mod_time='missing')
        return dict(
            css_class='unchanged' if file.sha == user_path_files[source_repo.owner.id, file.path].sha else None,
            mod_time=arrow.get(file.mod_time).humanize(),
            path=path
        )

    responses = [dict(user=repo.owner,
                      repo=repo,
                      responses=[file_presentation(user_path_files.get((repo.owner.id, path), None), path)
                                 for path in assignment_paths]
                      )
                 for repo in repos]

    return RepoForksModel(
        source_repo=source_repo,
        assignment_names=assignment_names,
        assignment_paths=assignment_paths,
        responses=responses)


def get_combined_notebook(assignment_id):
    session = Session()
    data = get_repo_forks_model(session)
    assignment_path = data.assignment_paths[assignment_id]

    files = session.query(FileCommit).filter(FileCommit.path == assignment_path).options(joinedload(FileCommit.repo)).all()
    nbs = {file.repo.owner.login: safe_read_notebook(file.file_content.content.decode(), clear_outputs=True)
           for file in files
           if file.file_content}
    owner_nb = nbs[data.source_repo.owner.login]
    student_nbs = {owner: nb for owner, nb in nbs.items() if owner != data.source_repo.owner.login and nb}
    return AssignmentModel(assignment_path, nb_combine(owner_nb, student_nbs))