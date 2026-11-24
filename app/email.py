"""Gửi email bằng Flask-Mail (Flask06) trong luồng nền (threading – Chương 6).

Khi chưa cấu hình SMTP (MAIL_SUPPRESS_SEND=True), email không gửi thật mà được ghi
thành tệp .eml trong instance/outbox/ để giảng viên/nhóm xem lại trên trang Quản trị.
"""
import os
from datetime import datetime
from threading import Thread

from flask import current_app, render_template
from flask_mail import Message

from . import mail


def _save_to_outbox(app, msg):
    folder = os.path.join(app.instance_path, 'outbox')
    os.makedirs(folder, exist_ok=True)
    name = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.eml'
    with open(os.path.join(folder, name), 'wb') as f:
        f.write(msg.as_bytes())


def _send_async(app, msg):
    with app.app_context():
        try:
            if app.config.get('MAIL_SUPPRESS_SEND'):
                _save_to_outbox(app, msg)
            mail.send(msg)
        except Exception as exc:  # không để lỗi SMTP làm hỏng request
            app.logger.error('Gửi email thất bại: %s', exc)


def send_email(to, subject, template, **kwargs):
    """Render templates/email/<template>.txt và .html rồi gửi; trả về Thread (hoặc None khi gửi đồng bộ)."""
    app = current_app._get_current_object()
    msg = Message(app.config['UNIJOB_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
                  sender=app.config['MAIL_DEFAULT_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    if not app.config.get('MAIL_ASYNC', True):
        _send_async(app, msg)
        return None
    thr = Thread(target=_send_async, args=[app, msg], daemon=True)
    thr.start()
    return thr
