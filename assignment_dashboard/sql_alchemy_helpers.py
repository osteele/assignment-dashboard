"""Jupyter notebook helper functions."""

from sqlalchemy.orm.exc import NoResultFound


def find_or_create(session, model, **kwargs):
    """Find an existing model keyed by `kwargs`, or create and add a new one.

    In either case the model is returned.

    Note: This method does not commit the model.

    Note: This method is not ACID.
    """
    q = session.query(model).filter_by(**kwargs)
    try:
        return q.one()
    except NoResultFound:
        instance = model(**kwargs)
        session.add(instance)
        return q.one()


def update_instance(instance, attrs):
    for k, v in attrs.items():
        setattr(instance, k, v)


def upsert_all(session, instances, *key_attrs):
    """Merge or add instances to the session.

    Instance are merged if the database contains a row with the same values for key_attrs.
    """
    MAX_ROWS = 200  # empirially, some number 200 < n < 550 can generate queries that are too long
    if not instances:
        return
    if len(instances) > MAX_ROWS:
        upsert_all(session, instances[:MAX_ROWS], *key_attrs)
        upsert_all(session, instances[MAX_ROWS:], *key_attrs)
        return

    assert key_attrs
    klass = instances[0].__class__
    instance_map = {tuple(getattr(instance, attr.key) for attr in key_attrs): instance
                    for instance in instances}

    rows = session.query(klass)
    for i, attr in enumerate(key_attrs):
        rows = rows.filter(getattr(klass, attr.key).in_({k[i] for k in instance_map.keys()}))

    for obj in rows:
        key = tuple(getattr(obj, attr.key) for attr in key_attrs)
        # the query filters by the outer product of the key attribute values, so the key might not be in the map
        if key not in instance_map:
            continue
        instance = instance_map.pop(key)
        for c in klass.__table__.columns:
            if c.key != 'id':
                setattr(obj, c.key, getattr(instance, c.key))

    session.add_all(instance_map.values())

    counts = {"Updated": len(instances) - len(instance_map), "Added": len(instance_map)}
    for verb, count in ((k, v) for k, v in counts.items() if v):
        print("%s %d %s record(s)" % (verb, count, klass.__name__))
