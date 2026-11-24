"""Phân loại ngành nghề từ tiêu đề tin bằng Multinomial Naive Bayes.

Mô hình huấn luyện offline trên 36.457 tin VietJobs (data-pipeline/pipeline.py), lưu trong
app/data/category_model.json gồm log P(c) và log P(w|c). Ở đây chỉ thực hiện suy luận bằng NumPy:
    score(c) = log P(c) + Σ_w log P(w|c)     ->  softmax  ->  top-k
"""
import numpy as np

from ..utils.text import tokenize
from .data_files import load_json


class CategoryClassifier:
    _instance = None

    def __init__(self, model):
        self.classes = model['classes']
        self.class_names = model.get('classNames', {})
        self.log_prior = np.array(model['logPrior'], dtype=float)
        self.log_lik = np.array(model['logLik'], dtype=float)        # (C, V)
        self.vocab = {w: i for i, w in enumerate(model['vocab'])}
        self.evaluation = model.get('evaluation', {})

    @classmethod
    def get(cls):
        if cls._instance is None:
            model = load_json('category_model.json')
            cls._instance = cls(model) if model else None
        return cls._instance

    def predict(self, title, top_k=3):
        idx = [self.vocab[t] for t in tokenize(title) if t in self.vocab]
        if not idx:
            return []
        scores = self.log_prior + self.log_lik[:, idx].sum(axis=1)
        p = np.exp(scores - scores.max())
        p /= p.sum()
        order = np.argsort(-p)[:top_k]
        return [{'code': self.classes[i], 'name': self.class_names.get(self.classes[i], self.classes[i]),
                 'probability': round(float(p[i]), 3)} for i in order]


def classify(title, top_k=3):
    clf = CategoryClassifier.get()
    return clf.predict(title, top_k) if clf else []
