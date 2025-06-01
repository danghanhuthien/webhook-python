from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/sepay-webhook', methods=['POST'])
def sepay_webhook():
    data = request.json

    print('📩 Nhận webhook từ Sepay:', data)

    # Xử lý dữ liệu (nếu cần)
    # Ví dụ: Gửi tin nhắn lên Facebook, lưu file JSON...

    return jsonify({'message': 'Webhook nhận thành công'}), 200

@app.route('/', methods=['GET'])
def index():
    return "Hello, Sepay Webhook Python is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
