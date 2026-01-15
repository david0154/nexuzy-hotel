# NEX Hotel AI - Deployment Guide

## Quick Deploy with Docker

### Prerequisites
- Docker
- Docker Compose

### Steps

1. **Clone Repository**
```bash
git clone https://github.com/david0154/nexuzy-hotel.git
cd nexuzy-hotel
```

2. **Configure Environment**
```bash
cp deployment/.env.example deployment/.env
nano deployment/.env  # Edit as needed
```

3. **Build and Run**
```bash
cd deployment
docker-compose up -d
```

4. **Access Services**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Website: http://localhost:80

## Production Deployment

### Ubuntu Server (20.04/22.04)

#### 1. Install Dependencies
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv nginx mysql-server
```

#### 2. Setup API Backend
```bash
cd /var/www/nex-hotel-api
git clone https://github.com/david0154/nexuzy-hotel.git .
python3 -m venv venv
source venv/bin/activate
pip install -r api/requirements.txt
```

#### 3. Create Systemd Service
```bash
sudo nano /etc/systemd/system/nex-hotel-api.service
```

Add:
```ini
[Unit]
Description=NEX Hotel API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/nex-hotel-api/api
ExecStart=/var/www/nex-hotel-api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 4. Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable nex-hotel-api
sudo systemctl start nex-hotel-api
sudo systemctl status nex-hotel-api
```

#### 5. Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/nex-hotel
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location / {
        root /var/www/html/nex-hotel;
        index index.php index.html;
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
    }
}
```

#### 6. Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/nex-hotel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 7. Setup SSL (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Windows Server Deployment

### 1. Install Python
Download and install Python 3.11+ from python.org

### 2. Install API as Windows Service
```powershell
pip install pywin32
python api/install_service.py install
```

### 3. Start Service
```powershell
net start NEXHotelAPI
```

## Environment Variables

```bash
# API
JWT_SECRET_KEY=your-secret-key-here
DB_PATH=/path/to/nexuzy_hotel.db

# PHP Website
DB_HOST=localhost
DB_NAME=nex_hotel
DB_USER=root
DB_PASS=password
API_URL=http://localhost:8000
```

## Monitoring

### Check API Status
```bash
curl http://localhost:8000/
```

### View Logs
```bash
# API logs
sudo journalctl -u nex-hotel-api -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Backup

### Database Backup
```bash
# Backup
sqlite3 nexuzy_hotel.db ".backup 'backup.db'"

# Restore
sqlite3 nexuzy_hotel.db ".restore 'backup.db'"
```

### Automated Backup Script
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/nex-hotel"
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
sqlite3 /var/www/nex-hotel-api/nexuzy_hotel.db ".backup '$BACKUP_DIR/backup_$DATE.db'"
find $BACKUP_DIR -name "backup_*.db" -mtime +30 -delete
```

### Setup Cron Job
```bash
crontab -e
```

Add:
```cron
0 2 * * * /usr/local/bin/backup-nex-hotel.sh
```

## Scaling

### Load Balancing (Multiple API Instances)
```nginx
upstream api_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}
```

### Database Replication
For high availability, consider:
- MySQL master-slave replication
- PostgreSQL instead of SQLite
- Redis for caching

## Troubleshooting

### API Not Starting
```bash
# Check logs
journalctl -u nex-hotel-api -n 50

# Check port
sudo netstat -tulpn | grep 8000

# Manual start for debugging
cd /var/www/nex-hotel-api/api
source ../venv/bin/activate
python main.py
```

### Database Issues
```bash
# Check permissions
ls -la nexuzy_hotel.db

# Fix permissions
chown www-data:www-data nexuzy_hotel.db
chmod 664 nexuzy_hotel.db
```

## Security Checklist

- [ ] Change default JWT secret key
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall (UFW)
- [ ] Disable root MySQL login
- [ ] Use strong passwords
- [ ] Enable fail2ban
- [ ] Regular security updates
- [ ] Database backups
- [ ] Rate limiting on API
- [ ] CORS configuration

## Support

For deployment issues:
- Email: support@nexuzy.in
- GitHub Issues: https://github.com/david0154/nexuzy-hotel/issues