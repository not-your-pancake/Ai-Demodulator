# MCM31 Data Collection Manual — v3

**Project:** Learned demodulation on the MCM31/EV digital modulations trainer
**Instrument:** Rohde & Schwarz HMO1002 (one per machine)
**Hardware:** 3 × MCM31/EV, run in parallel on the same modulation
**Team:** 3 people (Operator / Recorder / Verifier — roles rotate per machine)
**Supersedes:** all previous collection sheets

### Changes in v3, from bench feedback

| Change | Reason |
|---|---|
| CH2 V/div rules per stage; vertical POSITION step added | TP-20 has a −78 mV DC offset; Pass B needs matched quantisation |
| Record Mode table corrected to the instrument's actual 3 options | MAX WFM RATE / MAX SA RATE / AUTOMATIC |
| Word-sync search removed | Confirmed absent; TP-1 via EXT TRIG, phase recovered in software |
| Procedure B is now document-only | Decision taken not to attempt loop repair |
| Procedure C gains drift rules + drift brackets | Noise generator measured drifting ~6 dB across days |
| Procedure D rewritten for 3 parallel machines | Enables leave-one-board-out as a headline result |
| Batch verification replaces per-file | No dedicated Verifier per bench |
| Pass B verification added to the gate | `--mode passb`: I/Q balance, quadrature error, simultaneity |

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

*CH1 (TP-20):*
- Set pattern to **T1**, noise knob to its **maximum**, attenuation to **minimum** (largest possible amplitude).
- **First centre the trace.** TP-20 carries a ≈ −78 mV DC offset, so it does not sit on the centre line by default. Use the **vertical POSITION knob** to bring the waveform's midpoint onto the centre graticule *before* touching V/div. If you skip this, one half of the waveform clips while the other half wastes screen.
- Then reduce V/div until the waveform fills **≈80%** of the screen height — about 4 divisions peak-to-peak on an 8-division screen — never touching the top or bottom graticule.
- **Write this V/div down and never change it again for the whole campaign.**

*CH2, by stage:*

| Stage | CH2 signal | V/div rule |
|---|---|---|
| Procedure A | TP-1 (TX CK) | **1 or 2 V/div**, DC coupled. Logic levels only — resolution is irrelevant, you just need clean edges. |
| Pass A | TP-9 (RX DATA) | **1 or 2 V/div**, DC coupled. Same reason. |
| Pass B | TP-22 (Q) | **Same V/div as CH1** — see note below. |

> **Why match V/div on Pass B — and why it is *not* for the reason you might think.**
> The CSV stores real volts, not screen positions, so a V/div mismatch does **not**
> warp the constellation; it is exactly correctable in software. The real reason to
> match is different and more important: a mismatch changes the **quantisation step**
> on one channel only, and it hides gain imbalance in an instrument setting.
> **I/Q gain imbalance is a hardware impairment you want to measure, not an artifact
> you want to remove.** With both channels on identical V/div, `IQ_gain_imbalance_dB`
> from the gate is a real property of the board. With mismatched V/div it is
> partly your scope setting, and the measurement is worthless. Match them, and
> set the value from whichever of TP-21/TP-22 is *larger* so neither clips.

**0.3b Verify the vertical scale actually did something.** Take one capture and run the
gate. `CH1_step_V` should fall from **0.04 V** to roughly **(V/div ÷ 25)**.

| V/div | Expected `CH1_step_V` | Expected `CH1_levels` at 2 V pp |
|---|---|---|
| 1.0 (v1 setting) | 0.040 | ~48 |
| 0.5 | 0.020 | ~96 |
| 0.2 | 0.008 | ~240 |

If the step does **not** change when you change V/div, the CSV export resolution is
fixed in firmware and vertical scaling cannot help — record that fact and move on.
Do not spend a session fighting it.

**0.4 Record mode — confirmed.** The ACQUIRE **Record Mode** menu offers exactly three
options on this instrument:

| Option | Effect | Use it? |
|---|---|---|
| MAX WFM RATE | maximises screen refresh, uses short memory | **No** — throws away samples |
| **MAX SA RATE** | maximises sample rate, uses full memory | **Yes — always** |
| AUTOMATIC | compromise, gave 9.8 kSa/s in v1 | **No** — only 8 samples per carrier cycle |

