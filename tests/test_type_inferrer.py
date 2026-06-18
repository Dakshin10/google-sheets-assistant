import pandas as pd
from schema.type_inferrer import infer_sql_type


def test_infer_integer():
    s = pd.Series([1, 2, 3])
    assert infer_sql_type(s) == "INTEGER"


def test_infer_float():
    s = pd.Series([1.0, 2.5, 3.14])
    assert infer_sql_type(s) == "REAL"


def test_infer_date():
    s = pd.Series(["2026-06-18", "2026-06-19", "2026-06-20"])
    assert infer_sql_type(s) == "DATE"


def test_infer_text():
    s = pd.Series(["hello", "world", "2026/06/18"])
    assert infer_sql_type(s) == "TEXT"
