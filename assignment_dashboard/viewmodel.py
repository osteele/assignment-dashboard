""""
Implements the View-Model of an MVVM architecture.
"""

import hashlib
import pickle
import re
from collections import OrderedDict, namedtuple
from itertools import takewhile
from typing import List, Mapping

import dateutil.parser
import nbformat
from sqlalchemy.orm import joinedload, undefer

from nbcollate import NotebookCollator

from . import app  # for cache
from .database import session
from .globals import NBFORMAT_VERSION, PYNB_MIME_TYPE
from .helpers import lexituples
from .models import Assignment, AssignmentQuestion, AssignmentQuestionResponse, FileCommit, Repo
from .nb_helpers import safe_read_notebook

AssignmentViewModel = namedtuple('AssignmentViewModel', 'assignment_path collated_nb answer_status')
StudentViewModel = namedtuple('StudentViewModel', 'user repo display_name')
AssignmentResponseViewModel = namedtuple('AssignmentResponseViewModel', 'assignment_repo assignments students responses')


def get_source_repos(user=None) -> List:
    if not user:
        return session.query(Repo).options(joinedload(Repo.owner)).filter(Repo.source_id.is_(None)).all()
    # PERF replace this by a single query
    return [r
            for org in user.organizations
            for r in org.repos
            if r.is_source]


def update_content_types(file_contents):
    for fc in file_contents:
        if fc.content_type is None:
            content = fc.content
            if isinstance(content, bytes):
                content = content.decode()
            try:
                nbformat.reads(content, as_version=NBFORMAT_VERSION)  # for effect
                fc.content_type = PYNB_MIME_TYPE
            except nbformat.reader.NotJSONError:
                fc.content_type = ''


def compute_assignment_name(path: str) -> str:
    NOTEBOOK_ASSIGNMENT_PATH_RE = r'day(\d+)_reading_journal\.ipynb'
    NOTEBOOK_ASSIGNMENT_PATH_TITLE_TEMPLATE = r'Journal #\1'
    return re.sub(NOTEBOOK_ASSIGNMENT_PATH_RE, NOTEBOOK_ASSIGNMENT_PATH_TITLE_TEMPLATE, path)


def update_assignment_file_list(assignment_repo, assignment_paths):
    saved_assignments = {assignment.path: assignment
                         for assignment in assignment_repo.assignments}
    if set(assignment_paths) == set(saved_assignments):
        return

    map(session.delete, (assignment for assignment in assignment_repo.assignments if assignment.path not in assignment_paths))
    assignment_repo.assignments = [(saved_assignments.get(path) or
                                    Assignment(repo_id=assignment_repo.id, path=path, name=compute_assignment_name(path)))
                                   for path in assignment_paths]
    session.commit()


def get_assignment_responses(repo_id: int) -> AssignmentResponseViewModel:
    """Update the repo.assignments from its list of files."""
    assignment_repo = (session.query(Repo)
                       .options(joinedload(Repo.assignments).
                                joinedload(Assignment.repo))
                       .options(joinedload(Repo.files))
                       .filter(Repo.id == repo_id)
                       .one())

    assignment_paths = {f.path for f in assignment_repo.files if f.path.endswith('.ipynb')}
    update_assignment_file_list(assignment_repo, assignment_paths)

    # instead of assignment_repo.files, to avoid 1 + N
    # TODO filter to forks of source
    file_commits = (session.query(FileCommit)
                    .options(joinedload(FileCommit.repo))
                    .filter(FileCommit.path.in_(assignment_paths))).all()
    update_content_types([fc.file_content for fc in file_commits if fc.file_content])
    session.commit()

    # TODO move CSS logic from here to template
    def file_model(fc, path):
        if not fc:
            return dict(path=path, css_class='danger', unavailable=True)

        d = dict(path=path, status='complete', submission_date=fc.mod_time)
        if fc.sha in assignment_file_shas:
            d.update(dict(css_class='danger', unchanged=True))
        elif not fc.file_content:
            d.update(dict(css_class='danger', unavailable=True))
        elif fc.file_content.content_type != PYNB_MIME_TYPE:
            d.update(dict(css_class='warning', invalid_notebook=True))
        return d

    # re-query, since commit invalidates the cache
    # TODO DRY w/ code above
    assignment_repo = (session.query(Repo)
                       .options(joinedload(Repo.assignments).
                                joinedload(Assignment.repo))
                       .options(joinedload(Repo.files))
                       .filter(Repo.id == repo_id)).first()
    assignment_paths = {fc.path for fc in assignment_repo.files}
    file_commits = (session.query(FileCommit)
                    .options(joinedload(FileCommit.repo))
                    .filter(FileCommit.path.in_(assignment_paths))).all()
    assignment_file_shas = {fc.sha for fc in assignment_repo.files}
    user_path_files = {(fc.repo.owner_id, fc.path): fc
                       for fc in file_commits if fc.repo}

    assignments = assignment_repo.assignments
    student_repos = session.query(Repo).filter(Repo.source_id.in_(a.repo_id for a in assignments)).options(joinedload(Repo.owner)).all()
    responses = {assignment.id: {fork.owner_id: file_model(user_path_files.get((fork.owner_id, assignment.path)), assignment.path)
                                 for fork in student_repos}
                 for assignment in assignments}

    return AssignmentResponseViewModel(
        assignment_repo,
        sorted(assignments, key=lambda a: lexituples(a.name or a.path)),
        [StudentViewModel(repo.owner, repo, repo.owner.fullname or repo.owner.login)
         for repo in student_repos],
        responses)


