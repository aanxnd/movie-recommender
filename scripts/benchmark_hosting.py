"""Offline reference-only sizing; no application DB, provider calls or downloads."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time


def peak_mib():
    if sys.platform == 'win32':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'working', 'paged_peak',
                'paged', 'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
        counter = Counters()
        counter.cb = ctypes.sizeof(counter)
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        memory = ctypes.WinDLL('psapi').GetProcessMemoryInfo
        memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not memory(kernel.GetCurrentProcess(), ctypes.byref(counter), counter.cb):
            raise RuntimeError('Memory measurement unavailable')
        return counter.peak / 1024**2
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024**2 if sys.platform == 'darwin' else 1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    started = time.perf_counter()
    # Import the real native dependency graph, but never construct/start its app.
    import app.native_release
    from app.bootstrap import verify_local
    from app.historical import load_prepared
    from app import budget, recommender
    from app.schemas import MovieResponse
    imported = time.perf_counter()
    verify_local(args.prepared)
    verified = time.perf_counter()
    data = load_prepared(args.prepared)
    try:
        catalog = {r['movie_id']: MovieResponse(movie_id=r['movie_id'], title=r['title'],
                   genres=r['genres']) for r in data.catalog['movies']}
        genres, years = data.genres, data.release_years
        loaded = time.perf_counter()
        result = dict(platform=platform.platform(), python=platform.python_version(),
            machine=platform.machine(), logical_cpus=os.cpu_count(),
            manifest_sha256=hashlib.sha256((args.prepared / 'manifest.json').read_bytes()).hexdigest(),
            counts={k: data.manifest[k] for k in ('rating_count', 'movie_count', 'user_count')},
            prepared_bytes=sum(p.stat().st_size for p in args.prepared.rglob('*') if p.is_file()),
            import_seconds=imported-started, checksum_seconds=verified-imported,
            load_catalog_seconds=loaded-verified, loaded_peak_mib=peak_mib(), cases={})
        offsets = data.arrays['user_offsets']
        index = next(i for i in range(len(offsets)-1) if int(offsets[i+1]-offsets[i]) >= 100)
        movies, ratings = data.profile(index)
        for size in (5, 20, 100):
            profile = {int(data.arrays['movie_ids'][m]): float(r)
                       for m, r in zip(movies[:size], ratings[:size])}
            wall, cpu = [], []
            for repeat in range(4):
                before, cpu_before = time.perf_counter(), time.process_time()
                with budget.computation():
                    rows = recommender.recommend_details(profile, data, genres=genres)
                if repeat:  # one untimed warmup, three measured serial requests
                    wall.append(time.perf_counter()-before)
                    cpu.append(time.process_time()-cpu_before)
            result['cases'][size] = dict(wall_seconds=wall, cpu_seconds=cpu,
                median_seconds=statistics.median(wall), results=len(rows))
        result['final_peak_mib'] = peak_mib()
        print(json.dumps(result, indent=2, allow_nan=False))
    finally:
        data.close()


if __name__ == '__main__':
    main()
