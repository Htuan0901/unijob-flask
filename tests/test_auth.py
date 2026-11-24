from app import db, mail
from app.models import User
from tests.conftest import login


def test_register_student_sends_confirmation(client, app):
    with mail.record_messages() as outbox:
        r = client.post('/auth/register', data={
            'role': 'STUDENT', 'full_name': 'Lê Văn Test', 'email': 'new@test.vn', 'city': 'Hà Nội',
            'password': 'Abc12345', 'password2': 'Abc12345', 'accept_terms': 'y'}, follow_redirects=True)
    assert r.status_code == 200
    u = db.session.query(User).filter_by(email='new@test.vn').one()
    assert u.is_student and u.student_profile.city == 'Hà Nội' and not u.confirmed
    assert len(outbox) == 1 and 'Xác nhận' in outbox[0].subject
    link = outbox[0].body.split('\n')[3].strip()
    client.get(link.replace('http://localhost', ''), follow_redirects=True)
    db.session.refresh(u)
    assert u.confirmed


def test_register_validation(client, people):
    r = client.post('/auth/register', data={'role': 'STUDENT', 'full_name': 'A B', 'email': 'sv@test.vn',
                                            'city': 'Hà Nội', 'password': 'short', 'password2': 'khac'})
    html = r.get_data(as_text=True)
    assert 'Email đã được sử dụng' in html
    assert 'tối thiểu 8 ký tự' in html
    assert 'không khớp' in html


def test_register_employer_creates_company(client, app):
    client.post('/auth/register', data={'role': 'EMPLOYER', 'full_name': 'Chủ quán', 'email': 'quan@test.vn',
                                        'company_name': 'Quán Mới', 'city': 'Đà Nẵng', 'password': 'Abc12345',
                                        'password2': 'Abc12345', 'accept_terms': 'y'})
    u = db.session.query(User).filter_by(email='quan@test.vn').one()
    assert u.is_employer and u.employer_profile.company_name == 'Quán Mới'


def test_login_logout(client, people):
    assert 'không đúng' in login(client, 'sv@test.vn', 'sai').get_data(as_text=True)
    r = login(client, 'sv@test.vn')
    assert 'Xin chào' in r.get_data(as_text=True)
    assert client.get('/student/').status_code == 200
    client.get('/auth/logout')
    assert client.get('/student/').status_code == 302      # chuyển về trang đăng nhập


def test_disabled_user_cannot_login(client, people):
    people['stu'].enabled = False
    db.session.commit()
    assert 'bị khóa' in login(client, 'sv@test.vn').get_data(as_text=True)


def test_open_redirect_blocked(client, people):
    r = client.post('/auth/login?next=https://evil.example/', data={'email': 'sv@test.vn', 'password': 'Matkhau123'})
    assert 'evil.example' not in r.headers['Location']


def test_reset_password_flow(client, people):
    with mail.record_messages() as outbox:
        client.post('/auth/reset', data={'email': 'sv@test.vn'})
        client.post('/auth/reset', data={'email': 'khongco@test.vn'})     # không lộ email
    assert len(outbox) == 1
    token = people['stu'].generate_token('reset')
    client.post(f'/auth/reset/{token}', data={'password': 'MoiMoi123', 'password2': 'MoiMoi123'})
    assert 'Xin chào' in login(client, 'sv@test.vn', 'MoiMoi123').get_data(as_text=True)


def test_role_protection(client, people):
    login(client, 'sv@test.vn')
    assert client.get('/employer/').status_code == 403
    assert client.get('/admin/').status_code == 403
