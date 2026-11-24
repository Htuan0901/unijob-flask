from flask import current_app

from app.constants import to_monthly
from app.models import User


def test_app_exists(app):
    assert current_app is not None
    assert current_app.config['TESTING']


def test_password_hashing(people):
    u = people['stu']
    assert u.password_hash != 'Matkhau123'
    assert u.check_password('Matkhau123')
    assert not u.check_password('sai')


def test_confirm_token(people):
    u = people['stu']
    u.confirmed = False
    token = u.generate_token('confirm')
    assert u.confirm(token)
    assert u.confirmed
    assert not people['stu2'].confirm(token)          # token của người khác


def test_reset_token_purpose_isolated(people):
    u = people['stu']
    assert User.verify_token(u.generate_token('reset'), 'reset') == u
    assert User.verify_token(u.generate_token('confirm'), 'reset') is None   # khác salt
    assert User.verify_token('rác', 'reset') is None


def test_api_token(people):
    u = people['emp']
    t = u.get_api_token()
    assert User.check_api_token(t) == u
    u.revoke_api_token()
    assert User.check_api_token(t) is None


def test_monthly_salary_conversion():
    assert to_monthly(25000, 'HOUR') == 25000 * 88
    assert to_monthly(120000, 'SHIFT') == 120000 * 22
    assert to_monthly(5_000_000, 'MONTH') == 5_000_000
    assert to_monthly(None, 'HOUR') is None
