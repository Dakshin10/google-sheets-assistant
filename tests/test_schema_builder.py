import pandas as pd
from schema.schema_builder import build_schema, build_create_sql, build_insert_sql


def test_build_schema():
    df = pd.DataFrame({
        "ID": [1, 2],
        "Name": ["Alice", "Bob"],
        "Score": [95.5, 88.0]
    })
    schema = build_schema(df)
    assert schema == [
        {"name": "ID", "type": "INTEGER"},
        {"name": "Name", "type": "TEXT"},
        {"name": "Score", "type": "REAL"}
    ]


def test_build_create_sql():
    schema = [
        {"name": "ID", "type": "INTEGER"},
        {"name": "User Name", "type": "TEXT"}
    ]
    sql = build_create_sql(schema, "users")
    assert "CREATE TABLE IF NOT EXISTS users" in sql
    # Spaces replaced by underscore
    assert "User_Name TEXT" in sql


def test_build_insert_sql():
    df = pd.DataFrame({
        "Name": ["Alice", "Bob's Burger"],
        "Age": [25, 30]
    })
    sql = build_insert_sql(df, "users")
    assert "INSERT INTO users" in sql
    assert "Name, Age" in sql
    # Single quotes escaped
    assert "Bob''s Burger" in sql
