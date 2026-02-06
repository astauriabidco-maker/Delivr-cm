"""
Django settings for DELIVR-CM project.
Plateforme Logistique Décentralisée Cameroun

Configuration optimisée pour:
- PostGIS (géolocalisation)
- Redis/Celery (tâches asynchrones)
- JWT Authentication (API)
"""

import os
from pathlib import Path
from decouple import config, Csv
from datetime import timedelta

# ===========================================
# BASE CONFIGURATION
# ===========================================
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0', cast=Csv())

# ===========================================
# APPLICATION DEFINITION
# ===========================================
INSTALLED_APPS = [
    # Django Core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    
    # Daphne MUST be before staticfiles
    'daphne',  # ASGI server for WebSocket support
    'channels',  # Django Channels for real-time
    
    'django.contrib.staticfiles',
    
    # GeoDjango (PostGIS)
    'django.contrib.gis',
    
    # Third Party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    
    # DELIVR-CM Apps
    'core.apps.CoreConfig',
    'logistics.apps.LogisticsConfig',
    'finance.apps.FinanceConfig',
    'bot.apps.BotConfig',
    'partners.apps.PartnersConfig',
    'home.apps.HomeConfig',
    'integrations.apps.IntegrationsConfig',
    'courier.apps.CourierConfig',      # Courier dashboard
    'fleet.apps.FleetConfig',          # Fleet management admin
    'reports.apps.ReportsConfig',      # PDF reports
    
    # API Documentation & Keys
    'drf_spectacular',
    'rest_framework_api_key',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'delivr_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'delivr_core.wsgi.application'

# ===========================================
# DATABASE - PostgreSQL + PostGIS
# ===========================================
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='delivr_db'),
        'USER': config('DB_USER', default='delivr_user'),
        'PASSWORD': config('DB_PASSWORD', default='delivr_secret_2024'),
        'HOST': config('DB_HOST', default='db'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ===========================================
# CUSTOM USER MODEL
# ===========================================
AUTH_USER_MODEL = 'core.User'

# ===========================================
# PASSWORD VALIDATION
# ===========================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ===========================================
# INTERNATIONALIZATION (Cameroun)
# ===========================================
LANGUAGE_CODE = 'fr-cm'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

# ===========================================
# STATIC & MEDIA FILES
# ===========================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ===========================================
# DEFAULT PRIMARY KEY
# ===========================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===========================================
# DJANGO CHANNELS (WebSocket Real-time)
# ===========================================
ASGI_APPLICATION = 'delivr_core.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://redis:6379/1')],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# ===========================================
# DJANGO REST FRAMEWORK
# ===========================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ===========================================
# API DOCUMENTATION (drf-spectacular)
# ===========================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'DELIVR-CM API',
    'DESCRIPTION': 'API de logistique pour E-commerce au Cameroun',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ===========================================
# JWT CONFIGURATION
# ===========================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ===========================================
# CORS (Cross-Origin Resource Sharing)
# ===========================================
CORS_ALLOW_ALL_ORIGINS = True  # Development only - allow all origins
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:5050',
    cast=Csv()
)
CORS_ALLOW_CREDENTIALS = True

# ===========================================
# REDIS & CELERY CONFIGURATION
# ===========================================
REDIS_URL = config('REDIS_URL', default='redis://redis:6379/0')

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# Celery
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule (Periodic Tasks)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Send daily summary to couriers at 21:00 local time
    'send-daily-summaries': {
        'task': 'bot.tasks.send_all_daily_summaries',
        'schedule': crontab(hour=21, minute=0),
    },
    # Check for pending pickup reminders every 15 minutes
    'check-pending-reminders': {
        'task': 'bot.tasks.check_pending_reminders',
        'schedule': crontab(minute='*/15'),
    },
    # Check for high debt warnings every hour
    'check-debt-warnings': {
        'task': 'bot.tasks.check_debt_warnings',
        'schedule': crontab(minute=0),  # Every hour at :00
    },
}

# ===========================================
# EXTERNAL SERVICES (Self-Hosted)
# ===========================================

# OSRM Routing Service
OSRM_BASE_URL = config('OSRM_BASE_URL', default='http://osrm:5000')

# Nominatim Geocoding
NOMINATIM_BASE_URL = config('NOMINATIM_BASE_URL', default='http://nominatim:8080')

