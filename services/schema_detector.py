import pandas as pd


def infer_sql_type(series):
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"

    if pd.api.types.is_float_dtype(series):
        return "REAL"

    return "TEXT"


def generate_create_table_sql(df, table_name):
    columns = []

    for col in df.columns:
        sql_type = infer_sql_type(df[col])

        column_name = col.strip().replace(" ", "_")

        columns.append(f"{column_name} {sql_type}")

    columns_sql = ",\n    ".join(columns)

    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    {columns_sql}
);
"""