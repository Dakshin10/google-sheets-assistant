class SchemaIndexer:
    """Creates a searchable registry indexing database tables and column tokens."""
    def __init__(self):
        self._index = {}

    def index_schemas(self, schemas: dict):
        """
        Builds the search index from schema dict: {table_name: {col1: type, col2: type}}
        """
        indexed = {}
        for table_name, columns in schemas.items():
            keywords = set()
            keywords.add(table_name.lower())
            
            # Index table parts (e.g. order_items -> order, items)
            for part in table_name.split("_"):
                keywords.add(part.lower())

            col_names = []
            for col_name in columns.keys():
                col_names.append(col_name.lower())
                keywords.add(col_name.lower())
                for col_part in col_name.split("_"):
                    keywords.add(col_part.lower())

            indexed[table_name.lower()] = {
                "keywords": keywords,
                "columns": col_names,
                "schema_raw": columns
            }
        self._index = indexed

    def get_index(self) -> dict:
        return self._index


schema_indexer = SchemaIndexer()
