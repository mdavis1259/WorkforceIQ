import sqlite3
from flask import current_app, has_app_context

def get_db_connection():

    if has_app_context():
        database = current_app.config.get("DATABASE", "database/workforce.db")
    else:
        database = "database/workforce.db"

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    return connection
