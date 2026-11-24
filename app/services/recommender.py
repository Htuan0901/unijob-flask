"""Gợi ý việc làm theo nội dung (content-based filtering) – port từ RecommendationService.java.

- Vector TF-IDF (unigram + bigram, tf = 1 + log f, idf = log((1+n)/(1+df)) + 1)
- score = 0.55*min(1, 2*cosine) + 0.20*tỷ lệ khớp kỹ năng + 0.15*cùng tỉnh + 0.10*đúng ngành  (thang 0..100)
"""
import math
from collections import Counter
from dataclasses import dataclass, field

from ..utils.text import tokenize, truncate, skill_matches


@dataclass
class SkillMatch:
    score: int
    matched: list = field(default_factory=list)
    missing: list = field(default_factory=list)


@dataclass
class Scored:
    job: object
    score: int
    reasons: list


def job_text(j):
    skills = (j.skills or '').replace(';', ' ')
    cat = j.category.name if j.category else ''
    return ' '.join([j.title, j.title, skills, skills, cat, truncate(j.description or '', 500)])


def profile_text(p):
    skills = (p.skills or '').replace(';', ' ')
    return ' '.join([skills, skills, p.major or '', p.bio or '', p.availability or ''])


def _idf(tfs):
    df = Counter()
    for tf in tfs:
        df.update(tf.keys())
    n = len(tfs)
    return {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}


def _weight(tf, idf):
    return {t: (1 + math.log(f)) * idf[t] for t, f in tf.items() if t in idf}


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def skill_match(student_skills, job_skills):
    if not job_skills:
        return SkillMatch(0)
    matched, missing = [], []
    for js in job_skills:
        (matched if any(skill_matches(ss, js) for ss in student_skills) else missing).append(js)
    return SkillMatch(round(100 * len(matched) / len(job_skills)), matched, missing)


def recommend(profile, jobs, exclude_ids=(), limit=10):
    jobs = [j for j in jobs if j.id not in set(exclude_ids)]
    if not jobs or profile is None:
        return []
    tfs = [Counter(tokenize(job_text(j))) for j in jobs]
    idf = _idf(tfs)
    q = _weight(Counter(tokenize(profile_text(profile))), idf)
    my_skills = profile.skill_list
    out = []
    for j, tf in zip(jobs, tfs):
        cos = cosine(q, _weight(tf, idf))
        sm = skill_match(my_skills, j.skill_list)
        same_city = bool(profile.city) and (profile.city or '').lower() == (j.city or '').lower()
        same_cat = bool(profile.preferred_category) and j.category is not None \
            and profile.preferred_category == j.category.code
        s = 0.55 * min(1.0, cos * 2) + 0.20 * sm.score / 100 + (0.15 if same_city else 0) + (0.10 if same_cat else 0)
        reasons = []
        if sm.matched:
            reasons.append('Khớp kỹ năng: ' + ', '.join(truncate(x, 30) for x in sm.matched[:3]))
        if same_city:
            reasons.append(f'Cùng khu vực {j.city}')
        if same_cat:
            reasons.append('Đúng ngành bạn quan tâm')
        if cos > 0.12:
            reasons.append('Nội dung tin phù hợp với hồ sơ')
        out.append(Scored(j, round(s * 100), reasons))
    out.sort(key=lambda x: (x.score, x.job.created_at), reverse=True)
    return out[:limit]


def match_score(profile, job):
    r = recommend(profile, [job], limit=1)
    return r[0].score if r else 0


def similar(target, candidates, limit=4):
    pool = [j for j in candidates if j.id != target.id]
    if not pool:
        return []
    tfs = [Counter(tokenize(job_text(j))) for j in pool + [target]]
    idf = _idf(tfs)
    q = _weight(tfs[-1], idf)
    scored = []
    for j, tf in zip(pool, tfs):
        s = cosine(q, _weight(tf, idf))
        if j.category_id and j.category_id == target.category_id:
            s += 0.15
        if j.city == target.city:
            s += 0.05
        scored.append((s, j))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [j for _, j in scored[:limit]]
