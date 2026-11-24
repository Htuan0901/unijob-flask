import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db, mail  # noqa: E402
from app.constants import CATEGORIES  # noqa: E402
from app.models import Category, EmployerProfile, JobPost, StudentProfile, User  # noqa: E402


@pytest.fixture
def app(tmp_path):
    app = create_app('testing')
    app.instance_path = str(tmp_path)
    with app.app_context():
        db.create_all()
        for code, name in CATEGORIES:
            db.session.add(Category(code=code, name=name))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(email, role, password='Matkhau123', **profile):
    u = User(email=email, full_name=email.split('@')[0].title(), role=role, confirmed=True)
    u.set_password(password)
    if role == 'STUDENT':
        u.student_profile = StudentProfile(**profile)
    elif role == 'EMPLOYER':
        u.employer_profile = EmployerProfile(company_name=profile.get('company_name', 'Công ty ABC'),
                                             city=profile.get('city', 'TP. Hồ Chí Minh'))
    db.session.add(u)
    db.session.commit()
    return u


def make_job(employer, title='Nhân viên pha chế ca tối', category='HOSPITALITY', **kw):
    cat = db.session.query(Category).filter_by(code=category).one()
    data = dict(description='Pha chế đồ uống, phục vụ khách hàng tại quán cà phê.', city='TP. Hồ Chí Minh',
                skills='Pha chế;Giao tiếp', salary_min=25000, salary_max=30000, salary_unit='HOUR', slots=1)
    data.update(kw)
    j = JobPost(employer=employer, category=cat, title=title, **data)
    j.update_monthly_salary()
    db.session.add(j)
    db.session.commit()
    return j


@pytest.fixture
def people(app):
    emp = make_user('ntd@test.vn', 'EMPLOYER')
    stu = make_user('sv@test.vn', 'STUDENT', city='TP. Hồ Chí Minh', skills='Pha chế;Giao tiếp;Tiếng Anh',
                    preferred_category='HOSPITALITY', major='Quản trị khách sạn')
    stu2 = make_user('sv2@test.vn', 'STUDENT', city='Hà Nội', skills='Python;SQL')
    admin = make_user('admin@test.vn', 'ADMIN')
    return {'emp': emp, 'stu': stu, 'stu2': stu2, 'admin': admin}


def login(client, email, password='Matkhau123'):
    return client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)
