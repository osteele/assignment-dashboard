import sqlalchemy.types as types
from sqlalchemy import (CheckConstraint, Column, Enum, ForeignKey, Integer,
                        String, Text, UniqueConstraint, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

DATABASE_URL = 'sqlite:///database.db'

SHA_HASH_CONSTRAINT = CheckConstraint('length(sha) = 40')

Base = declarative_base()


class FileCommit(Base):
    __tablename__ = 'file_commit'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    mod_time = Column(types.DateTime, nullable=False)
    sha = Column(String(40), ForeignKey("file_content.sha"), SHA_HASH_CONSTRAINT, nullable=False)
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
    login = Column(String(80), nullable=False, index=True, unique=True)
    fullname = Column(String(80))
    role = Column(Enum('student', 'instructor', 'organization'), nullable=False, server_default='student')
    file_commits = relationship('FileCommit', backref='user')


engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

if __name__ == '__main__':
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
