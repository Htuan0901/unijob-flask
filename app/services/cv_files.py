"""Lưu / xóa / đọc tệp CV (PDF) của sinh viên.

- Tệp lưu ngoài thư mục static (instance/uploads/cv) để không ai tải trực tiếp được;
  muốn xem phải qua route có kiểm tra quyền (main.student_cv).
- Tên tệp trên đĩa sinh ngẫu nhiên, tên gốc được làm sạch bằng secure_filename chỉ để hiển thị.
- Kiểm tra cả phần mở rộng (ở form) lẫn chữ ký đầu tệp '%PDF-' (ở đây) để chặn tệp giả đuôi .pdf.
- CV_STORAGE=db: lưu nội dung PDF vào cột cv_data trong CSDL thay cho ổ đĩa. Dùng khi deploy lên host có
  ổ đĩa tạm (Render free...), vì mỗi lần khởi động lại tệp trên đĩa bị xóa còn CSDL Postgres thì giữ nguyên.
"""
import os
import secrets

from flask import current_app
from werkzeug.utils import secure_filename

from ..models import utcnow

PDF_MAGIC = b'%PDF-'


class CVError(ValueError):
    pass


def use_db():
    return (current_app.config.get('CV_STORAGE') or 'disk').lower() == 'db'


def upload_dir():
    folder = current_app.config.get('CV_UPLOAD_FOLDER') or os.path.join(current_app.instance_path, 'uploads', 'cv')
    os.makedirs(folder, exist_ok=True)
    return folder


def cv_path(profile):
    return os.path.join(upload_dir(), profile.cv_filename) if profile and profile.cv_filename else None


def save_cv(profile, file_storage):
    """Ghi tệp PDF cho hồ sơ sinh viên, thay thế CV cũ nếu có."""
    head = file_storage.stream.read(len(PDF_MAGIC))
    file_storage.stream.seek(0)
    if head != PDF_MAGIC:
        raise CVError('Tệp không phải PDF hợp lệ.')
    original = secure_filename(file_storage.filename or '') or 'cv.pdf'
    if not original.lower().endswith('.pdf'):
        original += '.pdf'
    new_name = f'cv_{profile.user_id}_{secrets.token_hex(8)}.pdf'
    delete_cv_file(profile)
    if use_db():
        profile.cv_data = file_storage.stream.read()
    else:
        file_storage.save(os.path.join(upload_dir(), new_name))
    profile.cv_filename, profile.cv_original_name, profile.cv_uploaded_at = new_name, original, utcnow()
    return new_name


def read_cv(profile):
    """Trả về nội dung PDF (bytes) hoặc None nếu không có."""
    if not profile or not profile.cv_filename:
        return None
    if profile.cv_data:
        return profile.cv_data
    path = cv_path(profile)
    if path and os.path.exists(path):
        with open(path, 'rb') as f:
            return f.read()
    return None


def delete_cv_file(profile):
    path = cv_path(profile)
    if path and os.path.exists(path):
        os.remove(path)
    profile.cv_data = None


def remove_cv(profile):
    delete_cv_file(profile)
    profile.cv_filename = profile.cv_original_name = profile.cv_uploaded_at = None
