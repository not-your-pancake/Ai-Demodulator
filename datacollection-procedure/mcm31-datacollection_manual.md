# MCM31 Neural Demodulator — Data Collection & Analysis Handbook

**Version:** 1.0 — 8 August 2026
**Owner:** Khalid (first author)
**Purpose:** Single source of truth for the capture campaign and the analysis pipeline.

---

## 0. Read this first

If you are an AI assistant picking this up cold, these are the rules:

1. **Never calculate a number from a description of a file.** Open the file and measure. Every number in Section 2 was measured from real captures.
2. **Ground truth is the coherent template, not the switch setting.** See Section 10. The mapping from DIP switches to transmitted symbols is *unresolved* and must not be assumed.
3. **Run a chance-level control before reporting any match.** A search over 12 rotations × 24 permutations scores ~7.7/12 on random data. Several plausible-looking results in this project turned out to be noise.
4. **The performance claim is dead.** A classical software receiver already achieves zero errors. Do not write code that tries to show the neural network "beats" it. See Section 1.
5. **Cap the model's receptive field at 5 bits.** This is a correctness constraint, not a hyperparameter. See Section 11.

---

## 1. Project context

### What this is

A hardware dataset and a parameter-free neural receiver, captured from **8 physically distinct MCM31/EV communication trainer boards**.

### The paper claim (the only one the data supports)

> A small physics-guided CNN, trained on waveforms captured from real hardware, reaches matched-filter symbol error rate across BPSK, QPSK and 8-QAM without being given the carrier frequency, the symbol rate, or the pulse shape — and it provably cannot memorise the transmitted sequence, because its receptive field is capped below the order of the board's PRBS.

### What was ruled out, and why

| Claim | Status | Evidence |
|---|---|---|
| "AI beats the analog demodulator on BER" | **DEAD** | A blind classical receiver got 32,391 / 32,391 bits correct across all noise and attenuation settings. Ceiling is a tie. |
| "BER vs SNR curve from the hardware" | **DEAD** | The noise knob adds +0.02 dB inside the signal band and +20 dB outside it. Decision margin moves 1.0 dB across full knob travel. Needs 11.6 dB more. |
| "The board's demodulator is aged/degraded" | **PARTLY TRUE** | It is not noise-limited. It has a hard *lock threshold*: BER 0.0000 at 570 mV, 0.2507 at 552 mV — a 0.28 dB cliff. |

### Where the SNR axis comes from

**Software-added AWGN on the clean hardware captures.** This must be stated plainly in the paper. The hardware contributes the real waveform — carrier, filter shape, quantisation, board-to-board variation. The noise is synthetic and controlled.

### Target venues

Primary: **AEU – International Journal of Electronics and Communications** (Elsevier, Q2).
Fallbacks: IET Communications, then MDPI Sensors or Electronics.
Dataset companion: Data in Brief, after the main paper is accepted.

---

## 2. Verified hardware facts

Every value below was measured from captured CSVs. Do not re-derive them from theory.

### 2.1 Acquisition

| Parameter | Value |
|---|---|
| Oscilloscope | Rohde & Schwarz HMO1002, 2 channels, 12 horizontal divisions |
| Time base | **500 ms/div** → 6.0004 s span |
| Sample rate | **87,260 Hz** |
| Samples per file | **523,600** |
| Acquire mode | Max Sa Rate |
| Trigger | External, TP-1, 2.5 V, rising |
| CSV header | `[s],CH1[V],CH2[V]` |

**Aliasing check (passed).** PSD at 862 kHz vs 87 kHz agrees to 0.32 dB in 2–5 kHz, 0.11 dB in 5–10 kHz, 0.50 dB in 10–20 kHz. Total out-of-band power that could fold in sits 28.3 dB below in-band. The slow time base is safe.

**Do not use 1 s/div.** It was tested and mis-set to 1 ms/div, producing 12 ms and 7 bits. 500 ms/div is proven and sufficient.