**Separately**, look for an **acquisition mode** setting (Sample / Peak Detect / High
Resolution / Average / Envelope). On R&S HMO-series instruments this is a *different*
control from Record Mode and may sit under ACQUIRE on a second page, or under a
neighbouring softkey. If **High Resolution** exists, take one capture in each mode:
```bash
python check_capture.py test_sample.CSV test_hres.CSV
```
If `CH1_step_V` gets smaller in HRes, use HRes for the whole campaign — you are
oversampled ~700× per carrier cycle, so there is no downside. **If you cannot find it in
five minutes, stop looking.** Sample mode is acceptable; this is a bonus, not a blocker.

**0.5 No word-sync output — confirmed.** The MCM31 provides only the continuous bit
clock at TP-1 (TX CK). There is no divide-by-24 or frame-sync test point.

**Consequence:** the 24-bit pattern starts at an unknown offset in every capture. This
is *not* a problem — you recover it in software by circular cross-correlation of the
recovered bit stream against the known 24-bit pattern, which has one sharp peak per
pattern. Budget one function for it in analysis; nothing changes at the bench.

**Trigger wiring:** jumper wire from **TP-1** to the scope's **EXT TRIG IN** on the rear
or front panel. Trigger source = EXT, level ≈ 2.5 V, slope rising, mode **Normal**.
Verify the trigger LED fires before the first real capture of every session.

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

## PROCEDURE B — Document the unlocked carrier recovery

**Decision taken: we do not attempt to fix the loop. We measure and report it.**

This is the right call. The unlocked state is reproducible, it is the same on every
board, and it is a stronger result than a repaired board would be — a characterised
impairment where coherent detection *provably* cannot work is a contribution; a working
trainer board is not.

**Run once per machine, at the start of the campaign. 4 captures per machine, ~10 minutes.**

### Bench steps — do exactly this

1. Set the pattern to **P00** (all switches down/zero).
2. Probe **CH1 → TP-20**, **CH2 → TP-21**. Same V/div on both.
3. Take these **4 captures**, changing only the two knobs:

   | # | Noise knob | Attenuation knob | Save as |
   |---|---|---|---|
   | 1 | fully counter-clockwise (min) | fully counter-clockwise (min) | `M<n>_LO_Nmin_Amin.CSV` |
   | 2 | fully clockwise (max) | fully counter-clockwise (min) | `M<n>_LO_Nmax_Amin.CSV` |
   | 3 | fully counter-clockwise (min) | fully clockwise (max) | `M<n>_LO_Nmin_Amax.CSV` |
   | 4 | fully clockwise (max) | fully clockwise (max) | `M<n>_LO_Nmax_Amax.CSV` |

4. Run the gate on all four:
   ```bash
   python check_capture.py "M*_LO_*.CSV" --summary > machine<n>_lo.csv
   ```

5. **Write these five numbers into the session header for each of the four captures:**

   | From the gate | What it is |
   |---|---|
   | `carrier_Hz` | transmitted carrier (expect ≈1199.90 Hz) |
   | `LO_Hz` | the demodulator's local oscillator |
   | `LO_offset_Hz` | **the headline number** (v1 gave +23.02 and +38.13 Hz) |
   | `CH1_dc_mV` | TP-20 DC offset |
   | `C_over_N0_dBHz` | noise level at that knob setting |

6. Then swap **CH2 → TP-9** and take one more capture at Nmin/Amin. Record
   `CH2_grid_locked` (expected `False`) and `CH2_rate_hz`. This is your evidence that
   TP-9 is a beat note rather than data.

### What you are proving

- The offset is **non-zero** → the loop never acquires.
- The offset **changes with the knobs** → the loop is connected and being pulled, not
  simply disconnected. (This distinction matters: a reviewer will ask.)
- The offset is **similar across all three machines** → it is a design characteristic of
  the MCM31, not one broken unit. This is the sentence that makes it publishable.

Record `lo_state = UNLOCKED` in every manifest row. Do not spend further time on it.

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

### C.1 — The noise generator drifts. Plan around it, do not fight it.

**Observed on the bench: TP-20 RMS at a fixed knob angle fell from ~600 mV to ~300 mV
across different days.** That is roughly a 6 dB swing from nothing but the calendar.

Three rules follow, and they are not optional:

**Rule 1 — Run the 10-step sweep ONCE, at the start of the campaign.**
Its only job is to pick **5 physical dial angles** (N01…N05) and write them down in
degrees. Those angles are then fixed for the entire campaign. **Do not re-run the sweep
each session and do not re-mark the knobs to chase a target.** If you re-mark, the
labels stop meaning the same thing across sessions and the dataset becomes unpoolable.

