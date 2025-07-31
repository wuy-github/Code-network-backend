# file: run.py
from app import create_app

# Gọi hàm "nhà máy" để tạo ra một instance của ứng dụng
app = create_app()

if __name__ == '__main__':
    # Chạy ứng dụng
    app.run(host='0.0.0.0', port=5000, debug=True)
