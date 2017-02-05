import sqlalchemy.types as types
from sqlalchemy import (CheckConstraint, Column, DateTime, Enum, ForeignKey,
                        Integer, String, Text, UniqueConstraint, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship, sessionmaker

DATABASE_URL = 'sqlite:///database.db'

SHA_HASH_CONSTRAINT = CheckConstraint('length(sha) = 40')

Base = declarative_base()


class FileCommit(Base):
    __tablename__ = 'file_commit'
    __table_args__ = (UniqueConstraint('repo_id', 'path'),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repo.id'), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    mod_time = Column(DateTime, nullable=False)  # de-normalized from the related commit
    sha = Column(String(40), ForeignKey('file_content.sha'), SHA_HASH_CONSTRAINT, nullable=False)

    file_content = relationship('FileContent')


class FileContent(Base):
    __tablename__ = 'file_content'

    id = Column(Integer, primary_key=True)
    sha = Column(String(40), SHA_HASH_CONSTRAINT, nullable=False, index=True, unique=True)
    content_type = Column(String(40), nullable=True)
    content = Column(Text, nullable=True)


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    login = Column(String(100), nullable=False, index=True, unique=True)
    fullname = Column(String(100))
    role = Column(Enum('student', 'instructor', 'organization'), nullable=False, server_default='student')

    # file_commits = relationship('FileCommit', backref='user')


class Repo(Base):
    __tablename__ = 'repo'

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    source_id = Column(Integer, ForeignKey('repo.id'), nullable=True)
    name = Column(String(100), nullable=False)
    refreshed_at = Column(DateTime)

    source = relationship('Repo', remote_side=[id])
    # forks = relationship('Repo', backref=backref('Repo', remote_side=[owner_id]))


class Commit(Base):
    __tablename__ = 'commit'
    __table_args__ = (UniqueConstraint('repo_id', 'sha'),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repo.id'), nullable=False, index=True)
    sha = Column(String(40), SHA_HASH_CONSTRAINT, nullable=False, index=True)
    commit_date = Column(DateTime, nullable=False)


engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

if __name__ == '__main__':
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
