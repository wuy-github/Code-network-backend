# file: app/routes/auth_routes.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
from .. import models 

# Tạo một "Blueprint". Đây giống như một "mini-app" cho các route xác thực.
auth_bp = Blueprint('auth_bp', __name__)

# --- DECORATOR BẢO VỆ ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        if not token:
            return jsonify({'message': 'Thiếu token!'}), 401
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        except:
            return jsonify({'message': 'Token không hợp lệ hoặc đã hết hạn!'}), 401
        return f(*args, **kwargs)
    return decorated

# --- CÁC ROUTE XÁC THỰC ---

@auth_bp.route('/teacher/register', methods=['POST'])
def register_teacher():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Thiếu username hoặc password'}), 400
        
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    
    # Gọi hàm từ model để tạo user, code đã ngắn hơn rất nhiều
    result = models.create_teacher(data['username'], hashed_password)
    
    if result['success']:
        return jsonify({'message': result['message']}), 201
    else:
        # Xử lý lỗi trả về từ model
        if result.get('errno') == 1062:
            return jsonify({'error': f"Tên đăng nhập '{data['username']}' đã tồn tại."}), 409
        return jsonify({'error': result['error']}), 500


@auth_bp.route('/teacher/login', methods=['POST'])
def login_teacher():
    auth = request.get_json()
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Thiếu username hoặc password'}), 401

    # Gọi hàm từ model để tìm user
    teacher = models.find_teacher_by_username(auth['username'])

    if not teacher:
        return jsonify({'message': 'Không tìm thấy người dùng'}), 401

    if check_password_hash(teacher['password_hash'], auth['password']):
        # Mật khẩu đúng, tạo token
        token = jwt.encode({
            'user_id': teacher['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, current_app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({'token': token})

    return jsonify({'message': 'Sai mật khẩu!'}), 403