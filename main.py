# main.py - Webhook SePay đơn giản với Flask
from flask import Flask, request, jsonify
import pyodbc
import re
import logging
from datetime import datetime
import json

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo Flask app
app = Flask(__name__)

# Cấu hình kết nối SQL Server
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-UI5VDN,1433;"
    "DATABASE=Cheese Cakes;"
    "UID=sctws;"
    "PWD=1;"
    "TrustServerCertificate=yes;"
)

def get_db_connection():
    """Tạo kết nối đến SQL Server"""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        return conn
    except Exception as e:
        logger.error(f"Lỗi kết nối database: {e}")
        raise Exception("Lỗi kết nối database")

def extract_order_id(content):
    """Trích xuất Order ID từ nội dung giao dịch"""
    if not content:
        return ""
    
    logger.info(f"Đang phân tích nội dung: {content}")
    
    # Pattern 1: Tìm chuỗi 32 ký tự hex (không có dấu gạch ngang)
    # Ví dụ: 47b79bbde90d46f7af6724c12a575d56
    hex_pattern = r'\b[0-9a-fA-F]{32}\b'
    hex_match = re.search(hex_pattern, content)
    
    if hex_match:
        order_id = hex_match.group(0)
        logger.info(f"Tìm thấy Order ID (hex 32): {order_id}")
        return order_id
    
    # Pattern 2: Tìm GUID pattern (có dấu gạch ngang)
    # Ví dụ: 12345678-1234-1234-1234-123456789012
    guid_pattern = r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
    guid_match = re.search(guid_pattern, content)
    
    if guid_match:
        order_id = guid_match.group(0)
        logger.info(f"Tìm thấy Order ID (GUID): {order_id}")
        return order_id
    
    # Pattern 3: Tìm trong cấu trúc MBVCB
    # Từ ví dụ: MBVCB.9737451341.677798.47b79bbde90d46f7af6724c12a575d56.CT
    mbvcb_pattern = r'MBVCB\.\d+\.\d+\.([0-9a-fA-F]{32})\.'
    mbvcb_match = re.search(mbvcb_pattern, content)
    
    if mbvcb_match:
        order_id = mbvcb_match.group(1)
        logger.info(f"Tìm thấy Order ID trong MBVCB: {order_id}")
        return order_id
    
    logger.warning(f"Không tìm thấy Order ID trong nội dung: {content}")
    return ""

