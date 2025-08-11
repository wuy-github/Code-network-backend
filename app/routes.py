# file: app/routes.py
# bao mat
from flask import Blueprint, jsonify, request, current_app
from functools import wraps
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

# Extensions & Helpers
from flask_mail import Message
from app import mail, socketio
import datetime
from time import sleep

# Local
from .config import DB_CONFIG
from .utils import get_mac_from_ip, scan_network
import mysql.connector

api = Blueprint('api', __name__)

# == CÁC BIẾN TOÀN CỤC ĐỂ QUẢN LÝ TRẠNG THÁI ==
session_active = False
# Dùng một biến cờ để đảm bảo tác vụ nền chỉ được khởi động MỘT LẦN
background_task_started = False 

# bao mat
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            # Lấy token từ header, dạng "Bearer <token>"
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Thiếu token!'}), 401

        try:
            # Giải mã token
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            # Bạn có thể lấy thông tin người dùng từ data['user_id'] nếu cần
        except:
            return jsonify({'message': 'Token không hợp lệ hoặc đã hết hạn!'}), 401

        return f(*args, **kwargs)

    return decorated

# ===================================================================
# == PHẦN LOGIC MỚI CỦA WEBSOCKET - TRÁI TIM CỦA HỆ THỐNG LIVE ==
# ===================================================================

def attendance_background_task():
    """
    Đây là hàm sẽ chạy liên tục trong một luồng riêng khi phiên điểm danh BẮT ĐẦU.
    Nó thay thế hoàn toàn cho route /api/attendance/live.
    """
    print("LOG: Bắt đầu tác vụ quét mạng chạy nền...")
    while session_active:
        try:
            # 1. Quét mạng để lấy các MAC đang hoạt động
            active_mac_set = scan_network()
            
            # 2. Lấy danh sách sinh viên từ DB và kiểm tra trạng thái
            # (Logic này được copy từ hàm live_attendance cũ của bạn)
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
            
            # 3. PHÁT SỰ KIỆN: Gửi dữ liệu điểm danh tới TẤT CẢ client
            # Tên sự kiện là 'update_attendance', kèm theo dữ liệu là danh sách điểm danh.
            socketio.emit('update_attendance', attendance_status_list)

        except Exception as e:
            print(f"ERROR: Lỗi trong tác vụ nền: {e}")
        finally:
            # Đóng kết nối DB sau mỗi lần quét
            if 'conn' in locals() and conn.is_connected():
                conn.close()
        
        # 4. Chờ 5 giây trước khi lặp lại
        # Dùng socketio.sleep() thay vì time.sleep() để không block server
        socketio.sleep(5)
    
    print("LOG: Đã dừng tác vụ quét mạng chạy nền.")

@socketio.on('connect')
def handle_connect():
    """
    Hàm này được tự động gọi mỗi khi có một trình duyệt mới kết nối tới WebSocket.
    """
    print('LOG: Một client vừa kết nối tới WebSocket.')


# ===================================================================
# == CẬP NHẬT CÁC ROUTE CŨ ĐỂ ĐIỀU KHIỂN LOGIC WEBSOCKET ==
# ===================================================================

@api.route('/api/session/start', methods=['POST'])
@token_required
def start_session():
    """Bắt đầu một phiên điểm danh VÀ khởi động tác vụ chạy nền."""
    global session_active, background_task_started
    
    if not session_active:
        session_active = True
        # Chỉ khởi động tác vụ nếu nó chưa từng được chạy
        if not background_task_started:
            # Dùng hàm của socketio để chạy hàm của chúng ta trong một luồng riêng
            socketio.start_background_task(target=attendance_background_task)
            background_task_started = True # Đánh dấu là tác vụ đã được kích hoạt
        return jsonify({"message": "Đã bắt đầu phiên điểm danh và quét mạng."})
    else:
        return jsonify({"message": "Phiên đã hoạt động từ trước."})


