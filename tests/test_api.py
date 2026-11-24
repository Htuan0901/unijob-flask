"""Kiểm thử REST API JSON + xác thực token."""
import base64

from app import db
from app.models import JobPost
from tests.conftest import make_job


def basic(email, pw='Matkhau123'):
    return {'Authorization': 'Basic ' + base64.b64encode(f'{email}:{pw}'.encode()).decode()}


def token(client, email):
    r = client.post('/api/tokens', headers=basic(email))
    assert r.status_code == 200
    return {'Authorization': 'Bearer ' + r.json['token']}


def test_token_required(client, people):
    assert client.post('/api/tokens', headers=basic('ntd@test.vn', 'sai')).status_code == 401
    r = client.post('/api/jobs', json={'title': 'x'})
    assert r.status_code == 401 and r.json['status'] == 401


def test_list_jobs_pagination_and_filters(client, people):
    for i in range(7):
        make_job(people['emp'], title=f'Job {i}')
    make_job(people['emp'], title='Kế toán', category='FINANCE')
    r = client.get('/api/jobs?per_page=5')
    assert r.json['_meta']['total_items'] == 8 and len(r.json['items']) == 5
    assert r.json['_links']['next'] and r.json['_links']['prev'] is None
    r = client.get('/api/jobs?category=FINANCE')
    assert [j['title'] for j in r.json['items']] == ['Kế toán']
    one = client.get(f"/api/jobs/{r.json['items'][0]['id']}").json
    assert one['description'] and one['salary_unit'] == 'HOUR'


def test_employer_creates_updates_deletes_job(client, people):
    h = token(client, 'ntd@test.vn')
    payload = {'title': 'CTV viết bài', 'category': 'MARKETING', 'city': 'Hà Nội', 'description': 'Viết bài SEO',
               'job_type': 'FREELANCE', 'salary_min': 100000, 'salary_unit': 'PROJECT', 'skills': ['SEO', 'Viết bài']}
    r = client.post('/api/jobs', json=payload, headers=h)
    assert r.status_code == 201 and r.headers['Location'].endswith(str(r.json['id']))
    jid = r.json['id']
    assert r.json['skills'] == ['SEO', 'Viết bài']
    r = client.patch(f'/api/jobs/{jid}', json={'salary_max': 200000, 'urgent': True}, headers=h)
    assert r.json['salary_max'] == 200000 and r.json['urgent'] is True
    assert client.delete(f'/api/jobs/{jid}', headers=h).status_code == 204
    assert db.session.get(JobPost, jid) is None


def test_validation_and_role_errors(client, people):
    h = token(client, 'ntd@test.vn')
    r = client.post('/api/jobs', json={'title': 'x', 'category': 'SAI', 'city': 'Paris'}, headers=h)
    assert r.status_code == 422 and {'category', 'city', 'description'} <= set(r.json['fields'])
    hs = token(client, 'sv@test.vn')
    assert client.post('/api/jobs', json={}, headers=hs).status_code == 403
    job = make_job(people['emp'])
    from tests.conftest import make_user
    make_user('khac@test.vn', 'EMPLOYER')
    assert client.delete(f'/api/jobs/{job.id}', headers=token(client, 'khac@test.vn')).status_code == 403


def test_revoke_token(client, people):
    h = token(client, 'sv@test.vn')
    assert client.get('/api/me/applications', headers=h).status_code == 200
    assert client.delete('/api/tokens', headers=h).status_code == 204
    assert client.get('/api/me/applications', headers=h).status_code == 401


def test_student_recommendations(client, people):
    make_job(people['emp'])
    make_job(people['emp'], title='Lập trình viên Python', category='IT', skills='Python;SQL')
    r = client.get('/api/me/recommendations', headers=token(client, 'sv@test.vn'))
    assert r.json['items'][0]['title'] == 'Nhân viên pha chế ca tối'
    assert r.json['items'][0]['score'] > r.json['items'][1]['score']


def test_insights_endpoints(client, people):
    r = client.get('/api/insights/classify?title=Nhân viên kế toán thuế')
    assert r.json['predictions'][0]['code'] == 'FINANCE'
    assert client.get('/api/insights/classify').status_code == 400
    s = client.get('/api/insights/salary-suggestion?category=HOSPITALITY').json
    assert s['hourly'] > 0 and s['per_shift'] == s['hourly'] * 4
    assert client.get('/api/categories').json['items']
    assert client.get('/api/rates').json['live'] is False      # mạng tắt khi test
