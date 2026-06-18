class ValidationSchemaCache:
    """
    In-memory schema dictionary cache for static query validation.
    Stores schemas in format: {table_name: {column_name: column_type, ...}}
    """
    def __init__(self):
        self._schemas = {}
        self._is_loaded = False

    def load_from_db_result(self, tables_info: list, pragma_results: dict):
        """
        Loads schema representation dictionary.
        pragma_results: {table_name: [{'name': col_name, 'type': col_type}, ...]}
        """
        schemas = {}
        for table in tables_info:
            cols = pragma_results.get(table, [])
            schemas[table.lower()] = {col["name"].lower(): col["type"].upper() for col in cols}
        self._schemas = schemas
        self._is_loaded = True

    def get_schema(self) -> dict:
        return self._schemas

    def get_columns_for_table(self, table_name: str) -> set:
        table_schema = self._schemas.get(table_name.lower(), {})
        return set(table_schema.keys())

    def table_exists(self, table_name: str) -> bool:
        return table_name.lower() in self._schemas

    def invalidate(self):
        self._schemas = {}
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded


schema_cache = ValidationSchemaCache()
