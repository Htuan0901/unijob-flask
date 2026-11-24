from datetime import date

from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateField, IntegerField, SelectField, StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, URL, ValidationError

from ..constants import CATEGORIES, CITIES, COMPANY_INDUSTRIES, EXPERIENCE_LEVELS, JOB_TYPES, SALARY_UNITS


class JobForm(FlaskForm):
    title = StringField('Tiêu đề tin', validators=[DataRequired(), Length(5, 200)])
    category = SelectField('Ngành nghề', choices=CATEGORIES, validators=[DataRequired()])
    job_type = SelectField('Loại hình', choices=list(JOB_TYPES.items()), default='PART_TIME')
    city = SelectField('Tỉnh/thành', choices=[(c, c) for c in CITIES])
    address = StringField('Địa chỉ làm việc', validators=[Optional(), Length(max=200)])
    salary_min = IntegerField('Lương từ (đồng)', validators=[Optional(), NumberRange(0, 500_000_000)])
    salary_max = IntegerField('Lương đến (đồng)', validators=[Optional(), NumberRange(0, 500_000_000)])
    salary_unit = SelectField('Tính theo', choices=[(k, 'Mỗi ' + v) for k, v in SALARY_UNITS.items()], default='HOUR')
    working_hours = StringField('Thời gian làm việc', validators=[Optional(), Length(max=200)],
                                render_kw={'placeholder': 'Ca tối 18h–22h, T2–T6'})
    experience_level = SelectField('Kinh nghiệm', choices=list(EXPERIENCE_LEVELS.items()), default='NONE')
    slots = IntegerField('Số lượng cần tuyển', default=1, validators=[DataRequired(), NumberRange(1, 100)])
    deadline = DateField('Hạn nộp hồ sơ', validators=[Optional()])
    skills = StringField('Kỹ năng yêu cầu (phân tách bằng ;)', validators=[Optional(), Length(max=500)])
    description = TextAreaField('Mô tả công việc', validators=[DataRequired(), Length(20, 5000)], render_kw={'rows': 6})
    requirements = TextAreaField('Yêu cầu', validators=[Optional(), Length(max=3000)], render_kw={'rows': 4})
    benefits = TextAreaField('Quyền lợi', validators=[Optional(), Length(max=3000)], render_kw={'rows': 3})
    urgent = BooleanField('Tuyển gấp')
    submit = SubmitField('Lưu tin')

    def validate_salary_max(self, field):
        if field.data and self.salary_min.data and field.data < self.salary_min.data:
            raise ValidationError('Lương tối đa phải lớn hơn hoặc bằng lương tối thiểu.')

    def validate_deadline(self, field):
        if field.data and field.data < date.today():
            raise ValidationError('Hạn nộp phải từ hôm nay trở đi.')


class CompanyForm(FlaskForm):
    full_name = StringField('Người liên hệ', validators=[DataRequired(), Length(2, 120)])
    phone = StringField('Số điện thoại', validators=[Optional(), Length(max=20)])
    company_name = StringField('Tên công ty / cửa hàng (bỏ trống nếu là cá nhân)', validators=[Optional(), Length(max=150)])
    industry = SelectField('Lĩnh vực', choices=[(c, c) for c in COMPANY_INDUSTRIES])
    city = SelectField('Tỉnh/thành', choices=[(c, c) for c in CITIES])
    address = StringField('Địa chỉ', validators=[Optional(), Length(max=200)])
    website = StringField('Website', validators=[Optional(), URL(message='URL không hợp lệ.'), Length(max=200)])
    description = TextAreaField('Giới thiệu', validators=[Optional(), Length(max=3000)], render_kw={'rows': 5})
    submit = SubmitField('Lưu thông tin')


class DecisionForm(FlaskForm):
    note = StringField('Ghi chú cho ứng viên', validators=[Optional(), Length(max=500)])
    accept = SubmitField('Nhận')
    reject = SubmitField('Từ chối')


class StatusForm(FlaskForm):
    status = SelectField('Trạng thái', choices=[('OPEN', 'Đang tuyển'), ('FILLED', 'Đã đủ người'),
                                                ('COMPLETED', 'Hoàn thành'), ('CLOSED', 'Đóng tin')])
    submit = SubmitField('Cập nhật')
