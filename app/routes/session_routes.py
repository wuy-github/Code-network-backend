# file: app/routes/session_routes.py

from flask import Blueprint, jsonify, current_app
import datetime

from .. import models, socketio, mail
from ..utils import scan_network
from .auth_routes import token_required
from flask_mail import Message

session_bp = Blueprint('session_bp', __name__)

# Các biến toàn cục để quản lý trạng thái phiên giờ sẽ nằm ở đây
session_active = False
background_task_started = False

# --- LOGIC WEBSOCKET VÀ TÁC VỤ NỀN ---

def attendance_background_task():
    """Tác vụ nền quét mạng và phát sự kiện điểm danh."""
    print("LOG: Bắt đầu tác vụ quét mạng chạy nền...")
    while session_active:
        try:
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
        
        socketio.sleep(5)
    print("LOG: Đã dừng tác vụ quét mạng chạy nền.")

@socketio.on('connect')
def handle_connect():
    """Xử lý khi một client mới kết nối WebSocket."""
    print('LOG: Một client vừa kết nối tới WebSocket.')

# --- CÁC ROUTE QUẢN LÝ PHIÊN ---

@session_bp.route('/session/start', methods=['POST'])
@token_required
def start_session():
    """Bắt đầu một phiên điểm danh và khởi động tác vụ nền."""
    global session_active, background_task_started
    
    if not session_active:
        session_active = True
        if not background_task_started:
            socketio.start_background_task(target=attendance_background_task)
            background_task_started = True
        return jsonify({"message": "Đã bắt đầu phiên điểm danh và quét mạng."})
    else:
        return jsonify({"message": "Phiên đã hoạt động từ trước."})


@session_bp.route('/session/stop', methods=['POST'])
@token_required
def stop_session():
    """Kết thúc phiên, gửi mail báo cáo, và trả về kết quả."""
    global session_active, background_task_started
    if not session_active:
        return jsonify({"error": "Không có phiên nào đang diễn ra."}), 400

    session_active = False
    background_task_started = False
    socketio.emit('session_stopped')
    
    final_report = []
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
            recipients=['quochuyhuy38@gmail.com'], # <-- Thay email người nhận ở đây
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
    """Kiểm tra trạng thái phiên hiện tại."""
    return jsonify({"is_active": session_active})