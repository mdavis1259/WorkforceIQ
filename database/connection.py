import sqlite3

from flask import current_app


def get_db_connection(database=None):
    if database is None:
        database = current_app.config.get("DATABASE", "database/workforce.db")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    return connection
