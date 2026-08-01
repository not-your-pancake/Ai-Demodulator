#!/usr/bin/env python3
"""
check_capture.py  --  MCM31 acquisition quality gate + calibration extractor.

Run this on EVERY capture before leaving the lab bench. It takes seconds and
catches the faults that are unrecoverable once you have gone home:
clipping, wrong sample rate, collapsed vertical resolution, dead channel.

Usage
-----
    python check_capture.py CAPTURE.CSV
    python check_capture.py CAPTURE.CSV --rb 150        # if bit rate known
    python check_capture.py *.CSV --summary > qc.csv    # batch, manifest-ready

CSV format expected: 3 columns  ->  [s], CH1[V], CH2[V]
"""

import sys, os, glob, argparse
import numpy as np
import pandas as pd
from scipy import signal as sg
from scipy.stats import norm

# ----- expected acquisition constants (edit if your setup changes) -----------
EXPECTED_ROWS   = 517128
EXPECTED_FS     = 862068.97      # Sa/s
MIN_LEVELS_CH1  = 100            # below this the vertical gain is too low
# ----------------------------------------------------------------------------


def load(path):
    df = pd.read_csv(path)
    t  = df.iloc[:, 0].to_numpy(float)
    c1 = df.iloc[:, 1].to_numpy(float)
    c2 = df.iloc[:, 2].to_numpy(float)
    fs = (len(t) - 1) / (t[-1] - t[0])
    return t, c1, c2, fs


def fine_freq(x, fs, lo, hi, nfft=1 << 22):
    """Frequency of the dominant tone in [lo,hi], to ~0.2 Hz."""
    w = (x - x.mean()) * np.hanning(len(x))
    X = np.abs(np.fft.rfft(w, nfft))
    f = np.fft.rfftfreq(nfft, 1 / fs)
    m = (f > lo) & (f < hi)
    if not m.any():
        return float("nan")
    return float(f[m][np.argmax(X[m])])


def power_split(x, fs, fc, half=40.0, skirt_lo=80.0, skirt_hi=400.0):
    """
    Separate signal power from in-band noise density using a notch-and-skirt
    method. Valid when the pattern is ALL ZEROS (unmodulated carrier = one tone).
    Returns (S in V^2, N0 in V^2/Hz).
    """
    w = x - x.mean()
    nper = min(1 << 16, len(w))
    f, P = sg.welch(w, fs, nperseg=nper)
    df = f[1] - f[0]
    sig = (f > fc - half) & (f < fc + half)
    skirt = (((f > fc - skirt_hi) & (f < fc - skirt_lo)) |
             ((f > fc + skirt_lo) & (f < fc + skirt_hi)))
    S  = float(P[sig].sum() * df)
    N0 = float(P[skirt].mean())
    return S, N0


