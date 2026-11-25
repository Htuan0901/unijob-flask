"""Trang /ai/assistant: hỏi đáp có trích dẫn, lịch sử 3 lượt trong session, chặn prompt injection, giới hạn tần suất."""
import re
import time

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape
from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from . import ai, rag
from flask import current_app

INJECTION = re.compile(r'(ignore (all|previous|the above)|bỏ qua (mọi|các|tất cả) (chỉ dẫn|hướng dẫn|quy tắc)|'
                       r'system prompt|you are now|đóng vai|jailbreak|reveal .*prompt)', re.I)


class AskForm(FlaskForm):
    question = TextAreaField('Câu hỏi', validators=[DataRequired(), Length(max=500)],
                             render_kw={'rows': 2, 'placeholder': 'VD: Làm sao để rút hồ sơ đã nộp?'})
    submit = SubmitField('Hỏi')


@ai.app_template_filter('chat_format')
def chat_format(text, citations=None):
    """Định dạng câu trả lời: thoát HTML, **đậm**, dòng '- '/'1. ' thành danh sách, [n] thành liên kết tới nguồn."""
    urls = {c['n']: c['url'] for c in (citations or [])}

    def inline(line):
        line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', str(escape(line)))
        return re.sub(r'\[(\d+)\]', lambda m: (f'<a class="cite" href="{urls[int(m[1])]}">[{m[1]}]</a>'
                                                 if int(m[1]) in urls else f'<span class="cite">[{m[1]}]</span>'), line)

    html, in_list = [], False
    for raw in (text or '').splitlines():
        line = raw.strip()
        item = re.match(r'^(?:[-*•]|\d+[.)])\s+(.*)', line)
        if item and not in_list:
            html.append('<ul class="chat-list">')
            in_list = True
        elif not item and in_list:
            html.append('</ul>')
            in_list = False
        if item:
            html.append(f'<li>{inline(item[1])}</li>')
        elif line.startswith('(Chế độ demo'):
            html.append(f'<div class="chat-note"><i class="bi bi-info-circle"></i> {escape(line.strip("()"))}</div>')
        elif line:
            html.append(f'<p>{inline(line)}</p>')
    if in_list:
        html.append('</ul>')
    return Markup(''.join(html))


def clean_input(text):
    text = re.sub(r'[\x00-\x08\x0b-\x1f]', ' ', text or '')
    return ' '.join(text.split())[:current_app.config['AI_MAX_QUESTION']]


def rate_limited():
    now = time.time()
    stamps = [t for t in session.get('ai_calls', []) if now - t < 60]
    if len(stamps) >= current_app.config['AI_RATE_LIMIT']:
        return True
    session['ai_calls'] = stamps + [now]
    return False


def ask(question):
    question = clean_input(question)
    if INJECTION.search(question):
        return {'answer': 'Câu hỏi có chứa yêu cầu thay đổi quy tắc của trợ lý nên không được xử lý.',
                'citations': [], 'provider': 'guard', 'refused': True}
    if rate_limited():
        return {'answer': 'Bạn hỏi quá nhanh, vui lòng thử lại sau 1 phút.', 'citations': [],
                'provider': 'guard', 'refused': True}
    history = session.get('ai_history', [])
    result = rag.answer(question, history, k=current_app.config['AI_TOP_K'])
    result['refused'] = False
    session['ai_history'] = (history + [{'q': question, 'a': result['answer'][:400]}])[-3:]
    return result


@ai.route('/assistant', methods=['GET', 'POST'])
def assistant():
    form = AskForm()
    result = None
    if request.args.get('reset'):
        session.pop('ai_history', None)
        return redirect(url_for('ai.assistant'))
    if form.validate_on_submit():
        result = ask(form.question.data)
        result['question'] = clean_input(form.question.data)
        form.question.data = ''          # ô nhập trống sau khi gửi, như ứng dụng chat
    return render_template('ai/assistant.html', form=form, result=result, history=session.get('ai_history', []),
                           provider=current_app.config['LLM_PROVIDER'])


@ai.route('/ask', methods=['POST'])
def ask_json():
    """Phiên bản JSON cho khung chat nổi (fetch, CSRF qua header X-CSRFToken); kèm 'html' đã định dạng sẵn."""
    data = request.get_json(silent=True) or {}
    if not data.get('question'):
        return jsonify(error='Thiếu câu hỏi'), 400
    result = ask(data['question'])
    result['html'] = str(chat_format(result['answer'], result['citations']))
    return jsonify(result)


@ai.route('/history')
def history_json():
    """Lịch sử hội thoại trong phiên để khung chat nổi hiển thị lại khi chuyển trang."""
    return jsonify(provider=current_app.config['LLM_PROVIDER'],
                   history=[{'q': t['q'], 'html': str(chat_format(t['a']))} for t in session.get('ai_history', [])])


@ai.route('/reset', methods=['POST'])
def reset_json():
    session.pop('ai_history', None)
    return jsonify(ok=True)
