import numpy as np
import pytest

from app import recommender as r
from scripts.evaluate_recommender import (
    Variant, aggregate, candidate_statistics, holdout, neighbor_pools,
    paired_interval, ranking_metrics, rating_keys, record, reference_statistics,
    sample_users, variant_predictions,
)
from app.historical import PreparedHistoricalData
from scripts import evaluate_recommender as evaluation


def prepared(profiles):
    ids = sorted(profiles)
    movies = sorted({m for p in profiles.values() for m in p})
    indexes = {m:i for i,m in enumerate(movies)}
    ms = []
    rs = []
    offsets = [0]
    means = []
    for uid in ids:
        p = profiles[uid]
        ms.extend(indexes[m] for m in sorted(p))
        rs.extend(p[m] for m in sorted(p))
        offsets.append(len(ms))
        means.append(sum(p.values())/len(p))
    postings = []
    movie_offsets = [0]
    counts = []
    totals = []
    for m in movies:
        users = [i for i,uid in enumerate(ids) if m in profiles[uid]]
        postings.extend(users)
        movie_offsets.append(len(postings))
        counts.append(len(users))
        totals.append(sum(profiles[ids[i]][m] for i in users))
    arrays = {'user_ids':np.array(ids),'movie_ids':np.array(movies),'user_offsets':np.array(offsets,dtype=np.uint64),
            'profile_movie_indices':np.array(ms,dtype=np.uint32),'profile_ratings':np.array(rs,dtype=float),
            'user_means':np.array(means),'posting_user_indices':np.array(postings,dtype=np.uint32),
            'movie_offsets':np.array(movie_offsets,dtype=np.uint64),'movie_counts':np.array(counts),
            'movie_totals':np.array(totals,dtype=float)}
    arrays['movie_averages'] = np.array(totals,dtype=float)/np.array(counts)
    arrays['popularity_order'] = np.lexsort((np.array(movies),-np.array(counts),-arrays['movie_averages']))
    return PreparedHistoricalData(arrays,{'movies':[{'movie_id':m,'genres':['Action']} for m in movies]},
                                  {'global_mean':sum(rs)/len(rs)})


def test_holdout_is_deterministic_order_independent_and_disjoint():
    profile = {m:float(m%5+1) for m in range(1,41)}
    train,test = holdout(profile,17)
    assert holdout(dict(reversed(list(profile.items()))),17)==(train,test)
    assert len(test)==8 and not train.keys() & test.keys()
    assert train|test==profile
    assert holdout(profile,18)[1]!=test


def test_stratified_sampling_splits_and_boundaries():
    lengths = [length for length in (20,50,100,200,500) for _ in range(12)]
    data = PreparedHistoricalData({'user_ids':np.arange(1,61),'user_offsets':np.r_[np.uint64(0),np.cumsum(lengths,dtype=np.uint64)]},{},{})
    sample = sample_users(data,12)
    assert sample_users(data,12)==sample
    assert len({x['id'] for x in sample})==60
    assert {s:sum(x['split']==s for x in sample) for s in ('train','validation','test')}=={'train':10,'validation':30,'test':20}
    with pytest.raises(ValueError):
        sample_users(data,7)


def test_reference_statistics_remove_entire_validation_and_test_profiles():
    data = prepared({1:{10:1.,20:5.},2:{10:5.,30:4.},3:{20:3.,30:2.}})
    counts,totals,means,baseline = reference_statistics(data,[1,2])
    assert counts.tolist()==[1,1,0]
    assert totals.tolist()==[1,5,0]
    assert means.tolist()==[1,5,3]
    assert baseline==3


def test_screened_neighbors_match_scalar_control_and_overlap_weighting(monkeypatch):
    monkeypatch.setattr(r, 'PEARSON_SHRINKAGE', 0.)
    target = {1:1.,2:2.,3:3.,4:4.,5:5.}
    profiles = {10:{1:1.,2:2.,9:5.},20:{**target,9:4.},30:{1:5.,2:4.,9:1.},40:dict.fromkeys(target,3.)}
    data = prepared(profiles)
    keys = rating_keys(data)
    pools = neighbor_pools(target,data,keys,[data.user_index(20)],[0.,2.])
    assert [(u,s) for u,s,_ in pools[0.]]==r.nearest_neighbors(target,data,exclude_user_id=20)
    assert pools[2.]==[(10,.5,2)]
    pools = neighbor_pools(target,data,keys,[],[0.,2.])
    assert pools[2.][0]==(20,pytest.approx(5/7),5)
    assert pools[2.][1]==(10,.5,2)


def test_screening_retains_all_perfect_ties_before_user_id_selection(monkeypatch):
    monkeypatch.setattr(r, 'PEARSON_SHRINKAGE', 0.)
    target = {1:1.,2:5.}
    data = prepared({uid:{1:2.,2:4.,100+uid:5.} for uid in range(1,101)})
    pool = neighbor_pools(target,data,rating_keys(data),[],[0.])[0.]
    assert [(u,s) for u,s,_ in pool]==r.nearest_neighbors(target,data)
    assert [u for u,_,_ in pool]==list(range(1,16))


