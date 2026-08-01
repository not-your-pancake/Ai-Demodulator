# MCM31 Data Collection Manual — v2

**Project:** Learned demodulation on the MCM31/EV digital modulations trainer
**Instrument:** Rohde & Schwarz HMO1002
**Team:** 3 people (Operator / Recorder / Verifier)
**Supersedes:** all previous collection sheets

---

## Why this version differs from v1

Measured from the v1 captures, three things were wrong with the old plan. You are not
repeating v1; you are replacing it.

| Problem found in v1 data | Consequence | Fixed by |
|---|---|---|
| Demodulator LO runs 23–38 Hz above the carrier and is never locked | TP-9 outputs a beat note, not data. There is no hardware baseline. | Procedure B (alignment attempt), then TP-9 is recorded as a *finding*, not a baseline |
| At the harshest setting the ideal BER is still ~0 — noise is 19–27 dB too weak | Nothing to plot. All 16 conditions error-free. | Procedure C (full-travel knob calibration to a C/N₀ target) + synthetic AWGN axis |
| Attenuation knob spans only 3.4 dB over half travel | The 4×4 grid was really 4 points | Full travel, 2 attenuation points, more noise points |
| Hand-recorded RMS disagrees with the CSV by 17.5% | Calibration built on a wrong number | Everything computed from the CSV by `check_capture.py` |

**Core principle of v2: capture more signal, write down less.** Anything derivable from
the CSV is never recorded by hand. Only what the CSV cannot contain gets written.

---

## Roles

| Role | Job | Never does |
|---|---|---|
| **Operator** | DIP switches, knobs, probes, scope, saves file | Fills the manifest |
| **Recorder** | Manifest row per capture, photographs panel, tracks knob angles | Touches the knobs |
| **Verifier** | Runs `check_capture.py` on each file **as it lands**, calls STOP on a FAIL | Anything else |

The Verifier is the reason this works. A failed capture caught at the bench costs 90
seconds. Caught at home it costs a lab session.

---

## PART 0 — One-time bench setup

Do once, at the start of the campaign. Photograph everything.

**0.1 Warm-up.** Power the board and scope, wait **15 minutes** before any capture.
Analog boards drift. Record the warm-up start time.

**0.2 Probe compensation.** Compensate both probes on the scope's CAL output. Record
probe attenuation (×1 or ×10) for each channel.

**0.3 Fix the vertical scale — this is critical and permanent.**
- Set pattern to **T1**, noise knob to its **maximum**, attenuation to **minimum** (largest possible amplitude).
- On CH1 (TP-20), reduce V/div until the waveform fills ≈80% of the screen height without ever touching the top or bottom graticule.
- **Write this V/div down and never change it again for the whole campaign.**
- Reason: v1 data used only 49 quantisation levels out of 256 — 5.6 effective bits instead of 8. Changing V/div mid-campaign makes files non-comparable.

**0.4 Test for a High-Resolution acquisition mode.** In the ACQUIRE menu, check whether
the scope offers **High Resolution** (or "HRes") in addition to Sample. If it does,
take one capture in each mode and run:
```bash
python check_capture.py test_sample.CSV test_hres.CSV
```
If `CH1_step_V` gets smaller in HRes, **use HRes for the whole campaign**. You are
oversampled ~700× per carrier cycle, so there is no downside and it buys real bits.

**0.5 Look for a frame / word-sync test point.** The board must reset its 24-bit
sequence somewhere. Check the handbook block diagram for a divide-by-24 or "word clock"
output. **If one exists, trigger on it instead of TP-1** — then bit 1 always lands at the
same place in every file and pattern-phase recovery becomes trivial. If it does not
exist, proceed with TP-1 and recover phase in software.

**0.6 Fixed scope configuration** (verify at the start of every session):

| Setting | Value |
|---|---|
| Timebase | 50 ms/div → 600 ms window |
| Trigger position | 0 s (centre) |
| Acquisition | MAX SA RATE, **single-shot** → 862.07 kSa/s, 517,128 points |
| Acquisition mode | High Resolution if available, else Sample |
| Trigger source | EXT, from TP-1 (or frame sync if found) |
| Trigger level / slope | ≈2.5 V, rising, **Normal** (not Auto) |
| CH1 coupling | DC |
| CH2 coupling | DC |
| CH1 V/div | fixed at step 0.3 — never change |

