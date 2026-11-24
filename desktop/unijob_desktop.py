"""UniJob Desktop – ứng dụng Tkinter gọi REST API của web UniJob.

Vận dụng các chương GUI của môn học:
  - Ch.1–3: Tk, ttk widget, Notebook (tab), Treeview, Combobox, Menu, messagebox
  - Ch.2:   quản lý bố cục bằng grid/pack, LabelFrame
  - Ch.4:   tách lớp dữ liệu (UniJobClient) khỏi giao diện
  - Ch.5:   nhúng biểu đồ Matplotlib vào Tkinter (FigureCanvasTkAgg)
  - Ch.6:   luồng (threading) + hàng đợi (queue) để gọi mạng không làm treo giao diện; lập trình mạng urllib

Chạy:  python desktop/unijob_desktop.py --server http://127.0.0.1:5000
"""
import argparse
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import ApiError, UniJobClient  # noqa: E402

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402


class UniJobDesktop(tk.Tk):
    def __init__(self, server):
        super().__init__()
        self.title('UniJob Desktop')
        self.geometry('1000x640')
        self.minsize(820, 520)
        self.client = UniJobClient(server)
        self.results = queue.Queue()
        self.page = 1
        self.categories = []
        self._build_menu()
        self._build_ui()
        self.after(100, self._poll_results)
        self.run_async(self.client.categories, self._on_categories)
        self.search()

    # ---------------------------------------------------------------- luồng nền
    def run_async(self, fn, on_done, *args, **kwargs):
        """Chạy fn ở luồng phụ; kết quả đưa vào queue, luồng GUI lấy ra trong _poll_results()."""
        self.status.set('Đang tải...')

        def worker():
            try:
                self.results.put((on_done, fn(*args, **kwargs), None))
            except ApiError as e:
                self.results.put((on_done, None, e))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_results(self):
        try:
            while True:
                callback, result, error = self.results.get_nowait()
                self.status.set('Sẵn sàng' if error is None else f'Lỗi: {error.message}')
                if error is not None:
                    messagebox.showerror('UniJob', error.message)
                else:
                    callback(result)
        except queue.Empty:
            pass
        self.after(100, self._poll_results)

    # ---------------------------------------------------------------- giao diện
    def _build_menu(self):
        menubar = tk.Menu(self)
        m = tk.Menu(menubar, tearoff=0)
        m.add_command(label='Đăng nhập...', command=self.login_dialog)
        m.add_command(label='Đăng xuất', command=self.logout)
        m.add_separator()
        m.add_command(label='Thoát', command=self.destroy)
        menubar.add_cascade(label='Tài khoản', menu=m)
        h = tk.Menu(menubar, tearoff=0)
        h.add_command(label='Giới thiệu', command=lambda: messagebox.showinfo(
            'UniJob Desktop', 'Ứng dụng desktop gọi REST API của UniJob\nĐồ án Lập trình Python nâng cao'))
        menubar.add_cascade(label='Trợ giúp', menu=h)
        self.config(menu=menubar)

    def _build_ui(self):
        self.status = tk.StringVar(value='Sẵn sàng')
        self.user_label = tk.StringVar(value='Chưa đăng nhập')
        top = ttk.Frame(self, padding=(8, 6))
        top.pack(fill='x')
        ttk.Label(top, text='UniJob Desktop', font=('Segoe UI', 14, 'bold')).pack(side='left')
        ttk.Label(top, textvariable=self.user_label).pack(side='right')

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=8, pady=4)
        nb.add(self._jobs_tab(nb), text='Việc làm')
        nb.add(self._stats_tab(nb), text='Thống kê')
        nb.add(self._post_tab(nb), text='Đăng tin (NTD)')
        nb.bind('<<NotebookTabChanged>>', lambda e: nb.index('current') == 1 and self.load_stats())

        ttk.Label(self, textvariable=self.status, relief='sunken', anchor='w', padding=(6, 2)).pack(fill='x', side='bottom')

    def _jobs_tab(self, parent):
        f = ttk.Frame(parent, padding=8)
        bar = ttk.Frame(f)
        bar.pack(fill='x')
        self.q = tk.StringVar()
        self.cat = tk.StringVar()
        ttk.Label(bar, text='Từ khóa').pack(side='left')
        e = ttk.Entry(bar, textvariable=self.q, width=30)
        e.pack(side='left', padx=4)
        e.bind('<Return>', lambda ev: self.search())
        ttk.Label(bar, text='Ngành').pack(side='left', padx=(10, 0))
        self.cat_box = ttk.Combobox(bar, textvariable=self.cat, width=34, state='readonly')
        self.cat_box.pack(side='left', padx=4)
        ttk.Button(bar, text='Tìm', command=self.search).pack(side='left', padx=4)
        ttk.Button(bar, text='◀', width=3, command=lambda: self.search(self.page - 1)).pack(side='right')
        self.page_label = ttk.Label(bar, text='Trang 1')
        self.page_label.pack(side='right', padx=6)
        ttk.Button(bar, text='▶', width=3, command=lambda: self.search(self.page + 1)).pack(side='right')

        body = ttk.PanedWindow(f, orient='horizontal')
        body.pack(fill='both', expand=True, pady=6)
        cols = ('title', 'company', 'city', 'salary')
        self.tree = ttk.Treeview(body, columns=cols, show='headings', selectmode='browse')
        for c, text, w in zip(cols, ('Tiêu đề', 'Nhà tuyển dụng', 'Tỉnh/thành', 'Lương'), (300, 200, 110, 160)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=w, anchor='w')
        self.tree.bind('<<TreeviewSelect>>', self.show_detail)
        body.add(self.tree, weight=3)
        self.detail = tk.Text(body, wrap='word', width=40, state='disabled', font=('Segoe UI', 10))
        body.add(self.detail, weight=2)
        return f

    def _stats_tab(self, parent):
        f = ttk.Frame(parent, padding=8)
        self.fig = Figure(figsize=(8, 4.5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=f)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        ttk.Button(f, text='Làm mới', command=self.load_stats).pack(anchor='e')
        return f

    def _post_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        box = ttk.LabelFrame(f, text='Tin tuyển dụng mới (cần đăng nhập tài khoản nhà tuyển dụng)', padding=10)
        box.pack(fill='x')
        self.post_vars = {k: tk.StringVar() for k in ('title', 'category', 'city', 'salary_min', 'salary_max')}
        self.post_vars['city'].set('TP. Hồ Chí Minh')
        rows = [('Tiêu đề', 'title'), ('Mã ngành', 'category'), ('Tỉnh/thành', 'city'),
                ('Lương từ (đ/giờ)', 'salary_min'), ('Lương đến (đ/giờ)', 'salary_max')]
        for r, (label, key) in enumerate(rows):
            ttk.Label(box, text=label).grid(row=r, column=0, sticky='w', pady=3)
            ttk.Entry(box, textvariable=self.post_vars[key], width=50).grid(row=r, column=1, sticky='we', pady=3)
        ttk.Button(box, text='Gợi ý ngành (AI)', command=self.suggest_category).grid(row=1, column=2, padx=6)
        ttk.Label(box, text='Mô tả').grid(row=5, column=0, sticky='nw')
        self.post_desc = tk.Text(box, height=6, width=50)
        self.post_desc.grid(row=5, column=1, sticky='we')
        box.columnconfigure(1, weight=1)
        ttk.Button(box, text='Đăng tin', command=self.post_job).grid(row=6, column=1, sticky='e', pady=8)
        return f

    # ---------------------------------------------------------------- hành động
    def _on_categories(self, items):
        self.categories = [('', 'Tất cả ngành')] + [(c['code'], c['name']) for c in items]
        self.cat_box['values'] = [n for _, n in self.categories]
        self.cat_box.current(0)

    def search(self, page=1):
        if page < 1:
            return
        code = dict((n, c) for c, n in self.categories).get(self.cat.get(), '') if self.categories else ''
        self.run_async(self.client.jobs, self._on_jobs, q=self.q.get().strip(), category=code, page=page)

    def _on_jobs(self, data):
        meta = data['_meta']
        if not data['items'] and meta['page'] > 1:
            return
        self.page = meta['page']
        self.page_label.config(text=f"Trang {meta['page']}/{max(meta['total_pages'], 1)} · {meta['total_items']} tin")
        self.tree.delete(*self.tree.get_children())
        for j in data['items']:
            self.tree.insert('', 'end', iid=str(j['id']), values=(j['title'], j['company'], j['city'], j['salary_label']))

    def show_detail(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self.run_async(self.client.job, self._on_detail, int(sel[0]))

    def _on_detail(self, j):
        text = (f"{j['title']}\n{j['company']} – {j['city']}\nLương: {j['salary_label']}\n"
                f"Loại hình: {j['job_type']} · Cần {j['slots']} người\nKỹ năng: {', '.join(j['skills'])}\n\n"
                f"{j['description']}\n\nYêu cầu:\n{j.get('requirements') or '—'}")
        self.detail.config(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text)
        self.detail.config(state='disabled')

    def load_stats(self):
        self.run_async(self.client.stats, self._on_stats)

    def _on_stats(self, s):
        self.fig.clear()
        ax1, ax2 = self.fig.subplots(1, 2, gridspec_kw={'width_ratios': [3, 2]})
        cats = sorted(s['jobs_by_category'], key=lambda x: x['count'])
        ax1.barh([c['name'].split(' - ')[0] for c in cats], [c['count'] for c in cats], color='#1b2a4a')
        ax1.set_title('Tin theo ngành', fontsize=10)
        ax1.tick_params(labelsize=7)
        st = s['applications_by_status']
        if st:
            ax2.pie([x['count'] for x in st], labels=[x['status'] for x in st], autopct='%1.0f%%',
                    textprops={'fontsize': 7}, wedgeprops={'width': 0.45})
        ax2.set_title(f"Hồ sơ ứng tuyển · {s['open_jobs']} tin đang tuyển", fontsize=10)
        self.fig.tight_layout()
        self.canvas.draw()

    def login_dialog(self):
        win = tk.Toplevel(self)
        win.title('Đăng nhập')
        win.transient(self)
        email, pw = tk.StringVar(value='ntd@unijob.vn'), tk.StringVar(value='Tuyendung@123')
        ttk.Label(win, text='Email').grid(row=0, column=0, padx=8, pady=6, sticky='w')
        ttk.Entry(win, textvariable=email, width=32).grid(row=0, column=1, padx=8)
        ttk.Label(win, text='Mật khẩu').grid(row=1, column=0, padx=8, pady=6, sticky='w')
        ttk.Entry(win, textvariable=pw, show='•', width=32).grid(row=1, column=1, padx=8)

        def done(user):
            self.user_label.set(f"{user['full_name']} ({user['role']})")
            win.destroy()
        ttk.Button(win, text='Đăng nhập',
                   command=lambda: self.run_async(self.client.login, done, email.get(), pw.get())
                   ).grid(row=2, column=1, sticky='e', padx=8, pady=8)

    def logout(self):
        self.run_async(self.client.logout, lambda _: self.user_label.set('Chưa đăng nhập'))

    def suggest_category(self):
        title = self.post_vars['title'].get().strip()
        if title:
            self.run_async(self.client.classify, self._on_classify, title)

    def _on_classify(self, preds):
        if preds:
            self.post_vars['category'].set(preds[0]['code'])
            self.status.set('Gợi ý: ' + ', '.join(f"{p['name']} {p['probability']:.0%}" for p in preds))

    def post_job(self):
        if not self.client.token:
            messagebox.showwarning('UniJob', 'Hãy đăng nhập bằng tài khoản nhà tuyển dụng.')
            return
        v = {k: x.get().strip() for k, x in self.post_vars.items()}
        payload = {'title': v['title'], 'category': v['category'].upper(), 'city': v['city'],
                   'description': self.post_desc.get('1.0', 'end').strip(), 'salary_unit': 'HOUR',
                   'job_type': 'PART_TIME'}
        for k in ('salary_min', 'salary_max'):
            if v[k].isdigit():
                payload[k] = int(v[k])
        self.run_async(self.client.create_job, lambda j: messagebox.showinfo(
            'UniJob', f"Đã đăng tin #{j['id']}: {j['title']}"), **payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='UniJob Desktop')
    parser.add_argument('--server', default=os.environ.get('UNIJOB_SERVER', 'http://127.0.0.1:5000'))
    UniJobDesktop(parser.parse_args().server).mainloop()
