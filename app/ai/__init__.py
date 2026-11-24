"""Trợ lý AI hỏi đáp bằng RAG (Flask09 – LLM & Retrieval-Augmented Generation)."""
from flask import Blueprint

ai = Blueprint('ai', __name__)

from . import routes  # noqa: E402,F401
