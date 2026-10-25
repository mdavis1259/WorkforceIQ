from werkzeug.security import (
    generate_password_hash, check_password_hash
)

def authenticate_user(username, password, conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            username,
            password
        FROM Users
        WHERE username = ?
        """, (username,))

    user = cursor.fetchone()

    if not user:
        return None

    if check_password_hash(user[1], password):
        return user

    return None
