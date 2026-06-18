import re
from retrieval.schema_index import schema_indexer


def search_relevant_tables(user_prompt: str, limit: int = 4) -> list:
    """
    Evaluates keyword overlap between the user request and database schemas.
    Returns table names that match the query tokens, falling back to a subset if no direct matches.
    """
    index = schema_indexer.get_index()
    if not index:
        return []

    # Tokenize user request into alphanumeric word sets
    words = set(re.findall(r"\w+", user_prompt.lower()))

    scored_tables = []
    for table_name, data in index.items():
        # Score intersection size of tokens and keywords
        overlap = len(words.intersection(data["keywords"]))
        scored_tables.append((table_name, overlap))

    # Sort tables by score descending
    scored_tables.sort(key=lambda x: x[1], reverse=True)

    selected = []
    top_score = scored_tables[0][1]

    if top_score == 0:
        # No direct keyword hit: Fall back to returning all available tables up to the limit
        selected = [tbl for tbl, _ in scored_tables[:limit]]
    else:
        # Include tables with positive match scores up to limit
        for tbl, score in scored_tables:
            if score > 0 and len(selected) < limit:
                selected.append(tbl)

    return selected
