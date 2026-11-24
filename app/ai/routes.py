"""Trang /ai/assistant: hỏi đáp có trích dẫn, lịch sử 3 lượt trong session, chặn prompt injection, giới hạn tần suất."""
import re
import time

from flask import flash, jsonify, redirect, render_template, request, session, url_for
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
    return render_template('ai/assistant.html', form=form, result=result, history=session.get('ai_history', []),
                           provider=current_app.config['LLM_PROVIDER'])


@ai.route('/ask', methods=['POST'])
def ask_json():
    """Phiên bản JSON cho fetch() trên trang (có CSRF qua header X-CSRFToken)."""
    data = request.get_json(silent=True) or {}
    if not data.get('question'):
        return jsonify(error='Thiếu câu hỏi'), 400
    return jsonify(ask(data['question']))
