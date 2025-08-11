# file: app/__init__.py

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_mail import Mail

socketio = SocketIO(cors_allowed_origins="*")
mail = Mail()

def create_app():
    """Hàm "nhà máy" (factory function) để tạo và cấu hình ứng dụng Flask."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'chuoi-bi-mat-sieu-dai-va-kho-doan-cua-ban' 
    
    # --- Cấu hình Mail ---
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'dqhuy.cv@gmail.com' 
    # Mật khẩu ứng dụng được viết liền nhau
    app.config['MAIL_PASSWORD'] = 'd p w s t t a d w j j d y i x b' 
    
    # --- Khởi tạo các Extension ---
    CORS(app)
    socketio.init_app(app)
    mail.init_app(app)

    # --- Đăng ký các Blueprint mới ---
    # 1. Import blueprint từ file auth_routes.py
    from .routes.auth_routes import auth_bp
    
    # 2. Đăng ký blueprint xác thực với ứng dụng chính
    app.register_blueprint(auth_bp, url_prefix='/api')
    from .routes.student_routes import student_bp
    app.register_blueprint(student_bp, url_prefix='/api')
    from .routes.session_routes import session_bp
    app.register_blueprint(session_bp, url_prefix='/api')

  

    return app