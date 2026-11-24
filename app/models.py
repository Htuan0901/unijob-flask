"""Các model Flask-SQLAlchemy của UniJob (Flask05 – Databases).

Quan hệ chính:
  User 1-1 StudentProfile / EmployerProfile
  User(employer) 1-n JobPost ;  Category 1-n JobPost
  JobPost 1-n Application n-1 User(student)
  JobPost 1-n Review ; User 1-n Notification ; User 1-n JobAlert
  User n-n JobPost   (saved_jobs – việc đã lưu)
  User n-n EmployerProfile (company_follows – theo dõi công ty)
"""
from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app
from flask_login import UserMixin, AnonymousUserMixin
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

from . import db, login_manager
from .constants import (ROLE_STUDENT, ROLE_EMPLOYER, ROLE_ADMIN, ROLES, JOB_TYPES, SALARY_UNITS,
                        EXPERIENCE_LEVELS, JOB_STATUSES, APP_STATUSES, to_monthly)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- bảng liên kết n-n
saved_jobs = sa.Table(
    'saved_jobs', db.metadata,
    sa.Column('user_id', sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('job_id', sa.ForeignKey('job_posts.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('created_at', sa.DateTime, default=utcnow),
)

company_follows = sa.Table(
    'company_follows', db.metadata,
    sa.Column('user_id', sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('company_id', sa.ForeignKey('employer_profiles.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('created_at', sa.DateTime, default=utcnow),
)


# ---------------------------------------------------------------- người dùng
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), unique=True, index=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    full_name: so.Mapped[str] = so.mapped_column(sa.String(120))
    phone: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    role: so.Mapped[str] = so.mapped_column(sa.String(16), index=True, default=ROLE_STUDENT)
    confirmed: so.Mapped[bool] = so.mapped_column(default=False)
    enabled: so.Mapped[bool] = so.mapped_column(default=True)
    rating_avg: so.Mapped[float] = so.mapped_column(default=0.0)
    rating_count: so.Mapped[int] = so.mapped_column(default=0)
    created_at: so.Mapped[datetime] = so.mapped_column(default=utcnow)
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=utcnow)
    api_token: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), index=True, unique=True)
    api_token_expiration: so.Mapped[Optional[datetime]]

    student_profile: so.Mapped[Optional['StudentProfile']] = so.relationship(
        back_populates='user', uselist=False, cascade='all, delete-orphan')
    employer_profile: so.Mapped[Optional['EmployerProfile']] = so.relationship(
        back_populates='user', uselist=False, cascade='all, delete-orphan')
    jobs: so.WriteOnlyMapped['JobPost'] = so.relationship(back_populates='employer')
    applications: so.WriteOnlyMapped['Application'] = so.relationship(back_populates='student')
    notifications: so.WriteOnlyMapped['Notification'] = so.relationship(
        back_populates='user', cascade='all, delete-orphan', passive_deletes=True)
    job_alerts: so.WriteOnlyMapped['JobAlert'] = so.relationship(
        back_populates='user', cascade='all, delete-orphan', passive_deletes=True)
    saved: so.WriteOnlyMapped['JobPost'] = so.relationship(secondary=saved_jobs)
    followed_companies: so.WriteOnlyMapped['EmployerProfile'] = so.relationship(
        secondary=company_follows, back_populates='followers')

    def __repr__(self):
        return f'<User {self.email} {self.role}>'

    # ---- mật khẩu (Werkzeug) ----
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    # ---- vai trò ----
    @property
    def is_active(self):              # Flask-Login: tài khoản bị khóa không đăng nhập được
        return self.enabled

    @property
    def is_student(self):
        return self.role == ROLE_STUDENT

    @property
    def is_employer(self):
        return self.role == ROLE_EMPLOYER

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def role_label(self):
        return ROLES.get(self.role, self.role)

    @property
    def display_name(self):
        if self.is_employer and self.employer_profile and self.employer_profile.company_name:
            return self.employer_profile.company_name
        return self.full_name

    # ---- token xác nhận email / đặt lại mật khẩu (itsdangerous) ----
    @staticmethod
    def _serializer(salt):
        return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=salt)

    def generate_token(self, purpose):
        return self._serializer(purpose).dumps({'id': self.id, 'email': self.email})

    @staticmethod
    def verify_token(token, purpose, max_age=3600):
        try:
            data = User._serializer(purpose).loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        user = db.session.get(User, data.get('id'))
        if user is None or user.email != data.get('email'):
            return None
        return user

    def confirm(self, token):
        user = User.verify_token(token, 'confirm', max_age=7 * 24 * 3600)
        if user is None or user.id != self.id:
            return False
        self.confirmed = True
        return True

    # ---- token REST API ----
    def get_api_token(self, expires_in=3600):
        now = utcnow()
        if self.api_token and self.api_token_expiration and self.api_token_expiration > now + timedelta(seconds=60):
            return self.api_token
        self.api_token = secrets.token_hex(32)
        self.api_token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.api_token

    def revoke_api_token(self):
        self.api_token_expiration = utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_api_token(token):
        user = db.session.scalar(sa.select(User).where(User.api_token == token))
        if user is None or user.api_token_expiration is None or user.api_token_expiration < utcnow():
            return None
        return user

    # ---- việc đã lưu, công ty theo dõi ----
    def has_saved(self, job):
        q = sa.select(saved_jobs).where(saved_jobs.c.user_id == self.id, saved_jobs.c.job_id == job.id)
        return db.session.execute(q).first() is not None

    def is_following(self, company):
        q = sa.select(company_follows).where(company_follows.c.user_id == self.id,
                                             company_follows.c.company_id == company.id)
        return db.session.execute(q).first() is not None

    def unread_notifications(self):
        return db.session.scalar(sa.select(sa.func.count(Notification.id)).where(
            Notification.user_id == self.id, Notification.read.is_(False))) or 0

    def recalc_rating(self):
        avg, cnt = db.session.execute(sa.select(sa.func.avg(Review.rating), sa.func.count(Review.id))
                                      .where(Review.reviewee_id == self.id)).one()
        self.rating_avg = round(float(avg or 0), 2)
        self.rating_count = cnt or 0


class AnonymousUser(AnonymousUserMixin):
    is_student = is_employer = is_admin = False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id'), unique=True)
    university: so.Mapped[Optional[str]] = so.mapped_column(sa.String(150))
    major: so.Mapped[Optional[str]] = so.mapped_column(sa.String(120))
    year_of_study: so.Mapped[Optional[int]]
    city: so.Mapped[Optional[str]] = so.mapped_column(sa.String(60))
    skills: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500))   # phân tách bằng ';'
    preferred_category: so.Mapped[Optional[str]] = so.mapped_column(sa.String(30))
    availability: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    bio: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    # CV dạng PDF: tên tệp lưu trên đĩa (sinh ngẫu nhiên) + tên gốc để hiển thị/tải về
    cv_filename: so.Mapped[Optional[str]] = so.mapped_column(sa.String(120))
    cv_original_name: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    cv_uploaded_at: so.Mapped[Optional[datetime]]

    user: so.Mapped[User] = so.relationship(back_populates='student_profile')

    @property
    def has_cv(self):
        return bool(self.cv_filename)

    @property
    def skill_list(self):
        return [s.strip() for s in (self.skills or '').split(';') if s.strip()]


