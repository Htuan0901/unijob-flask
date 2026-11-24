from app.models import JobPost, User
from app.seed import seed_all


def test_seed_demo_data(app):
    with app.test_request_context():
        msg = seed_all()
    assert 'Đã tạo' in msg
    from app import db
    assert db.session.query(JobPost).count() > 300
    assert db.session.query(User).filter_by(email='sv@unijob.vn').one().check_password('Sinhvien@123')
    assert 'bỏ qua' in seed_all()
