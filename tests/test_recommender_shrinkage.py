"""Hand calculations and integration checks for the accepted default model."""

import numpy as np
import pytest

from app import recommender as r
from scripts.evaluate_recommender import (
    Variant, candidate_statistics, neighbor_pools, rating_keys, variant_predictions,
)
from test_evaluation import prepared


def test_default_constants_are_the_frozen_validation_choice():
    assert r.PEARSON_SHRINKAGE == 10
    assert r.PREDICTION_SHRINKAGE == 5


def test_overlap_weighting_changes_selection_and_confidence_consistently():
    target = {1:1.,2:2.,3:3.,4:4.,5:5.}
    users = {1:{1:1.,2:2.,9:5.},2:{**target,9:5.}}
    neighbors = r.nearest_neighbors(target,users)
    assert neighbors==[(2,5/15),(1,2/12)]
    assert r.pearson_similarity(target,users[1])==1
    predictions = r.predict_ratings_with_confidence(target,users,neighbors)
    evidence = 5/15+(2/12)*.4
    assert predictions[9].confidence==pytest.approx(evidence/(evidence+3))
    mean1 = 8/3
    mean2 = 20/6
    deviation = ((5/15)*(5-mean2)+(2/12)*(5-mean1))/(5/15+2/12)
    assert predictions[9].raw_score==pytest.approx(3+(evidence/(evidence+5))*deviation)


def test_single_two_overlap_neighbor_cannot_copy_extreme_rating_unshrunk():
    target = {1:1.,2:5.}
    users = {1:{1:1.,2:5.,3:5.}}
    neighbors = r.nearest_neighbors(target,users)
    prediction = r.predict_ratings_with_confidence(target,users,neighbors)[3]
    # E=(1/6)*(.4)=1/15; E/(E+5)=1/76; confidence=1/46.
    assert prediction.raw_score==pytest.approx(3+(4/3)/76)
    assert prediction.confidence==pytest.approx(1/46)
    assert 3 < prediction.score < 3.02


def test_more_evidence_increases_deviation_weight_without_fabricating_support():
    target = {1:1.,2:5.}
    users = {u:{1:1.,2:5.,3:5.} for u in range(1,5)}
    one = r.predict_ratings_with_confidence(target,users,[(1,1/6)])[3]
    four = r.predict_ratings_with_confidence(target,users,[(u,1/6) for u in users])[3]
    assert 3 < one.raw_score < four.raw_score < 3+4/3
    assert one.confidence < four.confidence
    assert r.predict_ratings_with_confidence(target,users,[(1,1/6)],min_neighbors=2)=={}
    assert r.predict_ratings_with_confidence(target,users,[(1,1/6),(1,1/6)])[3]==one


@pytest.mark.parametrize('target', [{1:1.,2:5.},{1:5.,2:4.9},{1:4.9,2:5.},{1:.5,2:.51}])
def test_default_prepared_and_dictionary_paths_match_independent_evaluated_model(target):
    users = {1:{1:.5,2:1.,3:5.,4:.5},2:{1:1.,2:3.,3:4.,4:2.}}
    data = prepared(users)
    ns = r.nearest_neighbors(target,users)
    assert r.nearest_neighbors(target,data)==ns
    actual = r.predict_ratings_with_confidence(target,data,ns)
    assert actual==r.predict_ratings_with_confidence(target,users,ns)
    triples = [(uid,s,len(target.keys()&users[uid].keys())) for uid,s in ns]
    stats = candidate_statistics(target,data,triples)
    pref = r.genre_preferences(target,data.genres)
    aggregates = np.array([pref['Action']]*len(stats[0]))
    raw,scores,conf,top = variant_predictions(stats,sum(target.values())/len(target),Variant(10.,5.,'evidence'),aggregates,data.manifest['global_mean'])
    for i,m in enumerate(stats[0]):
        assert raw[i]==actual[m].raw_score
        assert conf[i]==actual[m].confidence
        assert scores[i]==r.genre_adjusted_score(actual[m],data.genres[m],pref)
    assert top.tolist()==[x.movie_id for x in r.recommend_details(target,data,genres=data.genres)]
    if target=={1:4.9,2:5.}:
        assert actual[3].raw_score>5 and actual[3].score==5
    if target=={1:.5,2:.51}:
        assert actual[4].raw_score<.5 and actual[4].score==.5


def test_evaluation_screening_matches_weighted_default_including_user_exclusion():
    target = {1:1.,2:2.,3:3.,4:4.,5:5.}
    users = {i:{**target,10+i:float(i%5+1)} for i in range(1,30)}
    users[40] = {1:1.,2:2.,90:5.}
    data = prepared(users)
    pool = neighbor_pools(target,data,rating_keys(data),[data.user_index(2)],[10.])[10.]
    assert [(uid,s) for uid,s,_ in pool]==r.nearest_neighbors(target,data,exclude_user_id=2)


def test_default_order_is_independent_of_dictionary_insertion_order():
    target = {1:1.,2:5.}
    users = {i:{1:1.,2:5.,3:5.,4:3.} for i in range(1,20)}
    expected = r.recommend_details(target,users)
    reverse = {u:dict(reversed(list(p.items()))) for u,p in reversed(list(users.items()))}
    assert r.recommend_details(dict(reversed(list(target.items()))),reverse)==expected
