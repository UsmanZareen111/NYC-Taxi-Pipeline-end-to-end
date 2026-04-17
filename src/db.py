"""
db.py – DuckDB connection management.

Provides a single get_connection() factory that returns a configured
DuckDB connection.  All pipeline modules import from here so the DB
path is never hard-coded twice.
"""


import duckdb
from pathlib import Path

from src.config  import DB_PATH, RAW_SCHEMA, ANALYTICS_SCHEMA
from src.logger import get_logger

log = get_logger(__name__)

connection = None


def get_connection(db_path = DB_PATH, read_only = False):
    """
    Return (and cache) a DuckDB connection.

    The first call creates the file and the required schemas.
    Subsequent calls return the cached connection.
    """
    global connection
    if connection is None:
        log.debug("Opening DuckDB at %s", db_path)
        connection = duckdb.connect(str(db_path), read_only=read_only)
        bootstrap_schemas(connection)
    return connection

# function to make schema when connection is first created, if it doesn't already exist.  Called by get_connection().
def bootstrap_schemas(connection):
    """Create raw and analytics schemas if they don't already exist."""
    for schema in (RAW_SCHEMA, ANALYTICS_SCHEMA):
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    log.debug("Schemas verified: %s, %s", RAW_SCHEMA, ANALYTICS_SCHEMA)


def close_connection():
    """Explicitly close the cached connection (useful in tests / cleanup)."""
    global connection
    if connection is not None:
        connection.close()
        connection = None
        log.debug("DuckDB connection closed")
        
        
        
