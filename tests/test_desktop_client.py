"""Kiểm thử client của ứng dụng desktop: chạy Flask thật trên cổng ngẫu nhiên (luồng nền) rồi gọi qua urllib."""
import threading

import pytest
from werkzeug.serving import make_server

from desktop.api_client import ApiError, UniJobClient
from tests.conftest import make_job


@pytest.fixture
def live(app, people):
    make_job(people['emp'])
    srv = make_server('127.0.0.1', 0, app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{srv.server_port}'
    srv.shutdown()


def test_client_flow(live):
    c = UniJobClient(live)
    assert c.jobs()['_meta']['total_items'] == 1
    assert c.classify('Nhân viên pha chế')[0]['code'] == 'HOSPITALITY'
    with pytest.raises(ApiError) as e:
        c.login('ntd@test.vn', 'sai')
    assert e.value.status == 401
    assert c.login('ntd@test.vn', 'Matkhau123')['role'] == 'EMPLOYER'
    job = c.create_job(title='Phát tờ rơi cuối tuần', category='SALES', city='Hà Nội', description='Phát tờ rơi',
                       salary_min=25000, salary_unit='HOUR')
    assert c.job(job['id'])['title'] == 'Phát tờ rơi cuối tuần'
    assert c.stats()['open_jobs'] == 2
    c.logout()
    with pytest.raises(ApiError):
        c.create_job(title='x')