---

## PART 1 — Session start checklist

Every lab session, before the first data capture. Takes ~10 minutes.

- [ ] Power on, **15 min warm-up**, log start time
- [ ] Confirm all settings in table 0.6
- [ ] Record room temperature
- [ ] Photograph the full front panel and all patch cables
- [ ] Run **Procedure A** (below) — mandatory, every session
- [ ] Verifier confirms `check_capture.py` shows PASS on the Procedure A file

---

## PROCEDURE A — Clock and carrier reference

**Run once per session. Not per pattern.** The TX clock does not depend on the DIP
switch settings.

1. Pattern: **T1**. Noise: minimum. Attenuation: minimum.
2. Probe **CH1 → TP-20**, **CH2 → TP-1 (TX CK)**.
3. Single-shot capture. Save as `SESSION<nn>_REF_CLOCK.CSV`.
4. Verifier runs:
   ```bash
   python check_capture.py SESSION<nn>_REF_CLOCK.CSV
   ```
5. Read off and record in the session header:
   - `carrier_Hz` → the carrier frequency (expected ≈1199.90 Hz)
   - `CH2_rate_hz` → **the bit rate R_b**
   - `CH2_min_run_ms` → one bit period

6. Compute samples per symbol: `862068.97 / R_b`. Record it.

> **This single file unblocks everything.** Until R_b is known you cannot label a
> single bit, size a network input, or compute Eb/N₀. Do not skip it, and do not
> substitute a written-down frequency for the capture — you need the edge positions,
> not just the rate.

---

## PROCEDURE B — Carrier recovery alignment attempt

**Run once at the start of the campaign, and again if the board is re-patched.**

The demodulator LO was measured at +23.02 Hz (quiet) and +38.13 Hz (noisy) relative to
the 1199.9032 Hz carrier. An offset that *moves with the knobs* means the loop is
connected and trying to acquire, but never captures.

1. Probe **CH1 → TP-20**, **CH2 → TP-21**.
2. Capture, then run `check_capture.py`. Note `LO_offset_Hz`.
3. Locate the carrier-recovery block's free-run trimmer in the handbook. Adjust in
   small steps, re-capturing after each, and drive `LO_offset_Hz` toward 0.
4. **Success criterion: |LO_offset_Hz| < 0.5 Hz, stable across noise settings.**
5. Record the outcome as one of:
   - **LOCKED** — trimmer fixed it. Record trimmer position. TP-9 becomes a real baseline.
   - **UNLOCKED** — could not achieve lock. Record the residual offset at min and max noise.

Either outcome is publishable. LOCKED gives you a hardware baseline. UNLOCKED gives you
a characterised impairment where coherent detection provably fails — which is the more
interesting result. **Do not spend more than one session on this.**

---

## PROCEDURE C — Knob calibration sweep

**Run once, after Procedure A. This defines the marks used for the whole campaign.**
Do *not* reuse the v1 marks — they cover the wrong range.

The target: drive the carrier-to-noise-density ratio **C/N₀** down until an ideal
receiver would start making errors.

**Target C/N₀ (dB-Hz) = 4.3 + 10·log₁₀(R_b)**

Using R_b from Procedure A. (4.3 dB is the Eb/N₀ giving BER ≈ 10⁻² for BPSK.)
*Example: R_b = 150 bps → target ≈ 26 dB-Hz. v1 reached only 51 dB-Hz.*

**Sweep procedure:**

1. Pattern **P00 (all zeros)**, attenuation at **minimum**.
2. Mark the noise knob's full travel in 10 equal steps with a protractor. Record each
   angle in **degrees**.
3. Capture at each of the 10 positions. Save as `CAL_N<01..10>_A00.CSV`.
4. Verifier runs `python check_capture.py CAL_*.CSV --summary > cal_noise.csv`.
5. Plot `C_over_N0_dBHz` against knob angle.
6. **Choose 5 noise marks** so their C/N₀ values are roughly evenly spaced in dB, with
   the lowest one at or below the target. Record the 5 angles.
7. Repeat steps 2–6 for the **attenuation** knob (noise at minimum) but choose only
   **2 marks**: minimum and maximum. Record both angles.

