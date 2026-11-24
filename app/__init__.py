"""Application factory của UniJob (Flask07)."""
import os

from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase

from config import config


class Base(DeclarativeBase):
    pass


bootstrap = Bootstrap5()
db = SQLAlchemy(model_class=Base)
mail = Mail()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Vui lòng đăng nhập để tiếp tục.'
login_manager.login_message_category = 'warning'


def create_app(config_name='default'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    os.makedirs(app.instance_path, exist_ok=True)
    app.json.ensure_ascii = False      # JSON trả tiếng Việt dễ đọc

    bootstrap.init_app(app)
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)
    login_manager.init_app(app)

    from .main import main as main_bp
    from .auth import auth as auth_bp
    from .student import student as student_bp
    from .employer import employer as employer_bp
    from .admin import admin as admin_bp
    from .api import api as api_bp
    from .ai import ai as ai_bp
    from .errors import errors as errors_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(employer_bp, url_prefix='/employer')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(errors_bp)
    csrf.exempt(api_bp)   # REST API xác thực bằng token, không dùng cookie phiên

    from . import template_filters
    template_filters.register(app)

    from . import cli
    cli.register(app)
    return app
