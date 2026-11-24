"""Dữ liệu mẫu: 16 ngành, tài khoản demo 3 vai trò, ~370 tin (360 tin thật từ VietJobs đã làm sạch + tin tự tạo),
hồ sơ ứng tuyển ở mọi trạng thái, công việc hoàn thành và đánh giá hai chiều."""
import random
from datetime import timedelta

import sqlalchemy as sa

from . import db
from .constants import CATEGORIES
from .models import (Application, Category, EmployerProfile, JobAlert, JobPost, Notification, Review,
                     StudentProfile, User, utcnow)
from .services import recommender
from .services.data_files import load_json

PW_ADMIN, PW_STUDENT, PW_EMPLOYER = 'Admin@123', 'Sinhvien@123', 'Tuyendung@123'

EMPLOYERS = [
    ('ntd@unijob.vn', 'Trần Thu Hà', 'Công ty TNHH Truyền thông Sao Việt', 'TP. Hồ Chí Minh', '45 Nguyễn Thị Minh Khai, Quận 1',
     'Agency truyền thông số, chuyên sản xuất nội dung và quản lý fanpage cho các thương hiệu F&B.',
     'MARKETING,DESIGN,SALES', 'Truyền thông / Nghệ thuật / Quảng cáo / Giải trí'),
    ('coffeelab@unijob.vn', 'Lê Quang Huy', 'The Coffee Lab', 'TP. Hồ Chí Minh', '12 Phan Xích Long, Phú Nhuận',
     'Chuỗi 6 quán cà phê specialty tại TP.HCM, môi trường trẻ, ca linh hoạt cho sinh viên.', 'HOSPITALITY',
     'Du lịch / Khách sạn / Nhà hàng'),
    ('brightstar@unijob.vn', 'Phạm Ngọc Lan', 'Trung tâm Anh ngữ BrightStar', 'TP. Hồ Chí Minh', '88 Đặng Văn Bi, Thủ Đức',
     'Trung tâm tiếng Anh thiếu nhi và giao tiếp, tuyển trợ giảng và gia sư bán thời gian.', 'EDUCATION,LANGUAGE',
     'Giáo dục / Đào tạo'),
    ('vietsoft@unijob.vn', 'Đỗ Minh Khoa', 'Công ty CP Công nghệ VietSoft', 'TP. Hồ Chí Minh', 'Tòa nhà Etown, Tân Bình',
     'Công ty phần mềm outsource, chương trình thực tập cho sinh viên CNTT.', 'IT,ELECTRONICS',
     'Công nghệ thông tin / IT phần mềm'),
    ('gomart@unijob.vn', 'Vũ Thị Mai', 'Chuỗi cửa hàng tiện lợi GoMart', 'Hà Nội', '102 Cầu Giấy, Hà Nội',
     'Chuỗi cửa hàng tiện lợi 24/7, tuyển nhân viên bán hàng ca xoay.', 'SALES,MANUFACTURING,OTHER,AGRICULTURE,CONSTRUCTION',
     'Bán buôn / Bán lẻ'),
    ('nhanhexpress@unijob.vn', 'Hoàng Văn Nam', 'Nhanh Express Logistics', 'Hà Nội', 'KCN Thăng Long, Đông Anh',
     'Dịch vụ giao nhận chặng cuối, tuyển shipper và nhân viên kho thời vụ.', 'LOGISTICS',
     'Logistics / Vận tải / Kho bãi / Bưu chính'),
    ('anduong@unijob.vn', 'Nguyễn Thị Ánh', 'Ánh Dương Finance', 'Đà Nẵng', '25 Bạch Đằng, Hải Châu',
     'Công ty tư vấn tài chính - kế toán, tuyển thực tập sinh kế toán và hành chính.', 'FINANCE,HR_ADMIN,HEALTHCARE',
     'Tài chính / Ngân hàng / Bảo hiểm'),
    ('canhan.minh@unijob.vn', 'Bùi Đức Minh', None, 'TP. Hồ Chí Minh', 'Quận 7',
     'Cá nhân cần thuê người hỗ trợ ngắn hạn (gia sư, trông cửa hàng, nhập liệu).', '', 'Dịch vụ cá nhân / Hộ gia đình'),
]

