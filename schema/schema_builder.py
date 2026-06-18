from schema.type_inferrer import infer_sql_type


def build_schema(df):
    """Generates schema dictionary list from a pandas DataFrame."""
    schema = []
    for column in df.columns:
        schema.append({
            "name": column,
            "type": infer_sql_type(df[column])
        })
    return schema


def build_create_sql(schema, table_name):
    """Generates CREATE TABLE IF NOT EXISTS statement for SQLite."""
    columns = []
    for col in schema:
        # replace spaces and keep a clean SQLite compatible column name
        safe_name = col["name"].replace(" ", "_")
        columns.append(f"{safe_name} {col['type']}")
    column_sql = ",\n    ".join(columns)
    return f"""CREATE TABLE IF NOT EXISTS {table_name} (
    {column_sql}
);"""


def build_insert_sql(df, table_name):
    """Generates bulk INSERT statement for SQLite."""
    columns = ", ".join([c.replace(" ", "_") for c in df.columns])
    values = []

    for _, row in df.iterrows():
        row_values = []
        for value in row:
            if isinstance(value, str):
                escaped_val = value.replace("'", "''")
                row_values.append(f"'{escaped_val}'")
            elif value is None or (hasarray := hasattr(value, 'isna') and value.isna()) or str(value) == 'nan' or str(value) == 'None':
                row_values.append("NULL")
            else:
                row_values.append(str(value))
        values.append(f"({', '.join(row_values)})")

    values_sql = ",\n".join(values)
    return f"INSERT INTO {table_name}\n({columns})\nVALUES\n{values_sql};"
