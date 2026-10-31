from werkzeug.security import (
    generate_password_hash, check_password_hash
)

def authenticate_user(username, password, conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            userid,
            username,
            password,
            system_role_id,
            employee_id
        FROM Users
        WHERE username = ?
        """, (username,))

    user = cursor.fetchone()

    if not user:
        return None

    if check_password_hash(user["password"], password):
        return user

    return None