# Tin tự tạo, lương theo giờ/ca để minh họa quy đổi lương
EXTRA_JOBS = [
    ('coffeelab@unijob.vn', 'Nhân viên pha chế (Barista) ca tối', 'HOSPITALITY', 'PART_TIME', 25000, 30000, 'HOUR',
     'Ca tối 18h–22h, tối thiểu 4 ca/tuần', 'Pha chế;Giao tiếp;Phục vụ', True),
    ('coffeelab@unijob.vn', 'Phục vụ quán cà phê cuối tuần', 'HOSPITALITY', 'PART_TIME', 110000, 130000, 'SHIFT',
     'Thứ 7 – Chủ nhật, ca 7h–12h hoặc 13h–18h', 'Phục vụ;Giao tiếp;Nhanh nhẹn', False),
    ('brightstar@unijob.vn', 'Trợ giảng tiếng Anh thiếu nhi', 'EDUCATION', 'PART_TIME', 60000, 80000, 'HOUR',
     'Tối T2–T6 17h30–20h30', 'Tiếng Anh;Giảng dạy;Kiên nhẫn', True),
    ('vietsoft@unijob.vn', 'Thực tập sinh Lập trình Web Python/Flask', 'IT', 'INTERNSHIP', 3000000, 5000000, 'MONTH',
     'Thứ 2 – Thứ 6, tối thiểu 3 buổi/tuần', 'Python;Flask;SQL;Git;HTML/CSS', False),
    ('vietsoft@unijob.vn', 'Cộng tác viên kiểm thử phần mềm (Tester)', 'IT', 'FREELANCE', 150000, 200000, 'DAY',
     'Linh hoạt, làm online', 'Kiểm thử phần mềm;Cẩn thận;Excel', False),
    ('nhanhexpress@unijob.vn', 'Nhân viên kho thời vụ cao điểm cuối năm', 'LOGISTICS', 'SEASONAL', 30000, 35000, 'HOUR',
     'Ca 4 tiếng, xoay ca sáng/chiều/tối', 'Quản lý kho;Nhập liệu;Sức khỏe tốt', True),
    ('gomart@unijob.vn', 'Nhân viên bán hàng cửa hàng tiện lợi ca đêm', 'SALES', 'PART_TIME', 28000, 32000, 'HOUR',
     'Ca 22h–6h hoặc 14h–22h', 'Bán hàng;Thu ngân;Trung thực', False),
    ('canhan.minh@unijob.vn', 'Gia sư Toán lớp 8 tại nhà (Quận 7)', 'EDUCATION', 'PART_TIME', 200000, 250000, 'SHIFT',
     '3 buổi/tuần, 19h–21h', 'Toán;Giảng dạy;Kiên nhẫn', False),
]


def _exp_code(text):
    t = (text or '').lower()
    if 'không' in t or not t:
        return 'NONE'
    if 'tháng' in t:
        return 'UNDER_1Y'
    for n, code in (('5', 'Y5'), ('4', 'Y4'), ('3', 'Y3'), ('2', 'Y2'), ('1', 'Y1')):
        if t.startswith(n):
            return code
    return 'NONE'


def _user(email, pw, name, role, phone=None):
    u = User(email=email, full_name=name, role=role, phone=phone, confirmed=True)
    u.set_password(pw)
    db.session.add(u)
    return u


