"""Deterministic offline quality evaluation; never writes reference artifacts.

Run validation first, then freeze its selected configuration with ``select``.
The ``test`` phase refuses to run without that frozen selection and refuses to
overwrite results. Evaluation users are disjoint by a seeded SHA256 ordering.
All validation/test users are removed from the reference pool AND statistics.
The train sample is for harness checks, not parameter selection. Other users
are reference training users. Each target hides a seeded 20% of its ratings.

All variants keep k=15, overlap>=2, positive Pearson, full-profile centering,
genre adjustment, confidence formula, clipping, and deterministic ranking.
Only overlap weighting and pre-clipping deviation shrinkage differ.

To keep the grid practical, vector sufficient statistics screen possible top
neighbors; every possible winner (including near ties) is recomputed with the
production scalar Pearson. A temporary in-memory sorted (user,movie) key array
locates posting ratings. No index is published or added to prepared artifacts.
"""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from math import log2
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import recommender as r
from app.historical import PreparedHistoricalData, load_prepared


SEED = 1042026
STRATA = ((20, 49), (50, 99), (100, 199), (200, 499), (500, 1999))
LAMBDAS = (0., 1., 2., 3., 5., 10.)
ALPHAS = (.5, 1., 2., 5.)
SUPPORTS = ('count', 'similarity', 'evidence')
SELECTION_RULE = {
    'primary': 'highest validation macro NDCG@10 among admissible models',
    'admissible': '95% paired MAE improvement or NDCG improvement over current; beats matched user-mean MAE or has positive paired NDCG improvement over current and item baseline with MAE no more than 0.05 above matched user mean; no material ranking/coverage/stratum regressions; fewer raw out-of-bound predictions',
    'uncertainty': 'paired user bootstrap 95% intervals; no adverse significant ranking or stratum MAE change',
    'coverage_guard': 'at least current coverage overall and at least 90% of current coverage within each stratum',
    'simplicity': 'within one paired standard error of best NDCG, prefer fewer changed components, then lower MAE',
    'test': 'freeze before test; no retuning; reject if main validation improvement reverses materially',
}


@dataclass(frozen=True)
class Variant:
    overlap_lambda: float = 0.
    alpha: float = 0.
    support: str = 'count'

    @property
    def name(self) -> str:
        return f'l{self.overlap_lambda:g}_a{self.alpha:g}_{self.support}'


def grid() -> list[Variant]:
    return [Variant(lam, alpha, support) for lam in LAMBDAS
            for alpha, support in [(0., 'count')] + [(a, s) for a in ALPHAS for s in SUPPORTS]]


def stable_key(value, purpose):
    return hashlib.sha256(f'{SEED}:{purpose}:{value}'.encode()).digest()


def sample_users(data: PreparedHistoricalData, per_stratum: int = 60) -> list[dict]:
    if per_stratum < 6 or per_stratum % 6:
        raise ValueError('per-stratum must be a positive multiple of 6, at least 6')
    sizes = np.diff(data.arrays['user_offsets'])
    sample = []
    for lo, hi in STRATA:
        eligible = np.flatnonzero((sizes >= lo) & (sizes <= hi))
        ordered = sorted(map(int, eligible), key=lambda ui: stable_key(int(data.arrays['user_ids'][ui]), 'users'))
        if len(ordered) < per_stratum:
            raise ValueError(f'Not enough users in {lo}-{hi}: need {per_stratum}')
        for position, ui in enumerate(ordered[:per_stratum]):
            split = 'train' if position < per_stratum // 6 else 'validation' if position < per_stratum * 2 // 3 else 'test'
            sample.append({'index': ui, 'id': int(data.arrays['user_ids'][ui]),
                           'stratum': f'{lo}-{hi}', 'split': split, 'ratings': int(sizes[ui])})
    return sample