class EmployerProfile(db.Model):
    __tablename__ = 'employer_profiles'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id'), unique=True)
    company_name: so.Mapped[Optional[str]] = so.mapped_column(sa.String(150), index=True)
    individual: so.Mapped[bool] = so.mapped_column(default=False)
    industry: so.Mapped[Optional[str]] = so.mapped_column(sa.String(120))
    city: so.Mapped[Optional[str]] = so.mapped_column(sa.String(60))
    address: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    website: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    verified: so.Mapped[bool] = so.mapped_column(default=False)

    user: so.Mapped[User] = so.relationship(back_populates='employer_profile')
    followers: so.WriteOnlyMapped[User] = so.relationship(
        secondary=company_follows, back_populates='followed_companies')

    @property
    def name(self):
        return self.company_name or f'{self.user.full_name} (cá nhân)'

    def follower_count(self):
        return db.session.scalar(sa.select(sa.func.count()).select_from(company_follows)
                                 .where(company_follows.c.company_id == self.id))


# ---------------------------------------------------------------- tin tuyển dụng
class Category(db.Model):
    __tablename__ = 'categories'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    code: so.Mapped[str] = so.mapped_column(sa.String(30), unique=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(120))
    jobs: so.WriteOnlyMapped['JobPost'] = so.relationship(back_populates='category')


