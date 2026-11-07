from flask import jsonify
from database.connection import get_db_connection

def get_availability():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
                   """
                   SELECT ea.*, s.shift_name, s.start_time, s.end_time, s.active
                   FROM EmployeeAvailability AS ea
                   JOIN Shifts AS s ON s.shift_id = ea.shift_id
                   """)
    returned_data = cursor.fetchall()
    conn.close()

    return returned_data

def getUserAvailability(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT employee_id FROM Users WHERE userid = ?", (user_id,))
    employee_id_row = cursor.fetchone()
    if employee_id_row is None:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    employee_id = employee_id_row['employee_id']

    cursor.execute(
                   """
                   SELECT ea.*, s.shift_name, s.start_time, s.end_time, s.active
                   FROM EmployeeAvailability AS ea
                   JOIN Shifts AS s ON s.shift_id = ea.shift_id
                   WHERE ea.employee_id = ?
                   """,
                   (employee_id,))
    returned_data = cursor.fetchall()
    conn.close()

    return returned_data
