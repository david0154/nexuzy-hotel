# NEX Hotel AI - FastAPI Backend
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import jwt
import datetime
import hashlib
import os
from contextlib import contextmanager

app = FastAPI(title="NEX Hotel AI API", version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production-2026")
ALGORITHM = "HS256"
DB_PATH = "../nexuzy_hotel.db"

# Database connection helper
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Pydantic Models
class UserLogin(BaseModel):
    username: str
    password: str

class AICommand(BaseModel):
    command: str
    user_id: Optional[int] = None

class BookingRequest(BaseModel):
    guest_name: str
    phone: str
    email: Optional[str] = None
    check_in: str  # YYYY-MM-DD
    check_out: str  # YYYY-MM-DD
    room_type: Optional[str] = None
    num_adults: int = 1
    num_children: int = 0
    budget: Optional[float] = None

class RoomStatus(BaseModel):
    room_id: int
    status: str  # Available, Occupied, Maintenance

# Authentication Helper
def create_token(user_id: int, role: str):
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Header(...)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============= API ENDPOINTS =============

@app.get("/")
async def root():
    return {
        "message": "NEX Hotel AI API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth/login",
            "ai": "/api/ai/command",
            "bookings": "/api/bookings",
            "rooms": "/api/rooms",
            "analytics": "/api/analytics/trend"
        }
    }

# ============= AUTHENTICATION =============

@app.post("/api/auth/login")
async def login(user: UserLogin):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, role FROM users WHERE username = ? AND password = ?",
            (user.username, user.password)
        )
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_id = result[0]
        role = result[1]
        token = create_token(user_id, role)
        
        return {
            "token": token,
            "user_id": user_id,
            "role": role,
            "message": "Login successful"
        }

# ============= AI COMMAND PROCESSING =============

@app.post("/api/ai/command")
async def process_ai_command(command: AICommand, payload: dict = Depends(verify_token)):
    """
    Process natural language commands like:
    - "Find 2 rooms for 3 nights starting tomorrow"
    - "Show me revenue for last week"
    - "Book deluxe room for John from 20-25 Jan"
    """
    cmd_lower = command.command.lower()
    
    # Simple keyword-based AI (will be replaced with actual AI model)
    if "book" in cmd_lower or "reserve" in cmd_lower:
        return await ai_handle_booking(command.command)
    elif "revenue" in cmd_lower or "income" in cmd_lower:
        return await ai_handle_analytics(command.command)
    elif "available" in cmd_lower or "rooms" in cmd_lower:
        return await ai_handle_room_search(command.command)
    else:
        return {
            "response": "I understand you want to: " + command.command,
            "action": "general_query",
            "suggestions": [
                "Try: 'Find available rooms for tomorrow'",
                "Try: 'Show revenue for last 7 days'",
                "Try: 'Book a deluxe room for 2 nights'"
            ]
        }

async def ai_handle_booking(command: str):
    # Extract booking details from natural language (simplified)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rooms WHERE status='Available'")
        available = cursor.fetchone()[0]
    
    return {
        "response": f"Found {available} available rooms. Please provide check-in/out dates.",
        "action": "booking_request",
        "available_rooms": available
    }

async def ai_handle_analytics(command: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE(check_out) as date, SUM(total_amount) as revenue
            FROM bookings
            WHERE status='Checked-Out' AND check_out >= date('now', '-7 days')
            GROUP BY DATE(check_out)
            ORDER BY date DESC
        """)
        data = [dict(row) for row in cursor.fetchall()]
    
    total = sum(row['revenue'] or 0 for row in data)
    return {
        "response": f"Revenue for last 7 days: ₹{total:.2f}",
        "action": "analytics",
        "data": data
    }

async def ai_handle_room_search(command: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT room_number, room_type, bed_type, rate, status
            FROM rooms WHERE status='Available'
            ORDER BY rate
        """)
        rooms = [dict(row) for row in cursor.fetchall()]
    
    return {
        "response": f"Found {len(rooms)} available rooms",
        "action": "room_list",
        "rooms": rooms
    }

# ============= BOOKING MANAGEMENT =============