def find_order_by_id(order_id):
    """Tìm order theo ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT OrderId, PaymentStatus FROM Orders WHERE OrderId = ?"
        cursor.execute(query, order_id)
        row = cursor.fetchone()
        conn.close()
        
        return row is not None
    except Exception as e:
        logger.error(f"Lỗi tìm order {order_id}: {e}")
        return False

def update_order_payment_status(order_id, payment_status="Đã thanh toán"):
    """Cập nhật trạng thái thanh toán của order"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            UPDATE Orders 
            SET PaymentStatus = ?, UpdatedAt = ? 
            WHERE OrderId = ?
        """
        cursor.execute(query, payment_status, datetime.now(), order_id)
        conn.commit()
        
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        logger.error(f"Lỗi cập nhật order {order_id}: {e}")
        return False

# API Routes
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "SePay Webhook API is running!"})

@app.route('/sepay-webhook', methods=['POST'])
def sepay_webhook():
    """Endpoint nhận webhook từ SePay"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu"}), 400
        
        logger.info(f"Received webhook: {json.dumps(data, ensure_ascii=False)}")
        
        # Lấy thông tin từ request
        content = data.get('content', '')
        transfer_amount = data.get('transferAmount', 0)
        transfer_type = data.get('transferType', '')
        gateway = data.get('gateway', '')
        transaction_date = data.get('transactionDate', '')
        
        # Chỉ xử lý giao dịch tiền vào
        if transfer_type != "in":
            logger.warning("Không phải giao dịch tiền vào")
            return jsonify({
                "success": True, 
                "message": "Không phải giao dịch tiền vào"
            })
        
        # Trích xuất Order ID từ nội dung
        order_id = extract_order_id(content)
        if not order_id:
            logger.warning(f"Không tìm thấy Order ID trong: {content}")
            return jsonify({
                "success": False, 
                "message": "Không tìm thấy Order ID trong nội dung giao dịch"
            })
        
        # Tìm order trong database
        order_exists = find_order_by_id(order_id)
        if not order_exists:
            logger.warning(f"Không tìm thấy Order {order_id}")
            return jsonify({
                "success": False, 
                "message": f"Không tìm thấy Order {order_id}"
            })
        
        # Cập nhật trạng thái thanh toán
        success = update_order_payment_status(order_id, "Đã thanh toán")
        if success:
            logger.info(f"Đã cập nhật Order {order_id} thành 'Đã thanh toán'")
            return jsonify({
                "success": True,
                "message": "Cập nhật trạng thái thanh toán thành công",
                "data": {
                    "order_id": order_id,
                    "payment_status": "Đã thanh toán",
                    "amount": transfer_amount,
                    "gateway": gateway,
                    "transaction_date": transaction_date
                }
            })
        else:
            logger.error(f"Lỗi cập nhật Order {order_id}")
            return jsonify({
                "success": False, 
                "message": "Lỗi cập nhật trạng thái thanh toán"
            })
            
    except Exception as e:
        logger.error(f"Lỗi xử lý webhook: {e}")
        return jsonify({
            "success": False, 
            "message": "Lỗi hệ thống"
        }), 500

@app.route('/api/order/<order_id>', methods=['GET'])
def get_order(order_id):
    """API kiểm tra thông tin order"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM Orders WHERE OrderId = ?"
        cursor.execute(query, order_id)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "Không tìm thấy order"}), 404
        
        return jsonify({
            "order_id": row.OrderId,
            "status": row.Status,
            "payment_status": row.PaymentStatus,
            "shipping_address": row.ShippingAddress,
            "created_at": str(row.CreatedAt),
            "updated_at": str(row.UpdatedAt)
        })
    except Exception as e:
        logger.error(f"Lỗi lấy thông tin order: {e}")
        return jsonify({"error": "Lỗi hệ thống"}), 500

# API test để kiểm tra extract order id
@app.route('/api/test-extract', methods=['POST'])
def test_extract():
    """API test trích xuất Order ID"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        order_id = extract_order_id(content)
        
        return jsonify({
            "content": content,
            "extracted_order_id": order_id,
            "success": bool(order_id)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

# requirements.txt
"""
Flask==2.3.3
pyodbc==5.0.1
"""

# Test với nội dung thực tế:
"""
curl -X POST http://localhost:8000/api/test-extract \
  -H "Content-Type: application/json" \
  -d '{
    "content": "MBVCB.9737451341.677798.47b79bbde90d46f7af6724c12a575d56.CT tu 1020608460 DANG HA NHU THIEN toi 20499761 DANG HA NHU THIEN tai ACB GD 677798-060425 22:32:01"
  }'
"""

# Test webhook với dữ liệu thực tế:
"""
curl -X POST https://webhook-python-11q6.onrender.com/sepay-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "gateway":"ACB",
    "transactionDate":"2025-06-04 22:32:01",
    "accountNumber":"20499761",
    "subAccount":null,
    "code":null,
    "content":"MBVCB.9737451341.677798.47b79bbde90d46f7af6724c12a575d56.CT tu 1020608460 DANG HA NHU THIEN toi 20499761 DANG HA NHU THIEN tai ACB GD 677798-060425 22:32:01",
    "transferType":"in",
    "description":"BankAPINotify MBVCB.9737451341.677798.47b79bbde90d46f7af6724c12a575d56.CT tu 1020608460 DANG HA NHU THIEN toi 20499761 DANG HA NHU THIEN tai ACB"
  }'
"""