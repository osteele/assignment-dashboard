def upsert(session, instances, *key_attrs):
    """Merge or add instances to the session.

    Instance are merged if the database contains a row with the same values for key_attrs.
    """
    MAX_ROWS = 200  # empirially, some number 200 < n < 550 can generate queries that are too long
    assert(key_attrs)
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
    print('%s: merged %d records; added %d records' % (klass.__name__, len(instances) - len(instance_map), len(instance_map)))
    session.add_all(instance_map.values())
