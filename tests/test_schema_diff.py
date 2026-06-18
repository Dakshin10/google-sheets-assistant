from sync.schema_diff import diff_schemas


def test_diff_schemas_added():
    d1 = [{"name": "id", "type": "INTEGER"}]
    new = [{"name": "id", "type": "INTEGER"}, {"name": "name", "type": "TEXT"}]
    diff = diff_schemas(d1, new)
    assert diff["added"] == [{"name": "name", "type": "TEXT"}]
    assert diff["removed"] == []
    assert diff["renamed"] == []
    assert diff["type_changed"] == []


def test_diff_schemas_type_changed():
    d1 = [{"name": "price", "type": "INTEGER"}]
    new = [{"name": "price", "type": "REAL"}]
    diff = diff_schemas(d1, new)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["renamed"] == []
    assert diff["type_changed"] == [{"name": "price", "old_type": "INTEGER", "new_type": "REAL"}]


def test_diff_schemas_renamed():
    d1 = [{"name": "first_name", "type": "TEXT"}]
    new = [{"name": "given_name", "type": "TEXT"}]
    diff = diff_schemas(d1, new)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["renamed"] == [("first_name", "given_name", "TEXT")]
    assert diff["type_changed"] == []
