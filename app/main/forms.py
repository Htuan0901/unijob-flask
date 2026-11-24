"""Form tìm kiếm (GET, không cần CSRF) và các form nhỏ ở khu vực công khai."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import NumberRange, Optional, Length

from ..constants import CATEGORIES, CITIES, EXPERIENCE_LEVELS, JOB_TYPES

SORTS = [('newest', 'Mới nhất'), ('salary', 'Lương cao nhất'), ('views', 'Xem nhiều'), ('match', 'Phù hợp với tôi (AI)')]
POSTED = [('', 'Bất kỳ lúc nào'), ('1', '24 giờ qua'), ('3', '3 ngày qua'), ('7', '7 ngày qua'), ('30', '30 ngày qua')]


class JobSearchForm(FlaskForm):
    class Meta:
        csrf = False                     # form GET: tham số nằm trên URL, có thể chia sẻ/bookmark

    q = StringField('Từ khóa', validators=[Optional(), Length(max=100)])
    category = SelectField('Ngành nghề', choices=[('', 'Tất cả ngành')] + CATEGORIES, validators=[Optional()])
    city = SelectField('Tỉnh/thành', choices=[('', 'Toàn quốc')] + [(c, c) for c in CITIES], validators=[Optional()])
    job_type = SelectField('Loại hình', choices=[('', 'Tất cả')] + list(JOB_TYPES.items()), validators=[Optional()])
    experience = SelectField('Kinh nghiệm', choices=[('', 'Tất cả')] + list(EXPERIENCE_LEVELS.items()), validators=[Optional()])
    min_salary = IntegerField('Lương tối thiểu (triệu/tháng)', validators=[Optional(), NumberRange(0, 200)])
    posted = SelectField('Đăng trong', choices=POSTED, validators=[Optional()])
    urgent = BooleanField('Chỉ việc gấp')
    sort = SelectField('Sắp xếp', choices=SORTS, default='newest', validators=[Optional()])
    submit = SubmitField('Tìm việc')


class ApplyForm(FlaskForm):
    cover_letter = TextAreaField('Lời nhắn tới nhà tuyển dụng', validators=[Optional(), Length(max=2000)],
                                 render_kw={'rows': 4, 'placeholder': 'Giới thiệu ngắn về bạn, thời gian có thể làm...'})
    submit = SubmitField('Ứng tuyển ngay')


class SalaryLookupForm(FlaskForm):
    class Meta:
        csrf = False

    category = SelectField('Ngành', choices=[('', 'Tất cả ngành')] + CATEGORIES, validators=[Optional()])
    experience = SelectField('Kinh nghiệm', choices=[('', 'Mọi mức')] + list(EXPERIENCE_LEVELS.items()), validators=[Optional()])
    city = SelectField('Tỉnh/thành', choices=[('', 'Toàn quốc')], validators=[Optional()], validate_choice=False)
    submit = SubmitField('Tra cứu')


class EmptyForm(FlaskForm):
    """Form rỗng chỉ để có CSRF token cho các nút POST (lưu tin, theo dõi, ...)."""
    submit = SubmitField('OK')