def seed_all():
    rnd = random.Random(42)
    now = utcnow()
    if not db.session.scalar(sa.select(sa.func.count(Category.id))):
        for code, name in CATEGORIES:
            db.session.add(Category(code=code, name=name))
        db.session.flush()
    if db.session.scalar(sa.select(sa.func.count(User.id))):
        return 'CSDL đã có dữ liệu – bỏ qua (dùng --reset để tạo lại).'
    cats = {c.code: c for c in db.session.scalars(sa.select(Category))}
    phone = lambda: '09' + ''.join(str(rnd.randint(0, 9)) for _ in range(8))

    _user('admin@unijob.vn', PW_ADMIN, 'Quản trị viên UniJob', 'ADMIN', '0900000000')

    employers, by_cat = {}, {}
    for email, contact, company, city, addr, desc, codes, industry in EMPLOYERS:
        u = _user(email, PW_EMPLOYER, contact, 'EMPLOYER', phone())
        u.employer_profile = EmployerProfile(company_name=company, individual=company is None, city=city, address=addr,
                                             description=desc, verified=company is not None, industry=industry)
        employers[email] = u
        for c in filter(None, codes.split(',')):
            by_cat.setdefault(c, []).append(u)

    # ---- sinh viên
    last = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ', 'Đặng', 'Bùi', 'Đỗ']
    mid = ['Minh', 'Thị', 'Văn', 'Ngọc', 'Gia', 'Thanh', 'Quốc', 'Hoài', 'Bảo', 'Khánh']
    first = ['Anh', 'Châu', 'Duy', 'Hân', 'Khang', 'Linh', 'My', 'Nhi', 'Phúc', 'Quân', 'Tâm', 'Thảo', 'Trí', 'Uyên',
             'Vy', 'Yến', 'Long', 'Hưng']
    unis = ['Trường Đại học Văn Lang', 'Trường ĐH Kinh tế TP.HCM', 'Trường ĐH Bách khoa - ĐHQG TP.HCM',
            'Trường ĐH Sư phạm TP.HCM', 'Trường ĐH Ngoại thương', 'Trường ĐH Đà Nẵng']
    majors = [('Công nghệ phần mềm', 'IT', 'Python;Flask;ReactJS;SQL;Git;Tiếng Anh'),
              ('Marketing', 'MARKETING', 'Content Marketing;Canva;Facebook Ads;Viết bài SEO;Giao tiếp'),
              ('Thiết kế đồ họa', 'DESIGN', 'Photoshop;Illustrator;Canva;Chỉnh sửa video;Sáng tạo'),
              ('Kế toán', 'FINANCE', 'Excel;MISA;Kế toán thuế;Cẩn thận;Tin học văn phòng'),
              ('Ngôn ngữ Anh', 'EDUCATION', 'Tiếng Anh;IELTS;Giảng dạy;Giao tiếp;Thuyết trình'),
              ('Quản trị khách sạn', 'HOSPITALITY', 'Giao tiếp;Phục vụ;Pha chế;Chăm sóc khách hàng;Tiếng Anh'),
              ('Quản trị kinh doanh', 'SALES', 'Bán hàng;Tư vấn khách hàng;Đàm phán;Excel;Giao tiếp'),
              ('Logistics', 'LOGISTICS', 'Quản lý kho;Excel;Lái xe máy;Nhập liệu;Cẩn thận')]
    students = []
    demo = _user('sv@unijob.vn', PW_STUDENT, 'Nguyễn Minh Anh', 'STUDENT', '0912345678')
    demo.student_profile = StudentProfile(
        university='Trường Đại học Văn Lang', major='Công nghệ phần mềm', year_of_study=3, city='TP. Hồ Chí Minh',
        skills='Python;Flask;SQL;Canva;Content Marketing;Tiếng Anh;Giao tiếp;Excel', preferred_category='IT',
        availability='Tối T2–T6 sau 18h, cả ngày Thứ 7 – Chủ nhật',
        bio='Sinh viên năm 3 ngành Công nghệ phần mềm, yêu thích lập trình web với Python/Flask và sáng tạo nội dung. '
            'Có kinh nghiệm làm cộng tác viên viết bài cho fanpage CLB.')
    students.append(demo)
    for i in range(28):
        name = f'{rnd.choice(last)} {rnd.choice(mid)} {rnd.choice(first)}'
        s = _user(f'sinhvien{i + 1}@unijob.vn', PW_STUDENT, name, 'STUDENT', phone())
        s.created_at = now - timedelta(days=rnd.randint(0, 60))
        m = rnd.choice(majors)
        s.student_profile = StudentProfile(university=rnd.choice(unis), major=m[0], preferred_category=m[1],
                                           year_of_study=rnd.randint(1, 4), skills=m[2],
                                           city=rnd.choice(['TP. Hồ Chí Minh', 'TP. Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng']),
                                           availability=rnd.choice(['Buổi tối các ngày trong tuần', 'Cuối tuần',
                                                                    'Sáng T2, T4, T6']),
                                           bio=f'Sinh viên ngành {m[0]}, mong muốn tìm việc làm thêm phù hợp chuyên ngành.')
        students.append(s)
    db.session.flush()

    # ---- tin tuyển dụng
    all_emp = list(employers.values())
    jobs = []
    for r in load_json('seed_jobs.json') or []:
        owner = rnd.choice(by_cat.get(r['categoryCode']) or all_emp)
        j = JobPost(employer=owner, category=cats.get(r['categoryCode']), title=r['title'][:200],
                    description=r['description'] or r['title'], requirements=r.get('requirements'),
                    benefits='\n'.join(r.get('benefits') or []) or None, skills=';'.join(r.get('skills') or []) or None,
                    city=r['city'], job_type=r['jobType'], salary_min=r['salaryMin'], salary_max=r['salaryMax'],
                    salary_unit=r['salaryUnit'], working_hours=r.get('workingHours'),
                    experience_level=_exp_code(r.get('experience')), slots=rnd.randint(1, 3),
                    urgent=rnd.random() < 0.12, view_count=rnd.randint(5, 400),
                    created_at=now - timedelta(days=rnd.randint(0, 45), hours=rnd.randint(0, 23)))
        j.deadline = (j.created_at + timedelta(days=rnd.randint(25, 60))).date()
        j.update_monthly_salary()
        jobs.append(j)
    coords = {'TP. Hồ Chí Minh': (10.7769, 106.7009), 'Hà Nội': (21.0285, 105.8542), 'Đà Nẵng': (16.0544, 108.2022)}
    for email, title, cat, jt, smin, smax, unit, hours, skills, urgent in EXTRA_JOBS:
        owner = employers[email]
        p = owner.employer_profile
        lat, lng = coords.get(p.city, (None, None))
        j = JobPost(employer=owner, category=cats[cat], title=title, job_type=jt, salary_min=smin, salary_max=smax,
                    salary_unit=unit, working_hours=hours, skills=skills, urgent=urgent, city=p.city, address=p.address,
                    latitude=lat and lat + rnd.uniform(-0.03, 0.03), longitude=lng and lng + rnd.uniform(-0.03, 0.03),
                    description=f'{title} tại {p.name}. Công việc phù hợp sinh viên, được hướng dẫn từ đầu, '
                                f'lịch làm linh hoạt theo lịch học.',
                    requirements='Sinh viên các trường, chăm chỉ, trung thực, có trách nhiệm.',
                    benefits='Lương trả đúng hạn\nĐược đào tạo\nMôi trường trẻ trung', slots=2,
                    view_count=rnd.randint(30, 300), created_at=now - timedelta(days=rnd.randint(0, 6)))
        j.deadline = (now + timedelta(days=30)).date()
        j.update_monthly_salary()
        jobs.append(j)
    db.session.add_all(jobs)
    db.session.flush()

    # ---- ứng tuyển + hoàn thành + đánh giá
    statuses = ['PENDING'] * 5 + ['ACCEPTED'] * 2 + ['REJECTED'] * 2 + ['WITHDRAWN']
    n_apps = n_reviews = 0
    for s in students:
        for j in rnd.sample(jobs, 6 if s is demo else rnd.randint(2, 6)):
            a = Application(job=j, student=s, status=rnd.choice(statuses), cover_letter='Em rất mong được làm việc cùng anh/chị.',
                            match_score=recommender.match_score(s.student_profile, j),
                            created_at=j.created_at + timedelta(days=rnd.randint(0, 5)))
            if a.status in ('ACCEPTED', 'REJECTED'):
                a.decided_at = a.created_at + timedelta(days=1)
            db.session.add(a)
            n_apps += 1
    db.session.flush()
    # một số tin đã hoàn thành, có đánh giá hai chiều
    done_jobs = rnd.sample(jobs[:360], 25)
    comments_s = ['Công việc đúng mô tả, quản lý thân thiện.', 'Trả lương đúng hạn, lịch linh hoạt.',
                  'Môi trường tốt, học được nhiều.', 'Ca làm hơi đông khách nhưng ổn.']
    comments_e = ['Bạn làm việc chăm chỉ, đúng giờ.', 'Nhanh nhẹn, giao tiếp tốt.', 'Cẩn thận, có trách nhiệm.',
                  'Cần chủ động hơn nhưng nhìn chung tốt.']
    for j in done_jobs:
        j.status = 'COMPLETED'
        workers = rnd.sample(students[1:], rnd.randint(1, 2))
        if j.id % 2 == 0:
            workers.append(demo)
        for s in workers:
            existing = db.session.scalar(sa.select(Application).where(Application.job_id == j.id,
                                                                      Application.student_id == s.id))
            if existing is None:
                existing = Application(job=j, student=s, match_score=recommender.match_score(s.student_profile, j),
                                       created_at=j.created_at + timedelta(days=1))
                db.session.add(existing)
            existing.status, existing.decided_at = 'COMPLETED', j.created_at + timedelta(days=2)
            if s is not demo or rnd.random() < 0.5:   # chừa vài đánh giá cho tài khoản demo tự làm
                db.session.add(Review(job=j, reviewer=s, reviewee=j.employer, rating=rnd.choice([4, 5, 5, 3]),
                                      comment=rnd.choice(comments_s), created_at=j.created_at + timedelta(days=10)))
                db.session.add(Review(job=j, reviewer=j.employer, reviewee=s, rating=rnd.choice([4, 5, 5, 4]),
                                      comment=rnd.choice(comments_e), created_at=j.created_at + timedelta(days=10)))
                n_reviews += 2
    db.session.flush()
    for u in db.session.scalars(sa.select(User)):
        u.recalc_rating()
    # ---- job alert + theo dõi + thông báo cho tài khoản demo
    db.session.add(JobAlert(user=demo, name='Thực tập IT tại TP.HCM', category_code='IT', city='TP. Hồ Chí Minh'))
    demo.followed_companies.add(employers['vietsoft@unijob.vn'].employer_profile)
    demo.followed_companies.add(employers['coffeelab@unijob.vn'].employer_profile)
    db.session.add(Notification(user=demo, type='SYSTEM', message='Chào mừng bạn đến với UniJob! Hãy hoàn thiện hồ sơ để nhận gợi ý việc làm.',
                                link='/student/profile'))
    db.session.commit()
    try:
        _demo_cv(demo)          # CV PDF mẫu cho tài khoản sinh viên demo
        db.session.commit()
    except Exception:           # không có matplotlib/ổ đĩa chỉ đọc -> bỏ qua, app vẫn chạy
        db.session.rollback()
    return (f'Đã tạo {len(students)} sinh viên, {len(employers)} nhà tuyển dụng, {len(jobs)} tin, '
            f'{n_apps} hồ sơ, {n_reviews} đánh giá.')


