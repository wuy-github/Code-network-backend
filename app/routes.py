# file: app/routes.py
from flask import Blueprint, jsonify, request
import mysql.connector
from .config import DB_CONFIG
from .utils import get_mac_from_ip, scan_network

api = Blueprint('api', __name__)
session_active = False

@api.route('/')
def home():
    return "<h1>API Server cho hệ thống điểm danh đang hoạt động!</h1>"

@api.route('/api/session/start', methods=['POST'])
def start_session():
    """Bắt đầu một phiên điểm danh."""
    global session_active
    session_active = True
    return jsonify({"message": "Đã bắt đầu phiên điểm danh."})

@api.route('/api/session/stop', methods=['POST'])
def stop_session():
    """Kết thúc phiên, quét lần cuối và trả về báo cáo."""
    global session_active
    if not session_active:
        return jsonify({"error": "Không có phiên nào đang diễn ra."}), 400

    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        # Lấy TẤT CẢ sinh viên để đưa vào báo cáo
        cursor.execute("SELECT student_id, full_name, mac_address FROM Students")
        students = cursor.fetchall()
        
        active_mac_set = scan_network()
        final_report = []
        for student in students:
            status = 'Vắng mặt'
            if student['mac_address'] and student['mac_address'].upper() in active_mac_set:
                status = 'Có mặt'
            student['status'] = status
            final_report.append(student)
            
        session_active = False
        # TRẢ VỀ CẢ MESSAGE VÀ REPORT
        return jsonify({
            "message": "Đã kết thúc và chốt danh sách phiên điểm danh.",
            "report": final_report
        })
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@api.route('/api/session/status', methods=['GET'])
def get_session_status():
    """Kiểm tra trạng thái phiên hiện tại."""
    return jsonify({"is_active": session_active})

@api.route('/api/students', methods=['GET', 'POST'])
def handle_students():
    """Xử lý việc LẤY và THÊM sinh viên."""
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
            student_id = request.get_json().get('student_id')
            return jsonify({"error": f"Mã số sinh viên '{student_id}' đã tồn tại."}), 409
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@api.route('/api/register', methods=['POST'])
def register_device():
    """Xử lý việc đăng ký MAC cho sinh viên."""
    if not session_active:
        return jsonify({"error": "Hiện không có phiên điểm danh nào đang mở."}), 403
    
    conn = None
    data = request.get_json()
    student_id_to_register = data.get('student_id')
    if not student_id_to_register:
        return jsonify({"error": "Vui lòng nhập MSSV"}), 400
    
    mac_address = get_mac_from_ip(request.remote_addr)
    if not mac_address:
        return jsonify({"error": "Không thể lấy địa chỉ MAC từ thiết bị của bạn."}), 500
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        check_cursor = conn.cursor(dictionary=True)
        query_check_mac = "SELECT student_id FROM Students WHERE mac_address = %s"
        check_cursor.execute(query_check_mac, (mac_address.upper(),))
        existing_registration = check_cursor.fetchone()
        check_cursor.close()

        if existing_registration and existing_registration['student_id'] != student_id_to_register:
            error_msg = f"Thiết bị này đã được đăng ký cho một sinh viên khác (MSSV: {existing_registration['student_id']})."
            return jsonify({"error": error_msg}), 409

        update_cursor = conn.cursor()
        query_update = "UPDATE Students SET mac_address = %s WHERE student_id = %s"
        update_cursor.execute(query_update, (mac_address.upper(), student_id_to_register))
        conn.commit()
        
        rowcount = update_cursor.rowcount
        update_cursor.close()

        if rowcount > 0:
            return jsonify({"message": f"Đăng ký thành công MAC {mac_address.upper()} cho sinh viên {student_id_to_register}."})
        else:
            return jsonify({"error": f"Không tìm thấy sinh viên có MSSV: {student_id_to_register}"}), 404
            
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally: 
        if conn and conn.is_connected():
            conn.close()

@api.route('/api/attendance/live', methods=['GET'])
def live_attendance():
    """Quét mạng và trả về trạng thái điểm danh trực tiếp."""
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
            student['status'] = status
            attendance_status_list.append(student)

        return jsonify(attendance_status_list)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
