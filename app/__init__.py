# file: app/__init__.py
from flask import Flask
from flask_cors import CORS

def create_app():
    """
    Hàm "nhà máy" (factory function) để tạo và cấu hình ứng dụng Flask.
    """
    app = Flask(__name__)
    CORS(app)

    # Import và đăng ký Blueprint từ file routes.py
    from .routes import api as api_blueprint
    app.register_blueprint(api_blueprint)

    return app
