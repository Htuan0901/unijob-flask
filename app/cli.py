"""Lệnh CLI: flask seed, flask test, flask ai-reindex."""
import sys

import click

from . import db


def register(app):
    @app.cli.command('seed')
    @click.option('--reset', is_flag=True, help='Xóa toàn bộ bảng rồi tạo lại')
    def seed(reset):
        """Tạo bảng (nếu chưa có) và nạp dữ liệu mẫu."""
        from .seed import seed_all
        if reset:
            db.drop_all()
        db.create_all()
        click.echo(seed_all())

    @app.cli.command('test')
    @click.argument('test_names', nargs=-1)
    def test(test_names):
        """Chạy unit test bằng pytest."""
        import pytest
        sys.exit(pytest.main(['-q', 'tests'] + list(test_names)))

    @app.cli.command('ai-reindex')
    def ai_reindex():
        """Xây lại chỉ mục RAG từ tài liệu hướng dẫn + tin đang tuyển."""
        from .ai.rag import get_index
        idx = get_index(rebuild=True)
        click.echo(f'Đã index {len(idx.chunks)} đoạn, {len(idx.vocab)} từ vựng.')
