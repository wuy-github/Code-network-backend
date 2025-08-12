# file: app/routes/session_routes.py

from flask import Blueprint, jsonify, current_app
import datetime
from .. import models, socketio, mail
from ..utils import scan_network
from .auth_routes import token_required
from flask_mail import Message

session_bp = Blueprint('session_bp', __name__)

# --- LOGIC WEBSOCKET VÀ TÁC VỤ NỀN (ĐÃ SỬA) ---

def attendance_background_task():
    """Tác vụ nền quét mạng và phát sự kiện điểm danh."""
    print("LOG: Bắt đầu tác vụ quét mạng chạy nền...")
    
    is_active = True
    while is_active:
        try:
            # === KIỂM TRA TRẠNG THÁI TRONG VÒNG LẶP ===
            conn_check = models.get_db_connection()
            cursor_check = conn_check.cursor(dictionary=True)
            cursor_check.execute("SELECT state_value FROM AppState WHERE state_key = 'session_active'")
            result = cursor_check.fetchone()
            conn_check.close()
            
            # Nếu state trong DB là 'false', dừng vòng lặp
            if result['state_value'] != 'true':
                is_active = False
                continue # Bỏ qua lần quét cuối và thoát

            # === LOGIC QUÉT MẠNG GIỮ NGUYÊN ===
            active_mac_set = scan_network()
            students = models.get_all_students()
            
            attendance_status_list = []
            for student in students:
                status = 'Vắng mặt'
                if student['mac_address'] and student['mac_address'].upper() in active_mac_set:
                    status = 'Có mặt'
                student['status'] = status
                attendance_status_list.append(student)
            
            socketio.emit('update_attendance', attendance_status_list)

        except Exception as e:
            print(f"ERROR: Lỗi trong tác vụ nền: {e}")
            is_active = False # Dừng tác vụ nếu có lỗi
        
        socketio.sleep(5) # Quét mỗi 5 giây
        
    print("LOG: Đã dừng tác vụ quét mạng chạy nền.")

# --- CÁC ROUTE QUẢN LÝ PHIÊN (ĐÃ SỬA) ---

@session_bp.route('/session/start', methods=['POST'])
@token_required
def start_session():
    conn = models.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE AppState SET state_value = 'true' WHERE state_key = 'session_active'")
    conn.commit()
    conn.close()

    socketio.start_background_task(target=attendance_background_task)
    
    return jsonify({"message": "Đã bắt đầu phiên điểm danh và quét mạng."})


@session_bp.route('/session/stop', methods=['POST'])
@token_required
def stop_session():
    # Chỉ cần cập nhật trạng thái trong DB, tác vụ nền sẽ tự dừng lại
    conn = models.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE AppState SET state_value = 'false' WHERE state_key = 'session_active'")
    conn.commit()
    conn.close()
    
    # Gửi tín hiệu cho client biết phiên đã kết thúc ngay lập tức
    socketio.emit('session_stopped')
    
    # Tạo báo cáo cuối kỳ (giữ nguyên logic)
    final_report = []
    # ... (toàn bộ code tạo báo cáo và gửi mail của bạn giữ nguyên ở đây)
    try:
        active_mac_set = scan_network()
        students = models.get_all_students()
        for student in students:
            status = 'Vắng mặt'
            if student['mac_address'] and student['mac_address'].upper() in active_mac_set:
                status = 'Có mặt'
            student['status'] = status
            final_report.append(student)
    except Exception as e:
        print(f"ERROR: Lỗi khi tạo báo cáo cuối kỳ: {e}")
        return jsonify({"error": "Lỗi khi tạo báo cáo."}), 500

    # Gửi mail báo cáo
    try:
        present_students = [s for s in final_report if s['status'] == 'Có mặt']
        absent_students = [s for s in final_report if s['status'] == 'Vắng mặt']
        html_body = f"""
        <h1>Báo cáo Điểm danh</h1>
        <p>Phiên điểm danh đã kết thúc vào lúc {datetime.datetime.now().strftime('%H:%M:%S %d-%m-%Y')}.</p>
        <h2>Sinh viên có mặt ({len(present_students)})</h2>
        <ul>{''.join([f'<li>{s["student_id"]} - {s["full_name"]}</li>' for s in present_students])}</ul>
        <h2>Sinh viên vắng mặt ({len(absent_students)})</h2>
        <ul>{''.join([f'<li>{s["student_id"]} - {s["full_name"]}</li>' for s in absent_students])}</ul>
        """
        msg = Message(
            subject=f"Báo cáo điểm danh ngày {datetime.datetime.now().strftime('%d-%m-%Y')}",
            sender=('Hệ thống Điểm danh', current_app.config['MAIL_USERNAME']),
            recipients=['quochuyhuy38@gmail.com'],
            html=html_body
        )
        mail.send(msg)
        print("LOG: Đã gửi mail báo cáo thành công!")
    except Exception as e:
        print(f"ERROR: Không thể gửi mail - {e}")
        
    return jsonify({
        "message": "Đã kết thúc và chốt danh sách phiên điểm danh.",
        "report": final_report
    })


@session_bp.route('/session/status', methods=['GET'])
def get_session_status():
    """Kiểm tra trạng thái phiên hiện tại từ DB."""
    conn = models.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT state_value FROM AppState WHERE state_key = 'session_active'")
    result = cursor.fetchone()
    conn.close()
    
    is_active = result['state_value'] == 'true' if result else False
    return jsonify({"is_active": is_active})