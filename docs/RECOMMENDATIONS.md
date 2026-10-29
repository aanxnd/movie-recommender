# Sparse-profile investigation

Reproduced against the existing official ml-32m artifacts (32,000,204 ratings). Matched IDs: Moana (2016) 166461, Human Centipede first sequence 77427, Totoro 5971, Salò 7024, Bee Movie 55768, A Serbian Film 79251, Paddington 2 178827, Cannibal Holocaust 8906. Ratings were exactly those supplied.

The target mean is **25/8 = 3.125**. The 15 selected neighbors have only 3–5 overlapping movies. Raw Pearson ranges from approximately .804 to 1.0; overlap shrinkage reduces selected similarities to approximately .231–.280. Strong correlation over a few shared films does not establish strong support for every unseen candidate.

The returned top ten all have confidence **.0441176471**, corresponding to candidate evidence `E = .1384615385`. Their prediction deviation is multiplied by `E/(E+5) ≈ .0269461`. Thus even a sizable neighbor deviation contributes little to the target's mean. Genre adjustment is also damped by confidence; ranking further shrinks estimates toward the historical mean. Displayed predictions are **3.15862–3.17400**. This matches the report closely and is expected sparse evidence, not a Pearson or indexing defect.

Complete neighbor/candidate traces and dataset manifest identity are in [recommendation-diagnostics.json](recommendation-diagnostics.json). Regenerate into a new file with `python scripts/diagnose_profile.py --output NEW_FILE.json` using existing local 32M artifacts. The command never reads application users or databases.

## Decision

Do not change scoring, neighbor selection, confidence, ranking, or fallback mathematics. A .1 confidence cutoff would remove **all ten** results in this example but is not validated as a general quality threshold. Confidence is an evidence heuristic, not probability. Hard filtering could reduce coverage or hide useful niche results; switching to popularity would optimize a different objective without evidence of improved personalized accuracy.

Instead the frontend displays **Limited recommendation evidence**, explains that estimates can stay close to the user's average, and suggests rating more films with varied ratings or explicitly selecting Popular. The .1 threshold is only a presentation heuristic when every returned CF candidate is weak. Existing labeled popularity fallback remains unchanged.

## Benchmarks

Compared the current engine to trusted local source from audited commit `6166c8d`. Same process, Python 3.14 on Windows, same read-only 32M arrays and cached genre mapping; one untimed warmup and three alternating timed repetitions per case. Exact comparison included movie IDs, scores, confidence, method, and ranking score.

| Profile | Ratings | Baseline median (s) | Current median (s) | Output |
|---|---:|---:|---:|---|
| Reported profile | 8 | .1910 | .2001 | Exact match |
| Reference profile | 5 | .3704 | .4079 | Exact match |
| Reference profile | 20 | 1.8944 | 1.9595 | Exact match |
| Reference profile | 100 | 5.8142 | 5.6770 | Exact match |
| Two-member union | 33 | 3.1900 | 3.0820 | Exact match |

Raw timings and artifact identity are in [recommendation-benchmark.json](recommendation-benchmark.json). These are local warm compute measurements, not Azure HTTP latency, Linux RSS measurements, calibrated confidence, or proof of general recommendation-quality improvement. The cooperative budget checks add bounded safety work; there is no claimed performance improvement. Existing model-quality/equivalence tests and a new hand-calculated sparse-evidence regression protect the mathematics. A separate opt-in test reproduces this exact 32M profile.
