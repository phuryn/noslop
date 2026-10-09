"""Estimate Pangram fraction_human from words kept (5-word runs copied from the human original H).

python scripts/estimate_band.py -> scores/track3x_estimated_band.json + stdout
Training data: the 40 Track 3 points that have both measures (10 assistant-model variants x 4 excerpts;
H and Emulate excluded, as in pangram_analyze.py). Two simple monotone fits, each with leave-one-out error:
isotonic regression (pool-adjacent-violators, step-wise, clipped to [0, 1]) and a logistic curve in x.
Applied to the extended-Track 3 outputs (v5 / v5i, interview and notes, 10 excerpts).
ESTIMATED FROM WORDS KEPT, NOT MEASURED.
"""
import csv
import json
import math
import statistics

from common import ROOT


def training():
    vb = json.loads((ROOT / "scores" / "track3_verbatim.json").read_text())
    pg = {}
    for r in csv.DictReader(open(ROOT / "scores" / "pangram_log.csv", encoding="utf-8")):
        if r["stage"] == "STAGE_SUCCESS" and r["group"].startswith("track3/"):
            pg[(r["group"].split("/", 1)[1], str(int(r["file"][:2])))] = float(r["fraction_human"] or 0)
    pts = []
    for v, d in vb.items():
        if v in ("H", "E"):
            continue
        for i, x in d.items():
            if (v, i) in pg:
                pts.append((x["share_of_H_5grams"], pg[(v, i)], f"{v}-{i}"))
    return pts


def pav(xs, ys):
    """Isotonic (non-decreasing) fit. Returns a step function predictor."""
    order = sorted(range(len(xs)), key=lambda k: xs[k])
    blocks = []  # [sum_y, n, min_x, max_x]
    for k in order:
        blocks.append([ys[k], 1, xs[k], xs[k]])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            b = blocks.pop()
            blocks[-1][0] += b[0]; blocks[-1][1] += b[1]; blocks[-1][3] = b[3]
    steps = [(b[2], b[3], b[0] / b[1]) for b in blocks]

    def predict(x):
        # linear interpolation between block means at block midpoints; flat outside the range
        mids = [((lo + hi) / 2, m) for lo, hi, m in steps]
        if x <= mids[0][0]:
            return mids[0][1]
        if x >= mids[-1][0]:
            return mids[-1][1]
        for (x0, y0), (x1, y1) in zip(mids, mids[1:]):
            if x0 <= x <= x1:
                return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return mids[-1][1]
    return predict


def logistic(xs, ys):
    best = None
    for a in [i / 4 for i in range(-40, 21)]:
        for b in [i / 2 for i in range(0, 81)]:
            err = sum((1 / (1 + math.exp(-(a + b * x))) - y) ** 2 for x, y in zip(xs, ys))
            if best is None or err < best[0]:
                best = (err, a, b)
    _, a, b = best
    return (lambda x: 1 / (1 + math.exp(-(a + b * x)))), (a, b)


def loo(fit, pts):
    errs = []
    for k in range(len(pts)):
        tr = [p for j, p in enumerate(pts) if j != k]
        f = fit([p[0] for p in tr], [p[1] for p in tr])
        f = f[0] if isinstance(f, tuple) else f
        errs.append(abs(f(pts[k][0]) - pts[k][1]))
    return round(statistics.mean(errs), 3), round(statistics.median(errs), 3), round(max(errs), 3)


def main():
    pts = training()
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    iso = pav(xs, ys)
    logi, (a, b) = logistic(xs, ys)
    res = {"training_points": len(pts), "logistic": {"a": a, "b": b},
           "loo_abs_error_mean_median_max": {"isotonic": loo(pav, pts), "logistic": loo(logistic, pts)},
           "training_by_band": {}}
    # how the training points behave by words-kept band
    for lo, hi in ((0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 1.01)):
        sel = [y for x, y in zip(xs, ys) if lo <= x < hi]
        if sel:
            res["training_by_band"][f"{lo}-{hi}"] = {"n": len(sel), "mean_pangram_human": round(statistics.mean(sel), 2),
                                                     "min": min(sel), "max": max(sel),
                                                     "share_scoring_at_least_0.67": f"{sum(y >= 0.67 for y in sel)}/{len(sel)}"}
    # needs your own Track 3 run (track3x_verbatim.json is not published; aggregates are in notes_route_aggregate.json)
    vb = json.loads((ROOT / "scores" / "track3x_verbatim.json").read_text())
    res["estimated_band_NOT_MEASURED"] = {}
    for v in ("D", "B5-ask", "B5I-ask", "B5-notes", "B5I-notes"):
        xv = [vb[v][str(i)] for i in range(1, 11)]
        for name, f in (("isotonic", iso), ("logistic", logi)):
            est = [round(f(x), 2) for x in xv]
            res["estimated_band_NOT_MEASURED"].setdefault(v, {})[name] = {
                "per_excerpt": est, "min": min(est), "median": round(statistics.median(est), 2), "max": max(est),
                "excerpts_estimated_at_least_0.67": sum(e >= 0.67 for e in est)}
    (ROOT / "scores" / "track3x_estimated_band.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "estimated_band_NOT_MEASURED"}, indent=1))
    for v, d in res["estimated_band_NOT_MEASURED"].items():
        for name, e in d.items():
            print(f"{v:10} {name:9} min {e['min']:.2f} median {e['median']:.2f} max {e['max']:.2f}  >=0.67: {e['excerpts_estimated_at_least_0.67']}/10  {e['per_excerpt']}")


if __name__ == "__main__":
    main()
