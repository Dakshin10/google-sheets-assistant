import pytest
import time
from cache.query_cache import QueryCache

def test_sql_cache_set_and_get():
    cache = QueryCache(ttl_seconds=2)
    sql = "SELECT * FROM products"
    result = {"columns": ["id", "name"], "result": [[1, "Apple"], [2, "Banana"]]}
    
    assert cache.get(sql) is None
    
    cache.set(sql, result)
    assert cache.get(sql) == result
    
    # Case insensitivity & whitespace trimming
    assert cache.get("  select * from products  ") == result

def test_sql_cache_ttl():
    cache = QueryCache(ttl_seconds=1)
    sql = "SELECT * FROM products"
    result = {"columns": ["id"], "result": [[1]]}
    
    cache.set(sql, result)
    assert cache.get(sql) == result
    
    time.sleep(1.1)
    assert cache.get(sql) is None

def test_question_cache_set_and_get():
    cache = QueryCache(ttl_seconds=2)
    question = "Show me all products"
    sql = "SELECT * FROM products"
    result = {"columns": ["id", "name"], "result": [[1, "Apple"], [2, "Banana"]]}
    
    assert cache.get_by_question(question) is None
    
    cache.set_by_question(question, sql, result)
    cached = cache.get_by_question(question)
    
    assert cached is not None
    assert cached["sql"] == sql
    assert cached["result"] == result["result"]
    assert cached["columns"] == result["columns"]
    
    # Case insensitivity & whitespace trimming
    cached_flex = cache.get_by_question("  SHOW me all products  ")
    assert cached_flex is not None
    assert cached_flex["sql"] == sql

def test_question_cache_ttl():
    cache = QueryCache(ttl_seconds=1)
    question = "Show me all products"
    sql = "SELECT * FROM products"
    result = {"columns": ["id"], "result": [[1]]}
    
    cache.set_by_question(question, sql, result)
    assert cache.get_by_question(question) is not None
    
    time.sleep(1.1)
    assert cache.get_by_question(question) is None

def test_cache_clear():
    cache = QueryCache(ttl_seconds=60)
    sql = "SELECT * FROM products"
    question = "Show me all products"
    result = {"columns": ["id"], "result": [[1]]}
    
    cache.set(sql, result)
    cache.set_by_question(question, sql, result)
    
    assert cache.get(sql) is not None
    assert cache.get_by_question(question) is not None
    
    cache.clear()
    
    assert cache.get(sql) is None
    assert cache.get_by_question(question) is None
