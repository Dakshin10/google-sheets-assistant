from retrieval.schema_index import schema_indexer
from retrieval.schema_search import search_relevant_tables


def build_compressed_schema_context(relevant_tables: list) -> str:
    """
    Builds a token-efficient representation:
    table_name(col1, col2, col3)
    """
    index = schema_indexer.get_index()
    if not index:
        return ""

    schema_parts = []
    for table_name in relevant_tables:
        table_lower = table_name.lower()
        if table_lower in index:
            columns = index[table_lower]["columns"]
            columns_str = ", ".join(columns)
            schema_parts.append(f"{table_lower}(\n  {columns_str}\n)")
            
    return "\n\n".join(schema_parts)


def compose_system_prompt(user_prompt: str) -> tuple[str, list]:
    """
    Identifies relevant tables, creates a compressed schema context,
    and returns (prompt_string, list_of_selected_tables).
    """
    # 1. Select relevant tables dynamically
    relevant_tables = search_relevant_tables(user_prompt)
    
    # 2. Build compressed schema
    schema_context = build_compressed_schema_context(relevant_tables)
    
    return schema_context, relevant_tables
