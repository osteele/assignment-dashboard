"""
Update the database from GitHub.
"""

import base64
import os
from collections import namedtuple
from datetime import datetime, timedelta

import dateutil
from github import Github

from .database import session
from .models import Commit, FileCommit, FileContent, Repo, User
from .sql_alchemy_helpers import find_or_create, update_instance, upsert_all

# globals
#

REPROCESS_COMMITS = os.environ.get('REPROCESS_COMMITS', 'False') not in ('False', '0')

# TODO use user token associated with assignment repo
GITHUB_API_TOKEN = os.environ['GITHUB_API_TOKEN']
gh = Github(GITHUB_API_TOKEN)


# helpers
#

RepoCommitFile = namedtuple('RepoCommitItem', 'commit file')


def unique_by(pairs):
    """Return a list of items with distinct keys. pairs yields (item, key)."""
    # return a list rather than a set, because items might not be hashable
    return list({key: item for item, key in pairs}.values())


def get_file_content(repo, blob_url):
    blob = repo.get_git_blob(blob_url.split('/')[-1])
    content = blob.content
    if blob.encoding == 'base64':
        content = base64.b64decode(content)
    return content


def is_downloadable_path(path):
    return any(path.endswith(suffix) for suffix in ['.ipynb', '.py', '.md', '.txt'])


def parse_git_datetime(s):
    return dateutil.parser.parse(s)


def own_commit(repo, commit):
    """Return true iff commit appears to be from the repo owner."""
    return not commit.author or commit.author == repo.owner or commit.author.login == 'web-flow'


# read the repos
#

def update_instructor_logins(source_repo):
    print("Reading organization members from GitHub")
    org_name = source_repo.full_name.split('/')[0]
    org_instance = session.query(User).filter(User.login == org_name).one()
    members = [u for u in gh.get_organization(org_name).get_members()]
    save_users(members, role='instructor')

    for member in members:
        member_instance = get_user_instance(member)
        if org_instance not in member_instance.organizations:
            member_instance.organizations.append(org_instance)
    session.commit()


def get_forks(source_repo):
    print("Reading repos from GitHub")
    owner = get_repo_db_instance(source_repo).owner
    instructor_logins = {user.login for user in owner.members} if owner.is_organization else {owner.login}
    repos = [repo
             for repo in source_repo.get_forks()
             if repo.owner.login not in instructor_logins]
    return repos


# read and update students
#

user_instance_map = {}


def save_users(users, role='student'):
    print("Updating %ss in database" % role)
    saved_instances = {instance.login: instance
                       for instance in session.query(User).filter(User.login.in_(user.login for user in users))}
    for user in users:
        attrs = dict(
            login=user.login,
            avatar_url=user.avatar_url or repo.owner.gravatar_url,
            gh_type=user.type,
            role=role,
            **dict(fullname=user.name) if user.name else {},
        )

        instance = saved_instances.get(user.login)
        if instance:
            update_instance(instance, attrs)
        else:
            instance = User(**attrs)
        session.add(instance)

    session.commit()

    user_instances = list(session.query(User).filter(User.login.in_([user.login for user in users])))
    user_instance_map.update({instance.login: instance for instance in user_instances})  # FIXME there's surely some way to do this within the ORM


def get_user_instance(user):
    if user_instance_map:
        return user_instance_map[user.login]
    else:
        return User.query.filter(User.login == user.login).one()


# update repos
#

repo_instance_map = None


def get_repo_instance(repo):
    global repo_instance_map
    if not repo_instance_map:
        repo_instance_map = {(instance.owner_id, instance.name): instance for instance in session.query(Repo)}
    owner = get_user_instance(repo.owner)
    return repo_instance_map[owner.id, repo.name]


def save_repos(source_repo, repos):
    print("Updating %d repos in database" % len(repos))
    source_repo_instance = find_or_create(session, Repo, owner_id=get_user_instance(source_repo.owner).id, name=source_repo.name)
    session.commit()
    assert source_repo_instance.id

    repo_instances = [Repo(owner_id=user_instance_map[repo.owner.login].id, name=repo.name, source_id=source_repo_instance.id)
                      for repo in repos
                      if repo != source_repo]
    upsert_all(session, [source_repo_instance] + repo_instances, Repo.owner_id, Repo.name)
    session.commit()


# record file commits
#

def get_repo_db_instance(gh_repo):
    owner_login, repo_name = gh_repo.full_name.split('/')
    instance = (session.query(Repo)
                .join(Repo.owner)
                .filter(User.login == owner_login)
                .filter(Repo.name == repo_name)
                .one())
    return instance


def get_new_repo_commits(repo, commit_limit=None, reprocess_commits=False):
    repo_instance = get_repo_db_instance(repo)

    saved_commits = set() if reprocess_commits else get_repo_instance(repo).commits
    saved_commit_shas = {commit.sha for commit in saved_commits}

    def get_commit_kwargs(repo):
        since = None
        if reprocess_commits:
            pass
        elif repo_instance.refreshed_at:
            since = repo_instance.refreshed_at + timedelta(days=-1)
        else:
            date_tuple = (session.query(FileCommit.mod_time)
                          .filter(FileCommit.repo_id == Repo.id)
                          .filter(Repo.owner_id == User.id)
                          .filter(User.login == repo.owner.login)
                          .order_by(FileCommit.mod_time.desc())
                          .first())
            if date_tuple:
                since = date_tuple[0] + timedelta(weeks=-1)

        args = {}
        if since:
            args['since'] = since
        return args

    repo_commits = [commit
                    for commit in repo.get_commits(**get_commit_kwargs(repo))
                    if commit.sha not in saved_commit_shas]

    if commit_limit:
        repo_commits = repo_commits[:commit_limit]

    if repo_commits:
        print("Processing %d new commits" % len(repo_commits))

    return repo_commits


