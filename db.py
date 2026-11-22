"""Single place for database connections. Credentials come only from the environment."""
import os

import psycopg
from psycopg.rows import dict_row


class DatabaseNotConfigured(RuntimeError):
    pass


def database_url():
    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        raise DatabaseNotConfigured(
            'DATABASE_URL is not set. Set it in this Command Prompt window before starting Flask.'
        )
    return url


def get_connection():
    """Open a new connection. Use as: with get_connection() as conn, conn.cursor() as cur: ..."""
    return psycopg.connect(database_url(), row_factory=dict_row)
