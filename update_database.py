import base64
import os
import sys

import arrow
from github import Github

from models import FileCommit, FileContent, Session, User

# Globals
#

GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN', None)
if not GITHUB_API_TOKEN:
    print("warning: GITHUB_API_TOKEN is not defined. API calls are rate-limited.", file=sys.stderr)

gh = Github(GITHUB_API_TOKEN)

session = Session()

source_repo_name = 'sd17spring/ReadingJournal'
organization_name = source_repo_name.split('/')[0]


# get the repos
#

instructor_logins = {user.login for team in gh.get_organization(organization_name).get_teams() for user in team.get_members()}

source_repo = gh.get_repo(source_repo_name)
student_repos = sorted((repo for repo in source_repo.get_forks()
                        if repo.owner.login not in instructor_logins),
                       key=lambda repo: repo.owner.login.lower())
all_repos = [source_repo] + student_repos
[repo.owner.login for repo in all_repos]


# insert students
#

def upsert(session, instances, *key_attrs):
    """Merge or add instances to the session.

    Instance are merged if the database contains a row with the same values for key_attrs.
    """
    MAX_ROWS = 200  # empirially, some number 200 < n < 550 can generate queries that are too long
    if not instances:
        return
    if len(instances) > MAX_ROWS:
        upsert(session, instances[:MAX_ROWS], *key_attrs)
        upsert(session, instances[MAX_ROWS:], *key_attrs)
        return
    klass = instances[0].__class__
    instance_map = {tuple(getattr(instance, attr.key) for attr in key_attrs): instance
                    for instance in instances}
    rows = session.query(klass.id, *(getattr(klass, attr.key) for attr in key_attrs))
    for i, attr in enumerate(key_attrs):
        rows = rows.filter(getattr(klass, attr.key).in_({k[i] for k in instance_map.keys()}))
    for id, *keys_values in rows:
        key = tuple(keys_values)
        # the query filters by the outer product of the key attribute values, so the key might not be in the map
        if key not in instance_map:
            continue
        instance = instance_map.pop(key)
        instance.id = id
        session.merge(instance)
    print('%s: updated %d records; added %d records' % (klass.__name__, len(instances) - len(instance_map), len(instance_map)))
    session.add_all(instance_map.values())

students = [User(login=repo.owner.login, fullname=repo.owner.name, role='organization' if repo == source_repo else 'student')
            for repo in all_repos]
upsert(session, students, User.login)
session.commit()


# insert file hashes
#

def get_file_content(repo, item):
    blob = repo.get_git_blob(item.url.split('/')[-1])
    content = blob.content
    if blob.encoding == 'base64':
        content = base64.b64decode(content)
    return content


def is_downloadable(item):
    return any(item.path.endswith(suffix) for suffix in ['.ipynb', '.py', '.md', '.txt'])


file_hashes = {item.sha: (repo, item)
               for repo in all_repos
               for item in repo.get_git_tree(repo.get_commits()[0].sha, recursive=True).tree
               if item.type == 'blob'}

db_file_contents = dict(session.query(FileContent.sha, FileContent.content_type).filter(FileContent.sha.in_(file_hashes)))

file_contents = [FileContent(sha=item.sha, content=get_file_content(repo, item) if is_downloadable(item) else None)
                 for repo, item in file_hashes.values()
                 if item.sha not in db_file_contents or is_downloadable(item) and db_file_contents[item.sha] is None]
len(file_contents)

upsert(session, file_contents, FileContent.sha)
session.commit()  # TODO remove this; commit with next transaction


# insert file commits
#


def parse_git_datetime(s):
    return arrow.get(s, 'ddd, DD MMM YYYY HH:mm:ss ZZZ').datetime

repo_commits = [(repo, commit)
                for repo in all_repos
                for commit in repo.get_commits()
                if repo == source_repo or (commit.author == repo.owner and len(commit.parents) == 1)]
len(repo_commits)

# Use a dict, to record only the latest commit for each file
file_commit_recs = {(repo.owner.login, item.filename): (item.sha, parse_git_datetime(commit.last_modified))
                    for repo, commit in reversed(repo_commits)
                    for item in commit.files}
len(file_commit_recs)

user_instances = list(session.query(User).filter(User.login.in_([repo.owner.login for repo in all_repos])))
user_instance_map = {instance.login: instance for instance in user_instances}  # FIXME there's surely some way to do this within the ORM

file_commits = [FileCommit(user_id=user_instance_map[login].id, path=path, mod_time=mod_time, sha=sha)
                for (login, path), (sha, mod_time) in file_commit_recs.items()]

upsert(session, file_commits, FileCommit.user_id, FileCommit.path)
session.commit()
