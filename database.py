#!/usr/bin/env python3

from models import Base, engine


def initdb():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
