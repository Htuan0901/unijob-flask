"""REST API trả về JSON (CLO3): dùng cho ứng dụng desktop, JavaScript trên trang và bên thứ ba."""
from flask import Blueprint

api = Blueprint('api', __name__)

from . import auth, jobs, insights  # noqa: E402,F401
