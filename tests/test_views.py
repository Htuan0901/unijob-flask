"""Kiểm thử giao diện: tìm kiếm + phân trang, CRUD tin qua form, quyền sở hữu, admin."""
from datetime import date, timedelta

from app import db
from app.models import Application, JobPost
from tests.conftest import login, make_job


def test_search_filter_and_pagination(client, people):
    for i in range(15):
        make_job(people['emp'], title=f'Gia sư Toán số {i}', category='EDUCATION', skills='Toán')
    make_job(people['emp'], title='Nhân viên kho', category='LOGISTICS', city='Hà Nội')
    html = client.get('/jobs?q=Gia+sư').get_data(as_text=True)
    assert '15 việc phù hợp' in html and 'Nhân viên kho' not in html
    assert 'page=2' in html                                             # có phân trang (12/trang)
    page2 = client.get('/jobs?q=Gia+sư&page=2').get_data(as_text=True)
    assert page2.count('Gia sư Toán số') == 3
    html = client.get('/jobs?city=Hà+Nội').get_data(as_text=True)
    assert '1 việc phù hợp' in html
    assert '0 việc' in client.get('/jobs?min_salary=50').get_data(as_text=True)


def test_hidden_and_expired_jobs_not_listed(client, people):
    make_job(people['emp'], title='Tin bị ẩn', hidden=True)
    make_job(people['emp'], title='Tin hết hạn', deadline=date.today() - timedelta(days=1))
    html = client.get('/jobs').get_data(as_text=True)
    assert 'Tin bị ẩn' not in html and 'Tin hết hạn' not in html


def test_employer_crud_job(client, people):
    login(client, 'ntd@test.vn')
    data = {'title': 'Thực tập sinh Python Flask', 'category': 'IT', 'job_type': 'INTERNSHIP',
            'city': 'TP. Hồ Chí Minh', 'salary_min': 3000000, 'salary_max': 5000000, 'salary_unit': 'MONTH',
            'experience_level': 'NONE', 'slots': 2, 'skills': 'Python; Flask ;python',
            'description': 'Phát triển ứng dụng web bằng Flask cùng đội dự án.'}
    r = client.post('/employer/jobs/new', data=data, follow_redirects=True)
    assert 'Đã đăng tin' in r.get_data(as_text=True)
    job = db.session.query(JobPost).filter_by(title=data['title']).one()
    assert job.skills == 'Python;Flask' and job.salary_monthly_max == 5_000_000
    data.update(title='Thực tập sinh Python Flask (sửa)', salary_max=1000)    # lương max < min -> lỗi
    assert 'phải lớn hơn' in client.post(f'/employer/jobs/{job.id}/edit', data=data).get_data(as_text=True)
    data['salary_max'] = 6000000
    client.post(f'/employer/jobs/{job.id}/edit', data=data)
    db.session.refresh(job)
    assert job.title.endswith('(sửa)')
    client.post(f'/employer/jobs/{job.id}/delete')
    assert db.session.get(JobPost, job.id) is None


def test_employer_cannot_edit_others_job(client, people):
    from tests.conftest import make_user
    other = make_user('khac@test.vn', 'EMPLOYER')
    job = make_job(other)
    login(client, 'ntd@test.vn')
    assert client.get(f'/employer/jobs/{job.id}/edit').status_code == 403
    assert client.post(f'/employer/jobs/{job.id}/delete').status_code == 403


def test_apply_via_form_and_decide(client, people):
    job = make_job(people['emp'])
    login(client, 'sv@test.vn')
    r = client.post(f'/jobs/{job.id}/apply', data={'cover_letter': 'Em chào anh chị'}, follow_redirects=True)
    assert 'Đã gửi hồ sơ' in r.get_data(as_text=True)
    client.get('/auth/logout')
    login(client, 'ntd@test.vn')
    app_ = db.session.query(Application).one()
    assert 'Em chào anh chị' in client.get(f'/employer/jobs/{job.id}/applicants').get_data(as_text=True)
    client.post(f'/employer/applications/{app_.id}/decide', data={'accept': '1', 'note': 'OK'})
    db.session.refresh(app_)
    assert app_.status == 'ACCEPTED'


def test_save_and_follow(client, people):
    job = make_job(people['emp'])
    login(client, 'sv@test.vn')
    client.post(f'/jobs/{job.id}/save')
    assert people['stu'].has_saved(job)
    assert job.title in client.get('/student/saved').get_data(as_text=True)
    client.post(f'/companies/{people["emp"].employer_profile.id}/follow')
    assert people['stu'].is_following(people['emp'].employer_profile)


def test_job_alert_crud(client, people):
    login(client, 'sv@test.vn')
    client.post('/student/alerts', data={'name': 'Việc IT', 'category_code': 'IT', 'min_salary': 3,
                                         'email_enabled': 'y', 'active': 'y'})
    from app.models import JobAlert
    a = db.session.query(JobAlert).one()
    assert a.min_salary == 3_000_000
    client.post(f'/student/alerts/{a.id}/edit', data={'name': 'Việc IT HN', 'category_code': '', 'city': 'Hà Nội', 'active': 'y'})
    db.session.refresh(a)
    assert a.name == 'Việc IT HN' and a.city == 'Hà Nội' and a.category_code is None
    client.post(f'/student/alerts/{a.id}/delete')
    assert db.session.query(JobAlert).count() == 0


def test_admin_pages_and_charts(client, people):
    make_job(people['emp'])
    login(client, 'admin@test.vn')
    assert client.get('/admin/').status_code == 200
    r = client.get('/admin/charts/jobs_by_category.png')
    assert r.status_code == 200 and r.data[:8] == b'\x89PNG\r\n\x1a\n'
    csv = client.get('/admin/export/applications.csv')
    assert csv.mimetype == 'text/csv'
    client.post(f'/admin/users/{people["stu"].id}/toggle')
    db.session.refresh(people['stu'])
    assert not people['stu'].enabled


def test_salary_and_tools_pages(client, people):
    assert 'Trung vị' in client.get('/salary?category=IT').get_data(as_text=True)
    assert client.get('/news').status_code == 200          # mạng tắt -> RSS mẫu
    assert 'dự phòng' in client.get('/currency').get_data(as_text=True)


def test_404_html_and_json(client):
    assert client.get('/khong-co').status_code == 404
    r = client.get('/api/khong-co')
    assert r.status_code == 404 and r.is_json
