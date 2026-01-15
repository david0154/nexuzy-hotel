# NEX Hotel AI - API Backend

## Quick Start

### 1. Install Dependencies
```bash
cd api
pip install -r requirements.txt
```

### 2. Run API Server
```bash
python main.py
```

API will be available at: `http://localhost:8000`

### 3. View API Documentation
Open browser: `http://localhost:8000/docs`

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login and get JWT token

### AI Commands
- `POST /api/ai/command` - Process natural language commands

### Bookings
- `POST /api/bookings` - Create new booking
- `GET /api/bookings` - List bookings

### Rooms
- `GET /api/rooms` - List rooms
- `PATCH /api/rooms/status` - Update room status

### Analytics
- `GET /api/analytics/trend` - Revenue trends
- `GET /api/analytics/dashboard` - Dashboard statistics

### Payment
- `POST /api/payment/create` - Create payment

## Authentication

All protected endpoints require JWT token in header:
```
Authorization: Bearer <token>
```

## Example Usage

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### AI Command
```bash
curl -X POST http://localhost:8000/api/ai/command \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"command":"Find available rooms for tomorrow"}'
```

## Environment Variables

- `JWT_SECRET_KEY` - Secret key for JWT tokens (change in production)
- `DB_PATH` - Path to SQLite database (default: ../nexuzy_hotel.db)

## Production Deployment

### Using Docker
```bash
docker build -t nex-hotel-api .
docker run -p 8000:8000 nex-hotel-api
```

### Using systemd (Ubuntu)
```bash
sudo systemctl enable nex-hotel-api
sudo systemctl start nex-hotel-api
```