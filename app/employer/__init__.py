from flask import Blueprint

employer = Blueprint('employer', __name__)

from . import routes  # noqa: E402,F401