**Rule 2 — The mark label is a *setting*, not a *measurement*.**
`N03` means "the knob is at 187°." It does **not** mean any particular noise level.
The actual noise level for every single capture comes from `C_over_N0_dBHz`, computed
by the gate from that capture's own CSV. **Never** use a hand-measured RMS, and never
assume today's N03 equals last week's N03.

**Rule 3 — In analysis, bin by measured C/N₀, not by mark.**
When the data is pooled, sort every capture by its own `C_over_N0_dBHz` and bin from
there. The mark label is metadata for reproducing the bench setup; the measured value
is the scientific variable. This is what makes the drift harmless instead of fatal.

### C.2 — Drift bracket (adds 10 captures per session, ~6 minutes)

At the **start** and again at the **end** of every session:

1. Pattern **P00**, attenuation at **A01**.
2. Capture at each of the 5 noise marks N01…N05.
3. Save as `M<n>_S<nn>_DRIFT_START_N<xx>.CSV` / `..._DRIFT_END_N<xx>.CSV`.
4. Run the gate; record `C_over_N0_dBHz` for all ten.

This measures how far the generator moved *during* the session. If start-to-end drift
exceeds **3 dB** at any mark, flag that session in the manifest — its captures still
count, but only via their individually measured C/N₀.

**This drift is itself a result.** "Measured thermal drift of the analog noise
generator, 6 dB across sessions" is a real characterisation finding and belongs in the
paper. It is also the cleanest justification you have for the synthetic AWGN axis:
you cannot build a reproducible BER-vs-Eb/N₀ curve on a source that moves 6 dB
between Tuesday and Sunday, and you can now *prove* that with your own measurements.

**Why all-zeros is used here:** an unmodulated carrier is a single tone, so a software
notch separates signal power from noise power exactly. No other pattern permits this.
P00 is your calibration instrument, not training data.

---

## PROCEDURE D — Main collection loop (3 machines in parallel)

**Conditions:** 5 noise marks × 2 attenuation marks = **10 conditions**
**Patterns:** P00 + T1…T5 = **6 patterns** (switch settings in Appendix A)
**Machines:** M1, M2, M3 — all three capturing the **same modulation, same pattern,
same nominal condition, at the same time**
**Passes:**
- **Pass A** — CH1 = TP-20, CH2 = TP-9
- **Pass B** — CH1 = TP-21, CH2 = TP-22 *(both simultaneously — this is the constellation)*

### D.0 — Running three machines in parallel

Capturing all three boards on the same modulation rather than splitting the schemes
between them is the **right** call, and it upgrades the paper: **leave-one-board-out
generalisation becomes a real experiment** instead of an aspiration. A learned receiver
that trains on M1+M2 and holds its BER on M3 is a substantially stronger claim than one
validated on a single unit. Make it a headline result, not an appendix.

**Requirements before you start:**

- [ ] **One oscilloscope per machine.** Three boards cannot share one scope in parallel; if you have fewer scopes than boards, run the machines sequentially instead and nothing else in this manual changes.
- [ ] **Procedure C is run separately on every machine.** The potentiometers are different physical parts — M1's N03 angle is not M2's N03 angle. Three sweeps, three sets of 5 angles.
- [ ] **Procedure B is run separately on every machine** (4 captures each).
- [ ] Step 0.3 (V/div) is set separately on every scope, and each scope's value is recorded.
- [ ] `machine_id` appears in **every** filename and **every** manifest row.

**What "parallel" must mean at the bench:** the same pattern is loaded on all three
boards and each is captured at its own N/A angles for that condition before anyone
advances. Do not let one machine run ahead by two patterns — if a fault appears you
want the three machines at the same point so the comparison stays clean.

**The nominal condition label is shared; the measured C/N₀ is not.** M1's `N03` and
M2's `N03` will not produce the same noise level. That is expected and harmless,
because analysis bins by measured `C_over_N0_dBHz` (Rule 3 in C.1), not by label.

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

### Batch verification — the workflow you will actually use

Per-file verification is impractical with three machines and no dedicated Verifier.
Batch it, with **one exception that costs 30 seconds and protects 20 files:**

> **Verify the FIRST capture of every pattern block immediately.**
> Then batch-verify the remaining 19 at the end of the block.

Rationale: the faults that ruin a whole block — wrong V/div, wrong record mode, probe
on the wrong test point, trigger not firing, a mis-set DIP switch — are all present on
capture #1. Catching it there costs one re-capture. Catching it at file 20 costs all 20.
Everything *after* capture #1 fails only sporadically, and batch is fine for that.

