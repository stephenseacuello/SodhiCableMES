"""
SodhiCable MES v4.0 — SQL Query Loader
Loads named queries from .sql files in the queries/ directory.
Format: -- name: query_name followed by SQL
"""
import os
import re

_cache = {}
_QUERIES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "queries")

def load_queries(filename):
    if filename in _cache:
        return _cache[filename]
    path = os.path.join(_QUERIES_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        text = f.read()
    queries = {}
    for match in re.finditer(r"--\s*name:\s*(\w+)\s*\n(.*?)(?=--\s*name:|\Z)", text, re.DOTALL):
        name = match.group(1)
        sql = match.group(2).strip().rstrip(";")
        if sql:
            queries[name] = sql
    _cache[filename] = queries
    return queries

def get_query(filename, query_name):
    queries = load_queries(filename)
    if query_name not in queries:
        raise KeyError(f"Query '{query_name}' not found in {filename}. Available: {list(queries.keys())}")
    return queries[query_name]