def _demo_cv(user):
    """Vẽ một CV 1 trang bằng Matplotlib (xuất PDF) rồi lưu như tệp sinh viên tự tải lên."""
    import io
    import textwrap

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from werkzeug.datastructures import FileStorage

    from .services.cv_files import save_cv

    p = user.student_profile
    fig = plt.figure(figsize=(8.27, 11.69))            # khổ A4
    fig.patches.append(plt.Rectangle((0, 0.88), 1, 0.12, transform=fig.transFigure, color='#1b2a4a'))
    fig.text(0.08, 0.94, user.full_name, fontsize=24, weight='bold', color='white')
    fig.text(0.08, 0.905, f'{p.major} · {p.university}', fontsize=11, color='#c8d1e4')
    lines = [('Liên hệ', f'{user.email} · {user.phone} · {p.city}'),
             ('Giới thiệu', p.bio),
             ('Kỹ năng', ', '.join(p.skill_list)),
             ('Thời gian có thể làm', p.availability),
             ('Học vấn', f'{p.university} – {p.major}, sinh viên năm {p.year_of_study}')]
    y = 0.83
    for title, body in lines:
        fig.text(0.08, y, title.upper(), fontsize=10, weight='bold', color='#d93a2f')
        fig.text(0.08, y - 0.025, textwrap.fill(body or '', 90), fontsize=10.5, color='#1b2a4a', va='top')
        y -= 0.11
    buf = io.BytesIO()
    fig.savefig(buf, format='pdf')
    plt.close(fig)
    buf.seek(0)
    save_cv(p, FileStorage(buf, filename='CV_Nguyen_Minh_Anh.pdf', content_type='application/pdf'))
