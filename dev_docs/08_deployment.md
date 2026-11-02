# Deployment

## Docker Production Deployment

### Build and Run

```bash
# Build the production image
docker build -t my-project .

# Run with docker-compose
docker compose -f docker-compose.prod.yml up -d
```

### Environment Variables

Create a `.env` file with production values:

```env
DEBUG=False
SECRET_KEY=<generate-a-secure-50-char-key>
DJANGO_SETTINGS_MODULE=config.settings.production
DATABASE_URL=postgresql://user:password@db:5432/mydb
ALLOWED_HOSTS=api.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com
CELERY_BROKER_URL=redis://redis:6379/0
DISABLE_SWAGGER=True
```

## VPS Deployment (Manual)

### 1. Server Setup

```bash
# Install dependencies
sudo apt update && sudo apt install -y python3.12 python3.12-venv nginx postgresql redis

# Clone project
git clone <repo-url> /var/www/myproject
cd /var/www/myproject

# Setup
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/production.txt
cp .env.example .env
# Edit .env with production values

# Migrate and collect static
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py createsuperuser
```

### 2. Gunicorn Service

Create `/etc/systemd/system/myproject.service`:

```ini
[Unit]
Description=MyProject Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/myproject
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/var/www/myproject/.venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --access-logfile -

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable myproject
sudo systemctl start myproject
```

### 3. Celery Service

Create `/etc/systemd/system/myproject-celery.service`:

```ini
[Unit]
Description=MyProject Celery Worker
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/myproject
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/var/www/myproject/.venv/bin/celery -A config worker --loglevel=info --concurrency=4

[Install]
WantedBy=multi-user.target
```

### 4. Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location /static/ {
        alias /var/www/myproject/staticfiles/;
    }

    location /media/ {
        alias /var/www/myproject/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5. SSL with Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
```

## Health Check

Always verify after deployment:
```bash
curl https://api.yourdomain.com/health/
# Should return: {"status": "ok"}
```
