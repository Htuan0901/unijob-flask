"""Kiểm thử tải CV PDF: chỉ nhận PDF thật, phân quyền xem/tải, thay và xóa tệp."""
import io
import os

from app import db
from app.services.cv_files import cv_path
from tests.conftest import login, make_job

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def upload(client, content=PDF, name='CV cua toi.pdf'):
    return client.post('/student/cv/upload', data={'cv': (io.BytesIO(content), name)},
                       content_type='multipart/form-data', follow_redirects=True)


def test_student_uploads_pdf_cv(client, people):
    login(client, 'sv@test.vn')
    html = upload(client).get_data(as_text=True)
    assert 'Đã tải CV lên' in html
    p = people['stu'].student_profile
    db.session.refresh(p)
    assert p.has_cv and p.cv_original_name == 'CV_cua_toi.pdf'        # secure_filename
    assert p.cv_filename != p.cv_original_name                          # tên lưu trên đĩa là ngẫu nhiên
    assert os.path.exists(cv_path(p))
    resp = client.get(f'/students/{people["stu"].id}/cv')
    assert resp.status_code == 200 and resp.mimetype == 'application/pdf' and resp.data.startswith(b'%PDF-')
    resp.close()


def test_rejects_non_pdf_and_fake_pdf(client, people):
    login(client, 'sv@test.vn')
    assert 'Chỉ nhận tệp PDF' in upload(client, b'MZ\x90\x00', 'virus.exe').get_data(as_text=True)
    assert 'không phải PDF hợp lệ' in upload(client, b'<html>hi</html>', 'gia.pdf').get_data(as_text=True)
    assert not people['stu'].student_profile.has_cv


def test_rejects_too_large_file(client, people):
    login(client, 'sv@test.vn')
    big = PDF + b'0' * (5 * 1024 * 1024)
    html = upload(client, big).get_data(as_text=True)
    assert 'tối đa 5 MB' in html
    assert not people['stu'].student_profile.has_cv


def test_cv_access_control(client, people):
    login(client, 'sv@test.vn')
    upload(client)
    url = f'/students/{people["stu"].id}/cv'
    client.get('/auth/logout')
    assert client.get(url).status_code == 302                           # khách -> chuyển tới đăng nhập
    login(client, 'sv2@test.vn')
    assert client.get(url).status_code == 403                           # sinh viên khác không được xem
    client.get('/auth/logout')
    for email in ('ntd@test.vn', 'admin@test.vn'):
        login(client, email)
        r = client.get(url + '?download=1')
        assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
        r.close()
        client.get('/auth/logout')


def test_employer_sees_cv_link_on_applicants_page(client, people):
    job = make_job(people['emp'])
    login(client, 'sv@test.vn')
    upload(client)
    client.post(f'/jobs/{job.id}/apply', data={'cover_letter': 'Em muốn ứng tuyển'})
    client.get('/auth/logout')
    login(client, 'ntd@test.vn')
    html = client.get(f'/employer/jobs/{job.id}/applicants').get_data(as_text=True)
    assert f'/students/{people["stu"].id}/cv' in html and 'Xem CV' in html


def test_replace_and_delete_cv(client, people):
    login(client, 'sv@test.vn')
    upload(client)
    p = people['stu'].student_profile
    first = cv_path(p)
    upload(client, name='cv-moi.pdf')
    db.session.refresh(p)
    assert not os.path.exists(first) and p.cv_original_name == 'cv-moi.pdf'   # tệp cũ bị xóa khi thay
    second = cv_path(p)
    assert 'Đã xóa tệp CV' in client.post('/student/cv/delete', follow_redirects=True).get_data(as_text=True)
    db.session.refresh(p)
    assert not p.has_cv and not os.path.exists(second)
    assert client.get(f'/students/{people["stu"].id}/cv').status_code == 404


def test_cv_stored_in_database_when_cv_storage_db(app, client, people):
    """Deploy lên host không có ổ đĩa bền: CV_STORAGE=db lưu PDF trong CSDL, không ghi ra đĩa."""
    app.config['CV_STORAGE'] = 'db'
    login(client, 'sv@test.vn')
    assert 'Đã tải CV lên' in upload(client).get_data(as_text=True)
    p = people['stu'].student_profile
    db.session.refresh(p)
    assert p.cv_data == PDF and not os.path.exists(cv_path(p))
    resp = client.get(f'/students/{people["stu"].id}/cv?download=1')
    assert resp.status_code == 200 and resp.data == PDF and 'attachment' in resp.headers['Content-Disposition']
    resp.close()


def test_postgres_url_normalized():
    from config import _db_url
    assert _db_url('postgres://u:p@h/db') == 'postgresql+psycopg://u:p@h/db'
    assert _db_url('postgresql://u:p@h/db?sslmode=require') == 'postgresql+psycopg://u:p@h/db?sslmode=require'
    assert _db_url('mysql+pymysql://u:p@h/db') == 'mysql+pymysql://u:p@h/db'
    assert _db_url(None) is None


def test_accepts_pdf_with_leading_bytes(client, people):
    """PDF hợp lệ có vài byte trước '%PDF-' (BOM, khoảng trắng) vẫn được nhận."""
    login(client, 'sv@test.vn')
    assert 'Đã tải CV lên' in upload(client, b'\xef\xbb\xbf\r\n' + PDF).get_data(as_text=True)