# ===========================================
# WHATSAPP PROVIDER CONFIGURATION
# ===========================================
# Toggle between providers: 'twilio' or 'meta'
ACTIVE_WHATSAPP_PROVIDER = config('ACTIVE_WHATSAPP_PROVIDER', default='twilio')

# -------------------------------------------
# META WHATSAPP CLOUD API
# -------------------------------------------
META_API_URL = config('META_API_URL', default='https://graph.facebook.com/v17.0')
META_API_TOKEN = config('META_API_TOKEN', default='')
META_PHONE_NUMBER_ID = config('META_PHONE_NUMBER_ID', default='')
META_VERIFY_TOKEN = config('META_VERIFY_TOKEN', default='delivr-cm-webhook-verify-token')

# Legacy aliases (for backward compatibility)
WHATSAPP_API_URL = META_API_URL
WHATSAPP_PHONE_NUMBER_ID = META_PHONE_NUMBER_ID
WHATSAPP_ACCESS_TOKEN = META_API_TOKEN
WHATSAPP_WEBHOOK_VERIFY_TOKEN = META_VERIFY_TOKEN

# -------------------------------------------
# TWILIO WHATSAPP INTEGRATION
# -------------------------------------------
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_WHATSAPP_NUMBER = config('TWILIO_WHATSAPP_NUMBER', default='whatsapp:+14155238886')  # Twilio Sandbox

# -------------------------------------------
# ORANGE CAMEROUN SMS API (Fallback)
# -------------------------------------------
ORANGE_SMS_CLIENT_ID = config('ORANGE_SMS_CLIENT_ID', default='')
ORANGE_SMS_CLIENT_SECRET = config('ORANGE_SMS_CLIENT_SECRET', default='')
ORANGE_SMS_SENDER = config('ORANGE_SMS_SENDER', default='DELIVR-CM')
SMS_FALLBACK_ENABLED = config('SMS_FALLBACK_ENABLED', default=False, cast=bool)

# -------------------------------------------
# MTN MOBILE MONEY API
# -------------------------------------------
MTN_MOMO_SUBSCRIPTION_KEY = config('MTN_MOMO_SUBSCRIPTION_KEY', default='')
MTN_MOMO_API_USER = config('MTN_MOMO_API_USER', default='')
MTN_MOMO_API_KEY = config('MTN_MOMO_API_KEY', default='')
MTN_MOMO_ENVIRONMENT = config('MTN_MOMO_ENVIRONMENT', default='sandbox')
MTN_MOMO_CALLBACK_URL = config('MTN_MOMO_CALLBACK_URL', default='')
MTN_MOMO_WEBHOOK_SECRET = config('MTN_MOMO_WEBHOOK_SECRET', default='')

# -------------------------------------------
# ORANGE MONEY WEBPAYMENT API
# -------------------------------------------
ORANGE_MONEY_MERCHANT_KEY = config('ORANGE_MONEY_MERCHANT_KEY', default='')
ORANGE_MONEY_MERCHANT_SECRET = config('ORANGE_MONEY_MERCHANT_SECRET', default='')
ORANGE_MONEY_ENVIRONMENT = config('ORANGE_MONEY_ENVIRONMENT', default='sandbox')
ORANGE_MONEY_CALLBACK_URL = config('ORANGE_MONEY_CALLBACK_URL', default='')
ORANGE_MONEY_RETURN_URL = config('ORANGE_MONEY_RETURN_URL', default='')


# ===========================================
# BUSINESS RULES - PRICING ENGINE
# ===========================================
PRICING_BASE_FARE = config('PRICING_BASE_FARE', default=500, cast=int)           # XAF
PRICING_COST_PER_KM = config('PRICING_COST_PER_KM', default=150, cast=int)       # XAF/km
PRICING_MINIMUM_FARE = config('PRICING_MINIMUM_FARE', default=1000, cast=int)    # XAF
PLATFORM_FEE_PERCENT = config('PLATFORM_FEE_PERCENT', default=20, cast=int)       # %
COURIER_DEBT_CEILING = config('COURIER_DEBT_CEILING', default=2500, cast=int)    # XAF

# ===========================================
# LOGGING CONFIGURATION
# ===========================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
