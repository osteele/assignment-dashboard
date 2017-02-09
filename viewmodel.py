""""
"Implements the View-Model of an MVVM architecture.
"""

import hashlib
import pickle
import re
from collections import namedtuple

import arrow
import nbformat
from sqlalchemy.orm import joinedload, undefer

from globals import PYNB_MIME_TYPE
from models import Assignment, AssignmentQuestion, AssignmentQuestionResponse, FileCommit, FileContent, Repo, Session
from nb_combine import NotebookExtractor, safe_read_notebook

RepoForksModel = namedtuple('RepoForksModel', 'source_repo assignment_names assignment_paths responses')
AssignmentModel = namedtuple('AssignmentModel', 'assignment_path collated_nb answer_status')

session = Session()


def update_content_types(file_contents):
    for fc in file_contents:
        if fc.content_type is None:
            try:
                nbformat.reads(fc.content, as_version=4)  # for effect
                fc.content_type = PYNB_MIME_TYPE
            except nbformat.reader.NotJSONError:
                fc.content_type = ''


def get_repo_forks_model():
    source_repo = session.query(Repo).filter(Repo.source_id.is_(None)).first()
    assert source_repo

    # source_repo.fork(lazy='joined') doesn't work :-()
    repos = session.query(Repo).options(joinedload(Repo.owner)).filter(Repo.source_id.is_(source_repo.id)).all()

    assignment_paths = sorted({file.path for file in source_repo.files if file.path.endswith('.ipynb')})
    assignment_names = [re.sub(r'day(\d+)_reading_journal\.ipynb', r'Journal #\1', path) for path in assignment_paths]

    # instead of repo.files, to avoid 1 + N
    file_commits = session.query(FileCommit).filter(FileCommit.path.in_(assignment_paths)).all()
    user_path_files = {(fc.repo.owner_id, fc.path): fc for fc in file_commits}
    update_content_types([fc.file_content for fc in file_commits if fc.file_content])
    session.commit()

    def file_presentation(file, path):
        if not file:
            return dict(css_class='danger', path=path, mod_time='missing')
        return dict(
            css_class=('warning' if file.sha == user_path_files[source_repo.owner.id, file.path].sha
                       else 'danger' if not file.file_content
                       else 'warning' if not file.file_content != 'PYNB_MIME_TYPE'
                       else None),
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


def get_assignment(assignment_id):
    session.rollback()
    source_repo = session.query(Repo).options(joinedload(Repo.files)).filter(Repo.source_id.is_(None)).first()
    assert source_repo
    assignemnt_paths = sorted({fc.path for fc in source_repo.files if fc.path.endswith('.ipynb')})
    assignment_path = assignemnt_paths[assignment_id]

    files = session.query(FileCommit).filter(FileCommit.path == assignment_path)
    files_hash = hashlib.md5(pickle.dumps(sorted(fc.sha for fc in files))).hexdigest()

    assignment = session.query(Assignment).\
        options(joinedload(Assignment.questions)).\
        filter(Assignment.path == assignment_path). \
        first()
    if assignment and assignment.md5 == files_hash:
        return assignment
    if assignment:
        session.delete(assignment)

    # .options(undefer(FileCommit.file_content.content)) \
    file_commits = session.query(FileCommit) \
        .options(joinedload(FileCommit.repo)) \
        .options(joinedload(FileCommit.file_content)) \
        .filter(FileCommit.path == assignment_path)
    nbs = {fc.repo.owner.login: safe_read_notebook(fc.content.decode(), clear_outputs=True)
           for fc in file_commits
           if fc.file_content}

    owner_nb = nbs[source_repo.owner.login]
    student_nbs = {owner: nb for owner, nb in nbs.items() if nb and owner != source_repo.owner.login}
    assert owner_nb

    collation = NotebookExtractor(owner_nb, student_nbs)
    answer_status = collation.report_missing_answers()

    student_login_ids = {fc.repo.owner.login: fc.repo.owner.id for fc in file_commits}
    questions = [AssignmentQuestion(assignment_id=assignment_id,
                                    question_order=question_index,
                                    question_name=question_name,
                                    responses=[AssignmentQuestionResponse(user_id=student_login_ids[login],
                                                                          status=status)
                                               for login, status in d.items()])
                 for question_index, (question_name, d) in enumerate(answer_status)]
    assignment = Assignment(repo_id=source_repo.id,
                            path=assignment_path,
                            nb_content=nbformat.writes(collation.get_combined_notebook()),
                            questions=questions,
                            md5=files_hash)
    session.add(assignment)
    session.commit()
    return assignment


def get_assignment_notebook(assignment_id):
    assignment = get_assignment(assignment_id)
    return nbformat.reads(assignment.nb_content, 4)


def get_combined_notebook(assignment_id):
    assignment = get_assignment(assignment_id)
    answer_status = [(question.question_name, {response.user.login: response.status for response in question.responses})
                     for question in assignment.questions]
    return AssignmentModel(assignment.path, nbformat.reads(assignment.nb_content, 4), answer_status)
