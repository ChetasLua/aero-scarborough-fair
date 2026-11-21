"""
voice_synth.py — Physical-modeling singing voice synthesizer for Aero
(warm, open, close-mic human baritone-tenor, range C3..E4, 22050 Hz).

Architecture (100% pure Python stdlib — math, array):
  1. C1-smooth physiological glottal flow derivative (sine opening lobe,
     rounded zero-slope closing trough, raised-cosine smooth return phase
     Tr=0.095..0.20) with 2-stage golden spectral tilt (520-1180 Hz),
     balanced warm chest H1/H2 resonance, and unit-RMS-normalized organic
     perturbations (jitter, shimmer, micro-intonation wander, formant life).
  2. Expressive singing F0 contour: asymmetric S-curve legato portamento,
     phrase-onset pitch scoops, melisma curves, delayed organic vibrato
     (rate & depth breathing + coupled tremolo & tilt bloom), tender
     phrase-end sigh, and straight-tone stillness on Coda's final fade.
  3. 5-formant (F1..F5) Klatt cascade vocal tract with balanced fleshy human
     bandwidths (B1 94-112, B2 122-140, B3 160-184, B4 250-290, B5 365-410),
     gentle high-note vocal cover above A3, nimble 13ms articulatory smoothing,
     smooth nasal pole-zero coupling, voiced stop voice bar, silky 3.45 kHz
     vocal-fold air sheen, and parallel dual-resonator fricative/burst branch.
  4. Gradual cosine diphthong trajectories (up to 0.42s) and coarticulated
     consonant formant loci (velar F2/F3 pinch, labial/alveolar sweeps).
  5. Dedicated dark non-resonant inhale breath generator (bypassing cascade)
     and dynamic-preserving gentle vocal mastering with silky 2.2 kHz close-mic
     presence bloom (+2.2 dB, Q=0.80).
"""

import array
import math

SAMPLE_RATE = 22050
BLOCK_SIZE = 16  # 0.725 ms coefficient update rate (click-free & fast)
TWO_PI = 2.0 * math.pi

_LUT_N = 1024
_SIN_LUT = [math.sin(TWO_PI * i / _LUT_N) for i in range(_LUT_N + 1)]
_COS_LUT = [math.cos(TWO_PI * i / _LUT_N) for i in range(_LUT_N + 1)]


# =============================================================================
# MALE BARITONE-TENOR PHONEME ACOUSTIC DATABASE
# =============================================================================
# Balanced fleshy human pharyngeal bandwidths: open, clear, non-muffled vowels
# with zero hollow synthetic tube ringing.

VOWELS = {
    # Symbol: (F1, F2, F3, F4, F5,  B1,  B2,  B3,  B4,  B5,  gain_trim)
    "IY":  (300, 2250, 2930, 3420, 4260,  92, 122, 160, 250, 365, 1.24),
    "IH":  (410, 1930, 2600, 3340, 4200,  96, 126, 165, 258, 375, 1.12),
    "EH":  (545, 1780, 2540, 3290, 4170, 102, 132, 170, 268, 385, 1.02),
    # Warm natural AE ("land", "strand", "cam-") — crisp yet zero nasal honk
    "AE":  (615, 1590, 2480, 3250, 4140, 108, 138, 178, 276, 395, 0.96),
    "AA":  (680, 1135, 2470, 3220, 4120, 112, 136, 178, 276, 395, 0.92),
    "AO":  (530,  890, 2440, 3200, 4100, 106, 128, 175, 272, 390, 0.98),
    "OW1": (470,  905, 2430, 3200, 4100, 102, 126, 172, 268, 385, 1.00),
    "UH":  (435, 1035, 2380, 3220, 4120, 100, 128, 172, 268, 385, 1.06),
    "UW":  (325,  885, 2320, 3200, 4100,  94, 122, 168, 262, 380, 1.18),
    "AH":  (585, 1225, 2460, 3240, 4140, 106, 134, 176, 272, 390, 0.96),
    "AX":  (495, 1385, 2480, 3260, 4160, 104, 134, 176, 272, 390, 1.00),
    # Warm natural ER ("shirt", "needlework", "water") — clear rhotic, zero honk
    "ER":  (468, 1305, 1685, 3160, 4080, 102, 132, 162, 268, 385, 1.04),
    "EY1": (455, 2050, 2670, 3340, 4200,  96, 126, 166, 260, 378, 1.08),
    "AY1": (685, 1215, 2490, 3240, 4140, 112, 138, 178, 276, 395, 0.92),
    "AW1": (680, 1195, 2470, 3230, 4130, 112, 138, 178, 276, 395, 0.93),
}

# True diphthongs: (primary_nucleus, offglide_target, hold_fraction)
DIPHTHONGS = {
    "EY": ("EY1", "IY", 0.68),
    "OW": ("OW1", "UW", 0.70),
    "AY": ("AY1", "IH", 0.70),
    "AW": ("AW1", "UH", 0.69),
}

# Sonorant consonants (nasals, liquids, glides):
#   (F1, F2, F3, F4, F5, B1, B2, B3, B4, B5, av_scale, nasal_amt, fn_zero, dur_onset, dur_coda)
SONORANTS = {
    "M":  (285,  940, 2260, 3200, 4100, 104, 155, 200, 285, 400, 0.72, 0.88, 1080.0, 0.062, 0.105),
    "N":  (290, 1640, 2540, 3260, 4150, 104, 160, 200, 285, 400, 0.74, 0.88, 1600.0, 0.056, 0.105),
    "NG": (295, 1980, 2500, 3240, 4140, 104, 165, 200, 285, 400, 0.70, 0.88, 2250.0, 0.060, 0.095),
    "R":  (420, 1245, 1505, 3140, 4060,  98, 134, 150, 265, 380, 0.88, 0.00, 1500.0, 0.062, 0.092),
    "L":  (350, 1145, 2700, 3320, 4180,  98, 138, 178, 270, 385, 0.86, 0.00, 1500.0, 0.060, 0.080),
    "DL": (390,  855, 2660, 3260, 4150, 104, 144, 185, 275, 390, 0.82, 0.00, 1500.0, 0.060, 0.094),
    "W":  (305,  700, 2280, 3200, 4100,  96, 130, 172, 265, 385, 0.86, 0.00, 1500.0, 0.068, 0.065),
    "Y":  (290, 2230, 2940, 3420, 4240,  94, 126, 165, 260, 378, 0.90, 0.00, 1500.0, 0.062, 0.060),
}

# Fricatives (clearly audible soft F/V/DH/Z, naturally integrated S/SH):
#   place, voiced, dur_onset, dur_coda, fric_gain, ff1, fb1, ff2, fb2, hp_amt, av_scale, locus_f1, locus_f2, locus_f3
FRICATIVES = {
    "S":  ("alv", False, 0.084, 0.090, 0.25, 5150, 1400, 6800, 1750, 0.78, 0.00, 330, 1750, 2650),
    "SH": ("pal", False, 0.090, 0.092, 0.31, 2600,  760, 3850,  980, 0.40, 0.00, 330, 1950, 2550),
    "F":  ("lab", False, 0.088, 0.090, 0.36, 2250, 1450, 5500, 2150, 0.48, 0.00, 330,  900, 2240),
    "TH": ("den", False, 0.084, 0.084, 0.30, 2500, 1500, 5800, 2150, 0.48, 0.00, 330, 1550, 2550),
    "Z":  ("alv", True,  0.068, 0.084, 0.31, 4750, 1350, 6500, 1750, 0.70, 0.54, 310, 1750, 2650),
    "V":  ("lab", True,  0.064, 0.080, 0.28, 2050, 1350, 5000, 2050, 0.40, 0.60, 310,  900, 2240),
    "DH": ("den", True,  0.064, 0.070, 0.26, 2200, 1350, 4850, 1980, 0.38, 0.62, 320, 1580, 2560),
    "HH": ("glo", False, 0.070, 0.052, 0.00, 1600, 1000, 3200, 1500, 0.00, 0.00, 500, 1400, 2500),
}