### 2.2 Signal parameters

| Parameter | BPSK | QPSK | 8-QAM |
|---|---|---|---|
| Carrier | 1199.91 Hz | 1199.91 Hz | 1199.91 Hz |
| Bit rate | **600 bps** | **1200 bps** | **1800 bps** |
| Symbol rate | 600 baud | 600 baud | 600 baud |
| Bits/symbol | 1 | 2 | 3 |
| Samples per bit @ 87,260 Hz | 145.44 | 72.72 | 48.48 |
| Samples per symbol | 145.44 | 145.44 | 145.44 |
| Carrier cycles per symbol | 2 | 2 | 2 |

The carrier is **coherent with the bit clock** — exactly 2 carrier cycles per symbol. Use this. It means the passband waveform repeats exactly at the word period, which is what makes coherent averaging work.

### 2.3 Word periods

| Data source | Length | BPSK | QPSK | 8-QAM |
|---|---|---|---|---|
| On-board PRBS | 63 bits | 105.0 ms | 52.5 ms | 35.0 ms |
| 24-bit DIP word | 24 bits | 40.0 ms | **20.0 ms** | **13.33 ms** |

### 2.4 The on-board sequence is a 63-bit maximal-length PRBS

The board's "64 BIT SEQUENCE" is actually **63 bits — an order-6 m-sequence**.

```
PRBS63 = 001000100101101100011101000011010111001111011111000000101010011
```

Proof (all measured, not assumed):
- Period is exactly 63 = 2⁶ − 1
- Run-length spectrum in one period: `{1:16, 2:8, 3:4, 4:2, 5:1, 6:1}` — 32 runs, the exact m-sequence signature
- The **complement** satisfies the linear recursion `s[i+6] = s[i] XOR s[i+5]` (mask 33 = 0b100001)
- 31 ones, 32 zeros

**This is the single most important fact in the project.** See Section 11.

### 2.5 Constellation geometry

| Modulation | Rings | Radius ratio | Phases | Measured concentration |
|---|---|---|---|---|
| BPSK | 1 | — | 2 (0°, 180°) | — |
| QPSK | 1 (spread 0.92–1.09) | 1.00 | 4 | 4-fold = 0.94 |
| **8-QAM** | **2** | **1.965 ≈ 2:1** | **4** | 4-fold = 0.85 |

**8-QAM is a 4-phase, 2-amplitude star. It is NOT a 16-QAM square grid.** Any loss function using `I,Q ∈ {−3,−1,+1,+3}` is wrong for this board and will fight the data term.

Allowed set, after per-window normalisation:

```
C_8QAM = { r·e^(jθ), 2r·e^(jθ) : θ ∈ {45°, 135°, 225°, 315°} }
C_QPSK = { r·e^(jθ)          : θ ∈ {45°, 135°, 225°, 315°} }
C_BPSK = { +r, −r }
```

### 2.6 Board-to-board consistency (measured on 2 boards so far)

| Measurement | B1 | B3 |
|---|---|---|
| Coherent template SNR (QPSK, same word) | 31.5 dB | 43.0 dB |
| Transmitted waveform, same word, cross-correlated | **+0.9997** | |

Transmitters are near-identical given the same word. Template *quality* varies by ~11 dB. That spread is the cross-device variation worth reporting.

---

## 3. Data generator patterns — exact assignments

### 3.1 Why the patterns are chosen this way

- **BPSK** uses the on-board PRBS63. Nothing to set.
- **QPSK** groups bits into dibits. A good word has all 4 quadrants represented.
- **8-QAM** groups bits into tribits. **A good word contains all 8 tribits**, so every constellation point appears.
- **Q1 (= the old P1) is unusable for 8-QAM.** Its tribits are `{6,2,0,5,5,3,3,6}` — only 5 of 8 points appear. Three constellation points would never be seen in training. This is why 8-QAM gets its own word.
- **The old P2 breaks the board's QPSK demodulator** on both B1 and B3 (self-consistency 0.5191 and 0.5242, i.e. chance). Cause unknown. Keep it out of QPSK captures.

