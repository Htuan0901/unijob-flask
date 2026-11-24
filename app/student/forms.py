from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired, FileSize
from wtforms import (BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from ..constants import CATEGORIES, CITIES, JOB_TYPES


class ProfileForm(FlaskForm):
    full_name = StringField('Họ và tên', validators=[DataRequired(), Length(2, 120)])
    phone = StringField('Số điện thoại', validators=[Optional(), Length(max=20)])
    university = StringField('Trường', validators=[Optional(), Length(max=150)])
    major = StringField('Ngành học', validators=[Optional(), Length(max=120)])
    year_of_study = IntegerField('Năm thứ', validators=[Optional(), NumberRange(1, 7)])
    city = SelectField('Khu vực muốn làm', choices=[(c, c) for c in CITIES])
    preferred_category = SelectField('Ngành quan tâm', choices=[('', '— Chọn —')] + CATEGORIES, validators=[Optional()])
    skills = StringField('Kỹ năng (phân tách bằng dấu ;)', validators=[Optional(), Length(max=500)],
                         render_kw={'placeholder': 'Excel;Canva;Tiếng Anh;Giao tiếp'})
    availability = StringField('Thời gian rảnh', validators=[Optional(), Length(max=200)],
                               render_kw={'placeholder': 'Tối T2–T6, cả ngày cuối tuần'})
    bio = TextAreaField('Giới thiệu bản thân', validators=[Optional(), Length(max=2000)], render_kw={'rows': 4})
    submit = SubmitField('Lưu hồ sơ')


class JobAlertForm(FlaskForm):
    name = StringField('Tên thông báo', validators=[DataRequired(), Length(max=100)],
                       render_kw={'placeholder': 'VD: Gia sư tiếng Anh Thủ Đức'})
    keyword = StringField('Từ khóa', validators=[Optional(), Length(max=100)])
    category_code = SelectField('Ngành', choices=[('', 'Tất cả')] + CATEGORIES, validators=[Optional()])
    city = SelectField('Tỉnh/thành', choices=[('', 'Toàn quốc')] + [(c, c) for c in CITIES], validators=[Optional()])
    job_type = SelectField('Loại hình', choices=[('', 'Tất cả')] + list(JOB_TYPES.items()), validators=[Optional()])
    min_salary = IntegerField('Lương tối thiểu (triệu/tháng)', validators=[Optional(), NumberRange(0, 200)])
    email_enabled = BooleanField('Gửi email khi có tin khớp', default=True)
    active = BooleanField('Đang bật', default=True)
    submit = SubmitField('Lưu')


class ReviewForm(FlaskForm):
    rating = SelectField('Số sao', choices=[(str(i), '★' * i) for i in range(5, 0, -1)], validators=[DataRequired()])
    comment = TextAreaField('Nhận xét', validators=[Optional(), Length(max=1000)], render_kw={'rows': 3})
    submit = SubmitField('Gửi đánh giá')


class CVUploadForm(FlaskForm):
    """Tải CV lên (Flask-WTF FileField): chỉ nhận PDF, tối đa CV_MAX_MB (mặc định 5 MB)."""
    cv = FileField('Tệp CV (PDF)', validators=[
        FileRequired('Hãy chọn tệp CV.'),
        FileAllowed(['pdf'], 'Chỉ nhận tệp PDF.'),
        FileSize(max_size=5 * 1024 * 1024, message='CV tối đa 5 MB.'),
    ], render_kw={'accept': 'application/pdf,.pdf'})
    submit = SubmitField('Tải CV lên')
