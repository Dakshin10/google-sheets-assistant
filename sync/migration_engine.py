from exceptions.sync_exceptions import MigrationError


def generate_migration_ddl(table_name: str, diff: dict) -> list:
    """
    Generates a list of SQLite ALTER TABLE DDL queries based on the schema diff.
    """
    ddl_statements = []

    # Handle Renamed Columns
    for old_name, new_name, _ in diff.get("renamed", []):
        safe_old = old_name.replace(" ", "_")
        safe_new = new_name.replace(" ", "_")
        ddl_statements.append(
            f'ALTER TABLE "{table_name}" RENAME COLUMN "{safe_old}" TO "{safe_new}";'
        )

    # Handle Added Columns
    for col in diff.get("added", []):
        safe_name = col["name"].replace(" ", "_")
        ddl_statements.append(
            f'ALTER TABLE "{table_name}" ADD COLUMN "{safe_name}" {col["type"]};'
        )

    # Handle Removed Columns (SQLite >= 3.35.0 supports ALTER TABLE DROP COLUMN)
    for col in diff.get("removed", []):
        safe_name = col["name"].replace(" ", "_")
        ddl_statements.append(
            f'ALTER TABLE "{table_name}" DROP COLUMN "{safe_name}";'
        )

    # If there are type changes, direct ALTER TABLE is not supported in SQLite.
    # In this case, we raise an exception indicating a full table rebuild is required.
    if diff.get("type_changed"):
        types_str = ", ".join([f"{c['name']} ({c['old_type']} -> {c['new_type']})" for c in diff["type_changed"]])
        raise MigrationError(
            f"Unsupported type change migration in SQLite for table '{table_name}': {types_str}. "
            f"Please run transactional staging load to rebuild the table."
        )

    return ddl_statements