@api.route('/api/session/stop', methods=['POST'])
@token_required
def stop_session():
    """Kết thúc phiên, dừng tác vụ nền, quét lần cuối và trả về báo cáo."""
    global session_active, background_task_started
    if not session_active:
        return jsonify({"error": "Không có phiên nào đang diễn ra."}), 400

   
    session_active = False
    background_task_started = False

    socketio.emit('session_stopped')
    
    # 3. Giữ nguyên logic tạo báo cáo cuối kỳ của bạn
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT student_id, full_name, mac_address FROM Students")
        students = cursor.fetchall()
        
        active_mac_set = scan_network() # Quét lần cuối
        final_report = []
        for student in students:
            status = 'Vắng mặt'
            if student['mac_address'] and student['mac_address'].upper() in active_mac_set:
                status = 'Có mặt'
            student['status'] = status
            final_report.append(student)
            
        try:
            # 1. Chuẩn bị nội dung email từ `final_report`
            present_students = [s for s in final_report if s['status'] == 'Có mặt']
            absent_students = [s for s in final_report if s['status'] == 'Vắng mặt']

            # Dùng HTML để định dạng email cho đẹp mắt
            html_body = f"""
            <h1>Báo cáo Điểm danh</h1>
            <p>Phiên điểm danh đã kết thúc vào lúc {datetime.datetime.now().strftime('%H:%M:%S %d-%m-%Y')}.</p>
            
            <h2>Sinh viên có mặt ({len(present_students)})</h2>
            <ul>
                {''.join([f'<li>{s["student_id"]} - {s["full_name"]}</li>' for s in present_students])}
            </ul>

            <h2>Sinh viên vắng mặt ({len(absent_students)})</h2>
            <ul>
                {''.join([f'<li>{s["student_id"]} - {s["full_name"]}</li>' for s in absent_students])}
            </ul>
            """

            # 2. Tạo đối tượng email
            msg = Message(
                subject=f"Báo cáo điểm danh ngày {datetime.datetime.now().strftime('%d-%m-%Y')}",
                # Lấy email người gửi từ config
                sender=('Hệ thống Điểm danh', current_app.config['MAIL_USERNAME']), 
                # Điền email của người nhận vào đây (có thể là một danh sách)
                recipients=['quochuyhuy38@gmail.com'], 
                html=html_body
            )

            # 3. Gửi mail
            mail.send(msg)
            print("LOG: Đã gửi mail báo cáo thành công!")

        except Exception as e:
            # In ra lỗi nếu không gửi được mail, nhưng không làm sập server
            print(f"ERROR: Không thể gửi mail - {e}")
        # ==================================
            
        return jsonify({
            "message": "Đã kết thúc và chốt danh sách phiên điểm danh.",
            "report": final_report
        })
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()



# Giữ nguyên các route này
@api.route('/')
def home():
    return "<h1>API Server cho hệ thống điểm danh đang hoạt động!</h1>"
    
@api.route('/api/session/status', methods=['GET'])
def get_session_status():
    return jsonify({"is_active": session_active})

@api.route('/api/students', methods=['GET', 'POST'])
def handle_students():
    # ... (code của bạn giữ nguyên)
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
    # ... (code của bạn giữ nguyên)
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

# bao mat 
@api.route('/api/teacher/register', methods=['POST'])
def register_teacher():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Teachers (username, password_hash) VALUES (%s, %s)", (data['username'], hashed_password))
        conn.commit()
        return jsonify({'message': 'Tạo tài khoản giáo viên thành công!'})
    except mysql.connector.Error as err:
        return jsonify({'error': f'Tên đăng nhập đã tồn tại: {err}'}), 409
    finally:
        cursor.close()
        conn.close()

# == API ĐĂNG NHẬP CHO GIÁO VIÊN ==
@api.route('/api/teacher/login', methods=['POST'])
def login_teacher():
    auth = request.get_json()
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Không thể xác thực'}), 401

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Teachers WHERE username = %s", (auth['username'],))
    teacher = cursor.fetchone()
    cursor.close()
    conn.close()

    if not teacher:
        return jsonify({'message': 'Không tìm thấy người dùng'}), 401

    if check_password_hash(teacher['password_hash'], auth['password']):
        # Mật khẩu đúng, tạo token JWT
        token = jwt.encode({
            'user_id': teacher['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Token hết hạn sau 24 giờ
        }, current_app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({'token': token})

    return jsonify({'message': 'Sai mật khẩu!'}), 403