# Plosives & Affricates (crisp P/K/KU/B/D/JH bursts with coarticulated loci):
#   place, voiced, closure_s, burst_s, vot_s, burst_gain, bf1, bb1, bf2, bb2, locus_f1, locus_f2, locus_f3
STOPS = {
    "P":  ("lab", False, 0.054, 0.019, 0.044, 0.62,  740,  460, 1480,  760, 250,  720, 2100),
    "PU": ("lab", False, 0.042, 0.014, 0.011, 0.38,  740,  460, 1480,  760, 250,  720, 2100),
    "T":  ("alv", False, 0.046, 0.015, 0.038, 0.40, 3600, 1100, 5700, 1550, 270, 1780, 2680),
    "TU": ("alv", False, 0.038, 0.013, 0.011, 0.34, 3600, 1100, 5700, 1550, 270, 1780, 2680),
    "K":  ("vel", False, 0.052, 0.019, 0.042, 0.58, 1520,  340, 1760,  520, 270, 1500, 1980),
    "KU": ("vel", False, 0.058, 0.020, 0.018, 0.64, 1460,  280, 1680,  420, 270, 1480, 1940),
    "B":  ("lab", True,  0.042, 0.014, 0.008, 0.33,  740,  500, 1520,  820, 260,  760, 2120),
    "D":  ("alv", True,  0.042, 0.014, 0.008, 0.33, 3400, 1050, 5400, 1500, 270, 1760, 2660),
    "G":  ("vel", True,  0.044, 0.015, 0.010, 0.36, 1480,  360, 1720,  540, 270, 1500, 1980),
    "JH": ("pal", True,  0.038, 0.015, 0.074, 0.45, 2500,  760, 3800,  960, 290, 1950, 2550),
}


def is_vowel_phone(ph):
    return ph in VOWELS or ph in DIPHTHONGS


def _get_vowel_tuple(vname):
    if vname in DIPHTHONGS:
        vname = DIPHTHONGS[vname][0]
    return VOWELS.get(vname, VOWELS["AX"])


def _velar_coarticulated_locus(adj_vowel_tuple):
    """Coarticulate velar K/G F2/F3 locus and compact resonant burst peak."""
    vf2 = adj_vowel_tuple[1]
    if vf2 > 1520:
        return (270.0, min(2240.0, vf2 + 120.0), 2380.0, 2150.0, 2450.0)
    else:
        return (270.0, 1480.0, 1940.0, 1460.0, 1680.0)


# =============================================================================
# PHONEME SEGMENT ALLOCATION WITHIN EACH SYLLABLE
# =============================================================================

def _phone_intrinsic_dur(ph, is_coda, is_phrase_final):
    if ph in SONORANTS:
        d = SONORANTS[ph][14] if is_coda else SONORANTS[ph][13]
        if is_coda and is_phrase_final and ph in ("M", "N", "NG", "R", "DL"):
            d *= 1.65
        return d
    if ph in FRICATIVES:
        d = FRICATIVES[ph][3] if is_coda else FRICATIVES[ph][2]
        if is_coda and is_phrase_final:
            d *= 1.18
        return d
    if ph in STOPS:
        _, _, clo, bst, vot, *_ = STOPS[ph]
        if is_coda:
            return clo * 0.90 + bst + (vot * 0.65 if ph != "JH" else vot)
        return clo + bst + vot
    return 0.06


def _build_phrase_phoneme_plan(phrase_sylls):
    segments = []
    if not phrase_sylls:
        return segments, 0.0, 0.0

    first = phrase_sylls[0]
    breath_dur = first.get("breath_before", 0.0)

    syll_plans = []
    for idx, sy in enumerate(phrase_sylls):
        phones = sy["phones"]
        t0 = sy["start"]
        t1 = sy["end"]
        dur = max(0.08, t1 - t0)
        is_last = (idx == len(phrase_sylls) - 1) or (not sy.get("legato", True))

        v_indices = [i for i, p in enumerate(phones) if is_vowel_phone(p)]
        if not v_indices:
            v_start_i = 0
            v_end_i = 0
        else:
            v_start_i = v_indices[0]
            v_end_i = v_indices[-1]

        onsets = phones[:v_start_i]
        nuclei = phones[v_start_i:v_end_i + 1]
        codas = phones[v_end_i + 1:]

        onset_durs = [_phone_intrinsic_dur(p, False, False) for p in onsets]
        coda_durs = [_phone_intrinsic_dur(p, True, is_last) for p in codas]

        sum_on = sum(onset_durs)
        sum_co = sum(coda_durs)

        max_cons_budget = dur * 0.54
        if sum_on + sum_co > max_cons_budget and (sum_on + sum_co) > 0:
            scale = max_cons_budget / (sum_on + sum_co)
            onset_durs = [d * scale for d in onset_durs]
            coda_durs = [d * scale for d in coda_durs]
            sum_on *= scale
            sum_co *= scale

        if idx == 0:
            antic = min(sum_on * 0.72, 0.088)
        else:
            prev_sy = phrase_sylls[idx - 1]
            gap = t0 - prev_sy["end"]
            if gap > 0.02:
                antic = min(sum_on * 0.72, gap * 0.70, 0.082)
            else:
                prev_dur = prev_sy["end"] - prev_sy["start"]
                max_borrow = min(0.036, prev_dur * 0.13)
                antic = min(sum_on * 0.44, max_borrow)

        eff_start = t0 - antic
        eff_end = t1
        syll_plans.append({
            "sy": sy,
            "idx": idx,
            "eff_start": eff_start,
            "eff_end": eff_end,
            "onsets": onsets,
            "onset_durs": onset_durs,
            "nuclei": nuclei,
            "codas": codas,
            "coda_durs": coda_durs,
            "is_last": is_last,
        })

    for i in range(len(syll_plans) - 1):
        cur = syll_plans[i]
        nxt = syll_plans[i + 1]
        if nxt["eff_start"] < cur["eff_end"]:
            cur["eff_end"] = nxt["eff_start"]

    phrase_start = syll_plans[0]["eff_start"]
    if breath_dur > 0.02:
        inhale_gap = 0.048
        inhale_end = phrase_start - inhale_gap
        inhale_start = max(0.0, inhale_end - breath_dur)
        if inhale_end > inhale_start + 0.04:
            segments.append({
                "kind": "INHALE",
                "t0": inhale_start,
                "t1": inhale_end,
                "sy": first,
            })
            phrase_start = inhale_start

    phrase_end = syll_plans[-1]["eff_end"] + 0.10

    def first_vowel_tuple(plan):
        for p in plan["nuclei"]:
            if is_vowel_phone(p):
                return _get_vowel_tuple(p)
        return VOWELS["AX"]

    def last_vowel_tuple(plan):
        for p in reversed(plan["nuclei"]):
            if is_vowel_phone(p):
                if p in DIPHTHONGS:
                    return VOWELS[DIPHTHONGS[p][1]]
                return VOWELS[p]
        return VOWELS["AX"]

    for sp in syll_plans:
        sy = sp["sy"]
        t_cur = sp["eff_start"]
        t_end = sp["eff_end"]
        tot = max(0.06, t_end - t_cur)

        sum_on = sum(sp["onset_durs"])
        sum_co = sum(sp["coda_durs"])
        v_dur = tot - sum_on - sum_co
        if v_dur < tot * 0.36:
            need = tot * 0.36 - v_dur
            if sum_on + sum_co > 0:
                sc = max(0.25, (sum_on + sum_co - need) / (sum_on + sum_co))
                sp["onset_durs"] = [d * sc for d in sp["onset_durs"]]
                sp["coda_durs"] = [d * sc for d in sp["coda_durs"]]
                sum_on = sum(sp["onset_durs"])
                sum_co = sum(sp["coda_durs"])
            v_dur = max(0.03, tot - sum_on - sum_co)

        next_v_tup = first_vowel_tuple(sp)
        prev_v_tup = last_vowel_tuple(sp)
        has_onset_cons = (len(sp["onsets"]) > 0)

        def emit_consonant(ph, d, is_coda, adj_v):
            nonlocal t_cur
            t_next = t_cur + d
            if ph in SONORANTS:
                segments.append({
                    "kind": "SONORANT",
                    "ph": ph,
                    "t0": t_cur,
                    "t1": t_next,
                    "sy": sy,
                    "is_coda": is_coda,
                    "adj_v": adj_v,
                })
            elif ph in FRICATIVES:
                segments.append({
                    "kind": "FRIC",
                    "ph": ph,
                    "t0": t_cur,
                    "t1": t_next,
                    "sy": sy,
                    "is_coda": is_coda,
                    "adj_v": adj_v,
                })
            elif ph in STOPS:
                place, voiced, clo, bst, vot, *_ = STOPS[ph]
                tot_raw = clo + bst + vot
                if is_coda and ph != "JH":
                    tot_raw = clo * 0.90 + bst + vot * 0.65
                    clo_d = d * (clo * 0.90 / tot_raw)
                    bst_d = d * (bst / tot_raw)
                    vot_d = max(0.004, d - clo_d - bst_d)
                else:
                    clo_d = d * (clo / tot_raw)
                    bst_d = d * (bst / tot_raw)
                    vot_d = max(0.004, d - clo_d - bst_d)
                segments.append({
                    "kind": "STOP_CLO",
                    "ph": ph,
                    "t0": t_cur,
                    "t1": t_cur + clo_d,
                    "sy": sy,
                    "is_coda": is_coda,
                    "adj_v": adj_v,
                })
                segments.append({
                    "kind": "STOP_BURST",
                    "ph": ph,
                    "t0": t_cur + clo_d,
                    "t1": t_cur + clo_d + bst_d,
                    "sy": sy,
                    "is_coda": is_coda,
                    "adj_v": adj_v,
                })
                segments.append({
                    "kind": "STOP_VOT",
                    "ph": ph,
                    "t0": t_cur + clo_d + bst_d,
                    "t1": t_next,
                    "sy": sy,
                    "is_coda": is_coda,
                    "adj_v": adj_v,
                })
            t_cur = t_next

        for ph, d in zip(sp["onsets"], sp["onset_durs"]):
            emit_consonant(ph, d, False, next_v_tup)

        nuclei = sp["nuclei"]
        soft_start = (not has_onset_cons) and (sp["idx"] == 0)
        if len(nuclei) == 1:
            vph = nuclei[0]
            if vph in DIPHTHONGS:
                v1, v2, hold_frac = DIPHTHONGS[vph]
                glide_d = max(0.065, min(0.42, v_dur * (1.0 - hold_frac)))
                if glide_d > v_dur * 0.45:
                    glide_d = v_dur * 0.36
                hold_d = v_dur - glide_d
                segments.append({
                    "kind": "VOWEL",
                    "ph": v1,
                    "t0": t_cur,
                    "t1": t_cur + hold_d,
                    "sy": sy,
                    "soft_start": soft_start,
                })
                segments.append({
                    "kind": "VOWEL_GLIDE",
                    "ph": v1,
                    "ph2": v2,
                    "t0": t_cur + hold_d,
                    "t1": t_cur + v_dur,
                    "sy": sy,
                    "soft_start": False,
                })
            else:
                segments.append({
                    "kind": "VOWEL",
                    "ph": vph,
                    "t0": t_cur,
                    "t1": t_cur + v_dur,
                    "sy": sy,
                    "soft_start": soft_start,
                })
            t_cur += v_dur
        else:
            d2 = max(0.065, min(0.36, v_dur * 0.26))
            if d2 > v_dur * 0.42:
                d2 = v_dur * 0.32
            d1 = v_dur - d2
            segments.append({
                "kind": "VOWEL",
                "ph": nuclei[0],
                "t0": t_cur,
                "t1": t_cur + d1,
                "sy": sy,
                "soft_start": soft_start,
            })
            segments.append({
                "kind": "VOWEL_GLIDE",
                "ph": nuclei[0],
                "ph2": nuclei[1],
                "t0": t_cur + d1,
                "t1": t_cur + v_dur,
                "sy": sy,
                "soft_start": False,
            })
            t_cur += v_dur

        for ph, d in zip(sp["codas"], sp["coda_durs"]):
            emit_consonant(ph, d, True, prev_v_tup)

    return segments, phrase_start, phrase_end