> **If the lowest achievable C/N₀ is still above target after full travel:** the board
> cannot generate enough in-band noise. This is expected — plan on it. Record the
> achievable range honestly and rely on the **synthetic AWGN axis** (added numerically
> in software at any Eb/N₀) for the BER curve. The hardware noise axis then documents
> the board's *real, non-Gaussian* impairment instead, which is a separate and better
> result. Nothing is lost.

**Why all-zeros is used here:** an unmodulated carrier is a single tone, so a software
notch separates signal power from noise power exactly. No other pattern permits this.
P00 is your calibration instrument, not training data.

---

## PROCEDURE D — Main collection loop

**Conditions:** 5 noise marks × 2 attenuation marks = **10 conditions**
**Patterns:** P00 + T1…T5 = **6 patterns** (switch settings in Appendix A)
**Passes:**
- **Pass A** — CH1 = TP-20, CH2 = TP-9
- **Pass B** — CH1 = TP-21, CH2 = TP-22 *(both simultaneously — this is the constellation)*

### Loop order — do not rearrange

Setting 24 DIP switches is the slowest operation on the bench; moving probes is second.
This order minimises both: 6 switch changes, 12 probe moves, 120 captures.

```
for pattern in [P00, T1, T2, T3, T4, T5]:
    set the 24 DIP switches            <- slowest step, done 6 times total
    Recorder photographs the switch bank
    move probes to Pass A (TP-20, TP-9)
    for each of the 10 conditions:
        set noise knob to its mark
        set attenuation knob to its mark
        arm, SINGLE, save
        Verifier runs check_capture.py     <- before the knobs move again
    move probes to Pass B (TP-21, TP-22)
    for each of the 10 conditions:
        (same)
```

### Per-capture steps

1. Operator sets the two knobs to their marked angles.
2. Press **RUN/STOP** to arm, then **SINGLE**.
3. Wait for the trigger. If it does not fire within 5 s, check the trigger level — do
   **not** switch to Auto mode.
4. Save to USB with the exact filename from the convention below.
5. Recorder adds one manifest row.
6. **Verifier runs the gate before the operator touches anything.** On FAIL, repeat the
   capture immediately.

### If time runs short

Mandatory: **P00 and T1 in both passes; T2–T5 in Pass A.** (= 80 files/scheme)
Droppable: T2–T5 Pass B. (= the remaining 40)

---

## PART 2 — What to record, and what not to

### DO NOT hand-record these — the CSV already contains them

RMS · peak-to-peak · DC offset · carrier frequency · LO frequency · noise power ·
quantisation step · sample count · SNR · number of transitions

All of it is produced exactly by `check_capture.py`. The v1 practice of writing 48 RMS
values per pattern is deleted: it cost hours, and those readings disagreed with the
files by 17.5%.

### DO record — one row per capture (the manifest)

| Field | Example | Why |
|---|---|---|
| `filename` | `B1_BPSK_T3_N04_A02_PA.CSV` | primary key |
| `board_id` | `B1` | cross-board generalisation |
| `modulation` | `BPSK` | |
| `pattern` | `T3` | |
| `noise_mark` | `N04` | |
| `noise_angle_deg` | `212` | **the actual reproducible quantity** |
| `atten_mark` | `A02` | |
| `atten_angle_deg` | `340` | |
| `pass` | `PA` | which test points |
| `session_id` | `S07` | |
| `timestamp` | `2026-08-04 14:22` | |
| `warmup_min` | `31` | analog drift |
| `room_temp_C` | `26` | |
| `operator` | `KH` | |
| `ch1_v_per_div` | `0.25` | must be constant — audit field |
| `ch2_v_per_div` | `2.0` | |
| `probe_atten_ch1` | `x1` | |
| `acq_mode` | `HRes` | |
| `lo_state` | `UNLOCKED` | from Procedure B |
| `notes` | free text | anything unusual |

### Record once per session (session header)

Carrier frequency · **bit rate R_b** · samples per symbol · LO offset at min and max
noise · warm-up start · room temperature · panel photographs · patch-cable photograph ·
trimmer position if adjusted

---

## PART 3 — File naming

```
<board>_<modulation>_<pattern>_<noise>_<atten>_<pass>.CSV

B1_BPSK_T3_N04_A02_PA.CSV
B2_8QAM_P00_N01_A01_PB.CSV
SESSION07_REF_CLOCK.CSV
CAL_N06_A00.CSV
```

