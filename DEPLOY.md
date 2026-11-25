# Đưa UniJob lên web thật (Render + Neon Postgres, miễn phí)

Kiến trúc: **Render** chạy web từ `Dockerfile` (tự build lại mỗi lần push GitHub), **Neon** cấp Postgres miễn phí
không hết hạn. Render free không có ổ đĩa bền nên đặt `CV_STORAGE=db` để CV PDF lưu trong Postgres.
Mỗi lần khởi động, `boot.sh` tự chạy `flask db upgrade` rồi `flask seed` (chỉ nạp mẫu khi CSDL trống).

## 1. Tạo CSDL trên Neon
1. Vào https://neon.tech, đăng nhập bằng GitHub.
2. *Create project*: tên `unijob`, Postgres 16, region **AWS Asia Pacific (Singapore)**.
3. Ở *Connection string*, bỏ chọn *Connection pooling*, copy chuỗi dạng
   `postgresql://neondb_owner:...@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
   Chuỗi này chứa mật khẩu: chỉ dán vào Render, không đưa lên GitHub.

## 2. Tạo web trên Render
1. Vào https://render.com, đăng nhập bằng GitHub, cho phép Render đọc repo `unijob-flask`.
2. *New* > *Blueprint* > chọn repo `unijob-flask` (Render đọc `render.yaml`).
3. Render hỏi các biến `sync: false`: dán chuỗi Neon vào `DATABASE_URL`; `UNIJOB_ADMIN`, `EXCHANGE_API_KEY` để trống cũng được.
4. *Apply*. Lần build đầu mất khoảng 5–10 phút. Xem *Logs*, khi thấy `Listening at: http://0.0.0.0:10000` là xong.
5. Mở địa chỉ `https://unijob-xxxx.onrender.com`, đăng nhập bằng tài khoản demo trong README.

`SECRET_KEY` do Render tự sinh. Đổi biến ở *Environment* của service rồi Render tự khởi động lại.

## 3. Biến môi trường
| Biến | Giá trị | Ghi chú |
|---|---|---|
| `FLASK_CONFIG` | `production` | có sẵn trong render.yaml |
| `SECRET_KEY` | tự sinh | |
| `DATABASE_URL` | chuỗi Neon | `postgres://` hay `postgresql://` đều được, config.py tự chuyển sang driver psycopg 3 |
| `CV_STORAGE` | `db` | `disk` (mặc định khi chạy máy) lưu ở `instance/uploads/cv` |
| `EXCHANGE_API_KEY` | khóa exchangerate-api.com | tùy chọn |
| `BREVO_API_KEY`, `MAIL_DEFAULT_SENDER` | khóa API Brevo, người gửi đã xác minh | gửi email thật trên Render, xem mục 4 |
| `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD` | Gmail + Mật khẩu ứng dụng | chỉ dùng khi chạy trên máy |

## 4. Email thật (Brevo API)
Gói free của Render chặn kết nối SMTP ra ngoài (cổng 25/465/587), nên web gửi email qua **API HTTPS của Brevo**
(miễn phí 300 email/ngày, code ở `app/email.py`, gọi bằng urllib + JSON).
1. Đăng ký https://www.brevo.com (gói Free), xác minh email đăng ký.
2. *Senders, Domains & Dedicated IPs* > *Senders* > *Add a sender*: nhập tên `UniJob` và địa chỉ Gmail của bạn,
   bấm link xác minh Brevo gửi vào Gmail đó.
3. *SMTP & API* > tab *API Keys* > *Generate a new API key*, copy khóa `xkeysib-...` (chỉ hiện 1 lần).
4. Render > service *unijob* > *Environment* > thêm:
   - `BREVO_API_KEY` = khóa vừa copy
   - `MAIL_DEFAULT_SENDER` = `UniJob <gmail-da-xac-minh@gmail.com>`
5. *Save, rebuild, and deploy*. Đăng ký thử một tài khoản mới, email xác nhận sẽ về hộp thư thật
   (lần đầu có thể nằm trong thư mục Spam/Quảng cáo).

Bản sao mọi email vẫn xem được ở *Quản trị > Hộp thư đi*. Chạy trên máy có thể dùng Gmail SMTP thay thế:
`MAIL_SERVER=smtp.gmail.com`, `MAIL_USERNAME`, `MAIL_PASSWORD` (Mật khẩu ứng dụng) trong `.env`.

## 5. Lưu ý gói free
- Web "ngủ" sau 15 phút không ai truy cập, lần mở đầu chờ khoảng 1 phút. Trước buổi demo nên mở trước vài phút.
- Muốn nạp lại dữ liệu mẫu: Render > service > *Shell* (gói trả phí) hoặc chạy trên máy
  `DATABASE_URL=<chuỗi Neon> FLASK_CONFIG=production flask seed --reset`.
- Ứng dụng desktop Tkinter gọi API web thật: `python desktop/unijob_desktop.py --server https://unijob-xxxx.onrender.com`.