class JobPost(db.Model):
    __tablename__ = 'job_posts'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    employer_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id'), index=True)
    category_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('categories.id'), index=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(200), index=True)
    description: so.Mapped[str] = so.mapped_column(sa.Text)
    requirements: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    benefits: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    skills: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500))
    city: so.Mapped[str] = so.mapped_column(sa.String(60), index=True)
    address: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    latitude: so.Mapped[Optional[float]]
    longitude: so.Mapped[Optional[float]]
    job_type: so.Mapped[str] = so.mapped_column(sa.String(20), default='PART_TIME', index=True)
    salary_min: so.Mapped[Optional[int]] = so.mapped_column(sa.BigInteger)
    salary_max: so.Mapped[Optional[int]] = so.mapped_column(sa.BigInteger)
    salary_unit: so.Mapped[str] = so.mapped_column(sa.String(10), default='HOUR')
    salary_monthly_max: so.Mapped[Optional[int]] = so.mapped_column(sa.BigInteger, index=True)
    working_hours: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    experience_level: so.Mapped[str] = so.mapped_column(sa.String(10), default='NONE')
    deadline: so.Mapped[Optional[datetime]] = so.mapped_column(sa.Date)
    slots: so.Mapped[int] = so.mapped_column(default=1)
    status: so.Mapped[str] = so.mapped_column(sa.String(12), default='OPEN', index=True)
    urgent: so.Mapped[bool] = so.mapped_column(default=False)
    hidden: so.Mapped[bool] = so.mapped_column(default=False)
    view_count: so.Mapped[int] = so.mapped_column(default=0)
    created_at: so.Mapped[datetime] = so.mapped_column(default=utcnow, index=True)
    updated_at: so.Mapped[Optional[datetime]] = so.mapped_column(onupdate=utcnow)

    employer: so.Mapped[User] = so.relationship(back_populates='jobs')
    category: so.Mapped[Optional[Category]] = so.relationship(back_populates='jobs')
    applications: so.WriteOnlyMapped['Application'] = so.relationship(
        back_populates='job', cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return f'<JobPost {self.id} {self.title!r}>'

    @property
    def skill_list(self):
        return [s.strip() for s in (self.skills or '').split(';') if s.strip()]

    @property
    def company(self):
        return self.employer.employer_profile

    @property
    def job_type_label(self):
        return JOB_TYPES.get(self.job_type, self.job_type)

    @property
    def status_label(self):
        return JOB_STATUSES.get(self.status, self.status)

    @property
    def experience_label(self):
        return EXPERIENCE_LEVELS.get(self.experience_level, self.experience_level)

    @property
    def salary_label(self):
        unit = SALARY_UNITS.get(self.salary_unit, '')
        fmt = lambda v: f'{v:,.0f}'.replace(',', '.')
        if self.salary_min and self.salary_max:
            return f'{fmt(self.salary_min)} – {fmt(self.salary_max)} đ/{unit}'
        if self.salary_max or self.salary_min:
            return f'{fmt(self.salary_max or self.salary_min)} đ/{unit}'
        return 'Thỏa thuận'

    @property
    def is_open(self):
        today = utcnow().date()
        return self.status == 'OPEN' and not self.hidden and (self.deadline is None or self.deadline >= today)

    def update_monthly_salary(self):
        self.salary_monthly_max = to_monthly(self.salary_max or self.salary_min, self.salary_unit)

    def count_applications(self, status=None):
        q = sa.select(sa.func.count(Application.id)).where(Application.job_id == self.id)
        if status:
            q = q.where(Application.status.in_(status if isinstance(status, (list, tuple, set)) else [status]))
        return db.session.scalar(q) or 0

    def to_dict(self, detail=False):
        """Biểu diễn JSON dùng cho REST API."""
        from flask import url_for
        data = {
            'id': self.id, 'title': self.title,
            'company': self.company.name if self.company else self.employer.full_name,
            'category': self.category.code if self.category else None,
            'category_name': self.category.name if self.category else None,
            'city': self.city, 'job_type': self.job_type,
            'salary_min': self.salary_min, 'salary_max': self.salary_max,
            'salary_unit': self.salary_unit, 'salary_label': self.salary_label,
            'status': self.status, 'urgent': self.urgent,
            'skills': self.skill_list,
            'created_at': self.created_at.isoformat() + 'Z',
            'deadline': self.deadline.isoformat() if self.deadline else None,
            '_links': {'self': url_for('api.get_job', job_id=self.id),
                       'html': url_for('main.job_detail', job_id=self.id, _external=False)},
        }
        if detail:
            data.update({'description': self.description, 'requirements': self.requirements,
                         'benefits': self.benefits, 'working_hours': self.working_hours,
                         'address': self.address, 'slots': self.slots,
                         'experience_level': self.experience_level, 'view_count': self.view_count,
                         'latitude': self.latitude, 'longitude': self.longitude})
        return data


class Application(db.Model):
    __tablename__ = 'applications'
    __table_args__ = (sa.UniqueConstraint('job_id', 'student_id', name='uq_application_job_student'),)
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    job_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('job_posts.id', ondelete='CASCADE'), index=True)
    student_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id'), index=True)
    cover_letter: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    status: so.Mapped[str] = so.mapped_column(sa.String(12), default='PENDING', index=True)
    employer_note: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500))
    match_score: so.Mapped[int] = so.mapped_column(default=0)
    created_at: so.Mapped[datetime] = so.mapped_column(default=utcnow)
    decided_at: so.Mapped[Optional[datetime]]

    job: so.Mapped[JobPost] = so.relationship(back_populates='applications')
    student: so.Mapped[User] = so.relationship(back_populates='applications')

    @property
    def status_label(self):
        return APP_STATUSES.get(self.status, self.status)


