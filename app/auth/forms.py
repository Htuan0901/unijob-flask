"""Form xác thực (Flask-WTF + WTForms validators, CSRF tự động)."""
import re

import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, RadioField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError

from .. import db
from ..constants import CITIES
from ..models import User


def strong_password(form, field):
    p = field.data or ''
    if len(p) < 8 or not re.search(r'[A-Za-z]', p) or not re.search(r'\d', p):
        raise ValidationError('Mật khẩu tối thiểu 8 ký tự, gồm cả chữ và số.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    remember_me = BooleanField('Ghi nhớ đăng nhập')
    submit = SubmitField('Đăng nhập')


class RegistrationForm(FlaskForm):
    role = RadioField('Bạn là', choices=[('STUDENT', 'Sinh viên tìm việc'), ('EMPLOYER', 'Nhà tuyển dụng')],
                      default='STUDENT', validators=[DataRequired()])
    full_name = StringField('Họ và tên', validators=[DataRequired(), Length(2, 120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Số điện thoại', validators=[Optional(), Regexp(r'^0\d{9,10}$', message='Số điện thoại không hợp lệ.')])
    company_name = StringField('Tên công ty / cửa hàng (bỏ trống nếu là cá nhân)', validators=[Optional(), Length(max=150)])
    city = SelectField('Tỉnh/thành', choices=[(c, c) for c in CITIES])
    password = PasswordField('Mật khẩu', validators=[DataRequired(), strong_password])
    password2 = PasswordField('Nhập lại mật khẩu', validators=[DataRequired(), EqualTo('password', 'Mật khẩu nhập lại không khớp.')])
    accept_terms = BooleanField('Tôi đồng ý với điều khoản sử dụng', validators=[DataRequired('Bạn cần đồng ý điều khoản.')])
    submit = SubmitField('Đăng ký')

    def validate_email(self, field):
        if db.session.scalar(sa.select(User).where(User.email == field.data.lower().strip())):
            raise ValidationError('Email đã được sử dụng.')


class ResetRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Gửi liên kết đặt lại mật khẩu')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Mật khẩu mới', validators=[DataRequired(), strong_password])
    password2 = PasswordField('Nhập lại', validators=[DataRequired(), EqualTo('password', 'Mật khẩu nhập lại không khớp.')])
    submit = SubmitField('Đặt lại mật khẩu')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Mật khẩu hiện tại', validators=[DataRequired()])
    password = PasswordField('Mật khẩu mới', validators=[DataRequired(), strong_password])
    password2 = PasswordField('Nhập lại', validators=[DataRequired(), EqualTo('password', 'Mật khẩu nhập lại không khớp.')])
    submit = SubmitField('Đổi mật khẩu')
