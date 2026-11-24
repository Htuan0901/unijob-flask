import pytest

from app import db, mail
from app.models import Application, JobAlert, Notification, Review
from app.services import workflow
from app.services.workflow import WorkflowError
from tests.conftest import make_job


@pytest.fixture
def ctx(app, people):
    with app.test_request_context():
        yield people


def test_apply_and_duplicate(ctx):
    job = make_job(ctx['emp'])
    with mail.record_messages() as outbox:
        a = workflow.apply(job, ctx['stu'], 'Em muốn ứng tuyển')
        db.session.commit()
    assert a.status == 'PENDING' and a.match_score > 0
    assert len(outbox) == 1 and outbox[0].recipients == ['ntd@test.vn']
    assert db.session.query(Notification).filter_by(user_id=ctx['emp'].id, type='NEW_APPLICATION').count() == 1
    with pytest.raises(WorkflowError):
        workflow.apply(job, ctx['stu'])
    with pytest.raises(WorkflowError):
        workflow.apply(job, ctx['emp'])                  # NTD không ứng tuyển được


def test_match_score_prefers_relevant_student(ctx):
    job = make_job(ctx['emp'])
    a1 = workflow.apply(job, ctx['stu'])
    a2 = workflow.apply(job, ctx['stu2'])
    assert a1.match_score > a2.match_score


def test_accept_fills_job_and_withdraw_reopens(ctx):
    job = make_job(ctx['emp'], slots=1)
    a = workflow.apply(job, ctx['stu'])
    workflow.decide(a, True, ctx['emp'], 'Hẹn em thứ 2')
    assert a.status == 'ACCEPTED' and job.status == 'FILLED'
    with pytest.raises(WorkflowError):
        workflow.apply(job, ctx['stu2'])                 # tin đã đủ người
    workflow.withdraw(a, ctx['stu'])
    assert a.status == 'WITHDRAWN' and job.status == 'OPEN'
    again = workflow.apply(job, ctx['stu'])              # rút rồi được nộp lại
    assert again.id == a.id and again.status == 'PENDING'


def test_only_owner_can_decide(ctx):
    job = make_job(ctx['emp'])
    a = workflow.apply(job, ctx['stu'])
    with pytest.raises(WorkflowError):
        workflow.decide(a, True, ctx['stu2'])


def test_status_transitions(ctx):
    job = make_job(ctx['emp'])
    with pytest.raises(WorkflowError):
        workflow.change_job_status(job, 'COMPLETED', ctx['emp'])    # OPEN -> COMPLETED không hợp lệ
    pending = workflow.apply(job, ctx['stu2'])
    workflow.change_job_status(job, 'CLOSED', ctx['emp'])
    assert pending.status == 'REJECTED'


def test_complete_then_two_way_review(ctx):
    job = make_job(ctx['emp'], slots=2)
    a = workflow.apply(job, ctx['stu'])
    workflow.decide(a, True, ctx['emp'])
    assert not workflow.can_review(job, ctx['stu'], ctx['emp'])        # chưa hoàn thành
    workflow.change_job_status(job, 'FILLED', ctx['emp'])
    workflow.change_job_status(job, 'COMPLETED', ctx['emp'])
    assert a.status == 'COMPLETED'
    assert [t for _, t in workflow.pending_reviews(ctx['stu'])] == [ctx['emp']]
    workflow.add_review(job, ctx['stu'], ctx['emp'], 5, 'Tốt')
    workflow.add_review(job, ctx['emp'], ctx['stu'], 4, 'Chăm chỉ')
    db.session.commit()
    assert ctx['emp'].rating_avg == 5 and ctx['stu'].rating_avg == 4
    with pytest.raises(WorkflowError):
        workflow.add_review(job, ctx['stu'], ctx['emp'], 1, 'lần 2')
    with pytest.raises(WorkflowError):
        workflow.add_review(job, ctx['stu2'], ctx['emp'], 1, 'không làm')
    assert db.session.query(Review).count() == 2


def test_job_alert_and_follow_notify(ctx):
    stu = ctx['stu']
    db.session.add(JobAlert(user=stu, name='Pha chế', keyword='pha che', city='TP. Hồ Chí Minh', min_salary=2_000_000))
    stu2 = ctx['stu2']
    stu2.followed_companies.add(ctx['emp'].employer_profile)
    db.session.commit()
    with mail.record_messages() as outbox:
        job = make_job(ctx['emp'])                        # 30.000đ/giờ ≈ 2,64 tr/tháng
        n = workflow.on_job_created(job)
        db.session.commit()
    assert n == 2
    assert [m.recipients for m in outbox] == [['sv@test.vn']]       # chỉ alert có gửi email
    types = {x.type for x in db.session.query(Notification).all()}
    assert {'JOB_ALERT', 'COMPANY_NEW_JOB'} <= types


def test_alert_matching_rules(ctx):
    job = make_job(ctx['emp'])
    a = JobAlert(user_id=ctx['stu'].id, name='x', active=True)
    assert a.matches(job)
    a.category_code = 'IT'
    assert not a.matches(job)
    a.category_code, a.min_salary = None, 10_000_000
    assert not a.matches(job)
