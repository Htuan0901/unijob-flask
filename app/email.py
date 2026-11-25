"""Gửi email bằng Flask-Mail (Flask06) trong luồng nền (threading – Chương 6).

Ba cách gửi, chọn theo cấu hình:
- BREVO_API_KEY: gửi email thật qua API HTTPS của Brevo (urllib + JSON, phần Lập trình mạng).
  Dùng khi deploy lên host chặn cổng SMTP (Render gói free). Bản sao vẫn lưu ở instance/outbox/.
- MAIL_SERVER (SMTP, vd Gmail + Mật khẩu ứng dụng): gửi bằng Flask-Mail.
- Không cấu hình gì (MAIL_SUPPRESS_SEND=True): chỉ ghi tệp .eml vào instance/outbox/ để xem ở trang Quản trị.
"""
import os
from datetime import datetime
from email.utils import parseaddr
from threading import Thread

from flask import current_app, render_template
from flask_mail import Message

from . import mail
from .net.http_client import NetworkError, post_json

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


def _save_to_outbox(app, msg):
    folder = os.path.join(app.instance_path, 'outbox')
    os.makedirs(folder, exist_ok=True)
    name = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.eml'
    with open(os.path.join(folder, name), 'wb') as f:
        f.write(msg.as_bytes())


def _send_via_brevo(app, msg):
    """POST JSON tới Brevo; khóa API đặt trong header 'api-key'. Trả về messageId."""
    name, addr = parseaddr(msg.sender)
    payload = {'sender': {'name': name or 'UniJob', 'email': addr},
               'to': [{'email': r} for r in msg.recipients],
               'subject': msg.subject, 'textContent': msg.body, 'htmlContent': msg.html or msg.body}
    data = post_json(BREVO_URL, payload, headers={'api-key': app.config['BREVO_API_KEY']},
                     timeout=app.config.get('MAIL_API_TIMEOUT', 15))
    return data.get('messageId')


def _send_async(app, msg):
    with app.app_context():
        try:
            if app.config.get('BREVO_API_KEY'):
                _save_to_outbox(app, msg)
                app.logger.info('Đã gửi email qua Brevo tới %s (%s)', msg.recipients, _send_via_brevo(app, msg))
                return
            if app.config.get('MAIL_SUPPRESS_SEND'):
                _save_to_outbox(app, msg)
            mail.send(msg)
        except NetworkError as exc:
            app.logger.error('Gửi email qua Brevo thất bại: %s', exc)
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
