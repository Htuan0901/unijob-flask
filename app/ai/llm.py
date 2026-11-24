"""Gọi LLM qua HTTP bằng urllib (http_client.post_json) – đổi nhà cung cấp chỉ bằng biến môi trường.

LLM_PROVIDER=demo   : không gọi mạng, ghép câu trả lời trích từ đoạn văn truy hồi được (chạy mọi máy)
LLM_PROVIDER=ollama : POST {LLM_BASE_URL}/api/chat          (Ollama cục bộ, vd qwen2.5:3b)
LLM_PROVIDER=openai : POST {LLM_BASE_URL}/chat/completions  (OpenAI hoặc endpoint tương thích, cần LLM_API_KEY)
"""
from flask import current_app

from ..net.http_client import NetworkError, post_json


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, provider='demo', model=None, base_url=None, api_key=None, timeout=60):
        self.provider, self.model, self.base_url = provider, model, (base_url or '').rstrip('/')
        self.api_key, self.timeout = api_key, timeout

    @classmethod
    def from_config(cls):
        c = current_app.config
        return cls(c['LLM_PROVIDER'], c['LLM_MODEL'], c['LLM_BASE_URL'], c['LLM_API_KEY'])

    def chat(self, messages, temperature=0.2, hits=None, question=''):
        if self.provider == 'demo':
            return self._demo(hits or [], question)
        try:
            if self.provider == 'ollama':
                data = post_json(f'{self.base_url}/api/chat', {
                    'model': self.model, 'messages': messages, 'stream': False,
                    'options': {'temperature': temperature}}, timeout=self.timeout)
                return data['message']['content'].strip()
            if self.provider == 'openai':
                if not self.api_key:
                    raise LLMError('Thiếu LLM_API_KEY')
                data = post_json(f'{self.base_url}/chat/completions',
                                 {'model': self.model, 'messages': messages, 'temperature': temperature},
                                 headers={'Authorization': f'Bearer {self.api_key}'}, timeout=self.timeout)
                return data['choices'][0]['message']['content'].strip()
        except (NetworkError, KeyError, IndexError, TypeError) as e:
            current_app.logger.warning('LLM lỗi: %s', e)
            raise LLMError(str(e)) from e
        raise LLMError(f'LLM_PROVIDER không hỗ trợ: {self.provider}')

    @staticmethod
    def _demo(hits, question=''):
        """Chế độ demo (không gọi LLM): với mỗi đoạn đủ liên quan, chọn 1-2 câu trùng nhiều từ với câu hỏi nhất."""
        from ..utils.text import fold
        qwords = {w for w in fold(question).split() if len(w) > 1}
        top = hits[0].score if hits else 0
        lines = ['Theo hướng dẫn và dữ liệu của UniJob:']
        for i, h in enumerate(hits[:3], 1):
            if i > 1 and h.score < 0.6 * top:          # bỏ đoạn kém liên quan hơn hẳn đoạn đầu
                continue
            sentences = [x.strip().rstrip('.') for x in h.chunk.text.replace(';', '.').split('. ') if x.strip()]
            ranked = sorted(sentences, key=lambda x: -len(qwords & set(fold(x).split())))
            best = [x for x in sentences if x in ranked[:2]]          # giữ thứ tự gốc
            prefix = f'Tin "{h.chunk.title}": ' if h.chunk.source == 'job' else ''
            lines.append(f'- {prefix}{". ".join(best)}. [{i}]')
        lines.append('(Chế độ demo: câu trả lời được trích từ tài liệu, chưa qua mô hình ngôn ngữ.)')
        return '\n'.join(lines)
