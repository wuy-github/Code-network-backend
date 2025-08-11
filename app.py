# file: app.py
from app import create_app,socketio

# Gọi hàm "nhà máy" (factory function) để tạo ra một instance của ứng dụng
app = create_app()

if __name__ == '__main__':
    # Chạy ứng dụng
    # Lệnh này sẽ khởi động server của bạn
    socketio.run(app,host='0.0.0.0', port=5000, debug=True)
