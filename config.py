"""Cấu hình ứng dụng theo lớp (Flask07 – Large Application Structure).

Mọi giá trị nhạy cảm (SECRET_KEY, mật khẩu email, khóa API) đọc từ biến môi trường
hoặc tệp .env (không đưa lên Git). Thiếu biến nào thì dùng giá trị mặc định an toàn
để ứng dụng vẫn chạy được trên máy sinh viên.
"""
import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _db_url(url):
    """Chuẩn hóa URL Postgres do Render/Neon cấp (postgres://...) sang driver psycopg 3 của SQLAlchemy."""
    if url and url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if url and url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    return url


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'unijob-dev-secret-change-me'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Bootstrap-Flask: dùng file CSS/JS đóng gói sẵn trong thư viện -> chạy được cả khi không có Internet
    BOOTSTRAP_SERVE_LOCAL = _bool('BOOTSTRAP_SERVE_LOCAL', True)

    # ---- Flask-Mail (Flask06) ----
    MAIL_SERVER = os.environ.get('MAIL_SERVER')            # vd: smtp.gmail.com
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = _bool('MAIL_USE_TLS', True)
    MAIL_USE_SSL = _bool('MAIL_USE_SSL', False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'UniJob <no-reply@unijob.vn>'
    # Không cấu hình SMTP -> không gửi thật, email được lưu vào instance/outbox để xem lại
    MAIL_SUPPRESS_SEND = _bool('MAIL_SUPPRESS_SEND', not os.environ.get('MAIL_SERVER'))
    # Gửi email thật qua API HTTPS của Brevo (miễn phí 300 mail/ngày) khi host chặn SMTP.
    # MAIL_DEFAULT_SENDER phải là địa chỉ đã xác minh trong Brevo (Senders).
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
    UNIJOB_MAIL_SUBJECT_PREFIX = '[UniJob]'
    UNIJOB_ADMIN = os.environ.get('UNIJOB_ADMIN') or 'admin@unijob.vn'

    # ---- Tải lên CV (PDF) ----
    # Form chỉ nhận PDF <= 5 MB (FileSize); request > 6 MB bị Flask chặn luôn (lỗi 413)
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    CV_UPLOAD_FOLDER = os.environ.get('CV_UPLOAD_FOLDER')    # mặc định: instance/uploads/cv
    CV_STORAGE = os.environ.get('CV_STORAGE') or 'disk'      # disk | db (host không có ổ đĩa bền)

    # ---- Phân trang ----
    JOBS_PER_PAGE = 12
    ADMIN_PER_PAGE = 20

    # ---- Lập trình mạng (CLO3) ----
    HTTP_TIMEOUT = float(os.environ.get('HTTP_TIMEOUT', '6'))
    HTTP_USER_AGENT = os.environ.get('HTTP_USER_AGENT') or 'UniJob/1.0 (student project; Flask)'
    NETWORK_ENABLED = _bool('NETWORK_ENABLED', True)        # tắt khi chạy test / không có mạng
    EXCHANGE_API_KEY = os.environ.get('EXCHANGE_API_KEY')   # có khóa -> dùng v6.exchangerate-api.com
    EXCHANGE_FALLBACK_USD = float(os.environ.get('EXCHANGE_FALLBACK_USD', '0.0000380'))
    GEOCODER_URL = os.environ.get('GEOCODER_URL') or 'https://nominatim.openstreetmap.org/search'
    NEWS_RSS_URL = os.environ.get('NEWS_RSS_URL') or 'https://vnexpress.net/rss/giao-duc.rss'
    API_TOKEN_TTL = int(os.environ.get('API_TOKEN_TTL', '3600'))

    # ---- Trợ lý AI (Flask09 – LLM & RAG) ----
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER') or 'demo'          # demo | ollama | openai
    LLM_MODEL = os.environ.get('LLM_MODEL') or 'qwen2.5:3b'
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL') or 'http://localhost:11434'
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    AI_TOP_K = int(os.environ.get('AI_TOP_K') or 4)
    AI_MAX_QUESTION = 500
    AI_RATE_LIMIT = int(os.environ.get('AI_RATE_LIMIT') or 10)       # số câu hỏi / phút / phiên

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _db_url(os.environ.get('DEV_DATABASE_URL')) or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    NETWORK_ENABLED = False
    MAIL_ASYNC = False
    BREVO_API_KEY = None
    LLM_PROVIDER = 'demo'
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite://'


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = _db_url(os.environ.get('DATABASE_URL')) or \
        'sqlite:///' + os.path.join(basedir, 'data.sqlite')
    # Postgres miễn phí (Neon) tự ngắt kết nối khi rảnh -> kiểm tra kết nối trước khi dùng
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}
    SESSION_COOKIE_SECURE = _bool('SESSION_COOKIE_SECURE', False)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        # Chạy sau reverse proxy HTTPS (Render, Railway...): lấy đúng scheme/host cho url_for(_external=True)
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        import logging
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
