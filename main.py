from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/sepay-webhook', methods=['POST'])
def sepay_webhook():
    data = request.json
    print('📩 Nhận webhook từ Sepay:', data)

    # Tạo nội dung message gửi sang .NET MVC
    message = f"Sepay: {data.get('Sender')} gửi {data.get('Amount')} với nội dung: {data.get('Content')}"

    # Gửi HTTP POST sang MVC API
    requests.post("https://localhost:7168/api/Notify/Push", json={"message": message})

    # Chuẩn bị phản hồi
    response = {
        "message": "Webhook nhận thành công hehe",
        "data": data
    }

    return jsonify(response), 200

@app.route('/', methods=['GET'])
def index():
    return "Hello, Sepay Webhook Python is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
# Cập nhật lần cuối để ép GitHub build lại
