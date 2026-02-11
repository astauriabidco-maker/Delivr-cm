---
description: How to deploy DELIVR-CM to a staging VPS server
---

# 🚀 Deploy DELIVR-CM to Staging VPS

## Prerequisites

- A VPS with Ubuntu 22.04+ (minimum 2GB RAM, 2 vCPU)
- Docker & Docker Compose installed
- Domain name pointing to VPS IP (e.g., `staging.delivr.cm`)
- SSH access to the VPS

## Step 1: Connect to VPS

```bash
ssh root@YOUR_VPS_IP
```

## Step 2: Install Docker (if not installed)

```bash
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin
```

## Step 3: Clone the repository

```bash
cd /opt
git clone https://github.com/astauriabidco-maker/Delivr-cm.git delivr-cm
cd delivr-cm
```

## Step 4: Configure environment

```bash
cp .env.example .env
nano .env
```

**Critical variables to change for staging:**

```env
# Django
DEBUG=False
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))">
ALLOWED_HOSTS=staging.delivr.cm,YOUR_VPS_IP

# Database (use strong password)
DB_PASSWORD=<strong-random-password>

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# BASE_URL for tracking links
BASE_URL=https://staging.delivr.cm

# WhatsApp (for real notifications, configure one provider)
ACTIVE_WHATSAPP_PROVIDER=meta
META_API_TOKEN=<your-meta-api-token>
META_PHONE_NUMBER_ID=<your-phone-number-id>
META_VERIFY_TOKEN=<your-verify-token>
```

## Step 5: Build and start services

// turbo
```bash
docker compose build --no-cache
```

// turbo
```bash
docker compose up -d
```

## Step 6: Apply migrations

// turbo
```bash
docker compose exec web python manage.py migrate
```

## Step 7: Create superuser

```bash
docker compose exec -it web python manage.py createsuperuser
```

When prompted, enter:
- Phone: `+237XXXXXXXXX` (your admin phone)
- Password: `<strong-password>`

## Step 8: Collect static files

// turbo
```bash
docker compose exec web python manage.py collectstatic --noinput
```

## Step 9: Initialize default configs

// turbo
```bash
docker compose exec web python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'delivr_core.settings')
django.setup()
from bot.models import NotificationConfiguration
from logistics.models import DispatchConfiguration
nc = NotificationConfiguration.get_config()
dc = DispatchConfiguration.get_config()
print(f'Notifications: {nc.summary}')
print(f'Dispatch: Rayon {dc.initial_radius_km}-{dc.max_radius_km}km, Weights valid: {dc.weights_valid}')
print('✅ Default configurations initialized!')
"
```

## Step 10: Setup Nginx reverse proxy (optional but recommended)

```bash
apt install -y nginx certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/delivr-cm << 'EOF'
server {
    server_name staging.delivr.cm;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/delivr-cm/staticfiles/;
    }

    location /media/ {
        alias /opt/delivr-cm/media/;
    }
}
EOF

ln -sf /etc/nginx/sites-available/delivr-cm /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# SSL certificate
certbot --nginx -d staging.delivr.cm
```

## Step 11: Verify deployment

// turbo
```bash
docker compose ps
docker compose exec web python manage.py check --deploy
```

**Check health:**
```bash
curl -s http://localhost:8000/health/ | python3 -m json.tool
```

## Post-deployment

### Access points:
- **Fleet Dashboard:** `https://staging.delivr.cm/fleet/`
- **Partner Space:** `https://staging.delivr.cm/partners/`
- **Django Admin:** `https://staging.delivr.cm/admin/`
- **API Docs:** `https://staging.delivr.cm/api/docs/`
- **Settings (super-admin):** `https://staging.delivr.cm/fleet/settings/`

### Monitor logs:
```bash
docker compose logs -f web          # Django logs
docker compose logs -f celery_worker # Task execution
docker compose logs -f celery_beat   # Scheduled tasks
```

### Restart after code update:
```bash
cd /opt/delivr-cm
git pull origin main
docker compose build web
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

### WhatsApp Webhook URL:
Configure this in your Meta/Twilio dashboard:
```
https://staging.delivr.cm/bot/webhook/
```
