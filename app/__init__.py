# file: app/__init__.py
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_mail import Mail

socketio = SocketIO(cors_allowed_origins="*")
mail = Mail()

def create_app():
    """
    Hàm "nhà máy" (factory function) để tạo và cấu hình ứng dụng Flask.
    """
    app = Flask(__name__)
    #  Key có thể là bất kỳ chuỗi ngẫu nhiên nào.
    app.config['SECRET_KEY'] = 'chuoi-bi-mat-sieu-dai-va-kho-doan-cua-ban' 
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    
    # Điền email của bạn sẽ dùng để gửi thư
    app.config['MAIL_USERNAME'] = 'dqhuy.cv@gmail.com' 
    
    # Điền Mật khẩu ứng dụng gồm 16 ký tự bạn đã lấy từ Google
    app.config['MAIL_PASSWORD'] = 'd p w s t t a d w j j d y i x b'
    
    CORS(app)

    socketio.init_app(app)
    mail.init_app(app)
    # Import và đăng ký Blueprint từ file routes.py
    from .routes import api as api_blueprint
    app.register_blueprint(api_blueprint)

    return app