# =============================================================================
# EXPRESSIVE F0 CONTOUR EVALUATION
# =============================================================================

def _smoothstep(x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x * x * (3.0 - 2.0 * x)


def _build_f0_anchors(phrase_sylls):
    anchors = []
    for idx, sy in enumerate(phrase_sylls):
        t0 = sy["start"]
        t1 = sy["end"]
        dur = max(0.05, t1 - t0)
        ppts = sy["pitch_points"]
        is_coda_final_mine = (
            sy.get("scene") == "coda"
            and idx == len(phrase_sylls) - 1
            and sy.get("word", "").lower().startswith("mine")
        )
        anchors.append({
            "t0": t0,
            "t1": t1,
            "dur": dur,
            "ppts": [(t0 + f * dur, math.log2(hz)) for f, hz in ppts],
            "scoop_oct": sy.get("scoop", 0.0) / 12.0,
            "vib_mult": sy.get("vibrato", 0.85),
            "vib_delay": sy.get("vib_delay", 0.20),
            "release_fade": sy.get("release_fade", 0.14),
            "is_phrase_end": (idx == len(phrase_sylls) - 1),
            "still_fade": is_coda_final_mine,
            "dyn": sy.get("dyn", 0.9),
            "stress": sy.get("stress", 0.7),
        })
    return anchors


def _eval_f0_at(t, anchors, vib_state, rate_drift_u, depth_drift_u, pitch_wander_u):
    n = len(anchors)
    idx = 0
    for i in range(n):
        if t < anchors[i]["t1"]:
            idx = i
            break
    else:
        idx = n - 1

    cur = anchors[idx]
    ppts = cur["ppts"]

    if len(ppts) == 1:
        log_f0 = ppts[0][1]
        note_onset = cur["t0"]
    else:
        log_f0 = ppts[0][1]
        note_onset = cur["t0"]
        for k in range(1, len(ppts)):
            tm, lhz = ppts[k]
            glide = 0.078
            if t >= tm - glide * 0.5:
                u = _smoothstep((t - (tm - glide * 0.5)) / glide)
                log_f0 = ppts[k - 1][1] * (1.0 - u) + lhz * u
                note_onset = tm if u > 0.5 else cur["t0"]

    if idx > 0:
        prev = anchors[idx - 1]
        gap = cur["t0"] - prev["t1"]
        if gap < 0.11:
            prev_end_lf0 = prev["ppts"][-1][1]
            port_dur = 0.080
            if abs(log_f0 - prev_end_lf0) > 0.01:
                dt_join = t - (cur["t0"] - 0.024)
                if dt_join < port_dur:
                    u = _smoothstep(dt_join / port_dur)
                    log_f0 = prev_end_lf0 * (1.0 - u) + log_f0 * u

    dt_on = t - cur["t0"]
    if cur["scoop_oct"] != 0.0 and -0.04 <= dt_on < 0.132:
        u = _smoothstep((dt_on + 0.024) / 0.132)
        log_f0 += cur["scoop_oct"] * (1.0 - u)

    if cur["is_phrase_end"] and t > cur["t1"] - 0.32:
        u_rel = _smoothstep((t - (cur["t1"] - 0.32)) / 0.36)
        log_f0 -= (0.12 / 12.0) * u_rel

    # Slow organic human micro-intonation wander (+/- 6.0 cents)
    log_f0 += (0.060 / 12.0) * max(-1.6, min(1.6, pitch_wander_u))

    note_age = max(0.0, t - note_onset)
    vib_delay = cur["vib_delay"]
    vib_ramp = 0.27
    vib_amp_mod = 1.0
    vib_tilt_mod = 0.0

    if cur["dur"] > 0.38 and note_age > vib_delay and cur["vib_mult"] > 0.01:
        env = _smoothstep((note_age - vib_delay) / vib_ramp)
        if cur["still_fade"]:
            # Coda final "mine": taper vibrato smoothly to 0.0 over final 42% -> pure still human sigh!
            frac_pos = (t - cur["t0"]) / cur["dur"]
            if frac_pos > 0.56:
                env *= max(0.0, 1.0 - _smoothstep((frac_pos - 0.56) / 0.42))
        elif cur["is_phrase_end"] and t > cur["t1"] - 0.24:
            env *= max(0.18, 1.0 - _smoothstep((t - (cur["t1"] - 0.24)) / 0.28) * 0.82)
        d_scale = max(0.62, min(1.38, 1.0 + 0.26 * depth_drift_u))
        vib_semitones = 0.28 * cur["vib_mult"] * env * d_scale
    else:
        vib_semitones = 0.0

    vib_rate = 5.28 + 0.36 * max(-1.3, min(1.3, rate_drift_u))
    vib_state[0] += TWO_PI * vib_rate * (BLOCK_SIZE / float(SAMPLE_RATE))
    if vib_semitones > 0.0:
        sv = math.sin(vib_state[0])
        log_f0 += (vib_semitones / 12.0) * sv
        norm_v = vib_semitones / 0.30
        vib_amp_mod = 1.0 + 0.055 * norm_v * sv
        vib_tilt_mod = 55.0 * norm_v * sv

    return 2.0 ** log_f0, vib_amp_mod, vib_tilt_mod


# =============================================================================
# RESONATOR & FILTER COEFFICIENT MATH
# =============================================================================

def _klatt_resonator_coeffs(freq, bw, sr=SAMPLE_RATE):
    nyq = sr * 0.47
    if freq > nyq:
        freq = nyq
    elif freq < 60.0:
        freq = 60.0
    if bw < 50.0:
        bw = 50.0
    r = math.exp(-math.pi * bw / sr)
    c = -(r * r)
    b = 2.0 * r * math.cos(TWO_PI * freq / sr)
    a = 1.0 - b - c
    return a, b, c


def _bp_resonator_coeffs(freq, bw, sr=SAMPLE_RATE):
    nyq = sr * 0.46
    if freq > nyq:
        freq = nyq
    elif freq < 150.0:
        freq = 150.0
    if bw < 80.0:
        bw = 80.0
    r = math.exp(-math.pi * bw / sr)
    c = -(r * r)
    b = 2.0 * r * math.cos(TWO_PI * freq / sr)
    g = (1.0 - r) * 0.85
    return g, b, c


def _notch_coeffs(freq, bw, sr=SAMPLE_RATE):
    nyq = sr * 0.46
    freq = max(300.0, min(nyq, freq))
    r = math.exp(-math.pi * bw / sr)
    b = -2.0 * r * math.cos(TWO_PI * freq / sr)
    c = r * r
    denom = 1.0 + b + c
    if abs(denom) < 1e-6:
        return 1.0, 0.0, 0.0
    inv = 1.0 / denom
    return inv, b * inv, c * inv


def _peaking_eq_coeffs(freq, q, gain_db, sr=SAMPLE_RATE):
    """Standard RBJ biquad peaking EQ (for subtle silky close-mic vocal presence)."""
    a_lin = 10.0 ** (gain_db / 40.0)
    w0 = TWO_PI * freq / sr
    cos_w = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * q)
    b0 = 1.0 + alpha * a_lin
    b1 = -2.0 * cos_w
    b2 = 1.0 - alpha * a_lin
    a0 = 1.0 + alpha / a_lin
    a1 = -2.0 * cos_w
    a2 = 1.0 - alpha / a_lin
    inv = 1.0 / a0
    return b0 * inv, b1 * inv, b2 * inv, a1 * inv, a2 * inv