### 3.2 The patterns

Set these on the three 8-way DIP banks, left to right, MSB first.

| ID | Bits (24) | Grouped for DIP banks | Use |
|---|---|---|---|
| **PRBS63** | *(on board, SW3 = 64 BIT)* | — | BPSK, Block 1 |
| **Q1** | `110010000101101011011110` | `11001000 01011010 11011110` | **QPSK, Block 1 — all boards** |
| **T1** | `000111001110010101011100` | `00011100 11100101 01011100` | **8-QAM, Block 1 — all boards** |
| **Q2** | `001001111000110101110010` | `00100111 10001101 01110010` | QPSK held-out, Block 2 |
| **Q3** | `110100101100011000111001` | `11010010 11000110 00111001` | QPSK held-out, Block 2 |
| **T2** | `111000110001101010100011` | `11100011 00011010 10100011` | 8-QAM held-out, Block 2 |
| **T3** | `010101000111011100110001` | `01010100 01110111 00110001` | 8-QAM held-out, Block 2 |
| **S1** | `011000101010111100001110` | `01100010 10101111 00001110` | BPSK held-out, Block 2 |

### 3.3 Pattern properties (verify these in code before use)

| ID | Dibits (QPSK view) | Quadrant counts | Tribits (8-QAM view) | Points covered | Max bit run |
|---|---|---|---|---|---|
| Q1 | 3,0,2,0,1,1,2,2,3,1,3,2 | 2/3/4/3 | 6,2,0,5,5,3,3,6 | **5 of 8** ✗ | 4 |
| Q2 | 0,2,1,3,2,0,3,1,1,3,0,2 | **3/3/3/3** ✓ | — | — | 4 |
| Q3 | 3,1,0,2,3,0,1,2,0,3,2,1 | **3/3/3/3** ✓ | — | — | 3 |
| T1 | — | — | 0,7,1,6,2,5,3,4 | **8 of 8** ✓ | 3 |
| T2 | — | — | 7,0,6,1,5,2,4,3 | **8 of 8** ✓ | 3 |
| T3 | — | — | 2,5,0,7,3,4,6,1 | **8 of 8** ✓ | 3 |
| S1 | 1,2,0,2,2,2,3,3,0,0,3,2 | 3/1/5/3 | 3,0,5,2,7,4,1,6 | 8 of 8 ✓ | 4 |

**Do not cross-use the patterns.** Verified in code:

- **S1** is a known QPSK-demodulator killer (self-consistency 0.519 on B1, 0.524 on B3 — both chance). BPSK only.
- **Q1** covers only 5 of 8 tribits. Never use it for 8-QAM.
- **T3** as dibits gives quadrant counts 3/6/0/3 — **quadrant 2 never appears**. Never use it for QPSK.
- **T2** as dibits gives 3/1/5/3, and **Q2** covers only 6 of 8 tribits. Also single-purpose.

Each pattern is assigned to exactly one modulation in Sections 6 and 7. Follow that assignment.

### 3.4 Status of T1

**T1 has not yet been tested against the board's own 8-QAM demodulator.** Board B1's file 6 is the test. If TP-9 comes back at chance for T1, that is fine — TP-9 is only the baseline, and labels come from TP-20. Record it as "8-QAM baseline unavailable" and continue.

---

## 4. Fixed bench settings

### 4.1 Never change these, on any board, in any file

