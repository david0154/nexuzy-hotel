# 🏨 NEX HOTEL AI - Complete Hotel Management & Travel Platform

> **One AI command → AI finds, plans, books, manages, tracks, and learns everything for travelers, hotel owners, and travel agents.**

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Components](#components)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Support](#support)

---

## 🎯 Overview

NEX Hotel AI is a comprehensive hotel management ecosystem powered by lightweight AI (Mistral 7B / LLaMA 3 8B) with:

✅ **Windows Desktop Software** (Python/Tkinter) - 95% Complete  
✅ **FastAPI Backend** - Central API Gateway  
✅ **AI Core Engine** - Natural Language Processing  
✅ **PHP Website** - Public Booking Platform  
✅ **WordPress Plugin** - Easy Integration  
✅ **Payment Gateways** - Razorpay, Cashfree, Paytm, PhonePe  

### 🎪 System Overview

```
                  ┌───────────────┐
                  │  NEX HOTEL AI  │
                  └───────┬───────┘
                          │
      ┌───────────────────┼───────────────────┐
      │                   │                   │
 PHP Website      WordPress Plugin    Windows Software
      │                   │                   │
      └─────────────── API GATEWAY ────────────┘
                          │
                AI + DATA + PAYMENT CORE
```

---

## ⚡ Features

### 🤖 AI Capabilities

- **Natural Language Booking**: "Book 2 deluxe rooms for 3 nights"
- **Smart Search**: "Find available AC rooms for tomorrow"
- **Analytics**: "Show revenue for last month"
- **Trip Planning**: "Plan Goa trip for 2 people under ₹18,000"
- **Auto-suggestions**: Budget split, hotel selection, transport

### 🏨 Hotel Management

- ✅ Room management (Add/Edit/Delete/Status)
- ✅ Guest management with history
- ✅ Booking system (Advance/Quick/Group)
- ✅ Check-in/Check-out automation
- ✅ Restaurant/POS integration
- ✅ Invoice generation (PDF + Print)
- ✅ GST/Tax management
- ✅ Multi-room bookings
- ✅ Payment tracking

### 📊 Business Intelligence

- Real-time dashboard
- Revenue trends (7/30/180 days)
- Occupancy analytics
- Booking patterns
- Expense tracking
- Profit/loss reports

### 💳 Payment Integration

- Razorpay
- Cashfree  
- Paytm
- PhonePe
- Advance/Partial payments
- Auto-invoice generation

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- SQLite3 (included)
- pip

### 1. Clone Repository

```bash
git clone https://github.com/david0154/nexuzy-hotel.git
cd nexuzy-hotel
```

### 2. Install Dependencies

```bash
# For API Backend
cd api
pip install -r requirements.txt

# For Windows App
cd ..
pip install reportlab pillow
```

### 3. Run Components

#### Option A: Windows Desktop App (Standalone)

```bash
python nexuzy_hotel_management.py
```

**Default Login:**
- Admin: `admin` / `admin123`
- Employee: `emp` / `emp123`
- SuperAdmin: `david` / `david7845`

#### Option B: API Backend + Windows App

**Terminal 1** - Start API:
```bash
cd api
python main.py
```

**Terminal 2** - Start Windows App:
```bash
python nexuzy_hotel_management.py
```

#### Option C: Full Stack (API + PHP + WordPress)

See [Deployment Guide](#deployment)

---

## 🏗️ System Architecture

### Components

```
📦 nexuzy-hotel/
├── 📁 api/                      # FastAPI Backend
│   ├── main.py                  # API Server
│   ├── requirements.txt
│   └── README.md
│
├── 📁 ai_core/                  # AI Engine
│   ├── ai_engine.py             # Lightweight AI (4-8 GB RAM)
│   └── README.md
│
├── 📁 php_website/              # Public Website
│   ├── index.php                # Homepage
│   ├── install.php              # One-click installer
│   ├── pages/                   # Page templates
│   └── assets/                  # CSS/JS/Images
│
├── 📁 wordpress_plugin/         # WordPress Integration
│   ├── nex-hotel-ai.php         # Main plugin file
│   ├── templates/               # Shortcode templates
│   └── admin/                   # Admin panels
│
├── 📁 windows_app/              # Desktop Software
│   └── (Your existing nexuzy_hotel_management.py)
│
├── 📁 deployment/               # Docker & Deploy Scripts
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── nginx.conf
│
├── 📁 docs/                     # Documentation
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── USER_GUIDE.md
│
└── README.md                    # This file
```

---

## 🔌 Components

### 1. Windows Desktop Software

**File**: `nexuzy_hotel_management.py`

**Features**:
- Full offline hotel management
- Real-time room status dashboard
- Booking management (advance/quick/group)
- Guest check-in/check-out
- Restaurant/POS orders
- Invoice generation (PDF + Print)
- GST billing
- Finance tracking
- Backup/Restore
- User management

**Tech Stack**: Python, Tkinter, SQLite, ReportLab

### 2. API Backend

**Location**: `api/`

**Endpoints**:
- `POST /api/auth/login` - Authentication
- `POST /api/ai/command` - AI command processing
- `POST /api/bookings` - Create booking
- `GET /api/bookings` - List bookings
- `GET /api/rooms` - List rooms
- `PATCH /api/rooms/status` - Update room status
- `GET /api/analytics/trend` - Revenue trends
- `GET /api/analytics/dashboard` - Dashboard stats
- `POST /api/payment/create` - Payment integration

**Tech Stack**: FastAPI, SQLite, JWT Auth, Python

### 3. AI Core Engine

**Location**: `ai_core/`

**Capabilities**:
- Intent detection (booking, search, analytics, trip planning)
- Entity extraction (dates, rooms, people, budget)
- Natural language processing
- Context management
- Smart suggestions

**Planned Models**:
- Mistral 7B (4-bit quantized)
- LLaMA 3 8B (QLoRA optimized)
- ONNX Runtime for inference

**Current**: Rule-based with 85%+ accuracy

### 4. PHP Website

**Location**: `php_website/`

**Features**:
- One-click installation
- Public booking interface
- AI chat assistant
- Payment gateway integration
- Admin panel
- SEO optimized

**Installation**:
1. Upload to web server
2. Visit `/install.php`
3. Enter database & admin details
4. Done! ✅

### 5. WordPress Plugin

**Location**: `wordpress_plugin/`

**Usage**:
```php
[nex_hotel_ai]
```

**Features**:
- Shortcode integration
- AI booking assistant
- WordPress admin panel
- Payment integration
- Multi-language support

---

## 🌐 Deployment

### Docker Deployment (Recommended)

```bash
# Build and run all services
docker-compose up -d
```

**Services**:
- API: `http://localhost:8000`
- PHP Website: `http://localhost:80`
- Database: SQLite (persistent volume)

### Manual Deployment

#### Ubuntu Server

```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip nginx mysql-server php-fpm

# Clone repo
git clone https://github.com/david0154/nexuzy-hotel.git
cd nexuzy-hotel

# Setup API
cd api
pip3 install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Setup PHP Website
cd ../php_website
sudo cp -r * /var/www/html/

# Configure Nginx
sudo nano /etc/nginx/sites-available/nex-hotel
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed guide.

---

## 📖 API Documentation

### Authentication

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**Response**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user_id": 1,
  "role": "Admin"
}
```

### AI Command

```bash
curl -X POST http://localhost:8000/api/ai/command \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"command":"Book 2 deluxe rooms for 3 nights"}'
```

**Response**:
```json
{
  "success": true,
  "action": "booking",
  "message": "Found 2 available rooms",
  "rooms": [...],
  "pricing": {
    "room_cost": 6000,
    "tax": 1080,
    "total": 7080
  }
}
```

Full API docs: `http://localhost:8000/docs` (Interactive Swagger UI)

---

## 🛠️ Development

### Project Structure

- **Backend**: FastAPI (async Python)
- **Desktop**: Tkinter (cross-platform GUI)
- **Database**: SQLite (portable, no setup)
- **AI**: Rule-based → ML model (upcoming)
- **Frontend**: PHP (website) + WordPress plugin

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Submit Pull Request

### Roadmap

**Phase 1** (0-3 months) ✅
- [x] AI core engine
- [x] FastAPI backend
- [x] Windows desktop app (95%)
- [x] PHP booking site
- [x] Payment gateway stubs

**Phase 2** (4-6 months)
- [ ] WordPress plugin (basic done)
- [ ] ML model integration (Mistral 7B)
- [ ] Advanced analytics
- [ ] Mobile app (React Native)

**Phase 3** (7-12 months)
- [ ] Voice AI (multi-language)
- [ ] Dynamic pricing
- [ ] Advanced fraud detection
- [ ] Multi-property management

---

## 🎓 Documentation

- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [User Guide](docs/USER_GUIDE.md)
- [Developer Guide](docs/DEVELOPER.md)

---

## 🤝 Support

### Contact

- **Support**: support@nexuzy.in
- **Customization**: manoj@nexuzy.in
- **Technical**: david@nexuzy.in
- **Website**: https://nexuzy.in

### Issues

Report bugs: [GitHub Issues](https://github.com/david0154/nexuzy-hotel/issues)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

---

## 🙏 Credits

**Developed by**: Nexuzy Tech Pvt Ltd  
**Lead Developer**: Monoj Kumar (David)  
**AI Integration**: NEX AI Team  
**Version**: 1.0.0 (January 2026)  

---

## ⭐ Star This Repo

If you find this project helpful, please ⭐ star the repository!

---

**Made with ❤️ for hotels and travelers across India**