def _lp_norm_gain(alpha):
    return math.sqrt(3.0 * (2.0 - alpha) / max(1e-9, alpha))


# =============================================================================
# PHRASE SYNTHESIS CORE
# =============================================================================

def _synthesize_phrase(
    phrase_sylls,
    vocal_buf,
    f0_buf,
    breath_buf,
    sr=SAMPLE_RATE,
    rng_seed=1337,
):
    segments, t_start, t_end = _build_phrase_phoneme_plan(phrase_sylls)
    if not segments:
        return

    n_total = len(vocal_buf)
    s_start = max(0, int(t_start * sr))
    s_end = min(n_total, int(t_end * sr))
    if s_end <= s_start:
        return

    anchors = _build_f0_anchors(phrase_sylls)
    vib_state = [0.0]

    ph_t0 = phrase_sylls[0]["start"]
    ph_t1 = phrase_sylls[-1]["end"]
    ph_dur = max(0.25, ph_t1 - ph_t0)

    seed = (rng_seed * 2654435761) & 0xFFFFFFFF
    inv_2p31 = 1.0 / 2147483648.0

    # Glottal oscillator & unit-RMS organic perturbations
    phi = 0.0
    jitter_lp = 0.0
    shimmer_lp = 0.0
    vrate_lp = 0.0
    vdepth_lp = 0.0
    pwander_lp = 0.0
    fdrift_lp1 = 0.0
    fdrift_lp2 = 0.0
    fdrift_lp3 = 0.0

    a_jit = 0.065;   g_jit = _lp_norm_gain(a_jit)
    a_shim = 0.085;  g_shim = _lp_norm_gain(a_shim)
    a_vrat = 0.012;  g_vrat = _lp_norm_gain(a_vrat)
    a_vdep = 0.014;  g_vdep = _lp_norm_gain(a_vdep)
    a_pwan = 0.004;  g_pwan = _lp_norm_gain(a_pwan)
    a_fdr = 0.012;   g_fdr = _lp_norm_gain(a_fdr)

    tilt_y1 = 0.0
    tilt_y2 = 0.0
    dc_x1 = 0.0
    dc_y1 = 0.0
    chest_y1 = 0.0
    chest_y2 = 0.0

    # Silky upper vocal-fold air (~560..3450 Hz) unifies vowels & consonants
    asp_lp1 = 0.0
    asp_lp2 = 0.0
    asp_hp_x1 = 0.0
    asp_hp_y1 = 0.0

    # Dedicated dark non-resonant inhale shaper (~270..1220 Hz, BYPASSES cascade)
    inh_lp1 = 0.0
    inh_lp2 = 0.0
    inh_hp_x1 = 0.0
    inh_hp_y1 = 0.0

    vbar_y1 = 0.0
    vbar_y2 = 0.0

    na_m, nb_m, nc_m = _klatt_resonator_coeffs(275.0, 95.0, sr)
    nm_y1 = 0.0
    nm_y2 = 0.0
    nz_x1 = 0.0
    nz_x2 = 0.0

    f1_y1 = f1_y2 = 0.0
    f2_y1 = f2_y2 = 0.0
    f3_y1 = f3_y2 = 0.0
    f4_y1 = f4_y2 = 0.0
    f5_y1 = f5_y2 = 0.0

    warm_lp = 0.0

    fr1_x1 = fr1_x2 = fr1_y1 = fr1_y2 = 0.0
    fr2_x1 = fr2_x2 = fr2_y1 = fr2_y2 = 0.0
    fr_hp_x1 = fr_hp_y1 = 0.0
    fr_deess_lp = 0.0

    s_f1, s_f2, s_f3, s_f4, s_f5 = 500.0, 1385.0, 2480.0, 3250.0, 4150.0
    s_b1, s_b2, s_b3, s_b4, s_b5 = 104.0, 134.0, 176.0, 272.0, 390.0
    s_av = 0.0
    s_asp = 0.0
    s_inhale = 0.0
    s_fric = 0.0
    s_nasal = 0.0
    s_fnz = 1500.0
    s_vbar = 0.0
    s_oq = 0.65
    s_tr = 0.125
    s_tilt_fc = 920.0
    s_ff1, s_fb1, s_ff2, s_fb2 = 4500.0, 1300.0, 6400.0, 1700.0
    s_hp_amt = 0.5
    s_breath_track = 0.0

    dt_blk = BLOCK_SIZE / float(sr)
    # Nimble 13ms articulatory smoothing -> crisp stop/consonant transitions without clicks!
    alpha_formant = 1.0 - math.exp(-dt_blk / 0.013)
    alpha_amp_up = 1.0 - math.exp(-dt_blk / 0.010)
    alpha_amp_dn = 1.0 - math.exp(-dt_blk / 0.015)
    alpha_fric = 1.0 - math.exp(-dt_blk / 0.0045)
    alpha_nasal = 1.0 - math.exp(-dt_blk / 0.016)

    # Golden sweet-spot fixed filters (open close-mic clarity, zero buzz!)
    asp_lp_a = 1.0 - math.exp(-TWO_PI * 3450.0 / sr)
    asp_hp_r = math.exp(-TWO_PI * 560.0 / sr)
    inh_lp_a = 1.0 - math.exp(-TWO_PI * 1220.0 / sr)
    inh_hp_r = math.exp(-TWO_PI * 270.0 / sr)
    tilt2_a = 1.0 - math.exp(-TWO_PI * 3300.0 / sr)
    chest_a = 1.0 - math.exp(-TWO_PI * 240.0 / sr)
    vbar_a = 1.0 - math.exp(-TWO_PI * 260.0 / sr)
    warm_lp_a = 1.0 - math.exp(-TWO_PI * 4150.0 / sr)
    deess_lp_a = 1.0 - math.exp(-TWO_PI * 5800.0 / sr)
    fr_hp_r = math.exp(-TWO_PI * 3300.0 / sr)
    dc_r = 0.992

    seg_idx = 0
    n_segs = len(segments)
    inv_sr = 1.0 / float(sr)
    pi = math.pi
    sin = math.sin
    exp = math.exp
    sin_lut = _SIN_LUT
    cos_lut = _COS_LUT

    for blk_s in range(s_start, s_end, BLOCK_SIZE):
        blk_e = blk_s + BLOCK_SIZE
        if blk_e > s_end:
            blk_e = s_end
        t_mid = (blk_s + 0.5 * (blk_e - blk_s)) * inv_sr

        while seg_idx < n_segs - 1 and t_mid >= segments[seg_idx]["t1"]:
            seg_idx += 1
        seg = segments[seg_idx]
        active = (seg["t0"] <= t_mid <= seg["t1"])

        sy = seg["sy"]
        dyn = sy.get("dyn", 0.90)
        extra_br = sy.get("breathiness", 0.0)
        stress = sy.get("stress", 0.70)

        ph_u = max(0.0, min(1.0, (t_mid - ph_t0) / ph_dur))
        phrase_arch = 0.90 + 0.14 * sin(pi * min(1.0, ph_u * 1.08))
        stress_mul = 0.82 + 0.26 * stress

        # Golden close-mic open-warm glottal sweet spot:
        #   Verses (dyn 0.78..1.18, extra_br ~0.0..0.06):
        #     Tr ~ 0.095..0.145, tilt_fc ~ 780..1180 Hz -> warm, velvety, crystal clear!
        #   Hushed Coda (dyn 0.48..0.55, extra_br ~0.28..0.38):
        #     Tr ~ 0.155..0.205, tilt_fc ~ 520..740 Hz -> tender, hushed, intelligible!
        t_oq = max(0.57, min(0.75, 0.73 - 0.13 * dyn + extra_br * 0.20))
        t_tr = max(0.092, min(0.205, 0.175 - 0.068 * dyn + extra_br * 0.11))
        t_tilt_fc = max(
            510.0,
            min(1200.0, 620.0 + 460.0 * dyn + 85.0 * (stress - 0.65) - extra_br * 440.0),
        )

        t_av = 0.0
        t_asp = 0.0
        t_inhale = 0.0
        t_fric = 0.0
        t_nasal = 0.0
        t_vbar = 0.0
        t_fnz = s_fnz
        t_f1, t_f2, t_f3, t_f4, t_f5 = s_f1, s_f2, s_f3, s_f4, s_f5
        t_b1, t_b2, t_b3, t_b4, t_b5 = s_b1, s_b2, s_b3, s_b4, s_b5
        t_ff1, t_fb1, t_ff2, t_fb2 = s_ff1, s_fb1, s_ff2, s_fb2
        t_hp_amt = s_hp_amt
        t_breath_vis = 0.0

        if active:
            kind = seg["kind"]
            seg_dur = max(1e-4, seg["t1"] - seg["t0"])
            u = (t_mid - seg["t0"]) / seg_dur

            sy_dur = max(0.05, sy["end"] - sy["start"])
            sy_u = max(0.0, min(1.0, (t_mid - sy["start"]) / sy_dur))

            if sy_dur > 0.55:
                syll_env = 0.84 + 0.22 * sin(pi * (sy_u ** 0.85))
            else:
                syll_env = 0.88 + 0.16 * sin(pi * sy_u)

            rel_env = 1.0
            if not sy.get("legato", True):
                rf = sy.get("release_fade", 0.40)
                if sy_u > 1.0 - rf:
                    rel_env = 0.08 + 0.92 * math.cos(0.5 * pi * (sy_u - (1.0 - rf)) / rf)

            eff_dyn = dyn * stress_mul * phrase_arch * syll_env * rel_env

            if kind == "INHALE":
                # Dedicated dark non-resonant breath intake (BYPASSES cascade, -27 dB!)
                env_in = (sin(pi * u) ** 2.1)
                t_inhale = 0.026 * env_in * (0.65 + 0.35 * dyn)
                t_breath_vis = 0.72 * env_in

            elif kind == "VOWEL":
                vt = VOWELS[seg["ph"]]
                t_f1, t_f2, t_f3, t_f4, t_f5 = vt[0], vt[1], vt[2], vt[3], vt[4]
                t_b1, t_b2, t_b3, t_b4, t_b5 = vt[5], vt[6], vt[7], vt[8], vt[9]
                g_trim = vt[10]
                on_env = 1.0
                if seg.get("soft_start", False) and (t_mid - seg["t0"]) < 0.050:
                    on_env = 0.22 + 0.78 * _smoothstep((t_mid - seg["t0"]) / 0.050)
                t_av = 1.00 * eff_dyn * g_trim * on_env
                # Silky vocal-fold air sheen (unifies vowels & consonants; breathier in Coda)
                br_base = 0.056 + max(0.0, 0.98 - dyn) * 0.070 + extra_br * 0.24
                if not sy.get("legato", True) and sy_u > 0.58:
                    br_base += 0.075 * (sy_u - 0.58) / 0.42
                t_asp = br_base * (0.45 + 0.55 * rel_env) * (0.62 + 0.38 * dyn)
                t_breath_vis = min(1.0, t_asp * 4.0)

            elif kind == "VOWEL_GLIDE":
                vt1 = VOWELS[seg["ph"]]
                vt2 = VOWELS[seg["ph2"]]
                ug = 0.5 - 0.5 * math.cos(pi * u)
                inv_ug = 1.0 - ug
                t_f1 = vt1[0] * inv_ug + vt2[0] * ug
                t_f2 = vt1[1] * inv_ug + vt2[1] * ug
                t_f3 = vt1[2] * inv_ug + vt2[2] * ug
                t_f4 = vt1[3] * inv_ug + vt2[3] * ug
                t_f5 = vt1[4] * inv_ug + vt2[4] * ug
                t_b1 = vt1[5] * inv_ug + vt2[5] * ug
                t_b2 = vt1[6] * inv_ug + vt2[6] * ug
                t_b3 = vt1[7] * inv_ug + vt2[7] * ug
                t_b4 = vt1[8] * inv_ug + vt2[8] * ug
                t_b5 = vt1[9] * inv_ug + vt2[9] * ug
                g_trim = vt1[10] * inv_ug + vt2[10] * ug
                t_av = 0.96 * eff_dyn * g_trim
                br_base = 0.062 + max(0.0, 0.98 - dyn) * 0.070 + extra_br * 0.24
                t_asp = br_base * (0.45 + 0.55 * rel_env) * (0.62 + 0.38 * dyn)
                t_breath_vis = min(1.0, t_asp * 4.0)

            elif kind == "SONORANT":
                sp = SONORANTS[seg["ph"]]
                t_f1, t_f2, t_f3, t_f4, t_f5 = sp[0], sp[1], sp[2], sp[3], sp[4]
                t_b1, t_b2, t_b3, t_b4, t_b5 = sp[5], sp[6], sp[7], sp[8], sp[9]
                av_sc, nas_amt, fnz = sp[10], sp[11], sp[12]
                if seg["ph"] in ("W", "Y", "R", "L", "DL"):
                    adj = seg["adj_v"]
                    blend = u * 0.45 if not seg["is_coda"] else (1.0 - u) * 0.42
                    inv_b = 1.0 - blend
                    t_f1 = t_f1 * inv_b + adj[0] * blend
                    t_f2 = t_f2 * inv_b + adj[1] * blend
                    t_f3 = t_f3 * inv_b + adj[2] * blend
                coda_taper = 1.0
                if seg["is_coda"] and not sy.get("legato", True):
                    coda_taper = max(0.06, 1.0 - 0.92 * (u ** 1.3))
                t_av = av_sc * eff_dyn * coda_taper
                t_nasal = nas_amt
                t_fnz = fnz
                t_asp = (0.038 + extra_br * 0.13) * coda_taper * (0.62 + 0.38 * dyn)
                t_breath_vis = min(1.0, t_asp * 3.5)

            elif kind == "FRIC":
                ph = seg["ph"]
                fr = FRICATIVES[ph]
                place, voiced, _, _, fgain, ff1, fb1, ff2, fb2, hp_a, av_sc, lf1, lf2, lf3 = fr
                adj = seg["adj_v"]
                if ph == "HH":
                    t_f1, t_f2, t_f3, t_f4, t_f5 = adj[0], adj[1], adj[2], adj[3], adj[4]
                    t_b1, t_b2, t_b3, t_b4, t_b5 = adj[5] * 1.35, adj[6] * 1.3, adj[7] * 1.2, adj[8], adj[9]
                    env_h = sin(pi * min(1.0, u * 0.88 + 0.08)) ** 1.3
                    t_asp = 0.17 * dyn * stress_mul * env_h
                    t_inhale = 0.011 * dyn * env_h
                    t_av = (0.48 * eff_dyn * ((u - 0.58) / 0.42)) if u > 0.58 else 0.0
                    t_breath_vis = min(1.0, 0.65 * env_h)
                else:
                    bl = (u * 0.40) if not seg["is_coda"] else ((1.0 - u) * 0.40)
                    t_f1 = lf1 * (1.0 - bl) + adj[0] * bl
                    t_f2 = lf2 * (1.0 - bl) + adj[1] * bl
                    t_f3 = lf3 * (1.0 - bl) + adj[2] * bl
                    t_f4, t_f5 = adj[3], adj[4]
                    t_b1, t_b2, t_b3, t_b4, t_b5 = 112.0, 142.0, 185.0, 275.0, 390.0
                    env_f = 1.0
                    if u < 0.18:
                        env_f = u / 0.18
                    elif u > 0.80:
                        env_f = (1.0 - u) / 0.20
                    # Dynamic consonant scaling (hushed Coda fricatives match whispered vowels!)
                    fric_dyn = 0.34 + 0.68 * dyn
                    t_fric = fgain * fric_dyn * env_f
                    t_ff1, t_fb1, t_ff2, t_fb2 = ff1, fb1, ff2, fb2
                    t_hp_amt = hp_a
                    if voiced:
                        t_av = av_sc * eff_dyn * (0.68 + 0.32 * env_f)
                        t_vbar = 0.18 * eff_dyn
                    t_breath_vis = min(1.0, t_fric * 1.6)

            elif kind == "STOP_CLO":
                ph = seg["ph"]
                st = STOPS[ph]
                place, voiced = st[0], st[1]
                adj = seg["adj_v"]
                if place == "vel":
                    lf1, lf2, lf3, _, _ = _velar_coarticulated_locus(adj)
                else:
                    lf1, lf2, lf3 = st[10], st[11], st[12]
                t_f1, t_f2, t_f3, t_f4, t_f5 = lf1, lf2, lf3, adj[3], adj[4]
                t_b1, t_b2, t_b3, t_b4, t_b5 = 104.0, 134.0, 178.0, 275.0, 390.0
                t_av = 0.0
                t_fric = 0.0
                if voiced:
                    t_vbar = 0.24 * eff_dyn * (0.6 + 0.4 * sin(pi * u))

            elif kind == "STOP_BURST":
                ph = seg["ph"]
                st = STOPS[ph]
                place, voiced = st[0], st[1]
                bgain, bf1, bb1, bf2, bb2 = st[5], st[6], st[7], st[8], st[9]
                adj = seg["adj_v"]
                if place == "vel":
                    lf1, lf2, lf3, bf1, bf2 = _velar_coarticulated_locus(adj)
                else:
                    lf1, lf2, lf3 = st[10], st[11], st[12]
                t_f1, t_f2, t_f3, t_f4, t_f5 = lf1, lf2, lf3, adj[3], adj[4]
                t_b1, t_b2, t_b3, t_b4, t_b5 = 108.0, 138.0, 182.0, 275.0, 390.0
                env_b = sin(pi * u) ** 0.72
                coda_sc = 0.85 if seg["is_coda"] else 1.0
                fric_dyn = 0.36 + 0.66 * dyn
                t_fric = bgain * fric_dyn * env_b * coda_sc
                t_ff1, t_fb1, t_ff2, t_fb2 = bf1, bb1, bf2, bb2
                t_hp_amt = 0.60 if place == "alv" else (0.0 if place == "vel" else 0.12)
                if voiced:
                    t_vbar = 0.18 * eff_dyn
                else:
                    t_asp = 0.17 * dyn * env_b * coda_sc
                t_breath_vis = min(1.0, t_fric * 2.0)

            elif kind == "STOP_VOT":
                ph = seg["ph"]
                st = STOPS[ph]
                place, voiced = st[0], st[1]
                adj = seg["adj_v"]
                if place == "vel":
                    lf1, lf2, lf3, _, _ = _velar_coarticulated_locus(adj)
                else:
                    lf1, lf2, lf3 = st[10], st[11], st[12]
                if not seg["is_coda"]:
                    bl = _smoothstep(u) * 0.80
                    t_f1 = lf1 * (1.0 - bl) + adj[0] * bl
                    t_f2 = lf2 * (1.0 - bl) + adj[1] * bl
                    t_f3 = lf3 * (1.0 - bl) + adj[2] * bl
                else:
                    t_f1, t_f2, t_f3 = lf1, lf2, lf3
                t_f4, t_f5 = adj[3], adj[4]
                t_b1, t_b2, t_b3, t_b4, t_b5 = adj[5] * 1.18, adj[6] * 1.14, adj[7] * 1.10, adj[8], adj[9]

                if ph == "JH":
                    env_j = sin(pi * min(1.0, u * 0.9 + 0.05))
                    fric_dyn = 0.36 + 0.66 * dyn
                    t_fric = 0.38 * fric_dyn * env_j
                    t_ff1, t_fb1, t_ff2, t_fb2 = 2500.0, 760.0, 3800.0, 960.0
                    t_hp_amt = 0.42
                    t_av = 0.40 * eff_dyn * (1.0 - 0.50 * u)
                elif not voiced:
                    env_v = (1.0 - u) ** 0.80
                    coda_sc = 0.74 if seg["is_coda"] else 1.0
                    t_asp = (0.25 if ph in ("P", "T", "K") else 0.12) * dyn * env_v * coda_sc
                    if not seg["is_coda"] and u > 0.62:
                        t_av = 0.48 * eff_dyn * ((u - 0.62) / 0.38)
                else:
                    if not seg["is_coda"]:
                        t_av = (0.40 + 0.55 * u) * eff_dyn
                    else:
                        t_vbar = 0.12 * eff_dyn * (1.0 - u)
                        t_asp = 0.06 * dyn * (1.0 - u)
                t_breath_vis = min(1.0, (t_asp + t_fric) * 2.5)

        s_f1 += (t_f1 - s_f1) * alpha_formant
        s_f2 += (t_f2 - s_f2) * alpha_formant
        s_f3 += (t_f3 - s_f3) * alpha_formant
        s_f4 += (t_f4 - s_f4) * alpha_formant
        s_f5 += (t_f5 - s_f5) * alpha_formant
        s_b1 += (t_b1 - s_b1) * alpha_formant
        s_b2 += (t_b2 - s_b2) * alpha_formant
        s_b3 += (t_b3 - s_b3) * alpha_formant
        s_b4 += (t_b4 - s_b4) * alpha_formant
        s_b5 += (t_b5 - s_b5) * alpha_formant

        a_av = alpha_amp_up if t_av > s_av else alpha_amp_dn
        s_av += (t_av - s_av) * a_av
        s_asp += (t_asp - s_asp) * alpha_fric
        s_inhale += (t_inhale - s_inhale) * alpha_amp_up
        s_fric += (t_fric - s_fric) * alpha_fric
        s_nasal += (t_nasal - s_nasal) * alpha_nasal
        s_fnz += (t_fnz - s_fnz) * alpha_formant
        s_vbar += (t_vbar - s_vbar) * alpha_amp_up
        s_oq += (t_oq - s_oq) * alpha_formant
        s_tr += (t_tr - s_tr) * alpha_formant
        s_tilt_fc += (t_tilt_fc - s_tilt_fc) * alpha_formant
        s_ff1 += (t_ff1 - s_ff1) * 0.48
        s_fb1 += (t_fb1 - s_fb1) * 0.48
        s_ff2 += (t_ff2 - s_ff2) * 0.48
        s_fb2 += (t_fb2 - s_fb2) * 0.48
        s_hp_amt += (t_hp_amt - s_hp_amt) * 0.48
        s_breath_track += (t_breath_vis - s_breath_track) * 0.15

        # Unit-RMS-normalized organic vocal-fold & tract perturbations
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rn1 = (seed - 2147483648.0) * inv_2p31
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rn2 = (seed - 2147483648.0) * inv_2p31
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rn3 = (seed - 2147483648.0) * inv_2p31
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rn4 = (seed - 2147483648.0) * inv_2p31
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rn5 = (seed - 2147483648.0) * inv_2p31

        jitter_lp += (rn1 - jitter_lp) * a_jit
        shimmer_lp += (rn2 - shimmer_lp) * a_shim
        vrate_lp += (rn3 - vrate_lp) * a_vrat
        vdepth_lp += (rn4 - vdepth_lp) * a_vdep
        pwander_lp += (rn5 - pwander_lp) * a_pwan
        fdrift_lp1 += (rn1 - fdrift_lp1) * a_fdr
        fdrift_lp2 += (rn2 - fdrift_lp2) * a_fdr
        fdrift_lp3 += (rn3 - fdrift_lp3) * a_fdr

        jit_u = jitter_lp * g_jit
        shim_u = shimmer_lp * g_shim
        vrat_u = vrate_lp * g_vrat
        vdep_u = vdepth_lp * g_vdep
        pwan_u = pwander_lp * g_pwan
        fdr1_u = max(-1.6, min(1.6, fdrift_lp1 * g_fdr))
        fdr2_u = max(-1.6, min(1.6, fdrift_lp2 * g_fdr))
        fdr3_u = max(-1.6, min(1.6, fdrift_lp3 * g_fdr))

        base_f0, vib_amp_mod, vib_tilt_mod = _eval_f0_at(
            t_mid, anchors, vib_state, vrat_u, vdep_u, pwan_u
        )
        f0_hz = base_f0 * (1.0 + 0.0025 * max(-1.8, min(1.8, jit_u)))
        shimmer_mul = (1.0 + 0.019 * max(-1.8, min(1.8, shim_u))) * vib_amp_mod

        # Gentle high-note baritone cover (warm without muffling "sage"/"Remember"/"Between"!)
        high_cover = max(0.0, min(1.0, (base_f0 - 205.0) / 95.0))

        dphi = f0_hz * inv_sr
        oq = max(0.56, min(0.75, s_oq + 0.012 * high_cover + 0.007 * shim_u))
        tr = max(0.092, min(0.215, s_tr + 0.022 * high_cover))
        if oq + tr > 0.97:
            tr = 0.97 - oq
        tp = 0.67 * oq
        inv_tp_512 = 512.0 / tp
        inv_cl_256 = 256.0 / max(1e-4, oq - tp)
        inv_tr_512 = 512.0 / max(1e-4, tr)
        oq_end = oq + tr
        inv_oq = 1.0 / oq

        eff_tilt_fc = max(460.0, min(1240.0, s_tilt_fc - 75.0 * high_cover + vib_tilt_mod))
        tilt1_a = 1.0 - exp(-TWO_PI * eff_tilt_fc * inv_sr)

        # Gentle cover (-3.8% F2, +8% B2/B3) + living formant drift
        ef1 = max(s_f1 * (1.0 + 0.014 * fdr1_u), f0_hz * 1.12)
        ef2 = s_f2 * (1.0 - 0.038 * high_cover) * (1.0 + 0.014 * fdr2_u)
        ef3 = s_f3 * (1.0 - 0.015 * high_cover) * (1.0 + 0.011 * fdr3_u)
        eb2 = s_b2 * (1.0 + 0.08 * high_cover)
        eb3 = s_b3 * (1.0 + 0.08 * high_cover)

        a1, b1, c1 = _klatt_resonator_coeffs(ef1, s_b1, sr)
        a2, b2, c2 = _klatt_resonator_coeffs(ef2, eb2, sr)
        a3, b3, c3 = _klatt_resonator_coeffs(ef3, eb3, sr)
        a4, b4, c4 = _klatt_resonator_coeffs(s_f4, s_b4, sr)
        a5, b5, c5 = _klatt_resonator_coeffs(s_f5, s_b5, sr)

        use_nasal = (s_nasal > 0.008)
        if use_nasal:
            nz_a, nz_b, nz_c = _notch_coeffs(s_fnz, 175.0, sr)
        else:
            nz_a, nz_b, nz_c = 1.0, 0.0, 0.0

        use_fric = (s_fric > 0.002)
        if use_fric:
            fg1, fb1_c, fc1_c = _bp_resonator_coeffs(s_ff1, s_fb1, sr)
            fg2, fb2_c, fc2_c = _bp_resonator_coeffs(s_ff2, s_fb2, sr)
        else:
            fg1 = fb1_c = fc1_c = fg2 = fb2_c = fc2_c = 0.0

        av_eff = s_av * shimmer_mul * 0.52
        asp_eff = s_asp * 0.44
        inhale_eff = s_inhale
        vbar_eff = s_vbar * 0.34
        fric_eff = s_fric * 0.35
        nas_mix = s_nasal
        oral_mix = 1.0 - nas_mix * 0.50
        hp_mix = s_hp_amt
        # Balanced warm baritone chest body (rich without low-mid wooliness!)
        chest_gain = av_eff * (0.20 + 0.06 * (1.0 - high_cover))

        f0_out = f0_hz if (s_av > 0.04 or s_vbar > 0.04) else 0.0

        # ---- INNER SAMPLE LOOP (16 samples, zero transcendental math!) ----
        for i in range(blk_s, blk_e):
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            noise = (seed - 2147483648.0) * inv_2p31

            phi += dphi
            if phi >= 1.0:
                phi -= 1.0

            if phi < tp:
                g_raw = 0.45 * sin_lut[int(phi * inv_tp_512)]
                u_gl = phi * inv_oq
                open_mod = 0.38 + 2.4 * u_gl * (1.0 - u_gl)
            elif phi < oq:
                g_raw = -sin_lut[int((phi - tp) * inv_cl_256)]
                u_gl = phi * inv_oq
                open_mod = 0.38 + 2.4 * u_gl * (1.0 - u_gl)
            elif phi < oq_end:
                g_raw = -0.5 * (1.0 + cos_lut[int((phi - oq) * inv_tr_512)])
                open_mod = 0.32
            else:
                g_raw = 0.0
                open_mod = 0.28

            tilt_y1 += (g_raw - tilt_y1) * tilt1_a
            tilt_y2 += (tilt_y1 - tilt_y2) * tilt2_a
            g_dc = tilt_y2 - dc_x1 + dc_r * dc_y1
            dc_x1 = tilt_y2
            dc_y1 = g_dc

            chest_y1 += (g_dc - chest_y1) * chest_a
            chest_y2 += (chest_y1 - chest_y2) * chest_a

            # Silky warm vocal-fold air (~560..3450 Hz)
            asp_lp1 += (noise - asp_lp1) * asp_lp_a
            asp_lp2 += (asp_lp1 - asp_lp2) * asp_lp_a
            asp_bp = asp_lp2 - asp_hp_x1 + asp_hp_r * asp_hp_y1
            asp_hp_x1 = asp_lp2
            asp_hp_y1 = asp_bp

            if av_eff > 0.02:
                asp_sig = asp_bp * asp_eff * open_mod
            else:
                asp_sig = asp_bp * asp_eff * 1.05

            x_in = g_dc * av_eff + asp_sig

            if use_nasal:
                nz_out = nz_a * x_in + nz_b * nz_x1 + nz_c * nz_x2
                nz_x2 = nz_x1
                nz_x1 = x_in
                nm_out = na_m * x_in + nb_m * nm_y1 + nc_m * nm_y2
                nm_y2 = nm_y1
                nm_y1 = nm_out
                x_tract = x_in * oral_mix + nz_out * (nas_mix * 0.45)
            else:
                nz_x2 = nz_x1
                nz_x1 = x_in
                nm_out = 0.0
                x_tract = x_in

            y1 = a1 * x_tract + b1 * f1_y1 + c1 * f1_y2
            f1_y2 = f1_y1
            f1_y1 = y1

            y2 = a2 * y1 + b2 * f2_y1 + c2 * f2_y2
            f2_y2 = f2_y1
            f2_y1 = y2

            y3 = a3 * y2 + b3 * f3_y1 + c3 * f3_y2
            f3_y2 = f3_y1
            f3_y1 = y3

            y4 = a4 * y3 + b4 * f4_y1 + c4 * f4_y2
            f4_y2 = f4_y1
            f4_y1 = y4

            y5 = a5 * y4 + b5 * f5_y1 + c5 * f5_y2
            f5_y2 = f5_y1
            f5_y1 = y5

            warm_lp += (y5 - warm_lp) * warm_lp_a
            voiced_out = (
                warm_lp
                + chest_y2 * chest_gain
                + (nm_out * nas_mix * 0.36 if use_nasal else 0.0)
            )

            if inhale_eff > 0.0002:
                inh_lp1 += (noise - inh_lp1) * inh_lp_a
                inh_lp2 += (inh_lp1 - inh_lp2) * inh_lp_a
                inh_bp = inh_lp2 - inh_hp_x1 + inh_hp_r * inh_hp_y1
                inh_hp_x1 = inh_lp2
                inh_hp_y1 = inh_bp
                voiced_out += inh_bp * inhale_eff

            if vbar_eff > 0.001:
                vbar_y1 += (g_dc - vbar_y1) * vbar_a
                vbar_y2 += (vbar_y1 - vbar_y2) * vbar_a
                voiced_out += vbar_y2 * vbar_eff

            if use_fric:
                fr_hp = noise - fr_hp_x1 + fr_hp_r * fr_hp_y1
                fr_hp_x1 = noise
                fr_hp_y1 = fr_hp
                fr_src = noise * (1.0 - hp_mix) + fr_hp * hp_mix

                fy1 = fg1 * (fr_src - fr1_x2) + fb1_c * fr1_y1 + fc1_c * fr1_y2
                fr1_x2 = fr1_x1
                fr1_x1 = fr_src
                fr1_y2 = fr1_y1
                fr1_y1 = fy1

                fy2 = fg2 * (fr_src - fr2_x2) + fb2_c * fr2_y1 + fc2_c * fr2_y2
                fr2_x2 = fr2_x1
                fr2_x1 = fr_src
                fr2_y2 = fr2_y1
                fr2_y1 = fy2

                fr_sum = (fy1 * 0.65 + fy2 * 0.45) * fric_eff
                fr_deess_lp += (fr_sum - fr_deess_lp) * deess_lp_a
                out = voiced_out + fr_deess_lp
            else:
                out = voiced_out

            vocal_buf[i] += out
            f0_buf[i] = f0_out
            breath_buf[i] = s_breath_track


