# file: app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
import subprocess
import platform

# --- KHỞI TẠO APP VÀ CẤU HÌNH ---
app = Flask(__name__)
CORS(app) 

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'diemdanh_wifi'
}

# =======================================================
# == CÁC HÀM HỖ TRỢ (HELPER FUNCTIONS)
# =======================================================

def get_mac_from_ip(ip_address):
    """Lấy địa chỉ MAC từ IP bằng cách đọc bảng ARP của hệ thống."""
    try:
        # Lệnh 'arp -a <ip>' chính xác hơn là chỉ 'arp -a'
        output = subprocess.check_output(["arp", "-a", ip_address], text=True, encoding='utf-8')
        for line in output.splitlines():
            if ip_address in line and (line.count('-') == 5 or line.count(':') == 5):
                mac = line.split()[1].upper().replace('-', ':')
                return mac
    except Exception as e:
        print(f"Không thể tìm thấy MAC cho IP {ip_address}: {e}")
        return None
    return None

def scan_network():
    """Quét mạng LAN và trả về một TẬP HỢP các địa chỉ MAC đang hoạt động."""
    current_os = platform.system()
    print(f"Đang chạy trên hệ điều hành: {current_os}")
    try:
        if current_os == "Windows":
            command = ["arp", "-a"]
            output = subprocess.check_output(command, text=True, encoding='utf-8')
            active_macs = set()
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].count('-') == 5:
                    active_macs.add(parts[1].upper().replace('-', ':'))
            return active_macs
        else:
            command = ["sudo", "arp-scan", "--localnet", "-q", "-g", "-F", "${mac}"]
            output = subprocess.check_output(command, text=True)
            active_macs = set(output.strip().upper().split('\n'))
            active_macs.discard('')
            return active_macs
    except Exception as e:
        print(f"Lỗi khi quét mạng: {e}")
        return set()

# =======================================================
# == CÁC API ENDPOINT
# =======================================================

@app.route('/api/students', methods=['GET'])
def get_students():
    """API lấy toàn bộ danh sách sinh viên."""
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True) 
        cursor.execute("SELECT student_id, full_name, mac_address FROM Students")
        students = cursor.fetchall() 
        return jsonify(students)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/register', methods=['POST'])
def register_device():
    """API xử lý việc đăng ký MAC cho sinh viên."""
    conn = None
    data = request.get_json()
    student_id = data.get('student_id')

    if not student_id:
        return jsonify({"error": "Vui lòng nhập MSSV"}), 400
    
    client_ip = request.remote_addr
    mac_address = get_mac_from_ip(client_ip)

    if not mac_address:
        return jsonify({"error": "Không thể lấy địa chỉ MAC từ thiết bị của bạn. Hãy thử lại."}), 500
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "UPDATE Students SET mac_address = %s WHERE student_id = %s"
        cursor.execute(query, (mac_address.upper(), student_id))
        conn.commit()

        if cursor.rowcount > 0:
            message = f"Đăng ký thành công MAC {mac_address.upper()} cho sinh viên {student_id}."
            return jsonify({"message": message})
        else:
            return jsonify({"error": f"Không tìm thấy sinh viên có MSSV: {student_id}"}), 404
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally: 
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/attendance/live', methods=['GET'])
def live_attendance():
    """API quét mạng và trả về trạng thái điểm danh trực tiếp."""
    conn = None
    print("Bắt đầu quét mạng để điểm danh...")
    active_mac_set = scan_network()
    print(f"Các MAC đang hoạt động: {active_mac_set}")
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT student_id, full_name, mac_address FROM Students WHERE mac_address IS NOT NULL")
        students = cursor.fetchall()
        
        attendance_status_list = []
        for student in students:
            if student['mac_address'] and student['mac_address'].upper() in active_mac_set:
                student['status'] = 'Có mặt'
            else:
                student['status'] = 'Vắng mặt'
            attendance_status_list.append(student)

        return jsonify(attendance_status_list)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- KHỞI ĐỘNG SERVER ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)