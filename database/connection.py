import sqlite3

def get_db_connection():
    connection = sqlite3.connect("database/workforce.db")
    connection.row_factory = sqlite3.Row #Lets us access columns by name instead of index

    return connection