def find_assignment(assignment_id: int) -> Assignment:
    """Return an Assignment.

    The associated repo and repo owner are eagerly loaded.
    """
    return session.query(Assignment).options(joinedload(Assignment.repo)).filter(Assignment.id == assignment_id).one()


def get_assignment_response_checksum(assignment: Assignment) -> str:
    """Return a constant that detects whether the set or contents of response files changes."""
    # FIXME restrict to forks of the assignment repo
    files = session.query(FileCommit).filter(FileCommit.path == assignment.path)
    return hashlib.md5(pickle.dumps(sorted(fc.sha for fc in files))).hexdigest()


def _compute_assignment_responses(assignment: Assignment, checksum=None) -> Mapping:
    """Update an assignment's related AssignmentQuestions, AssignmentQuestionResponses; return collated notebooks."""
    file_commits = [fc
                    for fc in (session.query(FileCommit)
                               .options(joinedload(FileCommit.repo).joinedload(Repo.owner))
                               .options(joinedload(FileCommit.file_content))
                               .options(undefer('file_content.content'))
                               .filter(FileCommit.path == assignment.path))
                    if fc.repo]

    notebooks = {fc.repo.owner.login: safe_read_notebook(fc.content.decode())
                 for fc in file_commits
                 if fc.file_content}

    student_nbs = OrderedDict(sorted(
        ((login, nb)
         for login, nb in notebooks.items()
         if nb and login != assignment.repo.owner.login)))

    assert assignment.repo.owner.login in notebooks, \
        "%s: %s is not in %s" % (assignment.path, assignment.repo.owner.login, notebooks.keys())
    assignment_nb = notebooks[assignment.repo.owner.login]

    collator = NotebookCollator(assignment_nb, student_nbs)

    answer_status = collator.report_missing_answers()
    student_login_id_map = {fc.repo.owner.login: fc.repo.owner.id for fc in file_commits}
    questions = [AssignmentQuestion(assignment_id=assignment.id,
                                    position=position,
                                    question_name=question_name,
                                    responses=[AssignmentQuestionResponse(user_id=student_login_id_map[login],
                                                                          status=status)
                                               for login, status in d.items()])
                 for position, (question_name, d) in enumerate(answer_status)]

    assignment.questions = []
    session.commit()

    assignment.questions = questions
    assignment.md5 = checksum
    session.add(assignment)
    session.commit()

    return {'usernames/%s' % include_usernames:
            nbformat.writes(collator.get_collated_notebook(
                clear_outputs=True, include_usernames=include_usernames))
            for include_usernames in [False, True]}


def update_assignment_responses(assignment_id: int, selector='assignment'):
    """Update an assignment's related AssignmentQuestions and AssignmentQuestionResponses, and create the collations.

    Return the assignment instance if selector == 'assignment' (the default).
    Return a collated notebook if selector is a dict.

    This method uses the app cache.
    """
    assignment = (session.query(Assignment)
                  .options(joinedload(Assignment.questions).
                           joinedload(AssignmentQuestion.responses))
                  .options(joinedload(Assignment.repo).joinedload(Repo.owner))
                  .filter(Assignment.id == assignment_id)
                  .one())

    checksum = get_assignment_response_checksum(assignment)

    key_prefix = 'responses/%s/' % assignment_id
    checksum_key = key_prefix + 'checksum'
    selector_subkey = selector if selector == 'assignment' else 'usernames/%s' % selector['include_usernames']

    if assignment.md5 == checksum and app.cache.get(checksum_key) == checksum:
        return (assignment if selector == 'assignment'
                else nbformat.reads(app.cache.get(key_prefix + selector_subkey), as_version=NBFORMAT_VERSION))

    results = _compute_assignment_responses(assignment, checksum=checksum)
    for k, v in results.items():
        app.cache.set(key_prefix + k, v)
    app.cache.set(checksum_key, checksum)  # do this last to insure integrity

    return (assignment if selector == 'assignment'
            else nbformat.reads(results[selector_subkey], as_version=NBFORMAT_VERSION))


def get_assignment_due_date(assignment: Assignment):
    """Return an assignment's due date.

    If this is not present in the database, try to read it from the first few markdown cells.
    """
    if assignment.due_date:
        return assignment.due_date

    nb = assignment.notebook
    if not nb or not nb.cells:
        return

    m = next((re.search('Due:?\s*(.+)', nb.cells[0].source, re.I)
              for cell in takewhile(lambda c: c.cell_type == 'markdown', nb.cells[:5])),
             None)
    if not m:
        return

    # prepare the date for dateutil.parse, which doesn't know "noon"
    s = m.group(1)
    s = re.sub(r'(12(:00)?)? ?noon', '12:00PM', s)
    s = re.sub(r'~~.*?~~', '', s)
    s = re.sub(r'\*', '', s)
    # TODO parse relative to timezone
    try:
        d = dateutil.parser.parse(s, fuzzy=True, default=assignment.file.mod_time)
        print(d)
    except ValueError:
        return
    else:
        assignment.due_date = d
        session.commit()
        return d


def get_collated_notebook(assignment_id: int, include_usernames=False):
    """Return the collated notebook for an assignment, updating it if necessary, and using the cache."""
    return update_assignment_responses(assignment_id, selector={'include_usernames': include_usernames})
