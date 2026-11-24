"""Xác thực API: HTTP Basic để lấy token, sau đó gửi 'Authorization: Bearer <token>'."""
import base64
from functools import wraps

import sqlalchemy as sa
from flask import current_app, g, jsonify, request

from . import api
from .. import db
from ..models import User


def error_response(status, message):
    return jsonify(error={400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
                          409: 'Conflict', 422: 'Unprocessable Entity'}.get(status, 'Error'),
                   message=message, status=status), status


def _basic_user():
    header = request.headers.get('Authorization', '')
    if not header.startswith('Basic '):
        return None
    try:
        email, password = base64.b64decode(header[6:]).decode('utf-8').split(':', 1)
    except (ValueError, UnicodeDecodeError):
        return None
    user = db.session.scalar(sa.select(User).where(User.email == email.lower().strip()))
    return user if user and user.enabled and user.check_password(password) else None


def _token_user():
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        user = User.check_api_token(header[7:].strip())
        return user if user and user.enabled else None
    return None


def token_auth_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = _token_user()
            if user is None:
                return error_response(401, 'Thiếu hoặc sai token. Lấy token qua POST /api/tokens (HTTP Basic).')
            if roles and user.role not in roles:
                return error_response(403, 'Vai trò của bạn không được phép gọi API này.')
            g.api_user = user
            return f(*args, **kwargs)
        return wrapper
    return decorator


@api.route('/tokens', methods=['POST'])
def get_token():
    user = _basic_user()
    if user is None:
        return error_response(401, 'Sai email hoặc mật khẩu.')
    token = user.get_api_token(current_app.config['API_TOKEN_TTL'])
    db.session.commit()
    return jsonify(token=token, expires=user.api_token_expiration.isoformat() + 'Z',
                   user={'id': user.id, 'email': user.email, 'full_name': user.full_name, 'role': user.role})


@api.route('/tokens', methods=['DELETE'])
@token_auth_required()
def revoke_token():
    g.api_user.revoke_api_token()
    db.session.commit()
    return '', 204
