from flask import Blueprint

errors = Blueprint('errors', __name__)

from . import handlers  # noqa: E402,F401
