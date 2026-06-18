def generate_insert_sql(df, table_name):
    statements = []

    columns = ", ".join(df.columns)

    for _, row in df.iterrows():
        values = []

        for value in row:
            if isinstance(value, str):
                values.append(f"'{value}'")
            else:
                values.append(str(value))

        values_str = ", ".join(values)

        statements.append(
            f"INSERT INTO {table_name} ({columns}) VALUES ({values_str});"
        )

    return statements