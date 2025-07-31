# file: app/routes.py
from flask import Blueprint, jsonify, request
import mysql.connector
from .config import DB_CONFIG  
from .utils import get_mac_from_ip, scan_network 

# Tạo một Blueprint mới. Tất cả các route trong file này sẽ thuộc về blueprint này.
api = Blueprint('api', __name__)

# Biến toàn cục để theo dõi trạng thái phiên, giờ nó thuộc về blueprint này
session_active = False

@api.route('/')
def home():
    return "<h1>API Server cho hệ thống điểm danh đang hoạt động! (Đã cấu trúc lại)</h1>"

@api.route('/api/session/start', methods=['POST'])
def start_session():
    global session_active
    session_active = True
    return jsonify({"message": "Đã bắt đầu phiên điểm danh."})

@api.route('/api/session/stop', methods=['POST'])
def stop_session():
    global session_active
    session_active = False
    return jsonify({"message": "Đã kết thúc phiên điểm danh."})

@api.route('/api/session/status', methods=['GET'])
def get_session_status():
    return jsonify({"is_active": session_active})

@api.route('/api/students', methods=['GET', 'POST'])
def handle_students():
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if request.method == 'POST':
            data = request.get_json()
            student_id, full_name = data.get('student_id'), data.get('full_name')
            if not student_id or not full_name:
                return jsonify({"error": "Vui lòng nhập đủ MSSV và Họ tên."}), 400
            
            cursor = conn.cursor()
            query = "INSERT INTO Students (student_id, full_name) VALUES (%s, %s)"
            cursor.execute(query, (student_id, full_name))
            conn.commit()
            return jsonify({"message": f"Đã thêm thành công sinh viên {full_name}."}), 201

        elif request.method == 'GET':
            cursor = conn.cursor(dictionary=True) 
            cursor.execute("SELECT student_id, full_name, mac_address FROM Students")
            return jsonify(cursor.fetchall())
            
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({"error": f"Mã số sinh viên '{student_id}' đã tồn tại."}), 409
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@api.route('/api/register', methods=['POST'])
def register_device():
    if not session_active:
        return jsonify({"error": "Hiện không có phiên điểm danh nào đang mở."}), 403
    
    conn = None
    data = request.get_json()
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({"error": "Vui lòng nhập MSSV"}), 400
    
    mac_address = get_mac_from_ip(request.remote_addr)
    if not mac_address:
        return jsonify({"error": "Không thể lấy địa chỉ MAC từ thiết bị của bạn."}), 500
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "UPDATE Students SET mac_address = %s WHERE student_id = %s"
        cursor.execute(query, (mac_address.upper(), student_id))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({"message": f"Đăng ký thành công MAC {mac_address.upper()} cho sinh viên {student_id}."})
        else:
            return jsonify({"error": f"Không tìm thấy sinh viên có MSSV: {student_id}"}), 404
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally: 
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@api.route('/api/attendance/live', methods=['GET'])
def live_attendance():
    if not session_active:
        return jsonify([])

    conn = None
    active_mac_set = scan_network()
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT student_id, full_name, mac_address FROM Students")
        students = cursor.fetchall()
        
        attendance_status_list = []
        for student in students:
            status = 'Vắng mặt'
            if student['mac_address'] and student['mac_address'].upper() in active_mac_set:
                status = 'Có mặt'
            
            if student['mac_address']:
                student['status'] = status
                attendance_status_list.append(student)

        return jsonify(attendance_status_list)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()