class Review(db.Model):
    __tablename__ = 'reviews'
    __table_args__ = (sa.UniqueConstraint('job_id', 'reviewer_id', 'reviewee_id', name='uq_review_once'),)
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    job_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('job_posts.id', ondelete='CASCADE'), index=True)
    reviewer_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id'), index=True)
    reviewee_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id'), index=True)
    rating: so.Mapped[int]
    comment: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    created_at: so.Mapped[datetime] = so.mapped_column(default=utcnow)

    job: so.Mapped[JobPost] = so.relationship()
    reviewer: so.Mapped[User] = so.relationship(foreign_keys=[reviewer_id])
    reviewee: so.Mapped[User] = so.relationship(foreign_keys=[reviewee_id])


class Notification(db.Model):
    __tablename__ = 'notifications'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id', ondelete='CASCADE'), index=True)
    type: so.Mapped[str] = so.mapped_column(sa.String(30), default='SYSTEM')
    message: so.Mapped[str] = so.mapped_column(sa.String(500))
    link: so.Mapped[Optional[str]] = so.mapped_column(sa.String(300))
    read: so.Mapped[bool] = so.mapped_column(default=False, index=True)
    created_at: so.Mapped[datetime] = so.mapped_column(default=utcnow, index=True)

    user: so.Mapped[User] = so.relationship(back_populates='notifications')


class JobAlert(db.Model):
    """Thông báo việc làm: sinh viên lưu tiêu chí, hệ thống báo khi có tin mới khớp."""
    __tablename__ = 'job_alerts'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100))
    keyword: so.Mapped[Optional[str]] = so.mapped_column(sa.String(100))
    category_code: so.Mapped[Optional[str]] = so.mapped_column(sa.String(30))
    city: so.Mapped[Optional[str]] = so.mapped_column(sa.String(60))
    job_type: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    min_salary: so.Mapped[Optional[int]] = so.mapped_column(sa.BigInteger)   # theo tháng
    email_enabled: so.Mapped[bool] = so.mapped_column(default=True)
    active: so.Mapped[bool] = so.mapped_column(default=True)
    created_at: so.Mapped[datetime] = so.mapped_column(default=utcnow)

    user: so.Mapped[User] = so.relationship(back_populates='job_alerts')

    def matches(self, job):
        from .utils.text import fold
        if not self.active or not job.is_open:
            return False
        if self.keyword and fold(self.keyword) not in fold(f'{job.title} {job.skills or ""}'):
            return False
        if self.category_code and (not job.category or job.category.code != self.category_code):
            return False
        if self.city and job.city != self.city:
            return False
        if self.job_type and job.job_type != self.job_type:
            return False
        if self.min_salary and (job.salary_monthly_max or 0) < self.min_salary:
            return False
        return True
