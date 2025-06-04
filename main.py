# requirements.txt
"""
fastapi==0.104.1
uvicorn==0.24.0
pyodbc==5.0.1
python-multipart==0.0.6
pydantic==2.5.0
"""

# main.py
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import pyodbc
import re
import logging
from datetime import datetime
from typing import Optional
import json

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo FastAPI
app = FastAPI(title="SePay Webhook API", version="1.0.0")

# Cấu hình kết nối SQL Server
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-UI5VDN,1433;"
    "DATABASE=Cheese Cakes;"
    "UID=sctws;"
    "PWD=1;"
    "TrustServerCertificate=yes;"
)

# Models
class Order:
    def __init__(self, order_id: str, order_date: datetime = None,
                shipping_address: str = "", status: str = None,
                note: str = None, user_id: str = "",
                created_at: datetime = None, updated_at: datetime = None,
                payment_id: str = "", image_url: str = None,
                shipping_fee: int = 0, payment_status: str = None):
        self.order_id = order_id
        self.order_date = order_date
        self.shipping_address = shipping_address
        self.status = status
        self.note = note
        self.user_id = user_id
        self.created_at = created_at
        self.updated_at = updated_at
        self.payment_id = payment_id
        self.image_url = image_url
        self.shipping_fee = shipping_fee
        self.payment_status = payment_status

class SePayWebhookRequest(BaseModel):
    content: str
    transferAmount: float
    transferType: str
    accountNumber: Optional[str] = None
    gateway: Optional[str] = None
    transactionDate: Optional[str] = None
    id: Optional[str] = None
    referenceCode: Optional[str] = None
    description: Optional[str] = None

class WebhookResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

# Database functions
def get_db_connection():
    """Tạo kết nối đến SQL Server"""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        return conn
    except Exception as e:
        logger.error(f"Lỗi kết nối database: {e}")
        raise HTTPException(status_code=500, detail="Lỗi kết nối database")

def find_order_by_id(order_id: str) -> Optional[Order]:
    """Tìm order theo ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM Orders WHERE OrderId = ?"
            cursor.execute(query, order_id)
            row = cursor.fetchone()
            
            if row:
                return Order(
                    order_id=row.OrderId,
                    order_date=row.OrderDate,
                    shipping_address=row.ShippingAddress,
                    status=row.Status,
                    note=row.Note,
                    user_id=row.UserId,
                    created_at=row.CreatedAt,
                    updated_at=row.UpdatedAt,
                    payment_id=row.PaymentId,
                    image_url=row.ImageUrl,
                    shipping_fee=row.ShippingFee,
                    payment_status=row.PaymentStatus
                )
            return None
    except Exception as e:
        logger.error(f"Lỗi tìm order {order_id}: {e}")
        return None

def update_order_payment_status(order_id: str, payment_status: str = "Đã thanh toán") -> bool:
    """Cập nhật trạng thái thanh toán của order"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                UPDATE Orders 
                SET PaymentStatus = ?, UpdatedAt = ? 
                WHERE OrderId = ?
            """
            cursor.execute(query, payment_status, datetime.now(), order_id)
            conn.commit()
            
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Lỗi cập nhật order {order_id}: {e}")
        return False

def extract_order_id(content: str) -> str:
    """Trích xuất Order ID từ nội dung giao dịch"""
    if not content:
        return ""
    
    # Tìm GUID pattern trong nội dung
    guid_pattern = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
    match = re.search(guid_pattern, content)
    
    if match:
        return match.group(0)
    
    return ""

# API Endpoints
@app.get("/")
async def root():
    return {"message": "SePay Webhook API is running!"}

@app.post("/api/webhook/sepay", response_model=WebhookResponse)
async def sepay_webhook(request: SePayWebhookRequest):
    """Endpoint nhận webhook từ SePay"""
    try:
        logger.info(f"Received webhook: {request.content}")
        
        # Chỉ xử lý giao dịch tiền vào
        if request.transferType != "in" or request.transferAmount <= 0:
            logger.warning("Không phải giao dịch tiền vào")
            return WebhookResponse(
                success=True, 
                message="Không phải giao dịch tiền vào"
            )
        
        # Trích xuất Order ID từ nội dung
        order_id = extract_order_id(request.content)
        if not order_id:
            logger.warning(f"Không tìm thấy Order ID trong: {request.content}")
            return WebhookResponse(
                success=False, 
                message="Không tìm thấy Order ID trong nội dung giao dịch"
            )
        
        # Tìm order trong database
        order = find_order_by_id(order_id)
        if not order:
            logger.warning(f"Không tìm thấy Order {order_id}")
            return WebhookResponse(
                success=False, 
                message=f"Không tìm thấy Order {order_id}"
            )
        
        # Cập nhật trạng thái thanh toán
        success = update_order_payment_status(order_id, "Đã thanh toán")
        if success:
            logger.info(f"Đã cập nhật Order {order_id} thành 'Đã thanh toán'")
            return WebhookResponse(
                success=True,
                message="Cập nhật trạng thái thanh toán thành công",
                data={
                    "order_id": order_id,
                    "payment_status": "Đã thanh toán",
                    "amount": request.transferAmount
                }
            )
        else:
            logger.error(f"Lỗi cập nhật Order {order_id}")
            return WebhookResponse(
                success=False, 
                message="Lỗi cập nhật trạng thái thanh toán"
            )
            
    except Exception as e:
        logger.error(f"Lỗi xử lý webhook: {e}")
        return WebhookResponse(
            success=False, 
            message="Lỗi hệ thống"
        )

@app.get("/api/order/{order_id}")
async def get_order(order_id: str):
    """API kiểm tra thông tin order"""
    order = find_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy order")
    
    return {
        "order_id": order.order_id,
        "status": order.status,
        "payment_status": order.payment_status,
        "shipping_address": order.shipping_address,
        "created_at": order.created_at,
        "updated_at": order.updated_at
    }

# Chạy server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

# Để test webhook local, tạo file test_webhook.py:
"""
import requests
import json

# Test data giống như SePay gửi
test_data = {
    "content": "HBVCB.9703482181.433578.DANG HA NHU THIEN chuyen tien 12345678-1234-1234-1234-123456789012",
    "transferAmount": 2000,
    "transferType": "in",
    "accountNumber": "20499761",
    "gateway": "ACB",
    "transactionDate": "2025-06-01 23:18:41"
}

response = requests.post("http://localhost:8000/api/webhook/sepay", json=test_data)
print(response.json())
"""