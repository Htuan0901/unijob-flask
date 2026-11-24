"""Danh mục, nhãn tiếng Việt và quy tắc dùng chung (port từ các enum của bản Spring Boot)."""

ROLE_STUDENT, ROLE_EMPLOYER, ROLE_ADMIN = 'STUDENT', 'EMPLOYER', 'ADMIN'
ROLES = {ROLE_STUDENT: 'Sinh viên', ROLE_EMPLOYER: 'Nhà tuyển dụng', ROLE_ADMIN: 'Quản trị viên'}

CATEGORIES = [
    ('SALES', 'Kinh doanh - Bán hàng - CSKH'), ('MANUFACTURING', 'Sản xuất - Lao động phổ thông'),
    ('MARKETING', 'Marketing - Truyền thông - Nội dung'), ('FINANCE', 'Tài chính - Kế toán - Ngân hàng'),
    ('HOSPITALITY', 'Du lịch - Nhà hàng - Khách sạn'), ('DESIGN', 'Thiết kế - Nghệ thuật - Giải trí'),
    ('HR_ADMIN', 'Nhân sự - Hành chính - Pháp chế'), ('CONSTRUCTION', 'Xây dựng - Kiến trúc - Bất động sản'),
    ('IT', 'Công nghệ thông tin'), ('LOGISTICS', 'Logistics - Vận tải'),
    ('ELECTRONICS', 'Kỹ thuật điện - Điện tử'), ('EDUCATION', 'Giáo dục - Đào tạo - Gia sư'),
    ('HEALTHCARE', 'Y tế - Dược - Sức khỏe'), ('LANGUAGE', 'Ngôn ngữ - Dịch thuật'),
    ('OTHER', 'Nhóm nghề khác'), ('AGRICULTURE', 'Nông nghiệp - Môi trường'),
]

JOB_TYPES = {
    'PART_TIME': 'Bán thời gian', 'INTERNSHIP': 'Thực tập', 'SEASONAL': 'Thời vụ',
    'FREELANCE': 'Cộng tác viên', 'FULL_TIME': 'Toàn thời gian',
}
SALARY_UNITS = {'HOUR': 'giờ', 'SHIFT': 'ca', 'DAY': 'ngày', 'MONTH': 'tháng', 'PROJECT': 'dự án'}
EXPERIENCE_LEVELS = {
    'NONE': 'Không yêu cầu', 'UNDER_1Y': 'Dưới 1 năm', 'Y1': '1 năm', 'Y2': '2 năm',
    'Y3': '3 năm', 'Y4': '4 năm', 'Y5': '5 năm', 'OVER_5Y': 'Trên 5 năm',
}
JOB_STATUSES = {'OPEN': 'Đang tuyển', 'FILLED': 'Đã đủ người', 'COMPLETED': 'Hoàn thành', 'CLOSED': 'Đã đóng'}
APP_STATUSES = {
    'PENDING': 'Chờ duyệt', 'ACCEPTED': 'Được nhận', 'REJECTED': 'Bị từ chối',
    'WITHDRAWN': 'Đã rút', 'COMPLETED': 'Đã hoàn thành',
}
# Chuyển trạng thái hợp lệ của tin tuyển dụng
JOB_TRANSITIONS = {
    'OPEN': {'FILLED', 'CLOSED'},
    'FILLED': {'OPEN', 'COMPLETED', 'CLOSED'},
    'COMPLETED': set(),
    'CLOSED': {'OPEN'},
}

# Quy đổi lương về tháng: part-time giả định 4 giờ/ca, 22 ngày/tháng
HOURS_PER_SHIFT = 4
DAYS_PER_MONTH = 22
MONTHLY_FACTOR = {'HOUR': HOURS_PER_SHIFT * DAYS_PER_MONTH, 'SHIFT': DAYS_PER_MONTH,
                  'DAY': DAYS_PER_MONTH, 'MONTH': 1, 'PROJECT': 1}

CITIES = ['TP. Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Cần Thơ', 'Hải Phòng', 'Bắc Ninh', 'Đồng Nai', 'Huế',
          'Hưng Yên', 'Quảng Ninh', 'Tây Ninh', 'Ninh Bình', 'Hà Tĩnh', 'Thanh Hóa', 'Nghệ An', 'Khánh Hòa',
          'Đắk Lắk', 'Phú Thọ', 'Lâm Đồng', 'Toàn quốc']

COMPANY_INDUSTRIES = [
    'Công nghệ thông tin / IT phần mềm', 'Truyền thông / Nghệ thuật / Quảng cáo / Giải trí',
    'Du lịch / Khách sạn / Nhà hàng', 'Giáo dục / Đào tạo', 'Bán buôn / Bán lẻ',
    'Logistics / Vận tải / Kho bãi / Bưu chính', 'Tài chính / Ngân hàng / Bảo hiểm',
    'Sản xuất', 'Xây dựng', 'Y tế / Chăm sóc sức khỏe', 'Dịch vụ cá nhân / Hộ gia đình', 'Khác',
]

NOTIFICATION_TYPES = ('NEW_APPLICATION', 'APPLICATION_ACCEPTED', 'APPLICATION_REJECTED',
                      'APPLICATION_WITHDRAWN', 'JOB_STATUS', 'NEW_REVIEW', 'REVIEW_REMINDER',
                      'JOB_ALERT', 'COMPANY_NEW_JOB', 'SYSTEM')


def category_name(code):
    return dict(CATEGORIES).get(code, code or '')


def to_monthly(amount, unit):
    if amount is None:
        return None
    return int(amount * MONTHLY_FACTOR.get(unit or 'MONTH', 1))
