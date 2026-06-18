from validation.ast_analyzer import analyze_sql_ast

# Simple schema dictionary for testing
MOCK_SCHEMA = {
    "users": {"id": "INTEGER", "name": "TEXT"},
    "products": {"id": "INTEGER", "price": "REAL"}
}


def test_ast_analyzer_valid():
    valid, err = analyze_sql_ast("SELECT name FROM users WHERE id = 1", MOCK_SCHEMA)
    assert valid is True
    assert err == ""


def test_ast_analyzer_invalid_columns():
    valid, err = analyze_sql_ast("SELECT age FROM users", MOCK_SCHEMA)
    assert valid is False
    assert "does not match" in err


def test_ast_analyzer_invalid_tables():
    valid, err = analyze_sql_ast("SELECT * FROM customers", MOCK_SCHEMA)
    assert valid is False
    assert "does not exist" in err


def test_ast_analyzer_destructive_block():
    # Attempting modification queries
    valid, err = analyze_sql_ast("INSERT INTO users (name) VALUES ('Alice')", MOCK_SCHEMA)
    assert valid is False
    assert "Forbidden destructive query node" in err
    
    valid, err = analyze_sql_ast("DROP TABLE users", MOCK_SCHEMA)
    assert valid is False
    assert "Forbidden destructive query node" in err
