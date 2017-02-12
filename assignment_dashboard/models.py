import os

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import backref, deferred, relationship

from .database import Base

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
MD5_HASH_CONSTRAINT = CheckConstraint('length(md5) = 32')
SHA_HASH_CONSTRAINT = CheckConstraint('length(sha) = 40')


# These mirror GitHub
#


class FileCommit(Base):
    __tablename__ = 'file_commit'
    __table_args__ = (UniqueConstraint('repo_id', 'path'),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repo.id'), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    mod_time = Column(DateTime, nullable=False)  # de-normalized from the related commit
    sha = Column(String(40), ForeignKey('file_content.sha'), SHA_HASH_CONSTRAINT, nullable=False)

    file_content = relationship('FileContent', backref='files')
    repo = relationship('Repo', backref='files')

    @property
    def content(self):
        return self.file_content.content

    def __repr__(self):
        return "<FileCommit %s>" % ' '.join('%s=%r' % (k, getattr(self, k)) for k in ['id', 'path', 'repo_id', 'mod_time'] if k)


class FileContent(Base):
    __tablename__ = 'file_content'

    id = Column(Integer, primary_key=True)
    sha = Column(String(40), SHA_HASH_CONSTRAINT, nullable=False, index=True, unique=True)
    content_type = Column(String(40), nullable=True)
    content = deferred(Column(Text, nullable=True))


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    login = Column(String(100), nullable=False, index=True, unique=True)
    fullname = Column(String(100))
    avatar_url = Column(String(1024))

    role = Column(Enum('student', 'instructor', 'organization'), nullable=False, server_default='student')
    status = Column(Enum('enrolled', 'waitlisted', 'dropped'))

    file_commits = relationship('Repo', backref='owner')

    def __repr__(self):
        return "<User %s>" % ' '.join('%s=%r' % (k, getattr(self, k)) for k in ['id', 'login', 'role'] if k)


class Repo(Base):
    __tablename__ = 'repo'
    __table_args__ = (UniqueConstraint('owner_id', 'name'),)

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    source_id = Column(Integer, ForeignKey('repo.id'), nullable=True)
    name = Column(String(100), nullable=False)
    refreshed_at = Column(DateTime)

    source = relationship('Repo', remote_side=[id])
    forks = relationship('Repo')
    # forks = relationship('Repo', backref=backref('Repo', remote_side=[owner_id]))

    def __repr__(self):
        return "<Repo %s>" % ' '.join('%s=%r' % (k, getattr(self, k)) for k in ['id', 'name', 'owner_id', 'source_id'] if k)

    @property
    def html_url(self):
        return "https://github.com/%s/%s" % (self.owner.login, self.name)


class Commit(Base):
    __tablename__ = 'commit'
    __table_args__ = (UniqueConstraint('repo_id', 'sha'),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repo.id'), nullable=False, index=True)
    sha = Column(String(40), SHA_HASH_CONSTRAINT, nullable=False, index=True)
    commit_date = Column(DateTime, nullable=False)


# Assignment-related models
#

class Assignment(Base):
    """A single assignment file within a repo that contains multiple assignments, one per file."""

    __tablename__ = 'assignment'
    __table_args__ = (UniqueConstraint('repo_id', 'path'),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repo.id'), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    name = Column(String(128), nullable=False)
    nb_content = deferred(Column(Text, nullable=True))
    md5 = Column(String(32), MD5_HASH_CONSTRAINT, nullable=True)

    repo = relationship('Repo', backref=backref('assignments', cascade='all, delete-orphan'))

    def __repr__(self):
        return "<Assignment %s>" % ' '.join('%s=%r' % (k, getattr(self, k)) for k in ['id', 'name', 'repo_id', 'path'] if k)


class AssignmentQuestion(Base):
    """A question within an assignment."""

    __tablename__ = 'assignment_question'
    __table_args__ = (UniqueConstraint('assignment_id', 'question_order'),)

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey('assignment.id'), nullable=False)
    question_order = Column(Integer, nullable=False)
    question_name = Column(String(1024))
    notebook_data = deferred(Column(Text, nullable=True))

    assignment = relationship('Assignment', backref=backref('questions', cascade='all, delete-orphan'))

    def __repr__(self):
        return "<AssignmentQuestion %s>" % ' '.join('%s=%r' % (k, getattr(self, k)) for k in ['id', 'assignment_id', 'repo_id', 'path'] if k)


class AssignmentQuestionResponse(Base):
    __tablename__ = 'assignment_question_response'
    __table_args__ = (UniqueConstraint('assignment_question_id', 'user_id'),)

    id = Column(Integer, primary_key=True)
    assignment_question_id = Column(Integer, ForeignKey('assignment_question.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    status = Column(String(20))
    notebook_data = deferred(Column(Text, nullable=True))

    question = relationship('AssignmentQuestion', backref=backref('responses', cascade='all, delete-orphan'))
    user = relationship('User')

    def __repr__(self):
        return "<AssignmentQuestionResponse %s>" % ' '.join('%s=%r' % (k, getattr(self, k)) for k in ['id', 'assignment_question_id', 'user_id'] if k)
