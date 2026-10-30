"""
Settings za JamiiLite 5G.

Mipangilio yote ya siri (database, Supabase, malipo) inasomwa kutoka kwenye
environment variables. Kwa kazi za ndani (local), weka kwenye faili `.env`
(angalia `.env.example`).
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY lazima iwekwe wakati DEBUG=False.")
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
# Render inaweka jina la huduma (mfano jamiilite.onrender.com) kwenye mazingira.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "core",
    "billing",
    "portal",
    "radius",
    "pages",
    "ui",
    "dashboard",
    "control",
]

LOGIN_URL = "dashboard:login"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "ui.middleware.UserLanguageMiddleware",
    "ui.middleware.UrlLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Database: Supabase Postgres -------------------------------------------
# Tumia connection string ya Supabase (Project Settings -> Database).
# Session pooler (port 5432) inafaa kwa Django. Ukitumia transaction pooler
# (port 6543), server-side cursors zinazimwa hapa chini kwa sababu pooler
# hiyo haiziwezi.
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    default_db = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
        ssl_require=env_bool("DB_SSL_REQUIRE", True),
    )
    if str(default_db.get("PORT")) == "6543":
        default_db["DISABLE_SERVER_SIDE_CURSORS"] = True
        default_db["CONN_MAX_AGE"] = 0
else:
    if not DEBUG:
        raise ImproperlyConfigured("DATABASE_URL lazima iwekwe wakati DEBUG=False.")
    default_db = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

DATABASES = {"default": default_db}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "sw"
# Lugha mbili: mmiliki anachagua anapojisajili, na anaweza kubadilisha wakati wowote.
# Maandishi ya asili (msgid) ni Kiswahili; tafsiri ya Kiingereza iko locale/en.
LANGUAGES = [("sw", "Kiswahili"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True


# --- Static & media --------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Picha (mfano logo za wamiliki) zinahifadhiwa kwenye Supabase Storage kupitia
# S3-compatible endpoint yake. Bucket iwe "public" ili picha zionekane kwenye
# ukurasa wa kulipia bila kuingia.
SUPABASE_PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "")
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "")
SUPABASE_S3_ACCESS_KEY_ID = os.environ.get("SUPABASE_S3_ACCESS_KEY_ID", "")
SUPABASE_S3_SECRET_ACCESS_KEY = os.environ.get("SUPABASE_S3_SECRET_ACCESS_KEY", "")
SUPABASE_S3_REGION = os.environ.get("SUPABASE_S3_REGION", "")

USE_SUPABASE_STORAGE = all(
    [
        SUPABASE_PROJECT_REF,
        SUPABASE_STORAGE_BUCKET,
        SUPABASE_S3_ACCESS_KEY_ID,
        SUPABASE_S3_SECRET_ACCESS_KEY,
        SUPABASE_S3_REGION,
    ]
)

if USE_SUPABASE_STORAGE:
    default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": SUPABASE_STORAGE_BUCKET,
            "endpoint_url": f"https://{SUPABASE_PROJECT_REF}.supabase.co/storage/v1/s3",
            "region_name": SUPABASE_S3_REGION,
            "access_key": SUPABASE_S3_ACCESS_KEY_ID,
            "secret_key": SUPABASE_S3_SECRET_ACCESS_KEY,
            "addressing_style": "path",
            "signature_version": "s3v4",
            "querystring_auth": False,
            "file_overwrite": False,
            "default_acl": None,
            # URL za picha zinapitia njia ya public objects ya Supabase.
            "custom_domain": (
                f"{SUPABASE_PROJECT_REF}.supabase.co/storage/v1/object/public/"
                f"{SUPABASE_STORAGE_BUCKET}"
            ),
        },
    }
else:
    # Server ya RADIUS haishughulikii picha, kwa hiyo inaweza kukaa bila keys hizi.
    if not DEBUG and not env_bool("JAMIILITE_NO_MEDIA", False):
        raise ImproperlyConfigured(
            "Weka SUPABASE_PROJECT_REF, SUPABASE_STORAGE_BUCKET, SUPABASE_S3_ACCESS_KEY_ID, "
            "SUPABASE_S3_SECRET_ACCESS_KEY na SUPABASE_S3_REGION wakati DEBUG=False."
        )
    default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
    MEDIA_URL = "media/"
    MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": default_storage,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}


# --- Malipo -----------------------------------------------------------------
# "sandbox" inathibitisha malipo papo hapo bila pesa halisi. Ni kwa majaribio
# tu, kwa hiyo inakataliwa DEBUG ikiwa False, isipokuwa
# ALLOW_SANDBOX_PAYMENTS=True imewekwa wazi.
PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "sandbox")
ALLOW_SANDBOX_PAYMENTS = env_bool("ALLOW_SANDBOX_PAYMENTS", DEBUG)


# --- RADIUS ------------------------------------------------------------------
# Kinga dhidi ya BlastRADIUS: Access-Request bila Message-Authenticator
# inakataliwa. RouterOS 7.15 na kuendelea inaituma. Zima tu kwa router za zamani.
RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR = env_bool("RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR", True)

# Anwani ambazo MikroTik (na wateja wake) wanaitumia kufikia mfumo huu. Kwa
# maabara ya VirtualBox, kompyuta mwenyeji inaonekana kama 10.0.2.2. Kwenye
# server halisi weka mfano https://jamiilite.co.tz na IP ya server.
JAMIILITE_PUBLIC_URL = os.environ.get("JAMIILITE_PUBLIC_URL", "http://10.0.2.2:8000")
RADIUS_PUBLIC_ADDRESS = os.environ.get("RADIUS_PUBLIC_ADDRESS", "10.0.2.2")

# Jinsi router inavyothibitisha vocha:
#   "local":  router inahifadhi vocha yenyewe, na JamiiLite inazituma kupitia
#             ripoti ya router (check-in). Haihitaji RADIUS server, kwa hiyo
#             mfumo mzima unaweza kukaa Render peke yake.
#   "radius": router inauliza RADIUS server (python manage.py radius_server),
#             ambayo inahitaji server yenye UDP 1812/1813.
JAMIILITE_AUTH_MODE = os.environ.get("JAMIILITE_AUTH_MODE", "local").strip().lower()
if JAMIILITE_AUTH_MODE not in {"local", "radius"}:
    raise ImproperlyConfigured("JAMIILITE_AUTH_MODE iwe 'local' au 'radius'.")
# Router inaripoti kila baada ya sekunde hizi. Ndogo = mteja anaunganishwa haraka
# baada ya kulipa (njia ya "local"), lakini maombi mengi zaidi kwa server.
JAMIILITE_CHECKIN_SECONDS = max(5, int(os.environ.get("JAMIILITE_CHECKIN_SECONDS", "10")))

# Idadi ya proxies mbele ya server (Render = 1). IP ya mtumiaji inasomwa kutoka X-Forwarded-For
# kulingana na hii, kwa ajili ya kuzuia majaribio mengi. 0 = tumia REMOTE_ADDR moja kwa moja.
JAMIILITE_PROXY_HOPS = int(os.environ.get("JAMIILITE_PROXY_HOPS", "0" if DEBUG else "1"))
# Hosts za ziada ambazo mteja anaruhusiwa kuzifikia kabla ya kulipa, mfano
# ukurasa wa malipo wa mtoa huduma: "checkout.example.co.tz,api.example.co.tz".
JAMIILITE_WALLED_GARDEN_EXTRA = env_list("JAMIILITE_WALLED_GARDEN_EXTRA")
# Interface ya LAN ambayo hotspot inawekwa ikiwa router haina hotspot bado.
# "bridge" ndiyo jina la default kwenye MikroTik mpya (hAP lite, hAP ac...).
JAMIILITE_HOTSPOT_INTERFACE = os.environ.get("JAMIILITE_HOTSPOT_INTERFACE", "bridge")


# --- Tovuti ya hadhara ---------------------------------------------------------
# Namba ya WhatsApp ya kupokea wateja wapya (bila +), mfano 255712345678.
JAMIILITE_WHATSAPP_NUMBER = os.environ.get("JAMIILITE_WHATSAPP_NUMBER", "").lstrip("+")


# --- Biashara ya JamiiLite -----------------------------------------------------
# Ada ya mmiliki kwa mwezi, na siku za majaribio bure kwa mmiliki mpya.
JAMIILITE_MONTHLY_FEE = int(os.environ.get("JAMIILITE_MONTHLY_FEE", "10000"))
JAMIILITE_TRIAL_DAYS = int(os.environ.get("JAMIILITE_TRIAL_DAYS", "14"))
# Asilimia inayokatwa kwenye kila mauzo kufidia ada za mtoa huduma wa malipo
# (Selcom/AzamPay...). 0 = mmiliki anapata kiasi chote.
JAMIILITE_SALE_FEE_PERCENT = int(os.environ.get("JAMIILITE_SALE_FEE_PERCENT", "0"))
JAMIILITE_MIN_WITHDRAWAL = int(os.environ.get("JAMIILITE_MIN_WITHDRAWAL", "1000"))


# --- Usalama wa production ---------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
    # Browser ikumbuke kutumia HTTPS tu (hata mtu akiandika http:// kwenye WiFi ya umma).
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    # Ukaguzi wa afya wa Render unaingia kwa http ndani ya mtandao wake.
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
