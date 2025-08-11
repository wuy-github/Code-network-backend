# file: app/models.py

import mysql.connector
from .config import DB_CONFIG

# --- HÀM TIỆN ÍCH ---
def get_db_connection():
    """Hàm tiện ích để tạo và trả về một kết nối database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Lỗi kết nối database: {err}")
        return None

# --- CÁC HÀM LIÊN QUAN ĐẾN STUDENT ---

def get_all_students():
    """Lấy tất cả sinh viên từ database."""
    conn = get_db_connection()
    if not conn:
        return [] # Trả về danh sách rỗng nếu không kết nối được
    
    students = []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT student_id, full_name, mac_address FROM Students")
        students = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Lỗi khi lấy danh sách sinh viên: {err}")
    finally:
        if conn.is_connected():
            conn.close()
    return students

def add_student(student_id, full_name):
    """Thêm một sinh viên mới và trả về kết quả."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Lỗi kết nối database"}

    try:
        cursor = conn.cursor()
        query = "INSERT INTO Students (student_id, full_name) VALUES (%s, %s)"
        cursor.execute(query, (student_id, full_name))
        conn.commit()
        return {"success": True, "message": f"Đã thêm thành công sinh viên {full_name}."}
    except mysql.connector.Error as err:
        return {"success": False, "error": str(err), "errno": err.errno}
    finally:
        if conn.is_connected():
            conn.close()

def find_student_by_mac(mac_address):
    """Tìm sinh viên dựa trên địa chỉ MAC."""
    conn = get_db_connection()
    if not conn:
        return None
        
    student = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT student_id FROM Students WHERE mac_address = %s", (mac_address,))
        student = cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Lỗi khi tìm sinh viên bằng MAC: {err}")
    finally:
        if conn.is_connected():
            conn.close()
    return student

def update_student_mac(student_id, mac_address):
    """Cập nhật MAC cho một sinh viên và trả về số hàng bị ảnh hưởng."""
    conn = get_db_connection()
    if not conn:
        return 0
        
    rows_affected = 0
    try:
        cursor = conn.cursor()
        query = "UPDATE Students SET mac_address = %s WHERE student_id = %s"
        cursor.execute(query, (mac_address, student_id))
        conn.commit()
        rows_affected = cursor.rowcount
    except mysql.connector.Error as err:
        print(f"Lỗi khi cập nhật MAC: {err}")
    finally:
        if conn.is_connected():
            conn.close()
    return rows_affected


# --- CÁC HÀM LIÊN QUAN ĐẾN TEACHER ---

def find_teacher_by_username(username):
    """Tìm giáo viên dựa trên username."""
    conn = get_db_connection()
    if not conn:
        return None
        
    teacher = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Teachers WHERE username = %s", (username,))
        teacher = cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Lỗi khi tìm giáo viên: {err}")
    finally:
        if conn.is_connected():
            conn.close()
    return teacher

def create_teacher(username, hashed_password):
    """Tạo một tài khoản giáo viên mới."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Lỗi kết nối database"}

    try:
        cursor = conn.cursor()
        query = "INSERT INTO Teachers (username, password_hash) VALUES (%s, %s)"
        cursor.execute(query, (username, hashed_password))
        conn.commit()
        return {"success": True, "message": "Tạo tài khoản giáo viên thành công!"}
    except mysql.connector.Error as err:
        return {"success": False, "error": str(err), "errno": err.errno}
    finally:
        if conn.is_connected():
            conn.close()