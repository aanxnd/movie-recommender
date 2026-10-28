"""Read-only MovieLens trace for the eight-film sparse-profile report."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.historical import load_prepared, checksum
from app import recommender as r


PROFILE = {166461: 4., 77427: 5., 5971: 1., 7024: 2., 55768: 5., 79251: 3., 178827: 1., 8906: 4.}


def diagnose(data, profile=PROFILE):
    catalog = {row['movie_id']: row for row in data.catalog['movies']}
    missing = sorted(set(profile) - catalog.keys())
    if missing:
        raise ValueError(f'Reference catalog is missing movie IDs: {missing}')
    neighbors = r.nearest_neighbors(profile, data)
    predictions = r.predict_ratings_with_confidence(profile, data, neighbors)
    results = r.recommend_details(profile, data, genres=data.genres)
    trace = []
    for uid, adjusted in neighbors:
        index = data.user_index(uid)
        shared = r.shared_profile(profile, data, index)
        trace.append({'reference_user': uid, 'overlap': len(shared),
                      'pearson': r.pearson_similarity(profile, shared), 'adjusted_similarity': adjusted,
                      'candidate_evidence_per_supported_movie': adjusted * min(len(shared) / 5, 1),
                      'neighbor_mean': float(data.arrays['user_means'][index])})
    return {'dataset': data.manifest['dataset'], 'ratings': data.manifest['rating_count'],
            'profile': [{'movie_id': m, 'title': catalog[m]['title'], 'rating': v} for m, v in profile.items()],
            'target_mean': sum(profile.values()) / len(profile), 'neighbors': trace,
            'top10': [{**asdict(row), 'title': catalog[row.movie_id]['title'],
                       'raw_score': predictions[row.movie_id].raw_score,
                       'evidence': row.confidence * 3 / (1 - row.confidence) if row.confidence is not None else None}
                      for row in results],
            'top10_below_0_1': sum(row.confidence is not None and row.confidence < .1 for row in results),
            'threshold_policy': '0.1 is a display warning only; no prediction, selection, confidence, ranking or fallback mathematics changed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, default=Path('data/prepared/ml-32m-v1'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = load_prepared(args.prepared)
    try:
        started = time.perf_counter()
        result = diagnose(data)
        result['trace_seconds'] = time.perf_counter() - started
        result['manifest_sha256'] = checksum(args.prepared / 'manifest.json')
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        print('Wrote read-only profile diagnostic')
    finally:
        data.close()


if __name__ == '__main__':
    main()