def test_zero_variant_replays_production_predictions_and_ranking(monkeypatch):
    monkeypatch.setattr(r, 'PEARSON_SHRINKAGE', 0.)
    monkeypatch.setattr(r, 'PREDICTION_SHRINKAGE', 0.)
    target = {1:1.,2:5.}
    data = prepared({1:{1:1.,2:5.,3:5.,4:3.},2:{1:1.,2:5.,3:4.,5:2.}})
    ns = r.nearest_neighbors(target,data)
    triples = [(uid,s,len(r.shared_profile(target,data,data.user_index(uid)))) for uid,s in ns]
    stats = candidate_statistics(target,data,triples)
    preferences = r.genre_preferences(target,data.genres)
    aggs = np.full(len(stats[0]),preferences['Action'])
    raw,scores,conf,top = variant_predictions(stats,3,Variant(),aggs,data.manifest['global_mean'])
    expected = r.predict_ratings_with_confidence(target,data,ns)
    for i,m in enumerate(stats[0]):
        assert raw[i]==expected[m].raw_score
        assert scores[i]==r.genre_adjusted_score(expected[m],data.genres[m],preferences)
        assert conf[i]==expected[m].confidence
    assert top.tolist()==[x.movie_id for x in r.recommend_details(target,data,genres=data.genres)]


@pytest.mark.parametrize('support,expected',[('count',4.),('similarity',3+2/3),('evidence',3+2*.4/1.4)])
def test_prediction_shrinkage_uses_named_support_before_clipping(support,expected):
    stats = (np.array([9]),np.array([2.]),np.array([.5]),np.array([1]),np.array([.4]))
    raw,scores,conf,_ = variant_predictions(stats,3.,Variant(0.,1.,support),np.array([0.]),3.5)
    assert raw[0]==pytest.approx(expected)
    assert scores[0]==raw[0]
    assert conf[0]==pytest.approx(.4/3.4)


def test_ranking_denominator_is_ten_and_relevance_is_four():
    metrics = ranking_metrics([8,9],{8:4.,9:3.5,10:5.})
    assert metrics['precision10']==.1
    assert metrics['recall10']==.5
    assert metrics['ndcg10']==pytest.approx(1/(1+1/np.log2(3)))
    assert ranking_metrics([],{8:3.})['recall10'] is None


def test_coverage_common_pairs_and_confidence_buckets_do_not_drop_missing_ratings():
    row = record({'id':1,'stratum':'x'}, {8:5.,9:1.},np.array([8]),np.array([4.]),[8],
               confidence=np.array([.2]),raw=np.array([4.]),support=np.array([1]),overlaps=[2],
               baseline_scores={'user':3.},control={8:3.,10:2.})
    result = aggregate([row])
    assert result['coverage']==.5 and result['mae']==1
    assert result['common']['mae']==1 and result['common_current']['mae']==2
    assert result['confidence_buckets']=={'2':{'n':1,'mae':1.,'rmse':1.}}
    assert result['single']==1


def test_bootstrap_resamples_users_and_preserves_pairs():
    left = [{'id':i,'n':10,'absolute':10.,'ndcg10':.4} for i in range(5)]
    right = [{'id':i,'n':10,'absolute':20.,'ndcg10':.2} for i in range(5)]
    result = paired_interval(left,right,'mae',100)
    assert result['difference']==result['lower']==result['upper']==-1.
    assert paired_interval(left,right,'ndcg10',100)['lower']==pytest.approx(.2)
    with pytest.raises(ValueError):
        paired_interval(left,list(reversed(right)),'mae',100)


def test_selection_rejects_controls_and_freezes_only_an_admissible_variant():
    def rows(improved):
        return [record({'id':i,'stratum':'20-49'}, {8:4.5},np.array([8]),
                       np.array([4.6 if improved else 5.]),[8] if improved else [],
                       confidence=np.array([.4 if improved else .12]),
                       raw=np.array([4.6 if improved else 5.2]),support=np.array([2 if improved else 1]),
                       overlaps=[5 if improved else 2],baseline_scores={'user':4.}) for i in range(6)]
    control = rows(False)
    records = {v.name:control for v in evaluation.grid()}
    records.update({name:control for name in ('global','user','item')})
    assert evaluation.choose(records)['winner'] is None
    selected = Variant(2.,0.)
    records[selected.name] = rows(True)
    assert evaluation.choose(records)['winner']=={'overlap_lambda':2.,'alpha':0.,'support':'count'}
    result = evaluation.test_decision(records,selected.name)
    assert result['accepted'] and not result['failures']
    assert not evaluation.test_decision(records,Variant().name)['accepted']