def iq_stats(i_ch, q_ch, fs):
    """
    Pass B analysis: CH1 = TP-21 (I), CH2 = TP-22 (Q). No TP-20 present, so no
    C/N0 is computable. What IS computable is the pair's own health, plus two
    real hardware impairments worth reporting in the paper.
    """
    R = {}
    fi = fine_freq(i_ch, fs, 400, 4000)
    fq = fine_freq(q_ch, fs, 400, 4000)
    R["I_Hz"] = round(fi, 4)
    R["Q_Hz"] = round(fq, 4)
    R["IQ_freq_split_Hz"] = round(fq - fi, 4)

    ai = float(np.sqrt(np.mean((i_ch - i_ch.mean()) ** 2)))
    aq = float(np.sqrt(np.mean((q_ch - q_ch.mean()) ** 2)))
    R["IQ_gain_imbalance_dB"] = round(20 * np.log10(aq / ai), 3) if ai > 0 else np.nan

    # Quadrature error: lag of peak cross-correlation, within one period.
    per = int(round(fs / fi)) if fi > 0 else 0
    if per > 4:
        seg = slice(len(i_ch) // 3, len(i_ch) // 3 + min(60000, len(i_ch) // 3))
        a = i_ch[seg] - i_ch[seg].mean()
        b = q_ch[seg] - q_ch[seg].mean()
        best_lag, best_v = 0, -9.0
        for lag in range(-per // 2, per // 2):
            v = float(np.corrcoef(a[per:-per], np.roll(b, lag)[per:-per])[0, 1])
            if v > best_v:
                best_lag, best_v = lag, v
        deg = 360.0 * best_lag / per
        R["IQ_phase_deg"] = round(deg, 2)
        R["quadrature_error_deg"] = round(abs(abs(deg) - 90.0), 2)
    return R


def digital_stats(x, fs):
    """Transition statistics for a logic-level channel (TP-9 or TP-1)."""
    thr = (x.max() + x.min()) / 2
    d = (x > thr).astype(np.int8)
    e = np.flatnonzero(np.diff(d) != 0)
    if len(e) < 3:
        return dict(transitions=len(e), high_frac=float(d.mean()),
                    min_run_ms=np.nan, med_run_ms=np.nan, rate_hz=np.nan,
                    grid_locked=None)
    runs = np.diff(e)
    ratios = runs / runs.min()
    # data lands on a bit grid -> ratios cluster near integers
    grid_err = float(np.mean(np.abs(ratios - np.round(ratios))))
    return dict(transitions=int(len(e)),
                high_frac=float(d.mean()),
                min_run_ms=float(1000 * runs.min() / fs),
                med_run_ms=float(1000 * np.median(runs) / fs),
                rate_hz=float(fs / runs.min()),
                grid_locked=bool(grid_err < 0.05),
                grid_err=grid_err)


def _report(name, R, fails, warns):
    print(f"\n=== {name} ===")
    for k, v in R.items():
        if k in ("FAIL", "WARN"):
            continue
        print(f"  {k:>22} : {v}")
    for f_ in fails:
        print(f"  ** FAIL ** {f_}")
    for w_ in warns:
        print(f"  ** WARN ** {w_}")
    if not fails and not warns:
        print("  ** PASS ** capture is clean")


def analyse(path, rb=None, verbose=True, mode="auto"):
    t, c1, c2, fs = load(path)
    name = os.path.basename(path)
    R = {"file": name, "rows": len(t), "fs_Sa_s": round(fs, 2)}
    fails, warns = [], []

    # ---- acquisition integrity ---------------------------------------------
    if len(t) != EXPECTED_ROWS:
        warns.append(f"row count {len(t)} != {EXPECTED_ROWS}")
    if abs(fs - EXPECTED_FS) / EXPECTED_FS > 0.001:
        warns.append(f"fs {fs:.1f} != {EXPECTED_FS} (wrong decimation preset?)")

    for tag, ch in (("CH1", c1), ("CH2", c2)):
        lv = np.unique(ch)
        step = float(np.median(np.diff(lv))) if len(lv) > 1 else np.nan
        R[f"{tag}_pp"]     = round(float(ch.max() - ch.min()), 4)
        R[f"{tag}_rms_mV"] = round(1000 * float(np.sqrt(np.mean(ch ** 2))), 2)
        R[f"{tag}_dc_mV"]  = round(1000 * float(ch.mean()), 2)
        R[f"{tag}_levels"] = int(len(lv))
        R[f"{tag}_step_V"] = round(step, 5)
        # Clipping test: hard clipping folds everything beyond the rail into
        # the extreme bin, so the extreme bin holds MORE samples than its
        # neighbour. An unclipped waveform always tapers toward its extreme
        # (a sine dwells near its peak, but the very last bin is reached only
        # on the largest cycles). Counting raw samples at the rail is NOT a
        # clipping test - a sine legitimately parks there.
        if len(lv) > 3:
            cnt = np.array([(ch == v).sum() for v in lv])
            for end, where in ((-1, "top"), (0, "bottom")):
                nb = cnt[-2] if end == -1 else cnt[1]
                if cnt[end] > nb and cnt[end] > 0.005 * len(ch):
                    fails.append(f"{tag} CLIPPING at {where} rail "
                                 f"({cnt[end]} vs {nb} in next bin)")

    if R["CH1_levels"] < MIN_LEVELS_CH1:
        warns.append(f"CH1 only {R['CH1_levels']} quantisation levels "
                     f"-> increase vertical gain (target >{MIN_LEVELS_CH1})")

    # ---- decide what this capture is ---------------------------------------
    # Pass B has BOTH channels carrying the same oscillator: two strong tones
    # within a few Hz of each other, both with many quantisation levels.
    f1p = fine_freq(c1, fs, 400, 4000)
    f2p = fine_freq(c2, fs, 400, 4000)
    looks_passb = (R["CH1_levels"] > 30 and R["CH2_levels"] > 30
                   and abs(f1p - f2p) < 5.0)
    if mode == "auto":
        mode = "passb" if looks_passb else "passa"
    R["mode"] = mode

    if mode == "passb":
        R.update(iq_stats(c1, c2, fs))
        if abs(R.get("IQ_gain_imbalance_dB", 0)) > 3.0:
            warns.append(f"I/Q gain imbalance {R['IQ_gain_imbalance_dB']:+.1f} dB "
                         f"- check both channels are on the same V/div")
        if R.get("quadrature_error_deg", 0) > 15.0:
            warns.append(f"quadrature error {R['quadrature_error_deg']:.1f} deg "
                         f"(expected ~0 from 90 deg)")
        if R["CH1_step_V"] != R["CH2_step_V"]:
            warns.append(f"CH1 step {R['CH1_step_V']} != CH2 step {R['CH2_step_V']} "
                         f"- different V/div, correctable in software but avoid")
        R["FAIL"] = "; ".join(fails)
        R["WARN"] = "; ".join(warns)
        if verbose:
            _report(name, R, fails, warns)
        return R

    # ---- Pass A / reference: CH1 is TP-20 ----------------------------------
    fc = fine_freq(c1, fs, 600, 4000)
    R["carrier_Hz"] = round(fc, 4)
    S, N0 = power_split(c1, fs, fc)
    R["S_V2"] = f"{S:.4e}"
    R["N0_V2_per_Hz"] = f"{N0:.4e}"
    # C/N0 in dB-Hz is the bandwidth-free calibration number. Once the bit
    # rate is known:  Eb/N0 (dB) = C/N0 (dB-Hz) - 10*log10(Rb).
    R["C_over_N0_dBHz"] = round(10 * np.log10(S / N0), 2) if N0 > 0 else np.nan
    if rb:
        ebn0 = S / (N0 * rb)
        R["EbN0_dB"] = round(10 * np.log10(ebn0), 2)
        R["ideal_BER"] = f"{norm.sf(np.sqrt(2 * ebn0)):.3e}"

    # ---- CH2: identify what it is ------------------------------------------
    f2 = fine_freq(c2, fs, 600, 4000)
    lo_pow = np.var(sg.detrend(c2))
    if not np.isnan(f2) and abs(f2 - fc) < 200 and R["CH2_levels"] > 40:
        # looks like TP-21 / TP-22 : local oscillator
        R["CH2_kind"] = "LO (TP-21/22)"
        R["LO_Hz"] = round(f2, 4)
        R["LO_offset_Hz"] = round(f2 - fc, 4)
        if abs(f2 - fc) > 1.0:
            fails.append(f"CARRIER RECOVERY UNLOCKED: LO offset {f2-fc:+.2f} Hz")
    else:
        ds = digital_stats(c2, fs)
        R["CH2_kind"] = "logic (TP-9 / TP-1)"
        R.update({f"CH2_{k}": v for k, v in ds.items()})
        if ds["transitions"] > 4 and ds["grid_locked"] is False:
            warns.append("CH2 transitions are NOT on a bit grid "
                         "-> beat note, not data (unlocked demodulator)")

    R["FAIL"] = "; ".join(fails)
    R["WARN"] = "; ".join(warns)

    if verbose:
        _report(name, R, fails, warns)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--rb", type=float, default=None,
                    help="bit rate in bps (from the TP-1 reference capture)")
    ap.add_argument("--summary", action="store_true",
                    help="emit one CSV row per file instead of a report")
    ap.add_argument("--mode", default="auto", choices=["auto", "passa", "passb"],
                    help="passa: CH1=TP-20. passb: CH1=TP-21, CH2=TP-22. "
                         "auto detects from the data (default).")
    a = ap.parse_args()

    paths = []
    for p in a.files:
        paths.extend(sorted(glob.glob(p)))
    if not paths:
        sys.exit("no files matched - on Windows put the pattern in quotes")
    rows = [analyse(p, a.rb, verbose=not a.summary, mode=a.mode) for p in paths]
    if a.summary:
        pd.DataFrame(rows).to_csv(sys.stdout, index=False)


if __name__ == "__main__":
    main()