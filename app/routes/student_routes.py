# file: app/routes/student_routes.py

from flask import Blueprint, jsonify, request
from .. import models
from ..utils import get_mac_from_ip

# Dòng import session_active không còn cần thiết nữa nên đã được xóa

student_bp = Blueprint('student_bp', __name__)

@student_bp.route('/students', methods=['GET', 'POST'])
def handle_students():
    """Xử lý việc lấy danh sách và thêm sinh viên."""
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('student_id') or not data.get('full_name'):
            return jsonify({"error": "Vui lòng nhập đủ MSSV và Họ tên."}), 400

        result = models.add_student(data['student_id'], data['full_name'])
        
        if result['success']:
            return jsonify({"message": result['message']}), 201
        else:
            if result.get('errno') == 1062:
                 return jsonify({"error": f"Mã số sinh viên '{data['student_id']}' đã tồn tại."}), 409
            return jsonify({"error": result['error']}), 500

    elif request.method == 'GET':
        students = models.get_all_students()
        return jsonify(students)


# === HÀM NÀY ĐÃ ĐƯỢC SỬA LẠI THỤT LỀ CHO ĐÚNG ===
@student_bp.route('/register', methods=['POST'])
def register_device():
    """Xử lý việc sinh viên đăng ký MAC của thiết bị."""
    # Toàn bộ code bên trong hàm này phải được thụt vào một cấp
    
    # ĐỌC TRẠNG THÁI TỪ DATABASE
    conn = models.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT state_value FROM AppState WHERE state_key = 'session_active'")
    result = cursor.fetchone()
    conn.close()
    
    # Thêm kiểm tra để phòng trường hợp bảng AppState trống
    if not result:
        return jsonify({"error": "Lỗi cấu hình server: không tìm thấy trạng thái phiên."}), 500

    is_active = result['state_value'] == 'true'

    if not is_active:
        return jsonify({"error": "Hiện không có phiên điểm danh nào đang mở."}), 403
    
    data = request.get_json()
    if not data or not data.get('student_id'):
        return jsonify({"error": "Vui lòng nhập MSSV"}), 400
    
    student_id_to_register = data.get('student_id')
    mac_address = get_mac_from_ip(request.remote_addr)

    if not mac_address:
        return jsonify({"error": "Không thể lấy địa chỉ MAC từ thiết bị của bạn."}), 500
    
    mac_address = mac_address.upper()
    
    # Kiểm tra xem MAC đã được đăng ký cho sinh viên khác chưa
    existing_registration = models.find_student_by_mac(mac_address)
    if existing_registration and existing_registration['student_id'] != student_id_to_register:
        error_msg = f"Thiết bị này đã được đăng ký cho một sinh viên khác (MSSV: {existing_registration['student_id']})."
        return jsonify({"error": error_msg}), 409

    # Cập nhật MAC cho sinh viên
    rows_affected = models.update_student_mac(student_id_to_register, mac_address)
    
    if rows_affected > 0:
        return jsonify({"message": f"Đăng ký thành công MAC {mac_address} cho sinh viên {student_id_to_register}."})
    else:
        return jsonify({"error": f"Không tìm thấy sinh viên có MSSV: {student_id_to_register}"}), 404