Fixed-width fields (`N04` not `N4`) so they sort correctly. Every field that varies must
appear — v1 filenames such as `N4A4P1P1.CSV` omitted the board and modulation, and two
files already collided in review.

---

## PART 4 — Quality gates

`check_capture.py` returns **FAIL**, **WARN**, or **PASS**.

| Result | Meaning | Action |
|---|---|---|
| `CLIPPING at top/bottom rail` | Signal exceeded the vertical range | **Re-capture.** Do not adjust V/div — reduce the noise mark and flag it. If it clips at your chosen scale, step 0.3 was done wrong and the campaign restarts. |
| `fs != 862068.97` | Wrong decimation preset | Re-capture after fixing ACQUIRE |
| `row count != 517128` | Truncated save | Re-capture |
| `only N quantisation levels` | Vertical gain too low | Only actionable at step 0.3. Mid-campaign, log it and continue. |
| `CARRIER RECOVERY UNLOCKED` | Expected until Procedure B succeeds | Log it. Not a re-capture. |
| `transitions NOT on a bit grid` | TP-9 is a beat note | Expected while unlocked. Log it. |

**Stop-the-line rule:** two consecutive FAILs of the same type → stop collecting and
diagnose. Do not push through a session producing files you already know are bad.

---

## Appendix A — Pattern switch settings

Each pattern is a permutation of all eight 3-bit symbols: every pattern exercises all 8
constellation states exactly once, and every pattern is exactly 12 ones and 12 zeros.
This is what makes them valid for BPSK, QPSK and 8-QAM without change.

| Pattern | Sw 1–8 | Sw 9–16 | Sw 17–24 |
|---|---|---|---|
| **P00** calibration | `0 0 0 0 0 0 0 0` | `0 0 0 0 0 0 0 0` | `0 0 0 0 0 0 0 0` |
| **T1** | `0 0 0 0 0 1 0 1` | `1 0 1 0 1 1 0 1` | `1 1 1 0 1 1 0 0` |
| **T2** | `1 0 0 1 0 1 1 1` | `1 1 1 0 0 1 0 0` | `1 1 0 0 1 0 0 0` |
| **T3** | `0 0 0 1 1 1 0 0` | `1 1 1 0 0 1 0 1` | `0 1 0 1 1 1 0 0` |
| **T4** | `0 0 0 1 0 0 0 1` | `0 1 1 0 0 0 1 1` | `0 1 0 1 1 1 1 1` |
| **T5** | `0 1 1 0 0 0 1 0` | `1 0 1 0 1 1 1 1` | `0 0 0 0 1 1 1 0` |

Recorder photographs the switch bank after every change and before the first capture of
that pattern. A mis-set switch invalidates 20 files and is invisible in the data.

**P00 is calibration only.** It never enters training or test sets. Its purpose is exact
signal/noise separation via the single-tone notch.

**Analysis splits:** 5-fold leave-one-pattern-out across T1–T5, plus leave-one-noise-mark-out
to test generalisation to unseen SNR. Never a random window split.

---

## Appendix B — Volume and time

| | Per modulation | All three |
|---|---|---|
| Conditions | 10 | 30 |
| Patterns | 6 | 18 |
| Captures | 120 | 360 |
| Reference + calibration | ~12 | ~36 |
| **Total files** | **~132** | **~396** |
| Switch changes | 6 | 18 |
| Probe moves | 12 | 36 |
| Estimated bench time | ~4 h | ~12 h |

Roughly one full lab shift per modulation scheme.

---

## Appendix C — Verifier's command reference

```bash
# single capture, full report
python check_capture.py B1_BPSK_T3_N04_A02_PA.CSV

# with bit rate known from Procedure A -> adds Eb/N0 and ideal BER
python check_capture.py B1_BPSK_T3_N04_A02_PA.CSV --rb 150

# whole session as a manifest-ready CSV
python check_capture.py *.CSV --summary > session07_qc.csv

# calibration sweep
python check_capture.py CAL_*.CSV --summary > cal_noise.csv
```

Back up the USB stick to two locations before leaving the lab. 396 files representing
12 hours of bench time is not something to carry on a single flash drive.