@app.post("/api/bookings")
async def create_booking(booking: BookingRequest, payload: dict = Depends(verify_token)):
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Find available room
        query = "SELECT id FROM rooms WHERE status='Available'"
        if booking.room_type:
            query += f" AND room_type='{booking.room_type}'"
        query += " LIMIT 1"
        
        cursor.execute(query)
        room = cursor.fetchone()
        
        if not room:
            raise HTTPException(status_code=404, detail="No rooms available")
        
        room_id = room[0]
        
        # Create guest
        cursor.execute(
            "INSERT INTO guests (name, phone, email) VALUES (?, ?, ?)",
            (booking.guest_name, booking.phone, booking.email)
        )
        guest_id = cursor.lastrowid
        
        # Generate booking reference
        import random
        booking_ref = f"NEX{random.randint(10000, 99999)}"
        
        # Calculate total amount
        cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
        rate = cursor.fetchone()[0]
        
        from datetime import datetime
        ci = datetime.strptime(booking.check_in, "%Y-%m-%d")
        co = datetime.strptime(booking.check_out, "%Y-%m-%d")
        nights = (co - ci).days
        total = rate * nights
        
        # Create booking
        cursor.execute("""
            INSERT INTO bookings 
            (booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, num_adults, num_children)
            VALUES (?, ?, ?, ?, ?, 'Reserved', ?, ?, ?)
        """, (booking_ref, guest_id, room_id, booking.check_in, booking.check_out, total, booking.num_adults, booking.num_children))
        
        conn.commit()
        
        return {
            "booking_ref": booking_ref,
            "room_id": room_id,
            "total_amount": total,
            "nights": nights,
            "message": "Booking created successfully"
        }

@app.get("/api/bookings")
async def list_bookings(status: Optional[str] = None, payload: dict = Depends(verify_token)):
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT b.booking_ref, g.name, b.check_in, b.check_out, b.status, b.total_amount
            FROM bookings b
            JOIN guests g ON b.guest_id = g.id
        """
        if status:
            query += f" WHERE b.status='{status}'"
        query += " ORDER BY b.check_in DESC LIMIT 50"
        
        cursor.execute(query)
        bookings = [dict(row) for row in cursor.fetchall()]
        
        return {"bookings": bookings, "count": len(bookings)}

# ============= ROOM MANAGEMENT =============

@app.get("/api/rooms")
async def list_rooms(status: Optional[str] = None):
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM rooms"
        if status:
            query += f" WHERE status='{status}'"
        
        cursor.execute(query)
        rooms = [dict(row) for row in cursor.fetchall()]
        
        return {"rooms": rooms, "count": len(rooms)}

@app.patch("/api/rooms/status")
async def update_room_status(room_status: RoomStatus, payload: dict = Depends(verify_token)):
    if payload['role'] not in ['Admin', 'SuperAdmin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE rooms SET status=? WHERE id=?",
            (room_status.status, room_status.room_id)
        )
        conn.commit()
        
        return {"message": "Room status updated", "room_id": room_status.room_id}

# ============= ANALYTICS =============

@app.get("/api/analytics/trend")
async def get_trends(days: int = 30, payload: dict = Depends(verify_token)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE(check_out) as date,
                COUNT(*) as bookings,
                SUM(total_amount) as revenue
            FROM bookings
            WHERE status='Checked-Out' 
            AND check_out >= date('now', ? || ' days')
            GROUP BY DATE(check_out)
            ORDER BY date
        """, (f'-{days}',))
        
        trends = [dict(row) for row in cursor.fetchall()]
        
        return {
            "period_days": days,
            "trends": trends,
            "total_revenue": sum(t['revenue'] or 0 for t in trends),
            "total_bookings": sum(t['bookings'] for t in trends)
        }

@app.get("/api/analytics/dashboard")
async def dashboard_stats(payload: dict = Depends(verify_token)):
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Total rooms by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM rooms
            GROUP BY status
        """)
        room_stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Today's bookings
        cursor.execute("""
            SELECT COUNT(*) FROM bookings
            WHERE DATE(check_in) = DATE('now')
        """)
        today_bookings = cursor.fetchone()[0]
        
        # Revenue this month
        cursor.execute("""
            SELECT SUM(total_amount) FROM bookings
            WHERE status='Checked-Out'
            AND strftime('%Y-%m', check_out) = strftime('%Y-%m', 'now')
        """)
        month_revenue = cursor.fetchone()[0] or 0
        
        return {
            "room_stats": room_stats,
            "today_bookings": today_bookings,
            "month_revenue": month_revenue
        }

# ============= PAYMENT INTEGRATION =============

@app.post("/api/payment/create")
async def create_payment(booking_ref: str, amount: float, gateway: str = "razorpay"):
    # Integration with payment gateways will be added here
    return {
        "payment_id": f"pay_{booking_ref}_{int(datetime.datetime.now().timestamp())}",
        "booking_ref": booking_ref,
        "amount": amount,
        "gateway": gateway,
        "status": "pending"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)