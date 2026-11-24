# Hướng dẫn cho nhà tuyển dụng

## Đăng tin tuyển dụng
Đăng ký với vai trò Nhà tuyển dụng, cập nhật thông tin công ty (hoặc để trống tên công ty nếu là cá nhân).
Vào "Đăng tin": nhập tiêu đề, ngành nghề, loại hình, địa chỉ, mức lương và đơn vị (giờ, ca, ngày, tháng, dự án), số lượng cần tuyển, hạn nộp.
Nút "Gợi ý ngành (AI)" dự đoán ngành nghề từ tiêu đề bằng mô hình Naive Bayes huấn luyện trên dữ liệu VietJobs.
Nút "Gợi ý lương" hiển thị P25, trung vị, P75 của tin bán thời gian cùng ngành và quy đổi ra lương giờ, lương ca.
Địa chỉ được chuyển thành tọa độ qua API OpenStreetMap để hiện bản đồ ở trang chi tiết.

## Duyệt hồ sơ
Trang "Ứng viên" của mỗi tin xếp hồ sơ theo điểm phù hợp (TF-IDF và tỷ lệ khớp kỹ năng). Bấm "Nhận" hoặc "Từ chối" kèm ghi chú.
Khi số người được nhận bằng số lượng cần tuyển, tin tự chuyển sang "Đã đủ người".
Mục "Tìm ứng viên" gợi ý sinh viên phù hợp với tin đang tuyển.

## Trạng thái tin
Đang tuyển → Đã đủ người → Hoàn thành; hoặc Đóng tin. Khi đóng tin, hồ sơ đang chờ bị từ chối tự động.
Khi chuyển sang Hoàn thành, hồ sơ được nhận chuyển thành "Đã hoàn thành" và hai bên được mời đánh giá nhau.
Tin đã có người được nhận không thể xóa, chỉ có thể đóng.