def get_file_commit_recs(repo, repo_commits, all_commits=False):
    # file_commit_recs = unique_by(
    #     (RepoCommitFile(commit, item), (repo.full_name, item.filename))
    #     for commit in reversed(repo_commits)
    #     if all_commits or own_commit(repo, commit)
    #     for item in commit.files
    #     if item.sha)
    #
    file_commit_recs = [
        RepoCommitFile(commit, item)
        for commit in reversed(repo_commits)
        if all_commits or own_commit(repo, commit)
        for item in commit.files
        if item.sha]

    if file_commit_recs:
        print('Processing %d file commits' % len(file_commit_recs))

    return file_commit_recs


def download_files(repo, repo_commits, file_commit_recs):
    incoming_file_shas = {item.file.sha for item in file_commit_recs}
    if not incoming_file_shas:
        return

    db_file_content_shas = {sha for sha, in session.query(FileContent.sha).filter(FileContent.sha.in_(incoming_file_shas))}

    download_commits = ((commit, {item.file.filename
                                  for item in file_commit_recs if item.commit == commit
                                  if item.file.sha not in db_file_content_shas})
                        for commit in repo_commits)

    download_commits = ((commit, paths)
                        for (commit, paths) in download_commits
                        if paths)

    if not download_commits:
        return

    print("Downloading %d file(s)" % len(incoming_file_shas - db_file_content_shas))

    seen = set()
    for commit, paths in download_commits:
        items = [item
                 for item in repo.get_git_tree(commit.sha, recursive=True).tree
                 if item.path in paths]
        for item in items:
            if item.sha in seen:
                continue
            seen |= {item.sha}

            print("Downloading %s/%s (sha=%s)" % (repo.full_name, item.path, item.sha))
            content = get_file_content(repo, item.url) if is_downloadable_path(item.path) else None
            fc = FileContent(sha=item.sha, content=content)
            session.add(fc)
            session.commit()


def update_file_commits(repo, file_commit_recs):
    file_commits = [FileCommit(repo_id=get_repo_instance(repo).id,
                               path=item.file.filename,
                               mod_time=parse_git_datetime(item.commit.last_modified),
                               sha=item.file.sha)
                    for item in file_commit_recs]
    upsert_all(session, file_commits, FileCommit.repo_id, FileCommit.path)
    session.commit()


# record repo commits
#

def record_repo_commits(repo, repo_commits, timestamp):
    repo_instance = get_repo_db_instance(repo)
    repo_instance.refreshed_at = timestamp

    commit_instances = [Commit(repo_id=get_repo_instance(repo).id,
                               sha=commit.sha,
                               commit_date=parse_git_datetime(commit.last_modified))
                        for commit in repo_commits]
    upsert_all(session, commit_instances, Commit.repo_id, Commit.sha)
    session.commit()


def update_repo_files(repo, all_commits=False, commit_limit=None, reprocess_commits=False):
    timestamp = datetime.utcnow()
    repo_commits = get_new_repo_commits(repo, commit_limit=commit_limit, reprocess_commits=reprocess_commits)
    file_commit_recs = get_file_commit_recs(repo, repo_commits, all_commits=all_commits)
    if repo_commits:
        download_files(repo, repo_commits, file_commit_recs)
        update_file_commits(repo, file_commit_recs)
    record_repo_commits(repo, repo_commits, timestamp)


def add_repo(repo_name):
    owner_login, shortname = repo_name.split('/')
    owner = find_or_create(session, User, login=owner_login)
    instance = find_or_create(session, Repo, owner_id=owner.id, name=shortname)
    # FIXME this doesn't detect forks that weren't previously imported
    assert not instance.source_id, "appears to be a fork: %r" % instance
    update_db(repo_name)


def update_db(source_repo_name, options={}):
    source_repo = gh.get_repo(source_repo_name)

    if options.get('update_users'):
        save_users([source_repo.owner], role='organization')
        update_instructor_logins(source_repo)

    repo = session.query(Repo).filter(Repo.source_id.is_(None)).all()
    forks = get_forks(source_repo)
    if options.get('update_users'):
        save_users([repo.owner for repo in forks], role='student')

    forks = sorted(forks, key=lambda r: r.owner.login)
    if options.get('update_users'):
        save_repos(source_repo, forks)

    repos = [source_repo] + forks
    if options.get('users'):
        repos = [repo for repo in repos if repo.owner.login in options['users']]
    if options.get('oldest_first'):
        repos = sorted(repos, key=lambda r: r.updated_at or datetime(1972, 1, 1))
    if options.get('repo_limit'):
        repos = repos[:options['repo_limit']]

    for i, repo in enumerate(repos):
        print("Updating %s (%d/%d)" % (repo.full_name, i + 1, len(repos)))
        update_repo_files(repo,
                          all_commits=(repo == source_repo),
                          commit_limit=options.get('commit_limit'),
                          reprocess_commits=options.get('reprocess_commits')
                          )