def holdout(profile: dict[int, float], user: int) -> tuple[dict[int, float], dict[int, float]]:
    ordered = sorted(profile, key=lambda m: stable_key(f'{user}:{m}', 'holdout'))
    hidden = set(ordered[:max(4, len(profile) // 5)])
    return ({m: v for m, v in profile.items() if m not in hidden},
            {m: profile[m] for m in sorted(hidden)})


def reference_statistics(data: PreparedHistoricalData, excluded):
    counts = np.array(data.arrays['movie_counts'], dtype=np.int64)
    totals = np.array(data.arrays['movie_totals'])
    for ui in excluded:
        movies, ratings = data.profile(int(ui))
        counts[movies] -= 1
        totals[movies] -= ratings
    baseline = float(totals.sum() / counts.sum())
    means = np.divide(totals, counts, out=np.full(len(counts), baseline), where=counts > 0)
    return counts, totals, means, baseline


def rating_keys(data: PreparedHistoricalData) -> np.ndarray:
    a = data.arrays
    keys = np.empty(len(a['profile_movie_indices']), dtype=np.uint64)
    # Chunking avoids a second corpus-sized user-ID array.
    for start in range(0, len(a['user_ids']), 1000):
        end = min(start + 1000, len(a['user_ids']))
        first, last = int(a['user_offsets'][start]), int(a['user_offsets'][end])
        users = np.repeat(np.arange(start, end, dtype=np.uint64), np.diff(a['user_offsets'][start:end+1]).astype(np.int64))
        keys[first:last] = users * len(a['movie_ids']) + a['profile_movie_indices'][first:last]
    return keys


def neighbor_pools(target: r.Profile, data: PreparedHistoricalData, keys: np.ndarray, excluded, lambdas):
    """Share one overlap pass across the grid, recomputing scalar tie contenders."""
    a = {k: np.asarray(v) for k, v in data.arrays.items()}
    mapped, indices = r._mapped_target(target, data)
    size = len(a['user_ids'])
    n = np.zeros(size)
    sx = np.zeros(size)
    sy = np.zeros(size)
    xx = np.zeros(size)
    yy = np.zeros(size)
    xy = np.zeros(size)
    for movie, mi in zip(mapped, indices):
        users = data.postings(mi)
        positions = np.searchsorted(keys, users.astype(np.uint64) * len(a['movie_ids']) + mi)
        values = a['profile_ratings'][positions]
        x = target[movie]
        n[users] += 1
        sx[users] += x
        sy[users] += values
        xx[users] += x*x
        yy[users] += values*values
        xy[users] += x*values
    n[np.asarray(excluded, dtype=int)] = 0
    valid = n >= 2
    denominator_n = np.where(valid, n, 1)
    vx = xx - sx*sx/denominator_n
    vy = yy - sy*sy/denominator_n
    valid &= (vx > 1e-9) & (vy > 1e-9)
    sims = np.zeros(size)
    sims[valid] = np.clip((xy[valid] - sx[valid]*sy[valid]/n[valid]) / np.sqrt(vx[valid]*vy[valid]), -1, 1)
    contenders = set()
    for lam in lambdas:
        adjusted = sims if lam == 0 else sims * n / np.where(n + lam > 0, n + lam, 1)
        positives = np.flatnonzero(adjusted > 0)
        if len(positives):
            threshold = np.partition(adjusted[positives], max(0, len(positives)-15))[max(0, len(positives)-15)]
            # MovieLens half-step ratings keep screening roundoff far below
            # this margin. Preserve all exact/near ties, not just 15 float rows.
            contenders.update(map(int, np.flatnonzero(valid & (adjusted >= max(0, threshold-1e-8)))))
    exact = []
    for ui in sorted(contenders):
        shared = r._shared_ratings(mapped, indices, a, ui)
        similarity = r.pearson_similarity(target, shared)
        if similarity > 0:
            exact.append((int(a['user_ids'][ui]), similarity, len(shared)))
    return {lam: sorted([(uid, s if lam == 0 else s*ov/(ov+lam), ov) for uid, s, ov in exact],
                        key=lambda x: (-x[1], x[0]))[:15] for lam in lambdas}


def candidate_statistics(target: r.Profile, data: PreparedHistoricalData, neighbors):
    weighted = {}
    similarities = {}
    counts = {}
    evidence = {}
    for uid, s, ov in neighbors:
        ui = data.user_index(uid)
        ms, vs = data.profile(ui)
        mean = float(data.arrays['user_means'][ui])
        e = min(s, 1.) * min(ov / 5, 1.)
        for mi, value in zip(ms, vs):
            movie = int(data.arrays['movie_ids'][mi])
            if movie in target:
                continue
            weighted[movie] = weighted.get(movie, 0.) + s * (float(value)-mean)
            similarities[movie] = similarities.get(movie, 0.) + s
            counts[movie] = counts.get(movie, 0) + 1
            evidence[movie] = evidence.get(movie, 0.) + e
    movies = np.array(sorted(weighted), dtype=np.int64)
    sums = np.array([similarities[m] for m in movies])
    deviation = np.array([weighted[m] for m in movies]) / sums
    return movies, deviation, sums, np.array([counts[m] for m in movies]), np.array([evidence[m] for m in movies])


def variant_predictions(stats, mean: float, variant: Variant, aggregates: np.ndarray, baseline: float):
    movies, deviation, similarities, counts, evidence = stats
    support = {'count': counts, 'similarity': similarities, 'evidence': evidence}[variant.support]
    weight = 1. if variant.alpha == 0 else support / (support + variant.alpha)
    raw = mean + weight * deviation
    confidence = evidence / (evidence + 3.)
    scores = np.clip(np.clip(raw, .5, 5.) + np.clip(.2*confidence*aggregates, -.35, .35), .5, 5.)
    ranking = baseline + confidence*(scores-baseline)
    order = np.lexsort((movies, -raw, -scores, -ranking))
    return raw, scores, confidence, movies[order[:10]]


def ranking_metrics(top, hidden):
    relevant = {m for m, v in hidden.items() if v >= 4.}
    hits = [int(int(m) in relevant) for m in top]
    ideal = sum(1/log2(i+2) for i in range(min(10, len(relevant))))
    return {'precision10': sum(hits)/10, 'recall10': sum(hits)/len(relevant) if relevant else None,
            'ndcg10': sum(h/log2(i+2) for i, h in enumerate(hits))/ideal if ideal else None}


def error_totals(errors):
    errors = np.asarray(errors)
    return {'n': len(errors), 'absolute': float(np.abs(errors).sum()), 'squared': float((errors**2).sum())}


def record(user, hidden, movies, scores, top, *, confidence=None, raw=None, support=None, overlaps=(), baseline_scores=None, control=None):
    positions = {int(m): i for i, m in enumerate(movies)}
    covered = [m for m in hidden if m in positions]
    indexes = np.array([positions[m] for m in covered], dtype=int)
    errors = np.array([scores[positions[m]] - hidden[m] for m in covered])
    row = {**user, 'hidden': len(hidden), **error_totals(errors), **ranking_metrics(top, hidden)}
    if baseline_scores is not None:
        for name, values in baseline_scores.items():
            row[f'matched_{name}_mean'] = error_totals([
                (values[m] if isinstance(values, dict) else values)-hidden[m] for m in covered
            ])
    if control is not None:
        common = [m for m in covered if m in control]
        row['common'] = error_totals([scores[positions[m]]-hidden[m] for m in common])
        row['common_current'] = error_totals([control[m]-hidden[m] for m in common])
    if confidence is not None:
        conf = confidence[indexes]
        absolute = np.abs(errors)
        row.update(candidate_n=len(movies), support_sum=int(support.sum()), single=int((support==1).sum()),
                   le2=int((support<=2).sum()), raw_outside=int(((raw<.5)|(raw>5)).sum()),
                   endpoints=int(((scores==.5)|(scores==5)).sum()), overlaps=list(map(int, overlaps)),
                   held_support_sum=int(support[indexes].sum()), held_single=int((support[indexes]==1).sum()),
                   held_le2=int((support[indexes]<=2).sum()), held_raw_outside=int(((raw[indexes]<.5)|(raw[indexes]>5)).sum()),
                   held_endpoints=int(((scores[indexes]==.5)|(scores[indexes]==5)).sum()))
        row['confidence_moments'] = [len(conf), float(conf.sum()), float(absolute.sum()), float((conf*conf).sum()), float((absolute*absolute).sum()), float((conf*absolute).sum())]
        row['buckets'] = {str(i): error_totals(errors[(conf>=i/10)&(conf<(i+1)/10)]) for i in range(10)}
    return row


def aggregate(rows):
    n = sum(x['n'] for x in rows)
    hidden = sum(x['hidden'] for x in rows)
    result = {'users': len(rows), 'hidden': hidden, 'covered': n, 'coverage': n/hidden if hidden else 0,
              'mae': sum(x['absolute'] for x in rows)/n if n else None,
              'rmse': (sum(x['squared'] for x in rows)/n)**.5 if n else None}
    for metric in ('precision10', 'recall10', 'ndcg10'):
        values = [x[metric] for x in rows if x[metric] is not None]
        result[metric] = float(np.mean(values)) if values else None
    if rows and 'candidate_n' in rows[0]:
        candidates = sum(x['candidate_n'] for x in rows)
        for name in ('support_sum','single','le2','raw_outside','endpoints'):
            result[name] = sum(x[name] for x in rows)/candidates if candidates else 0
        for name in ('held_support_sum','held_single','held_le2','held_raw_outside','held_endpoints'):
            result[name] = sum(x[name] for x in rows)/n if n else 0
        ovs = [ov for x in rows for ov in x['overlaps']]
        result['neighbor_overlaps'] = {str(ov): ovs.count(ov) for ov in sorted(set(ovs))}
        moments = np.sum([x['confidence_moments'] for x in rows], axis=0)
        nn, sx, sy, xx, yy, xy = moments
        denom = ((nn*xx-sx*sx)*(nn*yy-sy*sy))**.5
        result['confidence_error_correlation'] = float((nn*xy-sx*sy)/denom) if denom>0 else None
        result['confidence_buckets'] = {}
        for i in range(10):
            bs = [x['buckets'][str(i)] for x in rows]
            bn = sum(b['n'] for b in bs)
            if bn:
                result['confidence_buckets'][str(i)] = {'n': bn, 'mae': sum(b['absolute'] for b in bs)/bn, 'rmse': (sum(b['squared'] for b in bs)/bn)**.5}
        for key in ('matched_user_mean','matched_global_mean','matched_item_mean','common','common_current'):
            if key in rows[0]:
                bs = [x[key] for x in rows]
                bn = sum(b['n'] for b in bs)
                result[key] = {'n': bn, 'mae': sum(b['absolute'] for b in bs)/bn if bn else None,
                               'rmse': (sum(b['squared'] for b in bs)/bn)**.5 if bn else None}
    return result


def paired_interval(left, right, metric, repetitions=2000):
    """Resample users, preserving their paired counts/errors and missing labels."""
    pairs = [(a,b) for a,b in zip(left,right) if a['id']==b['id']]
    if len(pairs)!=len(left) or len(left)!=len(right):
        raise ValueError('Unpaired user records')
    rng = np.random.default_rng(SEED)
    sampled = rng.integers(0,len(pairs),(repetitions,len(pairs)))
    def values(rows):
        if metric=='mae':
            counts = np.array([x['n'] for x in rows])
            errors = np.array([x['absolute'] for x in rows])
            denominators = counts[sampled].sum(axis=1)
            draws = np.divide(errors[sampled].sum(axis=1),denominators,out=np.full(repetitions,np.nan),where=denominators>0)
            return errors.sum()/counts.sum() if counts.sum() else float('nan'),draws
        numbers = np.array([float('nan') if x[metric] is None else x[metric] for x in rows])
        return float(np.nanmean(numbers)),np.nanmean(numbers[sampled],axis=1)
    lv,ld = values(left)
    rv,rd = values(right)
    differences = ld-rd
    return {'difference': lv-rv, 'lower': float(np.nanquantile(differences,.025)),
            'upper': float(np.nanquantile(differences,.975)), 'standard_error': float(np.nanstd(differences,ddof=1))}


def evaluate_user(user, data, keys, excluded, counts, totals, means, baseline, variants, scalar_check=False):
    ms, rs = data.profile(user['index'])
    full = {int(data.arrays['movie_ids'][m]):float(v) for m,v in zip(ms,rs)}
    target, hidden = holdout(full, user['id'])
    mean = sum(target.values())/len(target)
    omitted = np.unique(np.append(excluded,user['index']))
    pools = neighbor_pools(target,data,keys,omitted,sorted(set(v.overlap_lambda for v in variants)))
    if scalar_check:
        # Independent exhaustive indexed scan checks screening on one train
        # user in each stratum, with the same excluded-reference mask.
        mapped, idx = r._mapped_target(target,data)
        a = {k:np.asarray(v) for k,v in data.arrays.items()}
        ovs = r._dense_overlap_counts(idx,a,None)
        ovs[omitted] = 0
        exact = []
        for ui in np.flatnonzero(ovs>=2):
            s = r.pearson_similarity(target,r._shared_ratings(mapped,idx,a,int(ui)))
            if s>0:
                exact.append((int(a['user_ids'][ui]),s,int(ovs[ui])))
        for lam,pool in pools.items():
            wanted = sorted([(uid,s if lam==0 else s*ov/(ov+lam),ov) for uid,s,ov in exact],key=lambda x:(-x[1],x[0]))[:15]
            if pool!=wanted:
                raise AssertionError(f'Scalar screening mismatch for {user["id"]}, lambda {lam}')
    if user['split']=='train':
        cc = counts.copy()
        tt = totals.copy()
        cc[ms]-=1
        tt[ms]-=rs
        baseline = float(tt.sum()/cc.sum())
        item = np.divide(tt,cc,out=np.full(len(cc),baseline),where=cc>0)
    else:
        cc = counts
        item = means
    genres = data.genres
    preferences = r.genre_preferences(target,genres)
    baseline_scores = {'user':mean,'global':baseline,
                     'item':{m:float(item[data.movie_index(m)]) for m in hidden}}
    results = {}
    controls = None
    for lam in sorted(pools):
        stats = candidate_statistics(target,data,pools[lam])
        movies = stats[0]
        aggregates = np.array([sum(preferences.get(g,0.) for g in set(genres[m]) if g!='(no genres listed)')/max(1,len(set(genres[m])-{'(no genres listed)'})) for m in movies])
        for variant in (v for v in variants if v.overlap_lambda==lam):
            raw,scores,conf,top = variant_predictions(stats,mean,variant,aggregates,baseline)
            if not len(movies):
                ids = np.asarray(data.arrays['movie_ids'])
                eligible = np.flatnonzero((cc>=20)&~np.isin(ids,list(target)))
                top = ids[eligible[np.lexsort((ids[eligible],-cc[eligible],-item[eligible]))[:10]]]
            if variant==Variant():
                controls = dict(zip(map(int,movies),map(float,scores)))
            results[variant.name] = record(user,hidden,movies,scores,top,confidence=conf,raw=raw,support=stats[3],
                overlaps=[x[2] for x in pools[lam]],baseline_scores=baseline_scores,control=controls)
    ids = np.asarray(data.arrays['movie_ids'])
    available = cc>0
    # Train users are in reference statistics; subtract their entire profile
    # for their own baseline. Validation/test users were already removed.
    unseen = ~np.isin(ids,list(target))
    for name,scores in [('global',np.full(len(ids),baseline)),('user',np.full(len(ids),mean)),('item',item)]:
        # Constant-score ties use movie ID. Item ranking uses >=20 reference
        # ratings, preventing singleton perfect averages dominating baseline.
        # Item predictions use the global reference mean when no training
        # rating exists, so baseline coverage includes that explicit fallback.
        eligible = np.flatnonzero(unseen & ((cc>=20) if name=='item' else available))
        top = ids[eligible[np.lexsort((ids[eligible],-scores[eligible]))[:10]]]
        results[name] = record(user,hidden,ids,scores,top)
    return results


def summaries(records):
    return {name:{'overall':aggregate(rows),'strata':{s:aggregate([x for x in rows if x['stratum']==s]) for s in sorted(set(x['stratum'] for x in rows))}} for name,rows in records.items()}


def test_decision(records, winner):
    """Apply the frozen acceptance rule; never search the test configuration."""
    rows = records[winner]
    current = records[Variant().name]
    metrics = aggregate(rows)
    baseline = aggregate(current)
    paired = {m:paired_interval(rows,current,m) for m in ('mae','precision10','recall10','ndcg10')}
    vs_item = paired_interval(rows,records['item'],'ndcg10')
    failures = []
    if not (paired['mae']['upper']<0 or paired['ndcg10']['lower']>0):
        failures.append('main quality improvement not confirmed')
    if not (metrics['mae']<metrics['matched_user_mean']['mae'] or
            (paired['ndcg10']['lower']>0 and vs_item['lower']>0 and
             metrics['mae']<=metrics['matched_user_mean']['mae']+.05)):
        failures.append('mean baseline bar not met')
    if any(paired[m]['upper']<0 for m in ('precision10','recall10','ndcg10')):
        failures.append('ranking regression')
    if metrics['coverage']<baseline['coverage']:
        failures.append('coverage collapse')
    if metrics['raw_outside']>=baseline['raw_outside']:
        failures.append('extremes not reduced')
    strata = {}
    for s in sorted(set(x['stratum'] for x in rows)):
        rr = [x for x in rows if x['stratum']==s]
        aa = [x for x in current if x['stratum']==s]
        strata[s] = paired_interval(rr,aa,'mae')
        if strata[s]['lower']>0:
            failures.append(f'{s} significant MAE regression')
        if aggregate(rr)['coverage']<.9*aggregate(aa)['coverage']:
            failures.append(f'{s} coverage regression')
    return {'accepted':not failures,'failures':failures,'paired_vs_current':paired,
            'ndcg_vs_item':vs_item,'stratum_mae_intervals':strata}


def choose(records):
    """Validation-only gates declared above; a failed search yields no model."""
    current = records[Variant().name]
    baseline = aggregate(current)
    candidates = []
    checks = {}
    for variant in grid()[1:]:
        rows = records[variant.name]
        metrics = aggregate(rows)
        ndcg = paired_interval(rows,current,'ndcg10')
        comparisons = {m:paired_interval(rows,current,m) for m in ('mae','precision10','recall10')}
        item_ndcg = paired_interval(rows,records['item'],'ndcg10')
        failures = []
        if not (comparisons['mae']['upper']<0 or ndcg['lower']>0):
            failures.append('no clear quality improvement')
        if not (metrics['mae']<metrics['matched_user_mean']['mae'] or (ndcg['lower']>0 and item_ndcg['lower']>0 and metrics['mae']<=metrics['matched_user_mean']['mae']+.05)):
            failures.append('does not beat mean baseline or justify small error tradeoff with ranking')
        if any(comparisons[m]['upper']<0 for m in ('precision10','recall10')) or ndcg['upper']<0:
            failures.append('ranking regression')
        if metrics['coverage']<baseline['coverage']:
            failures.append('coverage collapse')
        if metrics['raw_outside']>=baseline['raw_outside']:
            failures.append('extremes not reduced')
        for s in sorted(set(x['stratum'] for x in rows)):
            rr = [x for x in rows if x['stratum']==s]
            aa = [x for x in current if x['stratum']==s]
            if aggregate(rr)['coverage']<.9*aggregate(aa)['coverage']:
                failures.append(f'{s} coverage regression')
            ci = paired_interval(rr,aa,'mae',500)
            if ci['lower']>0:
                failures.append(f'{s} significant MAE regression')
        checks[variant.name] = {'failures':failures,'ndcg_vs_current':ndcg,'ndcg_vs_item':item_ndcg,**comparisons}
        if not failures:
            candidates.append((variant,metrics,ndcg))
    if not candidates:
        return {'winner':None,'rule':SELECTION_RULE,'checks':checks}
    best = max(candidates,key=lambda x:x[1]['ndcg10'])
    within = [x for x in candidates if best[1]['ndcg10']-x[1]['ndcg10']<=paired_interval(records[x[0].name],records[best[0].name],'ndcg10')['standard_error']]
    selected = min(within,key=lambda x:(int(x[0].overlap_lambda>0)+int(x[0].alpha>0),x[1]['mae'],x[0].overlap_lambda,x[0].alpha,x[0].support))
    return {'winner':asdict(selected[0]),'rule':SELECTION_RULE,'checks':checks,
            'admissible':[x[0].name for x in candidates],'best_ndcg':best[0].name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,default=Path('data/prepared/ml-32m-v1'))
    parser.add_argument('--output',type=Path,default=Path('data/evaluation/stage10-quality'))
    parser.add_argument('--phase',choices=('train','validation','select','test'),required=True)
    parser.add_argument('--per-stratum',type=int,default=60)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    destination = args.output/f'{args.phase}.json'
    if destination.exists():
        raise SystemExit(f'Refusing to overwrite {destination}; use another output directory for a new experiment')
    if args.phase=='select':
        validation = json.loads((args.output/'validation.json').read_text())
        decision = choose(validation['records'])
        decision['validation_sha256'] = hashlib.sha256((args.output/'validation.json').read_bytes()).hexdigest()
        destination.write_text(json.dumps(decision,indent=2))
        print(json.dumps({k:v for k,v in decision.items() if k!='checks'},indent=2))
        return
    if args.phase=='test':
        decision = json.loads((args.output/'select.json').read_text())
        if decision['winner'] is None:
            raise SystemExit('No admissible validation model; do not open test set')
        variants = list(dict.fromkeys([Variant(),Variant(**decision['winner'])]))
        expected = hashlib.sha256((args.output/'validation.json').read_bytes()).hexdigest()
        if expected!=decision['validation_sha256']:
            raise SystemExit('Validation records changed after freeze')
    else:
        variants = grid() if args.phase=='validation' else [Variant()]
    started = time.perf_counter()
    data = load_prepared(args.prepared)
    try:
        sample = sample_users(data,args.per_stratum)
        manifest_path = args.output/'design.json'
        design = {'seed':SEED,'sample':sample,'rule':SELECTION_RULE,'lambda_grid':LAMBDAS,'alpha_grid':ALPHAS,
                'support_grid':SUPPORTS,'holdout_fraction':.2,'relevance':4,'k':15,'min_overlap':2,
                'dataset':data.manifest['dataset'],'rating_count':data.manifest['rating_count'],
                'item_ranking_min_count':20,'tail_excluded_above':1999}
        if manifest_path.exists():
            if json.loads(manifest_path.read_text())!=json.loads(json.dumps(design)):
                raise SystemExit('Experiment design differs from frozen design')
        else:
            manifest_path.write_text(json.dumps(design,indent=2))
        excluded = np.array([u['index'] for u in sample if u['split']!='train'],dtype=int)
        counts,totals,means,baseline = reference_statistics(data,excluded)
        keys = rating_keys(data)
        records = {v.name:[] for v in variants}
        records.update({name:[] for name in ('global','user','item')})
        checked = set()
        for user in (u for u in sample if u['split']==args.phase):
            scalar_check = args.phase=='train' and user['stratum'] not in checked
            result = evaluate_user(user,data,keys,excluded,counts,totals,means,baseline,variants,scalar_check)
            checked.add(user['stratum'])
            for name,row in result.items():
                records[name].append(row)
            # Per-user checkpoint is ignored, enables review without reopening
            # final test; incomplete phases cannot be selected.
            (args.output/f'{args.phase}-progress.json').write_text(json.dumps({'records':records}))
            print(f'{args.phase} {len(records[variants[0].name])}: user {user["id"]}, {user["stratum"]}',flush=True)
        result = {'phase':args.phase,'seconds':time.perf_counter()-started,'reference_global_mean':baseline,
                'records':records,'summaries':summaries(records),'scalar_checked_strata':sorted(checked) if args.phase=='train' else []}
        if args.phase=='test':
            winner = Variant(**decision['winner']).name
            result['decision'] = test_decision(records,winner)
        destination.write_text(json.dumps(result,indent=2))
        print(json.dumps(result['summaries'][variants[-1].name]['overall'],indent=2))
    finally:
        data.close()


if __name__=='__main__':
    main()