```bash
# capture #1 of the block - run this before continuing
python check_capture.py "F:\USB Drive\M1_BPSK_T3_N01_A01_PA.CSV"

# ...take the remaining 19 captures...

# end of block: all 20 files at once, seconds
python check_capture.py "F:\USB Drive\M1_BPSK_T3_*.CSV" --summary > M1_T3_qc.csv
```

**On Windows the quotes are required** — the shell will not expand `*` for you, and the
script does its own globbing. Without quotes you get "no files matched."

Open the summary CSV and scan two columns only: **FAIL** and **WARN**. Anything with a
FAIL gets re-captured before the DIP switches change, while the knobs are still set.

**Pass B files are verified too, and the gate now handles them.** It auto-detects Pass B
(both channels carrying the same oscillator) and reports:

| Field | What to check |
|---|---|
| `IQ_gain_imbalance_dB` | should be small; >3 dB warns. Large values mean mismatched V/div — fix the scope, not the data |
| `quadrature_error_deg` | deviation from 90°. **This is a real hardware measurement — report it, do not "fix" it** |
| `IQ_freq_split_Hz` | must be ≈0. Non-zero means the two channels were *not* captured simultaneously |
| `CH1_step_V` vs `CH2_step_V` | must match — confirms both channels on the same V/div |
| clipping | on either channel → re-capture |

Force the mode with `--mode passb` if auto-detection ever picks wrong.

### Pass A and Pass B as separate captures — confirmed valid

Your reasoning is correct, with one clarification worth having in writing for the
methods section:

- **Pass B is self-contained.** I and Q are captured *simultaneously on the two channels*, so the constellation is internally consistent and needs no alignment assumption whatsoever. This is the whole reason the pass was restructured.
- **The deterministic signal aligns across passes** (measured: 0–1 sample lag, correlation 0.9996 at low noise, 0.933 at high noise). External triggering off TP-1 is doing its job.
- **The noise realisation does not align, and does not need to.** Pass A gives you the received waveform and the board's decode; Pass B gives you the constellation. Nothing in the analysis requires a sample-wise comparison *between* the two passes.

Requirement: knob angles identical between Pass A and Pass B of the same condition. You
already have this. Since the generator drifts, also confirm the two passes' measured
`C_over_N0_dBHz` are within ~1 dB — if they diverge badly, a knob was bumped.

### If time runs short

Mandatory: **P00 and T1 in both passes; T2–T5 in Pass A.** (= 80 files/machine/scheme)
Droppable: T2–T5 Pass B. (= the remaining 40)
**Never droppable:** Procedure A, Procedure C, and the drift brackets.

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
| `filename` | `M1_BPSK_T3_N04_A02_PA.CSV` | primary key |
| `machine_id` | `M1` | **leave-one-board-out generalisation** |
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
<machine>_<modulation>_<pattern>_<noise>_<atten>_<pass>.CSV

M1_BPSK_T3_N04_A02_PA.CSV
M3_8QAM_P00_N01_A01_PB.CSV
M2_S07_REF_CLOCK.CSV
M1_CAL_N06_A00.CSV
M2_S07_DRIFT_START_N03.CSV
M1_LO_Nmax_Amin.CSV
```

Fixed-width fields (`N04` not `N4`) so they sort correctly. Every field that varies must
appear — v1 filenames such as `N4A4P1P1.CSV` omitted the machine and modulation, and two
files already collided in review. **With three machines writing to three USB sticks, the
`M<n>` prefix is what stops the merge from silently overwriting.** Verify it before the
sticks are pooled.

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

| | Per machine, per modulation | 3 machines × 3 modulations |
|---|---|---|
| Conditions | 10 | 10 |
| Patterns | 6 | 6 |
| Data captures | 120 | 1080 |
| Reference + drift brackets | ~12 | ~108 |
| One-time calibration (Proc B + C) | ~24 | ~72 |
| **Total files** | **~156** | **~1260** |
| Switch changes | 6 | 18 per machine |
| Probe moves | 12 | 36 per machine |

**Wall-clock time is unchanged by running in parallel** — roughly **one lab shift per
modulation scheme**, about 4 hours, because all three machines advance together. You get
3× the data for the same bench time, which is the entire point.

Add ~1 session at the very start for Procedures B and C on all three machines. Do not
skip it to save time; every downstream number depends on it.

**Storage:** ~18 MB per file × 1260 ≈ **23 GB**. Convert to `.npy` once after collection
and the working set drops to about a third of that. Back up to two locations before
leaving the lab — 1260 files is roughly 12 hours of bench time across three people, and
a single USB stick is not an acceptable place to keep it.

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