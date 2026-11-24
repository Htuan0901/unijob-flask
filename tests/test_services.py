from app.services import classifier, market, recommender
from app.utils.text import fold, skill_matches, split_skills, tokenize


def test_tokenize_matches_pipeline():
    assert tokenize('Nhân viên Bán hàng 2024!') == ['nhân', 'viên', 'bán', 'hàng', 'nhân_viên', 'viên_bán', 'bán_hàng']
    assert tokenize('') == []


def test_fold_and_skill_match():
    assert fold('Kỹ năng Đàm phán') == 'ky nang dam phan'
    assert skill_matches('tieng anh', 'Tiếng Anh giao tiếp')
    assert skill_matches('Excel', 'MS Excel')
    assert not skill_matches('Python', 'Photoshop')
    assert split_skills('A; b ;a;,C') == ['A', 'b', 'C']


def test_classifier_top3(app):
    preds = classifier.classify('Thực tập sinh lập trình web Python', 3)
    assert preds[0]['code'] == 'IT' and len(preds) == 3
    assert abs(sum(p['probability'] for p in preds) - 1) < 0.05
    assert classifier.classify('xyzxyz') == []


def test_salary_lookup_fallback(app):
    r = market.salary_lookup('IT', 'NONE', 'Cà Mau')
    assert r['result'] and r['scope'] != 'Trong tỉnh/thành đã chọn'      # ít mẫu -> lùi về phạm vi rộng
    full = market.salary_lookup()
    assert full['result']['count'] > 20000 and len(full['by_experience']) == 8


def test_recommender_similar(app, people):
    from tests.conftest import make_job
    base = make_job(people['emp'])
    near = make_job(people['emp'], title='Pha chế quán cà phê cuối tuần')
    far = make_job(people['emp'], title='Kỹ sư xây dựng công trình', category='CONSTRUCTION', skills='AutoCAD')
    assert recommender.similar(base, [near, far, base], 2) == [near, far]
    gap = recommender.skill_match(['pha che'], ['Pha chế', 'Tiếng Trung'])
    assert gap.score == 50 and gap.missing == ['Tiếng Trung']