# =============================================================================
# POST-PROCESSING: HPF, CLOSE-MIC SILKY PRESENCE, DYNAMIC-PRESERVING LIMITING
# =============================================================================

def _postprocess_vocal(buf, sr=SAMPLE_RATE):
    """
    75 Hz Butterworth HPF, gentle +2.2 dB close-mic silky presence bloom at
    2.2 kHz (Q=0.80), whisper-light 0.06 chest warmth, and dynamic-preserving
    peak-only leveling (1.4:1 above 0.45 RMS) + soft tanh limiting.
    """
    n = len(buf)
    if n == 0:
        return buf

    # 1. 2nd-order Butterworth HPF at 75 Hz
    fc = 75.0
    w0 = TWO_PI * fc / sr
    cos_w = math.cos(w0)
    alpha = math.sin(w0) / math.sqrt(2.0)
    b0 = (1.0 + cos_w) * 0.5
    b1 = -(1.0 + cos_w)
    b2 = (1.0 + cos_w) * 0.5
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w
    a2 = 1.0 - alpha
    b0 /= a0; b1 /= a0; b2 /= a0; a1 /= a0; a2 /= a0

    # 2. Silky close-mic vocal presence bell (+2.2 dB @ 2200 Hz, Q=0.80)
    pb0, pb1, pb2, pa1, pa2 = _peaking_eq_coeffs(2200.0, 0.80, 2.2, sr)

    chest_a = 1.0 - math.exp(-TWO_PI * 235.0 / sr)
    env_att = 1.0 - math.exp(-1.0 / (0.050 * sr))
    env_rel = 1.0 - math.exp(-1.0 / (0.200 * sr))

    x1 = x2 = y1 = y2 = 0.0
    px1 = px2 = py1 = py2 = 0.0
    chest_lp = 0.0
    env_sq = 1e-6

    temp = array.array("d", [0.0]) * n
    max_abs = 1e-9
    for i in range(n):
        x = buf[i]
        # HPF
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = x; y2 = y1; y1 = y

        # Close-mic silky presence EQ
        yp = pb0 * y + pb1 * px1 + pb2 * px2 - pa1 * py1 - pa2 * py2
        px2 = px1; px1 = y; py2 = py1; py1 = yp

        # Subtle warm chest touch (0.06 — keeps intimacy without wooliness)
        chest_lp += (yp - chest_lp) * chest_a
        yw = yp + 0.06 * chest_lp

        temp[i] = yw
        ay = abs(yw)
        if ay > max_abs:
            max_abs = ay

    norm = 0.90 / max_abs if max_abs > 1e-6 else 1.0
    thresh = 0.45
    tanh = math.tanh
    sqrt = math.sqrt

    out_peak = 1e-9
    for i in range(n):
        s = temp[i] * norm
        sq = s * s
        if sq > env_sq:
            env_sq += (sq - env_sq) * env_att
        else:
            env_sq += (sq - env_sq) * env_rel
        rms = sqrt(env_sq)
        if rms > thresh:
            ratio = (thresh + (rms - thresh) * 0.72) / rms
            s *= ratio
        s = tanh(s * 0.95) * 0.96
        buf[i] = s
        as_ = abs(s)
        if as_ > out_peak:
            out_peak = as_

    if out_peak > 1e-6:
        sc = 0.86 / out_peak
        for i in range(n):
            buf[i] *= sc

    return buf


