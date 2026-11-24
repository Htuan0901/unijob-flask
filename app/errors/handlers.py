"""Xử lý lỗi toàn cục: trả JSON cho /api/..., trang HTML cho phần còn lại."""
from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from . import errors
from .. import db


def wants_json():
    return request.path.startswith('/api/') or \
        request.accept_mimetypes['application/json'] > request.accept_mimetypes['text/html']


@errors.app_errorhandler(HTTPException)
def http_error(e):
    if e.code == 413:
        e.description = 'Tệp tải lên quá lớn. CV chỉ được tối đa 5 MB.'
    if wants_json():
        return jsonify(error=e.name, message=e.description, status=e.code), e.code
    template = f'errors/{e.code}.html' if e.code in (403, 404) else 'errors/generic.html'
    return render_template(template, error=e), e.code


@errors.app_errorhandler(500)
def internal_error(e):
    db.session.rollback()
    if wants_json():
        return jsonify(error='Internal Server Error', status=500), 500
    return render_template('errors/generic.html', error=e), 500