| Item | Setting |
|---|---|
| CH1 probe | **TP-20** (modulated signal, after noise and attenuation) |
| CH2 probe | **TP-9** (board's recovered data) |
| Trigger | External from **TP-1**, 2.5 V, rising slope |
| Time base | **500 ms/div** |
| Acquire mode | **Max Sa Rate** |
| Noise knob | **Fully counter-clockwise, to the mechanical stop. Never touched.** |
| SW1 | TTL |
| SW2 | NORMAL (not DIFFERENTIAL) |
| SW6 | PSK/QPSK/QAM |
| J3 | PSK/Q position |
| J4 | link fitted |
| SW7, J6 | **Copy B1's positions. Photograph B1 first and match every board.** |

### 4.2 Change with modulation only

| Modulation | SW3 | J1 | SW8 | Data source | Bit rate |
|---|---|---|---|---|---|
| BPSK | **64 BIT** | BIT | BIT | on-board PRBS63 | 600 bps |
| QPSK | **24 BIT** | DIBIT | DI/TRIBIT | **Q1** on switches | 1200 bps |
| 8-QAM | **24 BIT** | TRIBIT | DI/TRIBIT | **T1** on switches | 1800 bps |

### 4.3 Trimmers — leave alone

**Do not adjust the PHASE trimmer or re-optimise the attenuation trimmer to make a board "look better."** Their as-found positions are the cross-device variation being measured. Photograph, record, do not turn.

Discrete switches and jumpers are different: a switch in the wrong position is a configuration error and **must** be standardised.

---

## 5. Block 0 — pre-flight, once per board

### 5.1 The START button test (30 seconds, mandatory)

The DIP word is latched. Flipping switches does nothing until the board reloads. This has already produced one wasted capture where two "different" patterns turned out to be the identical waveform (cross-correlation **+0.9999**).

| Step | Action | Expected |
|---|---|---|
| 1 | Set QPSK, attenuation fully CCW, TP-20 on CH1 | modulated trace |
| 2 | Set **all 24 switches OFF**, press **START** | trace collapses to a **clean unmodulated sine** |
| 3 | Set **Q1**, press **START** | trace becomes modulated again |

If step 2 does not visibly change the screen, the load failed. Press START again, or RESET, or power-cycle, and repeat until it does.

**Press START after every switch change, for the rest of the campaign.**

### 5.2 Board setup order

1. Photograph the entire switch panel, as-found.
2. Set all switches to match B1's reference photo. Do not touch trimmers.
3. Run the START test above.
4. Take file 1. **Stop.** Copy it to the laptop, open it, confirm 3 columns and ~523,600 rows.
5. Only then take files 2 through 7.

---

## 6. Block 1 — main campaign

**8 boards × 7 files = 56 files.**

### 6.1 Per-board file table

Work top to bottom. `<B>` = `B1` … `B8`.

| # | Filename | Mod | SW3 | J1 | SW8 | Pattern | Attenuation knob | Before saving |
|---|---|---|---|---|---|---|---|---|
| 1 | `<B>_BPSK_A0.CSV` | BPSK | 64 BIT | BIT | BIT | PRBS63 | fully CCW, at the stop | 3 columns; CH1 fills screen |
| 2 | `<B>_BPSK_APRE.CSV` | BPSK | 64 BIT | BIT | BIT | PRBS63 | one step **before** TP-9 turns to hash | photograph knob slot |
| 3 | `<B>_BPSK_APOST.CSV` | BPSK | 64 BIT | BIT | BIT | PRBS63 | one step **after** the break | photograph knob slot |
| 4 | `<B>_QPSK_A0.CSV` | QPSK | 24 BIT | DIBIT | DI/TRIBIT | **Q1** + START | back to fully CCW | re-range CH1 |
| 5 | `<B>_QPSK_APOST.CSV` | QPSK | 24 BIT | DIBIT | DI/TRIBIT | Q1 | one step after the break | **skip if TP-9 is already hash at A0** |
| 6 | `<B>_8QAM_A0.CSV` | 8-QAM | 24 BIT | TRIBIT | DI/TRIBIT | **T1** + START | fully CCW | re-range CH1 again |
| 7 | `<B>_8QAM_APOST.CSV` | 8-QAM | 24 BIT | TRIBIT | DI/TRIBIT | T1 | one step after the break | photograph knob slot |

### 6.2 Finding the break point

Do this **by eye, with no file**. Watch TP-9 on the screen while turning the attenuation knob slowly clockwise from the stop. The moment the clean pattern turns to hash is the break. Back off one step for APRE, go one step past for APOST.

Rotate the knob by roughly **one hour on a clock face (~30°)** per step. Photograph the slot angle at each captured position.

### 6.3 The skip rule

If TP-9 is already unstable hash at minimum attenuation, there is no break point. Skip that APOST file and write **"<mod> not locked"** in the log for that board. That note is data, not a failure.

### 6.4 Time budget

~45 minutes per board including setup and photographs. 8 boards ≈ 6 hours ≈ 1.5 lab sessions.

---

## 7. Block 2 — held-out patterns, board B1 only

**5 files.** These exist to test memorisation. Only TP-20 matters, so a pattern that breaks TP-9 is acceptable here.

Attenuation fully CCW, noise fully CCW, 500 ms/div, START pressed after every switch change.

| # | Filename | Mod | SW3 | J1 | SW8 | Pattern |
|---|---|---|---|---|---|---|
| 1 | `B1_8QAM_T2.CSV` | 8-QAM | 24 BIT | TRIBIT | DI/TRIBIT | **T2** |
| 2 | `B1_8QAM_T3.CSV` | 8-QAM | 24 BIT | TRIBIT | DI/TRIBIT | **T3** |
| 3 | `B1_QPSK_Q2.CSV` | QPSK | 24 BIT | DIBIT | DI/TRIBIT | **Q2** |
| 4 | `B1_QPSK_Q3.CSV` | QPSK | 24 BIT | DIBIT | DI/TRIBIT | **Q3** |
| 5 | `B1_BPSK_S1.CSV` | BPSK | **24 BIT** | BIT | BIT | **S1** |

**Note file 5 uses SW3 = 24 BIT**, unlike every BPSK file in Block 1. Set it back to 64 BIT afterwards.

### 7.1 Resulting pattern counts for leave-one-pattern-out

| Modulation | Patterns available | Source |
|---|---|---|
| BPSK | 2 | PRBS63 (Block 1) + S1 |
| QPSK | 3 | Q1 (Block 1) + Q2 + Q3 |
| 8-QAM | 3 | T1 (Block 1) + T2 + T3 |

---

## 8. Naming and directory layout

```
mcm31-dataset/
├── raw/
│   ├── B1/
│   │   ├── B1_BPSK_A0.CSV
│   │   ├── B1_BPSK_APRE.CSV
│   │   ├── B1_BPSK_APOST.CSV
│   │   ├── B1_QPSK_A0.CSV
│   │   ├── B1_QPSK_APOST.CSV
│   │   ├── B1_8QAM_A0.CSV
│   │   ├── B1_8QAM_APOST.CSV
│   │   ├── B1_8QAM_T2.CSV        # Block 2
│   │   ├── B1_8QAM_T3.CSV
│   │   ├── B1_QPSK_Q2.CSV
│   │   ├── B1_QPSK_Q3.CSV
│   │   └── B1_BPSK_S1.CSV
│   ├── B2/ … B8/
├── photos/
│   ├── B1_panel_asfound.jpg
│   ├── B1_panel_asset.jpg
│   ├── B1_BPSK_APRE_knob.jpg
│   └── …
├── logbook.csv
├── templates/          # generated: coherent templates per file
├── labels/             # generated: symbol sequences per file
└── src/
```

### 8.1 logbook.csv — fill one row per capture, at the bench

```csv
filename,board,modulation,pattern_id,attenuation_step,start_pressed,tp9_locked_by_eye,date,notes
B1_BPSK_A0.CSV,B1,BPSK,PRBS63,A00,n/a,yes,2026-08-11,
B1_QPSK_A0.CSV,B1,QPSK,Q1,A00,yes,yes,2026-08-11,
```

---

## 9. Per-file verification — run before trusting any capture

Implement each of these as a check that returns pass/fail. Run the whole set on every file at ingest.

| # | Check | Pass condition | If it fails |
|---|---|---|---|
| 1 | Column count | header is `[s],CH1[V],CH2[V]` | recapture — CH2 was off |
| 2 | Sample count | 520,000 – 526,000 rows | wrong time base — recapture |
| 3 | Duration | 5.99 – 6.01 s | wrong time base — recapture |
| 4 | Sample rate | 87,000 – 87,500 Hz | wrong time base |
| 5 | CH1 dynamic range | ≥ 90 distinct voltage levels | re-range CH1 vertically |
| 6 | Carrier (4th power) | 1199.5 – 1200.5 Hz | check modulation setting |
| 7 | TP-20 word period | matches Section 2.3 for that modulation, correlation ≥ 0.95 | wrong pattern or bad load |
| 8 | Coherent template SNR | ≥ 15 dB | investigate before using |
| 9 | Pattern identity | cross-correlate template against the reference template for that pattern ID; expect ≥ 0.99 | **START was not pressed — the word is stale** |
| 10 | TP-9 lock | self-consistency across repeats; log the value | if < 0.6, mark `baseline_unavailable` and continue |

**Check 9 is the one that has already caught a real error.** Build a reference template per pattern ID from the first verified capture, then test every later file against it.

---

## 10. Ground truth definition

**Do not derive labels from the DIP switch setting.** The mapping from switch bits to transmitted symbols is **unresolved**. A joint search over both known words scored 14/24 against a chance level of 14.1/24 — i.e. nothing.

### 10.1 The correct procedure

1. Estimate the bit period by least squares on TP-9 edge positions.
2. Refine the word period by maximising the energy of the coherent average over a ±6 sample window in 0.02-sample steps.
3. Average all K periods of the **raw passband** CH1 waveform → template. (K ≈ 300 for a 24-bit word, K ≈ 57 for PRBS63.)
4. Report template SNR: `10·log10( (var(template) − var(residual)/K) / var(residual) )`.
5. **Circularly extend the template** (concatenate it three times) before filtering and symbol extraction. Without this, the last symbol lands on the wrap boundary and comes out corrupted — this produced a spurious radius of 0.07 in an early run.
6. Downconvert at `fc = 24 / word_period_seconds` for a 24-bit word (2 carrier cycles per symbol).
7. Extract N symbols; the label sequence is the quantised symbol index.

For BPSK only, labels can also come directly from PRBS63 (Section 2.4), aligned by cross-correlation over all 63 rotations and both polarities.

### 10.2 How to describe this in the paper

> Ground truth is defined by coherent averaging of the transmitted waveform over N repetitions, yielding a template at X dB SNR. This measures what the board actually transmitted rather than what was requested at the switches.

That is defensible and survives the question "how do you know the board sent what you set?"

---

## 11. Model constraints

### 11.1 The receptive field cap — this is a correctness requirement

PRBS63 is an order-6 m-sequence. **Any 6 consecutive bits determine the next bit exactly** via `s[i+6] = s[i] XOR s[i+5]` (on the complement). Any 5 consecutive bits do not — each 5-bit window occurs twice per period with different successors.

Therefore:

| Modulation | Bits per symbol | **Max receptive field** |
|---|---|---|
| BPSK | 1 | **5 symbols** |
| QPSK | 2 | **2 symbols** |
| 8-QAM | 3 | **1 symbol** |

Compute the receptive field explicitly and assert it in code. Print the number in the paper.

With the cap in place, prediction-from-context is *mathematically impossible* and the network must read the waveform. This is a proof, not an empirical control, and it is the project's strongest methodological card.

**Consequence: no Bi-GRU.** A recurrent layer spanning ≥ 6 bits can reproduce the entire sequence from the LFSR recursion without touching TP-20. Not "might memorise" — will.

For 8-QAM the cap is tight (1 symbol), so the proof is weakest there. That is why 8-QAM gets 3 distinct patterns for leave-one-pattern-out.

### 11.2 Architecture

- 1D CNN only. 3–4 conv layers, 16–32 channels, ~10k–30k parameters.
- **Decimate to 16–24 samples per symbol before the network.** The raw rate is 145 samples per symbol, which is ~6× more than needed.
- Two heads: bit/symbol classifier, and a latent I/Q head for the constellation loss.
- Add a small GRU **only as an ablation**. If it helps on a random split but not on leave-one-pattern-out, that gap *is* the memorisation evidence — put it in the paper as a figure.

### 11.3 Loss

Per-window normalisation (divide predicted Î, Q̂ by window RMS), then:

```
L = L_CE(bits) + λ · L_const
L_const = min over c in C of ||(Î, Q̂) − c||²
```

`C` is the table from Section 2.5, swapped per modulation. Nothing else changes.

Use this instead of the degree-8 polynomial wells — those explode outside ±3 and are wrong for a star constellation anyway. Allow one learnable global rotation per capture, since the network chooses its own I/Q axes.

### 11.4 Evaluation

| Split | Purpose |
|---|---|
| Leave-one-pattern-out | primary |
| Leave-one-board-out (8 folds) | cross-device generalisation |
| Leave-one-attenuation-out | includes at least one past the lock threshold |
| Random split | report it, **labelled as the inflated number**, and show the gap |
| Bit-index-only baseline | model sees no signal; if it scores well, the task is trivially memorisable |
| Shuffled-label control | must fail; if it does not, there is a leak |

Always compare against a **blind classical receiver** (squaring/4th-power carrier recovery, matched filter, no supplied parameters). Do not hide it. Then run the experiment that justifies the network: **give the classical receiver a deliberately wrong carrier estimate** (off by 1, 5, 20 Hz) and show it collapses while the learned receiver does not.

---

## 12. Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Two "different" patterns give cross-correlation ≈ 1.0 | START not pressed; word is stale | Section 5.1 |
| TP-9 at chance in QPSK | pattern S1/old-P2, or PRBS63 in dibit mode | use Q1 |
| TP-9 at chance in QPSK/8-QAM with PRBS63 | 64-bit sequence does not frame correctly in dibit/tribit mode | use 24-bit DIP words |
| Last symbol of a template has near-zero radius | template wrap boundary | circular extension, Section 10.1 |
| Fewer than 90 distinct CH1 levels | vertical range too coarse after attenuation | re-range CH1 |
| Only 7 bits in a file | time base set to 1 ms/div not 1 s/div | 500 ms/div |
| SNR estimate bounces 3–32 dB with no trend | too few averaging periods (K=5) | use 500 ms/div, K ≥ 57 |
| 8-QAM BER ≈ 0.5 when aligned to 24 bits | TP-9 output period is **48** bits, double the transmitter | align to 48 |

---

## 13. Do not collect

These are answered. Collecting more costs lab time and adds nothing.

- **No noise sweeps.** Measured: +0.02 dB in the signal band across full knob travel.
- **No further attenuation sweeps.** The cliff is located to 0.28 dB. Three points per board is enough.
- **No TP-21 / TP-22 captures.** Both are hard-sliced digital lines, 50% at 0 V and 50% at 5 V. There is no analog constellation to capture. Compute I/Q in software from TP-20.
- **No all-zeros or all-ones patterns.** The demodulator free-runs on mains pickup (~50 Hz, 27 edges in 0.6 s).
- **No repeat passes.** CH1 and CH2 are simultaneous, so input and baseline come from one file.

---

## 14. Totals

| Block | Files | Time |
|---|---|---|
| Block 1 — 8 boards × 7 | 56 | ~6 h |
| Block 2 — held-out patterns, B1 | 5 | ~30 min |
| **Total** | **61** | **~1.5 lab sessions** |

After this, bench work on the project is finished. Everything remaining is analysis.
