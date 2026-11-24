# UniJob (Flask) – Nền tảng việc làm part-time cho sinh viên

Đồ án môn **Lập trình Python nâng cao** (71ITSE31003). Đây là bản phát triển tiếp đồ án UniJob (bản gốc Spring Boot + React)
được viết lại hoàn toàn bằng **Python/Flask** theo yêu cầu của môn học: Flask + Jinja2, Flask-WTF, Flask-SQLAlchemy,
Flask-Mail, lập trình mạng (urllib/JSON/XML/API key), cấu trúc ứng dụng lớn và kiểm thử.

## Chạy nhanh

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # (tùy chọn) cấu hình email thật, khóa API, LLM
flask db upgrade                 # tạo CSDL SQLite data-dev.sqlite từ migration
flask seed                       # nạp dữ liệu mẫu (~370 tin, 29 sinh viên, 8 NTD)
flask run                        # http://127.0.0.1:5000
```

Lệnh khác: `flask test` (chạy 69 test pytest), `flask seed --reset`, `flask ai-reindex`, `flask shell`.
Docker: `docker build -t unijob . && docker run -p 5000:5000 unijob`.

### Bản chạy thật trên web
Deploy lên Render (Docker) + Neon Postgres miễn phí: xem [DEPLOY.md](DEPLOY.md). Địa chỉ web: **https://unijob-puhx.onrender.com** (gói free, lần mở đầu có thể chờ khoảng 1 phút).

### Tài khoản demo
| Vai trò | Email | Mật khẩu |
|---|---|---|
| Sinh viên | sv@unijob.vn | Sinhvien@123 |
| Nhà tuyển dụng | ntd@unijob.vn (hoặc vietsoft@, coffeelab@ ...) | Tuyendung@123 |
| Quản trị viên | admin@unijob.vn | Admin@123 |

### Ứng dụng desktop (Tkinter)
```bash
flask run                                  # cửa sổ 1
python desktop/unijob_desktop.py           # cửa sổ 2 – gọi REST API tại http://127.0.0.1:5000
```

## Cấu trúc thư mục
```
unijob-flask/
├── config.py            # Config / DevelopmentConfig / TestingConfig / ProductionConfig
├── unijob.py            # launch script: create_app(), shell context
├── app/
│   ├── __init__.py      # application factory, khởi tạo extension (init_app)
│   ├── models.py        # 9 model + 2 bảng n-n (saved_jobs, company_follows)
│   ├── email.py         # Flask-Mail, gửi trong luồng nền
│   ├── auth/ main/ student/ employer/ admin/   # blueprint: routes.py + forms.py
│   ├── api/             # REST API JSON + token (auth.py, jobs.py, insights.py)
│   ├── ai/              # trợ lý RAG: rag.py, llm.py, kb/*.md
│   ├── net/             # lập trình mạng urllib: http_client, exchange (API key), geocode, news (RSS/XML)
│   ├── services/        # workflow nghiệp vụ, recommender (TF-IDF), classifier (Naive Bayes), market, charts (Matplotlib)
│   ├── templates/       # Jinja2 (base.html → các trang con), email/*.txt|html
│   └── data/            # dữ liệu VietJobs đã xử lý: seed_jobs, market_stats, category_model
├── migrations/          # Flask-Migrate (Alembic)
├── desktop/             # ứng dụng Tkinter + client urllib
└── tests/               # pytest: 69 test
```

## CV PDF của sinh viên

Sinh viên vào *CV của tôi* để tải CV (PDF, tối đa 5 MB). Nhà tuyển dụng và admin xem hoặc tải CV ở trang
*Ứng viên*, *Tìm ứng viên* và hồ sơ sinh viên. Tệp lưu ở `instance/uploads/cv` (đổi bằng `CV_UPLOAD_FOLDER`), hoặc lưu trong CSDL khi đặt `CV_STORAGE=db`
(dùng khi deploy lên host không có ổ đĩa bền).
Tài khoản demo `sv@unijob.vn` có sẵn một CV mẫu sau khi chạy `flask seed`.
Đã có CSDL từ bản trước: chạy `flask db upgrade` để thêm cột CV.

## Biến môi trường chính
`SECRET_KEY`, `DATABASE_URL` (production, vd Postgres), `CV_STORAGE` (`disk`/`db`), `DEV_DATABASE_URL` (vd `mysql+pymysql://user:pass@localhost/unijob`), `MAIL_SERVER`, `MAIL_USERNAME`,
`MAIL_PASSWORD` (không đặt MAIL_SERVER → email lưu ở `instance/outbox`, xem tại Quản trị › Hộp thư đi),
`EXCHANGE_API_KEY`, `NETWORK_ENABLED`, `LLM_PROVIDER` (`demo`/`ollama`/`openai`), `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`.

## REST API
| Phương thức | Đường dẫn | Mô tả | Xác thực |
|---|---|---|---|
| POST / DELETE | /api/tokens | Lấy / thu hồi token | HTTP Basic / Bearer |
| GET | /api/jobs?q=&category=&city=&job_type=&page=&per_page= | Tìm tin, phân trang, `_links` | – |
| GET | /api/jobs/{id}, /api/jobs/{id}/similar | Chi tiết, việc tương tự | – |
| POST / PUT / PATCH / DELETE | /api/jobs, /api/jobs/{id} | CRUD tin của nhà tuyển dụng | Bearer (EMPLOYER) |
| GET | /api/me/recommendations, /api/me/applications | Gợi ý, hồ sơ của sinh viên | Bearer (STUDENT) |
| GET | /api/categories, /api/stats, /api/rates | Danh mục, thống kê, tỷ giá | – |
| GET | /api/insights/classify?title=, /salary-suggestion?category=, /salary-lookup | Dữ liệu/AI | – |

Ví dụ: `curl -u ntd@unijob.vn:Tuyendung@123 -X POST http://127.0.0.1:5000/api/tokens`

## Ghi chú
- Bootstrap được phục vụ cục bộ qua Bootstrap-Flask nên giao diện chạy được khi không có Internet. Bản đồ (Leaflet + OSM tile) cần Internet.
- Khi không có mạng, tỷ giá / RSS / geocode tự dùng dữ liệu dự phòng và ghi rõ nguồn.
