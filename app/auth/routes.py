"""Đăng ký, đăng nhập (Flask-Login), xác nhận email, quên/đổi mật khẩu."""
from urllib.parse import urlsplit

import sqlalchemy as sa
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import auth
from .forms import ChangePasswordForm, LoginForm, RegistrationForm, ResetPasswordForm, ResetRequestForm
from .. import db
from ..email import send_email
from ..models import EmployerProfile, StudentProfile, User, utcnow


@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = utcnow()
        db.session.commit()


def _send_confirmation(user):
    token = user.generate_token('confirm')
    send_email(user.email, 'Xác nhận tài khoản', 'email/confirm', user=user,
               link=url_for('auth.confirm', token=token, _external=True))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if request.method == 'GET' and request.args.get('role') in ('STUDENT', 'EMPLOYER'):
        form.role.data = request.args['role']
    if form.validate_on_submit():
        user = User(email=form.email.data.lower().strip(), full_name=form.full_name.data.strip(),
                    phone=form.phone.data or None, role=form.role.data)
        user.set_password(form.password.data)
        if user.role == 'STUDENT':
            user.student_profile = StudentProfile(city=form.city.data)
        else:
            name = (form.company_name.data or '').strip()
            user.employer_profile = EmployerProfile(company_name=name or None, individual=not name, city=form.city.data)
        db.session.add(user)
        db.session.commit()
        _send_confirmation(user)
        login_user(user)
        flash('Đăng ký thành công! Email xác nhận đã được gửi tới hộp thư của bạn.', 'success')
        return redirect(url_for('student.profile' if user.is_student else 'employer.company'))
    return render_template('auth/register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data.lower().strip()))
        if user is None or not user.check_password(form.password.data):
            flash('Email hoặc mật khẩu không đúng.', 'danger')
            return redirect(url_for('auth.login'))
        if not user.enabled:
            flash('Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.', 'danger')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        flash(f'Xin chào {user.full_name}!', 'success')
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':     # chống open redirect
            next_page = {'STUDENT': url_for('student.dashboard'), 'EMPLOYER': url_for('employer.dashboard'),
                         'ADMIN': url_for('admin.dashboard')}.get(user.role, url_for('main.index'))
        return redirect(next_page)
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
def logout():
    logout_user()
    flash('Bạn đã đăng xuất.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        db.session.commit()
        flash('Đã xác nhận email. Cảm ơn bạn!', 'success')
    else:
        flash('Liên kết xác nhận không hợp lệ hoặc đã hết hạn.', 'danger')
    return redirect(url_for('main.index'))


@auth.route('/confirm')
@login_required
def resend_confirmation():
    _send_confirmation(current_user)
    flash('Đã gửi lại email xác nhận.', 'info')
    return redirect(request.referrer or url_for('main.index'))


@auth.route('/reset', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data.lower().strip()))
        if user:
            send_email(user.email, 'Đặt lại mật khẩu', 'email/reset_password', user=user,
                       link=url_for('auth.reset_password', token=user.generate_token('reset'), _external=True))
        # Luôn báo cùng một câu để không lộ email nào đã đăng ký
        flash('Nếu email tồn tại trong hệ thống, liên kết đặt lại mật khẩu đã được gửi.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_request.html', form=form)


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_token(token, 'reset', max_age=3600)
    if user is None:
        flash('Liên kết không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('auth.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Đã đặt lại mật khẩu, mời bạn đăng nhập.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('Mật khẩu hiện tại không đúng.', 'danger')
        else:
            current_user.set_password(form.password.data)
            db.session.commit()
            flash('Đã đổi mật khẩu.', 'success')
            return redirect(url_for('main.index'))
    return render_template('auth/change_password.html', form=form)
