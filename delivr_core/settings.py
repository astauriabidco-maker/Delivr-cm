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
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
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

# ===========================================
# EXTERNAL SERVICES (Self-Hosted)
# ===========================================

# OSRM Routing Service
OSRM_BASE_URL = config('OSRM_BASE_URL', default='http://osrm:5000')

# Nominatim Geocoding
NOMINATIM_BASE_URL = config('NOMINATIM_BASE_URL', default='http://nominatim:8080')

# ===========================================
# WHATSAPP BUSINESS API
# ===========================================
WHATSAPP_API_URL = config('WHATSAPP_API_URL', default='https://graph.facebook.com/v18.0')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_WEBHOOK_VERIFY_TOKEN = config('WHATSAPP_WEBHOOK_VERIFY_TOKEN', default='')

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
