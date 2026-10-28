import pytest
import os
from pathlib import Path
from app import recommender as r


def test_sparse_evidence_stays_near_target_mean_without_mathematical_defect():
    target = {1: 4., 2: 5., 3: 1., 4: 2., 5: 5., 6: 3., 7: 1., 8: 4.}
    users = {1: {1: 4., 2: 5., 9: 5.}, 2: {3: 1., 4: 2., 9: 5.}}
    neighbors = r.nearest_neighbors(target, users)
    assert neighbors == [(1, pytest.approx(1 / 6)), (2, pytest.approx(1 / 6))]
    prediction = r.predict_ratings_with_confidence(target, users, neighbors)[9]
    evidence = 2 / 15
    mean = 25 / 8
    deviation = ((5 - 14 / 3) + (5 - 8 / 3)) / 2
    assert prediction.confidence == pytest.approx(evidence / (evidence + 3))
    assert prediction.raw_score == pytest.approx(mean + evidence / (evidence + 5) * deviation)
    assert .04 < prediction.confidence < .05
    assert mean < prediction.score < mean + .04


@pytest.mark.skipif(not os.environ.get('MOVIELENS_32M_EQUIVALENCE'), reason='Opt-in local 32M profile regression')
def test_reported_profile_reproduces_on_official_32m():
    from app.historical import load_prepared
    from scripts.diagnose_profile import diagnose
    data = load_prepared(Path('data/prepared/ml-32m-v1'))
    try:
        result = diagnose(data)
        assert result['target_mean'] == 3.125
        assert result['top10_below_0_1'] == 10
        assert result['top10'][0]['movie_id'] == 1147
        assert all(3.15 < row['score'] < 3.18 for row in result['top10'])
        assert all(row['confidence'] == pytest.approx(.04411764705882353) for row in result['top10'])
    finally:
        data.close()