# =============================================================================
# PUBLIC API
# =============================================================================

def synthesize_vocals(spec, sr=SAMPLE_RATE):
    total_samples = int(spec["duration"] * sr)
    vocal_buf = array.array("d", [0.0]) * total_samples
    f0_buf = array.array("d", [0.0]) * total_samples
    breath_buf = array.array("d", [0.0]) * total_samples

    phrases_map = {}
    for sy in spec["syllables"]:
        phrases_map.setdefault(sy["phrase_index"], []).append(sy)

    for p_idx in sorted(phrases_map.keys()):
        _synthesize_phrase(
            phrases_map[p_idx],
            vocal_buf,
            f0_buf,
            breath_buf,
            sr=sr,
            rng_seed=1009 + p_idx * 97,
        )

    _postprocess_vocal(vocal_buf, sr=sr)
    return vocal_buf, f0_buf, breath_buf


if __name__ == "__main__":
    import time
    import wave
    import os
    from song_spec import build_song_spec

    t0 = time.perf_counter()
    spec = build_song_spec()
    vocal, f0_t, br_t = synthesize_vocals(spec, sr=SAMPLE_RATE)
    dt = time.perf_counter() - t0

    n = len(vocal)
    peak = max(abs(x) for x in vocal)
    rms = math.sqrt(sum(x * x for x in vocal) / max(1, n))
    nans = sum(1 for x in vocal if math.isnan(x) or math.isinf(x))
    print(f"Synthesized {spec['duration']:.2f}s vocal in {dt:.2f}s (realtime x{spec['duration']/max(0.01,dt):.1f})")
    print(f"Samples: {n}, Peak: {peak:.4f}, RMS: {rms:.4f}, NaN/Inf: {nans}")

    for sc in spec["scenes"]:
        if sc["id"] in ("verse1", "verse2", "verse3", "coda"):
            s0 = int(sc["start"] * SAMPLE_RATE)
            s1 = int(sc["end"] * SAMPLE_RATE)
            seg_rms = math.sqrt(sum(vocal[i] * vocal[i] for i in range(s0, s1)) / max(1, s1 - s0))
            db = 20.0 * math.log10(max(1e-9, seg_rms))
            print(f"  {sc['id']:8s} RMS={seg_rms:.4f} ({db:6.2f} dBFS)")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
    os.makedirs(out_dir, exist_ok=True)
    for sc_id in ("verse1", "coda"):
        sc_phrases = [p for p in spec["phrases"] if p["scene"] == sc_id]
        t_a = max(0.0, sc_phrases[0]["start"] - 0.35)
        t_b = min(spec["duration"], sc_phrases[-1]["end"] + 0.45)
        s0 = int(t_a * SAMPLE_RATE)
        s1 = int(t_b * SAMPLE_RATE)
        test_wav = os.path.join(out_dir, f"_v3_dry_{sc_id}.wav")
        pcm = array.array("h", (max(-32767, min(32767, int(vocal[i] * 32767.0))) for i in range(s0, s1)))
        with wave.open(test_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        print(f"Wrote {test_wav} ({(s1-s0)/SAMPLE_RATE:.2f}s)")
