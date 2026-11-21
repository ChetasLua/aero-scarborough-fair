"""Accompaniment, Room Reverb, Mastering & Timeline Feature Extraction
for "Aero Sings Scarborough Fair" (D Dorian, 3/4 waltz, 22050 Hz).

100% pure Python standard library only (no numpy, no scipy, no external assets).

Public API consumed by render_song.py:
  - render_accompaniment(chord_events, tempo_map, total_duration, sr=22050)
        -> (acc_left: array('d'), acc_right: array('d'))
  - mix_and_master(vocal_mono, acc_left, acc_right, sr=22050)
        -> (mix_left: array('d'), mix_right: array('d'), vocal_wet_mono: array('d'))
  - write_wav(path, channels, sr=22050) -> None
  - extract_timeline_features(vocal_mono, mix_left, mix_right,
                              f0_track, breath_track, sr=22050, fps=30)
        -> list[dict]
"""

from array import array
import math
import os
import random
import sys
import wave


# ---------------------------------------------------------------------------
# Musical pitch & chord tables (D Dorian acoustic folk / Drop-D guitar + cello)
# ---------------------------------------------------------------------------

def midi_to_hz(midi_note):
    """Convert MIDI note number (A4=69 -> 440.0 Hz) to exact equal-temperament Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


# Guitar voicings: (bass_midi, alt_bass_midi, [n0, n1, n2, n3] ascending inner/upper strings)
# Designed in Drop-D / folk guitar range so inner arpeggios stay warm around D3-D4
# and cradle Aero's baritone-tenor voice (D3-E4) with smooth voice-leading.
GUITAR_VOICINGS = {
    "Dm":     (38, 45, (50, 53, 57, 62)),   # D2 / A2 + D3, F3, A3, D4
    "Dm/F":   (41, 45, (50, 53, 57, 62)),   # F2 / A2 + D3, F3, A3, D4
    "Dm7":    (38, 45, (50, 53, 57, 60)),   # D2 / A2 + D3, F3, A3, C4
    "Dm9":    (38, 45, (50, 52, 57, 62)),   # D2 / A2 + D3, E3, A3, D4
    "Dsus2":  (38, 45, (50, 52, 57, 62)),   # D2 / A2 + D3, E3, A3, D4
    "D5":     (38, 45, (50, 57, 62, 62)),   # D2 / A2 + D3, A3, D4
    "D":      (38, 45, (50, 54, 57, 62)),   # D2 / A2 + D3, F#3, A3, D4
    "C":      (48, 48, (52, 55, 60, 64)),   # C3 + E3, G3, C4, E4
    "C/G":    (43, 48, (52, 55, 60, 64)),   # G2 / C3 + E3, G3, C4, E4
    "Cadd9":  (48, 48, (52, 55, 60, 62)),   # C3 + E3, G3, C4, D4
    "Csus2":  (48, 48, (50, 55, 60, 62)),   # C3 + D3, G3, C4, D4 (no E3/E4 clash vs F3!)
    "Csus4":  (48, 48, (53, 55, 60, 62)),   # C3 + F3, G3, C4, D4
    "F":      (41, 48, (48, 53, 57, 60)),   # F2 / C3 + C3, F3, A3, C4
    "F/C":    (48, 48, (53, 57, 60, 62)),   # C3 + F3, A3, C4, D4
    "Fmaj7":  (41, 48, (48, 53, 57, 64)),   # F2 / C3 + C3, F3, A3, E4
    "G":      (43, 50, (50, 55, 59, 62)),   # G2 / D3 + D3, G3, B3, D4 (iconic Dorian B-nat)
    "G/B":    (47, 50, (50, 55, 59, 62)),   # B2 / D3 + D3, G3, B3, D4
    "Gm":     (43, 50, (50, 55, 58, 62)),   # G2 / D3 + D3, G3, Bb3, D4
    "Am":     (45, 52, (52, 57, 60, 64)),   # A2 / E3 + E3, A3, C4, E4
    "Am7":    (45, 52, (52, 55, 60, 64)),   # A2 / E3 + E3, G3, C4, E4
    "A":      (45, 52, (52, 57, 61, 64)),   # A2 / E3 + E3, A3, C#4, E4
    "A7":     (45, 52, (52, 55, 61, 64)),   # A2 / E3 + E3, G3, C#4, E4
    "Em":     (40, 47, (47, 52, 55, 59)),   # E2 / B2 + B2, E3, G3, B3
    "Bb":     (46, 50, (50, 53, 58, 62)),   # Bb2 / D3 + D3, F3, Bb3, D4
    "Dm_end": (38, 45, (50, 53, 57, 62)),   # Lingering open D+A+F+D + 12th-fret harmonics
}

# Cello voicings: (bass_voice_midi, lyrical_tenor_harmony_midi)
# Bass anchors warmly in D2-C3; upper harmony sings in golden tenor-cello register (D3-G3),
# tucked cleanly beneath Aero's vocal formants while unmistakably enriching Verses 2 & 3.
CELLO_VOICINGS = {
    "Dm":     (38, 50),   # D2 (73 Hz), open D3 string (147 Hz)
    "Dm/F":   (41, 53),   # F2, F3
    "Dm7":    (38, 50),   # D2, D3
    "Dm9":    (38, 50),   # D2, D3
    "Dsus2":  (38, 50),   # D2, D3
    "D5":     (38, 50),   # D2, D3
    "D":      (38, 50),   # D2, D3
    "C":      (48, 55),   # C3 (131 Hz), G3 (196 Hz) — warm singing fifth, no muddy C2 growl
    "C/G":    (43, 55),   # G2, G3
    "Cadd9":  (48, 55),   # C3, G3
    "Csus2":  (48, 55),   # C3, G3 (zero clash vs F3 on "true")
    "Csus4":  (48, 53),   # C3, F3
    "F":      (41, 53),   # F2, F3 (175 Hz)
    "F/C":    (48, 53),   # C3, F3
    "Fmaj7":  (41, 53),   # F2, F3
    "G":      (43, 55),   # G2 (98 Hz), G3 (196 Hz) — soaring Dorian IV lift!
    "G/B":    (47, 55),   # B2, G3
    "Gm":     (43, 55),   # G2, G3
    "Am":     (45, 52),   # A2, E3 (165 Hz)
    "Am7":    (45, 52),   # A2, E3
    "A":      (45, 52),   # A2, E3
    "A7":     (45, 52),   # A2, E3
    "Em":     (40, 52),   # E2, E3
    "Bb":     (46, 53),   # Bb2, F3
    "Dm_end": (38, 45),   # D2, A2 fading peacefully to silence
}


def _normalize_section(section):
    if not section:
        return "verse1"
    s = str(section).strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    if "intro" in s:
        return "intro"
    if "outro" in s or "ending" in s:
        return "outro"
    if "coda" in s or "reprise" in s:
        return "coda"
    if "verse3" in s or "v3" in s or "act3" in s:
        return "verse3"
    if "verse2" in s or "v2" in s or "act2" in s:
        return "verse2"
    if "verse1" in s or "v1" in s or "act1" in s:
        return "verse1"
    if "verse" in s:
        return "verse1"
    return s


def _lookup_guitar_voicing(chord_name):
    if not chord_name:
        return GUITAR_VOICINGS["Dm"]
    key = str(chord_name).strip()
    if key in GUITAR_VOICINGS:
        return GUITAR_VOICINGS[key]
    # Case-insensitive / simplified fallback
    kl = key.lower()
    for k, v in GUITAR_VOICINGS.items():
        if k.lower() == kl:
            return v
    if kl.startswith("dm"):
        return GUITAR_VOICINGS["Dm"]
    if kl.startswith("am"):
        return GUITAR_VOICINGS["Am"]
    if kl.startswith("em"):
        return GUITAR_VOICINGS["Em"]
    if kl.startswith("gm"):
        return GUITAR_VOICINGS["Gm"]
    if kl.startswith("bb"):
        return GUITAR_VOICINGS["Bb"]
    if kl.startswith("c"):
        return GUITAR_VOICINGS["C"]
    if kl.startswith("f"):
        return GUITAR_VOICINGS["F"]
    if kl.startswith("g"):
        return GUITAR_VOICINGS["G"]
    if kl.startswith("a"):
        return GUITAR_VOICINGS["Am"]
    return GUITAR_VOICINGS["Dm"]


def _lookup_cello_voicing(chord_name):
    if not chord_name:
        return CELLO_VOICINGS["Dm"]
    key = str(chord_name).strip()
    if key in CELLO_VOICINGS:
        return CELLO_VOICINGS[key]
    kl = key.lower()
    for k, v in CELLO_VOICINGS.items():
        if k.lower() == kl:
            return v
    if kl.startswith("dm"):
        return CELLO_VOICINGS["Dm"]
    if kl.startswith("c"):
        return CELLO_VOICINGS["C"]
    if kl.startswith("f"):
        return CELLO_VOICINGS["F"]
    if kl.startswith("g"):
        return CELLO_VOICINGS["G"]
    if kl.startswith("a"):
        return CELLO_VOICINGS["Am"]
    return CELLO_VOICINGS["Dm"]


# ---------------------------------------------------------------------------
# Pure-Python Biquad & Filter Primitives (RBJ Cookbook, Transposed Direct Form II)
# ---------------------------------------------------------------------------

def _biquad_peaking(fc, q, gain_db, sr):
    fc = max(20.0, min(fc, 0.45 * sr))
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    cw = math.cos(w0)
    sw = math.sin(w0)
    alpha = sw / (2.0 * max(q, 0.1))
    b0 = 1.0 + alpha * a
    b1 = -2.0 * cw
    b2 = 1.0 - alpha * a
    a0 = 1.0 + alpha / a
    a1 = -2.0 * cw
    a2 = 1.0 - alpha / a
    inv = 1.0 / a0
    return (b0 * inv, b1 * inv, b2 * inv, a1 * inv, a2 * inv)


def _biquad_lowpass(fc, q, sr):
    fc = max(20.0, min(fc, 0.45 * sr))
    w0 = 2.0 * math.pi * fc / sr
    cw = math.cos(w0)
    sw = math.sin(w0)
    alpha = sw / (2.0 * max(q, 0.1))
    b0 = (1.0 - cw) * 0.5
    b1 = 1.0 - cw
    b2 = b0
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    inv = 1.0 / a0
    return (b0 * inv, b1 * inv, b2 * inv, a1 * inv, a2 * inv)


def _biquad_highpass(fc, q, sr):
    fc = max(15.0, min(fc, 0.45 * sr))
    w0 = 2.0 * math.pi * fc / sr
    cw = math.cos(w0)
    sw = math.sin(w0)
    alpha = sw / (2.0 * max(q, 0.1))
    b0 = (1.0 + cw) * 0.5
    b1 = -(1.0 + cw)
    b2 = b0
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    inv = 1.0 / a0
    return (b0 * inv, b1 * inv, b2 * inv, a1 * inv, a2 * inv)


def _biquad_highshelf(fc, gain_db, sr):
    fc = max(20.0, min(fc, 0.45 * sr))
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    cw = math.cos(w0)
    sw = math.sin(w0)
    alpha = sw * 0.7071067811865476  # shelf slope S = 1.0
    two_sq_a = 2.0 * math.sqrt(a) * alpha
    b0 = a * ((a + 1.0) + (a - 1.0) * cw + two_sq_a)
    b1 = -2.0 * a * ((a - 1.0) + (a + 1.0) * cw)
    b2 = a * ((a + 1.0) + (a - 1.0) * cw - two_sq_a)
    a0 = (a + 1.0) - (a - 1.0) * cw + two_sq_a
    a1 = 2.0 * ((a - 1.0) - (a + 1.0) * cw)
    a2 = (a + 1.0) - (a - 1.0) * cw - two_sq_a
    inv = 1.0 / a0
    return (b0 * inv, b1 * inv, b2 * inv, a1 * inv, a2 * inv)


def _apply_biquad_inplace(buf, coeffs):
    """Apply a single biquad filter in-place on an array/list of floats."""
    b0, b1, b2, a1, a2 = coeffs
    z1 = 0.0
    z2 = 0.0
    for i in range(len(buf)):
        x = buf[i]
        y = b0 * x + z1
        z1 = b1 * x - a1 * y + z2
        z2 = b2 * x - a2 * y
        buf[i] = y


def _apply_biquad_chain_inplace(buf, coeffs_list, start_idx=0):
    """Apply a chain of biquad filters in-place in fused chunks (1 memory pass for up to 5 stages)."""
    k = len(coeffs_list)
    if k == 0:
        return
    n = len(buf)
    if start_idx >= n:
        return

    # Process up to 5 cascaded biquads in a single loop so filter states stay in fast locals
    idx_c = 0
    while idx_c < k:
        chunk = coeffs_list[idx_c : idx_c + 5]
        m = len(chunk)
        if m == 1:
            b0, b1, b2, a1, a2 = chunk[0]
            z1 = z2 = 0.0
            for i in range(start_idx, n):
                x = buf[i]
                y = b0 * x + z1
                z1 = b1 * x - a1 * y + z2
                z2 = b2 * x - a2 * y
                buf[i] = y
        elif m == 2:
            b00, b01, b02, a01, a02 = chunk[0]
            b10, b11, b12, a11, a12 = chunk[1]
            z01 = z02 = z11 = z12 = 0.0
            for i in range(start_idx, n):
                x = buf[i]
                y = b00 * x + z01
                z01 = b01 * x - a01 * y + z02
                z02 = b02 * x - a02 * y
                y2 = b10 * y + z11
                z11 = b11 * y - a11 * y2 + z12
                z12 = b12 * y - a12 * y2
                buf[i] = y2
        elif m == 3:
            b00, b01, b02, a01, a02 = chunk[0]
            b10, b11, b12, a11, a12 = chunk[1]
            b20, b21, b22, a21, a22 = chunk[2]
            z01 = z02 = z11 = z12 = z21 = z22 = 0.0
            for i in range(start_idx, n):
                x = buf[i]
                y = b00 * x + z01
                z01 = b01 * x - a01 * y + z02
                z02 = b02 * x - a02 * y
                y2 = b10 * y + z11
                z11 = b11 * y - a11 * y2 + z12
                z12 = b12 * y - a12 * y2
                y3 = b20 * y2 + z21
                z21 = b21 * y2 - a21 * y3 + z22
                z22 = b22 * y2 - a22 * y3
                buf[i] = y3
        elif m == 4:
            b00, b01, b02, a01, a02 = chunk[0]
            b10, b11, b12, a11, a12 = chunk[1]
            b20, b21, b22, a21, a22 = chunk[2]
            b30, b31, b32, a31, a32 = chunk[3]
            z01 = z02 = z11 = z12 = z21 = z22 = z31 = z32 = 0.0
            for i in range(start_idx, n):
                x = buf[i]
                y = b00 * x + z01
                z01 = b01 * x - a01 * y + z02
                z02 = b02 * x - a02 * y
                y2 = b10 * y + z11
                z11 = b11 * y - a11 * y2 + z12
                z12 = b12 * y - a12 * y2
                y3 = b20 * y2 + z21
                z21 = b21 * y2 - a21 * y3 + z22
                z22 = b22 * y2 - a22 * y3
                y4 = b30 * y3 + z31
                z31 = b31 * y3 - a31 * y4 + z32
                z32 = b32 * y3 - a32 * y4
                buf[i] = y4
        else:
            b00, b01, b02, a01, a02 = chunk[0]
            b10, b11, b12, a11, a12 = chunk[1]
            b20, b21, b22, a21, a22 = chunk[2]
            b30, b31, b32, a31, a32 = chunk[3]
            b40, b41, b42, a41, a42 = chunk[4]
            z01 = z02 = z11 = z12 = z21 = z22 = z31 = z32 = z41 = z42 = 0.0
            for i in range(start_idx, n):
                x = buf[i]
                y = b00 * x + z01
                z01 = b01 * x - a01 * y + z02
                z02 = b02 * x - a02 * y
                y2 = b10 * y + z11
                z11 = b11 * y - a11 * y2 + z12
                z12 = b12 * y - a12 * y2
                y3 = b20 * y2 + z21
                z21 = b21 * y2 - a21 * y3 + z22
                z22 = b22 * y2 - a22 * y3
                y4 = b30 * y3 + z31
                z31 = b31 * y3 - a31 * y4 + z32
                z32 = b32 * y3 - a32 * y4
                y5 = b40 * y4 + z41
                z41 = b41 * y4 - a41 * y5 + z42
                z42 = b42 * y4 - a42 * y5
                buf[i] = y5
        idx_c += m


def _apply_onepole_hp_lp(src, hp_fc, lp_fc, sr):
    """Return a newly filtered list: 1-pole highpass -> 1-pole lowpass."""
    n = len(src)
    out = [0.0] * n
    a_hp = math.exp(-2.0 * math.pi * hp_fc / sr)
    g_hp = 0.5 * (1.0 + a_hp)
    a_lp = math.exp(-2.0 * math.pi * lp_fc / sr)
    b_lp = 1.0 - a_lp
    prev_x = 0.0
    hp_y = 0.0
    lp_y = 0.0
    for i in range(n):
        x = src[i]
        hp_y = g_hp * (x - prev_x) + a_hp * hp_y
        prev_x = x
        lp_y = b_lp * hp_y + a_lp * lp_y
        out[i] = lp_y
    return out


# ---------------------------------------------------------------------------
# Instrument 1: Extended Karplus-Strong Fingerpicked Acoustic Guitar / Lute
# ---------------------------------------------------------------------------

def _synthesize_ks_pluck(
    freq_hz,
    n_samples,
    velocity,
    sr,
    rng,
    pluck_pos=0.27,
    brightness=0.45,
    t60_scale=1.0,
    is_harmonic=False,
):
    """Synthesize one plucked acoustic guitar string using extended Karplus-Strong.

    Features:
      - Exact phase-matched 1st-order allpass fractional delay (<0.2 cents error!)
      - Warm flesh-pluck low-passed noise excitation + pluck-position comb filter
      - Frequency-dependent loop lowpass damping with calibrated T60 decay
      - Soft finger-release onset + tiny warm wooden fingertip transient (zero clicks)
      - Smooth tail damping over final 25ms
    """
    if n_samples <= 0 or freq_hz <= 25.0 or freq_hz >= 0.42 * sr:
        return []

    period = sr / freq_hz
    w0 = 2.0 * math.pi * freq_hz / sr

    # Loop 2-point weighted lowpass: y = (1-b)*x + b*x_prev
    # b in [0.475, 0.50] produces warm nylon/flesh acoustic string decay (never harpsichord/metallic).
    if is_harmonic:
        b = 0.495
    else:
        b = 0.500 - 0.032 * max(0.0, min(1.0, brightness))

    # Exact magnitude and phase delay (in samples) of loop lowpass at f0
    lp_re = (1.0 - b) + b * math.cos(w0)
    lp_im = -b * math.sin(w0)
    lp_mag = math.hypot(lp_re, lp_im)
    tau_lp = -math.atan2(lp_im, lp_re) / w0

    # Partition remaining delay into integer ring buffer N + allpass fractional delay eta in [0.5, 1.5]
    d_rem = period - tau_lp
    n_delay = int(math.floor(d_rem - 0.5))
    if n_delay < 2:
        n_delay = 2
    eta = d_rem - n_delay

    # Exact 1st-order allpass coefficient matching phase delay eta at fundamental w0:
    # H_ap(z) = (C + z^-1) / (1 + C * z^-1), |H_ap(e^jw)| == 1 for all w.
    half_w0 = 0.5 * w0
    denom = math.sin((1.0 + eta) * half_w0)
    if abs(denom) > 1e-12:
        c_ap = math.sin((1.0 - eta) * half_w0) / denom
    else:
        c_ap = (1.0 - eta) / (1.0 + eta)
    if c_ap > 0.92:
        c_ap = 0.92
    elif c_ap < -0.92:
        c_ap = -0.92

    # Calibrated acoustic string decay T60 (bass strings ring warmly, high strings sweeter)
    if is_harmonic:
        t60 = 4.6 * t60_scale
    else:
        t60 = max(2.0, min(4.5, 3.70 * ((110.0 / max(freq_hz, 55.0)) ** 0.30))) * t60_scale

    n_periods_t60 = max(12.0, t60 * freq_hz)
    g_loop = (0.001 ** (1.0 / n_periods_t60)) / max(lp_mag, 1e-6)
    if g_loop > 0.9993:
        g_loop = 0.9993

    # Build warm finger-pluck excitation buffer of length n_delay
    lag_pluck = max(1, min(n_delay - 1, int(round(pluck_pos * period))))
    raw_len = n_delay + lag_pluck + 8

    # Three-pass warm lowpass on white noise simulates soft flesh fingertip pluck over soundhole
    fc_excite = min(
        1700.0,
        max(780.0, 720.0 + 480.0 * brightness + 420.0 * min(1.0, velocity)),
    )
    a_ex = math.exp(-2.0 * math.pi * fc_excite / sr)
    b_ex = 1.0 - a_ex
    st1 = 0.0
    st2 = 0.0
    st3 = 0.0
    raw = [0.0] * raw_len
    rand_u = rng.uniform
    for i in range(raw_len):
        r = rand_u(-1.0, 1.0)
        st1 = b_ex * r + a_ex * st1
        st2 = b_ex * st1 + a_ex * st2
        st3 = b_ex * st2 + a_ex * st3
        raw[i] = st3

    # Pluck-position comb filter (models warm fingerstyle pluck around 12th fret / soundhole)
    buf = [0.0] * n_delay
    if is_harmonic:
        # 12th-fret harmonic: crystalline pure fundamental + whisper of 2nd harmonic + gentle pluck air
        two_pi_p = 2.0 * math.pi / period
        for i in range(n_delay):
            comb = raw[i + lag_pluck] - raw[i]
            buf[i] = 0.74 * math.sin(two_pi_p * i) + 0.14 * math.sin(2.0 * two_pi_p * i) + 0.14 * comb
    else:
        for i in range(n_delay):
            buf[i] = raw[i + lag_pluck] - raw[i]

    # Remove DC offset and normalize RMS cleanly
    mean_v = sum(buf) / n_delay
    sq_sum = 0.0
    for i in range(n_delay):
        v = buf[i] - mean_v
        buf[i] = v
        sq_sum += v * v
    rms = math.sqrt(sq_sum / n_delay) if sq_sum > 1e-18 else 1.0

    # Warm acoustic balance: thumb bass notes (D2-C3) bloom warmly while treble plucks stay delicate
    pitch_eq = (155.0 / max(freq_hz, 60.0)) ** 0.24
    pitch_eq = max(0.76, min(1.22, pitch_eq))
    amp = (0.36 * velocity * pitch_eq) / rms
    for i in range(n_delay):
        buf[i] *= amp

    # Core Karplus-Strong synthesis loop
    out = [0.0] * n_samples
    one_minus_b = 1.0 - b
    lp_prev = buf[n_delay - 1]
    ap_x_prev = lp_prev
    ap_y_prev = 0.0
    idx = 0

    for i in range(n_samples):
        x = buf[idx]
        out[i] = x
        lp = one_minus_b * x + b * lp_prev
        lp_prev = x
        ap = c_ap * lp + ap_x_prev - c_ap * ap_y_prev
        ap_x_prev = lp
        ap_y_prev = ap
        buf[idx] = g_loop * ap
        idx += 1
        if idx == n_delay:
            idx = 0

    # Soft flesh fingertip release onset (5.2 ms raised-cosine) + subtle wooden finger touch
    att_n = min(n_samples, max(12, int(0.0052 * sr)))
    if att_n > 1:
        pi_att = math.pi / att_n
        for i in range(att_n):
            out[i] *= 0.5 * (1.0 - math.cos(pi_att * i))

    if not is_harmonic:
        tap_n = min(n_samples, max(16, int(0.0055 * sr)))
        tap_amp = 0.016 * velocity
        tap_st = 0.0
        a_tap = math.exp(-2.0 * math.pi * 320.0 / sr)
        b_tap = 1.0 - a_tap
        for i in range(tap_n):
            env = math.sin(math.pi * i / tap_n)
            tap_st = b_tap * rand_u(-1.0, 1.0) + a_tap * tap_st
            out[i] += tap_amp * env * tap_st

    # Smooth damping release over final 26 ms so re-plucks / bar endings never click
    rel_n = min(n_samples // 3, max(16, int(0.026 * sr)))
    if rel_n > 1:
        start_rel = n_samples - rel_n
        pi_rel = math.pi / rel_n
        for k in range(rel_n):
            out[start_rel + k] *= 0.5 * (1.0 + math.cos(pi_rel * k))

    return out


def _midi_to_guitar_string(midi_note):
    """Map MIDI note to one of 6 virtual Drop-D guitar strings (0=low D2 .. 5=high E4)."""
    if midi_note <= 43:
        return 0
    if midi_note <= 48:
        return 1
    if midi_note <= 53:
        return 2
    if midi_note <= 57:
        return 3
    if midi_note <= 61:
        return 4
    return 5


def _render_guitar_track(chord_events, n_samples, sr, rng):
    """Render stereo physical-modeled fingerpicked acoustic guitar / Celtic lute."""
    left = array("d", [0.0]) * n_samples
    right = array("d", [0.0]) * n_samples
    if not chord_events:
        return left, right

    # Build note schedule: list of dicts {start_s, midi, vel, string, pluck_pos, brightness, ring_s, is_harmonic}
    notes = []
    prev_chord = None
    same_chord_count = 0

    for ev_idx, ev in enumerate(chord_events):
        t0 = float(ev.get("start", 0.0))
        t1 = float(ev.get("end", t0 + 1.5))
        bar_dur = max(0.25, t1 - t0)
        chord = str(ev.get("chord", "Dm")).strip()
        sec = _normalize_section(ev.get("section", "verse1"))
        intensity = float(ev.get("intensity", 0.55))
        intensity = max(0.1, min(1.2, intensity))
        bar_num = int(ev.get("bar", ev_idx + 1))

        if chord == prev_chord:
            same_chord_count += 1
        else:
            same_chord_count = 0
        prev_chord = chord

        bass, alt_bass, upper = _lookup_guitar_voicing(chord)
        n0, n1, n2, n3 = upper

        # Section-aware dynamic scaling & warmth (wide musical arc: hushed Coda, intimate V1, rich V3)
        if sec == "intro":
            sec_vel = 0.72
            base_bright = 0.42
        elif sec == "verse1":
            sec_vel = 0.62
            base_bright = 0.36
        elif sec == "verse2":
            sec_vel = 0.72
            base_bright = 0.42
        elif sec == "verse3":
            sec_vel = 0.84
            base_bright = 0.48
        elif sec == "coda":
            sec_vel = 0.34   # Gossamer hushed dynamics so whispered Coda floats clearly in front
            base_bright = 0.28
        else:  # outro
            sec_vel = 0.44
            base_bright = 0.28

        dyn = sec_vel * (0.76 + 0.34 * min(1.0, intensity))
        if chord.startswith("C"):
            base_bright = max(0.24, base_bright - 0.05)
        slot_dt = bar_dur / 6.0  # 6 eighth notes per 3/4 waltz bar

        is_final_bar = (ev_idx == len(chord_events) - 1) or (chord == "Dm_end")
        next_sec = _normalize_section(chord_events[ev_idx + 1].get("section", sec)) if ev_idx + 1 < len(chord_events) else sec

        # --- OUTRO / FINAL LINGERING HARMONIC CHORD ---
        if is_final_bar and (sec == "outro" or chord == "Dm_end"):
            # Lush, tender harp-rolled open D Dorian chord + shimmering 12th-fret harmonics
            roll_notes = [bass, alt_bass, n0, n1, n2, n3]
            roll_step = 0.062
            for k, m in enumerate(roll_notes):
                st = t0 + k * roll_step + rng.uniform(-0.003, 0.003)
                vel = dyn * (0.86 - 0.05 * k) * rng.uniform(0.95, 1.05)
                notes.append({
                    "start_s": max(0.0, st),
                    "midi": m,
                    "vel": vel,
                    "string": k,
                    "pluck_pos": 0.36 + rng.uniform(-0.02, 0.02),
                    "brightness": 0.30,
                    "ring_s": max(4.5, (n_samples / sr) - st),
                    "is_harmonic": False,
                })
            # Ethereal natural 12th-fret harmonics (D4 & A4) blooming softly after the roll
            harm_t1 = t0 + len(roll_notes) * roll_step + 0.44
            harm_t2 = harm_t1 + 0.56
            for ht, hm, hv, hstr in (
                (harm_t1, 62, dyn * 0.32, 4),  # D4 natural harmonic
                (harm_t2, 69, dyn * 0.26, 5),  # A4 natural harmonic
            ):
                if ht < (n_samples / sr) - 0.3:
                    notes.append({
                        "start_s": ht,
                        "midi": hm,
                        "vel": hv,
                        "string": hstr,
                        "pluck_pos": 0.50,
                        "brightness": 0.28,
                        "ring_s": max(3.8, (n_samples / sr) - ht),
                        "is_harmonic": True,
                    })
            continue

        # --- CODA & EARLIER OUTRO BARS: hushed harp-like slow rolled chords ---
        if sec in ("coda", "outro"):
            fade_mult = 0.80 if sec == "outro" else 1.0
            roll = [bass, n0, n1, n2]
            roll_step = 0.046 if sec == "coda" else 0.056
            for k, m in enumerate(roll):
                st = t0 + k * roll_step + rng.uniform(-0.003, 0.003)
                vel = dyn * fade_mult * (0.82 - 0.07 * k) * rng.uniform(0.94, 1.06)
                notes.append({
                    "start_s": max(0.0, st),
                    "midi": m,
                    "vel": vel,
                    "string": _midi_to_guitar_string(m),
                    "pluck_pos": 0.36 + rng.uniform(-0.02, 0.02),
                    "brightness": base_bright,
                    "ring_s": bar_dur * 2.0,
                    "is_harmonic": False,
                })
            # Single lingering bell tone on beat 2.5 (slot 3) leaving spacious dusk stillness
            st_hi = t0 + 3.0 * slot_dt + rng.uniform(-0.006, 0.006)
            notes.append({
                "start_s": max(0.0, st_hi),
                "midi": n3 if (bar_num % 2 == 0) else n2,
                "vel": dyn * fade_mult * 0.46 * rng.uniform(0.93, 1.07),
                "string": _midi_to_guitar_string(n3),
                "pluck_pos": 0.37,
                "brightness": base_bright - 0.03,
                "ring_s": bar_dur * 1.7,
                "is_harmonic": False,
            })
            continue

        # --- INTRO & VERSES 1-3: breathing section-varied 3/4 Celtic fingerstyle ---
        use_high_arc = (same_chord_count % 2 == 1) or (sec in ("verse2", "verse3") and intensity > 0.68)
        use_alt_bass = (same_chord_count % 2 == 1) and (sec != "intro") and (alt_bass != bass)

        b_note = alt_bass if (use_alt_bass and chord == "Dm" and intensity < 0.62) else bass

        if sec == "verse1" and same_chord_count >= 1:
            # Intimate sparse breathing waltz on sustained bars of Verse 1 (lets solo voice shine!)
            pattern = (
                (0, b_note, 0.90),
                (1, n0,     0.50),
                (2, n1,     0.58),
                (4, n2,     0.50),
            )
        elif sec == "intro" and next_sec != "intro":
            # Final Intro bar breathes open on beat 3.5 so guitar inhales right before Aero sings
            pattern = (
                (0, b_note, 0.92),
                (1, n0,     0.54),
                (2, n1,     0.62),
                (3, n2,     0.54),
                (4, n1,     0.44),
            )
        elif sec == "verse1":
            # Tender 5-note lilting folk waltz for Verse 1 chord changes
            pattern = (
                (0, b_note, 0.92),
                (1, n0,     0.52),
                (2, n1,     0.62),
                (3, n2,     0.54),
                (5, n0,     0.44),
            )
        elif use_high_arc:
            # Flowing 6-note Celtic waltz reaching gently up to top bell note n3
            pattern = (
                (0, b_note, 0.92),
                (1, n0,     0.54),
                (2, n2,     0.62),
                (3, n3,     0.54),
                (4, n2,     0.52),
                (5, n1,     0.45),
            )
        else:
            # Classic warm inward waltz lilt: Bass - Mid - High - Mid - High - Mid
            pattern = (
                (0, b_note, 0.94),
                (1, n0,     0.54),
                (2, n1,     0.64),
                (3, n2,     0.56),
                (4, n1,     0.52),
                (5, n0,     0.45),
            )

        # Warm thumb+finger dyad pinch on expressive downbeats in verse2/3
        add_pinch = (
            (sec == "verse3" and same_chord_count == 0)
            or (sec == "verse2" and intensity > 0.68 and same_chord_count == 0)
        )

        for slot, m, rel_vel in pattern:
            jitter = rng.uniform(-0.003, 0.003) if slot == 0 else rng.uniform(-0.007, 0.007)
            st = max(0.0, t0 + slot * slot_dt + jitter)
            vel = dyn * rel_vel * rng.uniform(0.93, 1.07)
            ring = bar_dur * (1.85 if slot == 0 else 1.35)
            notes.append({
                "start_s": st,
                "midi": m,
                "vel": vel,
                "string": _midi_to_guitar_string(m),
                "pluck_pos": 0.35 + rng.uniform(-0.025, 0.03),
                "brightness": base_bright + (0.04 if slot == 0 else -0.02) + rng.uniform(-0.025, 0.025),
                "ring_s": ring,
                "is_harmonic": False,
            })

        if add_pinch:
            st_p = max(0.0, t0 + 0.011 + rng.uniform(-0.003, 0.003))
            notes.append({
                "start_s": st_p,
                "midi": n2,
                "vel": dyn * 0.44 * rng.uniform(0.94, 1.06),
                "string": _midi_to_guitar_string(n2),
                "pluck_pos": 0.36,
                "brightness": base_bright - 0.04,
                "ring_s": bar_dur * 1.45,
                "is_harmonic": False,
            })

    # Natural 6-string polyphony: trim a string cleanly (with 20ms damping overlap) only
    # when that SAME virtual string is re-plucked, letting all other strings ring sympathetically.
    by_string = [[] for _ in range(6)]
    for note in notes:
        s_idx = max(0, min(5, note["string"]))
        by_string[s_idx].append(note)

    for s_notes in by_string:
        s_notes.sort(key=lambda d: d["start_s"])
        for i in range(len(s_notes) - 1):
            cur = s_notes[i]
            nxt = s_notes[i + 1]
            max_dur = (nxt["start_s"] - cur["start_s"]) + 0.022
            if max_dur < 0.04:
                max_dur = 0.04
            if cur["ring_s"] > max_dur:
                cur["ring_s"] = max_dur

    # Constant-power natural stereo panning across the 6 strings (-0.26 left to +0.28 right)
    # Gentle acoustic stereo width leaves dead-center wide open for Aero's singing voice.
    string_pans = (-0.25, -0.15, -0.05, 0.08, 0.19, 0.28)

    for s_idx, s_notes in enumerate(by_string):
        pan = string_pans[s_idx]
        angle = (pan + 1.0) * 0.25 * math.pi
        g_l = math.cos(angle)
        g_r = math.sin(angle)

        for note in s_notes:
            start_i = int(round(note["start_s"] * sr))
            if start_i >= n_samples:
                continue
            dur_n = int(round(note["ring_s"] * sr))
            if start_i + dur_n > n_samples:
                dur_n = n_samples - start_i
            if dur_n < 16:
                continue

            freq = midi_to_hz(note["midi"])
            sig = _synthesize_ks_pluck(
                freq_hz=freq,
                n_samples=dur_n,
                velocity=note["vel"],
                sr=sr,
                rng=rng,
                pluck_pos=note["pluck_pos"],
                brightness=note["brightness"],
                t60_scale=1.18 if note["ring_s"] > 3.5 else 1.0,
                is_harmonic=note["is_harmonic"],
            )
            if not sig:
                continue
            for k in range(len(sig)):
                val = sig[k]
                idx = start_i + k
                left[idx] += val * g_l
                right[idx] += val * g_r

    # Wooden acoustic guitar body resonator (Helmholtz ~105 Hz, top plate ~205 Hz, warm body ~390 Hz)
    # + clean sub-rumble highpass (62 Hz) + warm acoustic wood-string lowpass (~3650 Hz).
    guitar_body_eq = [
        _biquad_highpass(62.0, 0.707, sr),
        _biquad_peaking(105.0, 2.1, 2.6, sr),    # Warm Helmholtz air cavity bloom
        _biquad_peaking(205.0, 2.4, 2.0, sr),    # Spruce top-plate resonance
        _biquad_peaking(390.0, 1.8, 1.1, sr),    # Wooden body richness
        _biquad_lowpass(3650.0, 0.65, sr),       # Crisp warm acoustic wood-string definition
    ]
    _apply_biquad_chain_inplace(left, guitar_body_eq)
    _apply_biquad_chain_inplace(right, guitar_body_eq)

    return left, right


# ---------------------------------------------------------------------------
# Instrument 2: Warm Bowed Cello / Chamber Strings Pad
# ---------------------------------------------------------------------------

def _build_cello_wavetables(table_size=2048):
    """Precompute two alias-free warm wooden bowed-cello wavetables (pp sul-tasto & mf lyrical).

    Uses 12 smooth bowed-string partials (k^-1.88 soft, k^-1.56 rich) with raised-cosine
    upper smoothing so warm mid-wood harmonics sing clearly in Verses 2-3 with ZERO sawtooth buzz.
    """
    two_pi = 2.0 * math.pi
    tab_soft = [0.0] * (table_size + 1)
    tab_rich = [0.0] * (table_size + 1)

    phases = (0.0, 0.0, 0.21, -0.28, 0.44, -0.37, 0.55, -0.22, 0.34, -0.46, 0.25, -0.31, 0.19)

    for i in range(table_size):
        th = two_pi * i / table_size
        s_soft = 0.0
        s_rich = 0.0
        for k in range(1, 13):
            bow_notch = 0.65 + 0.35 * abs(math.sin(k * math.pi * 0.125))
            win = 0.5 * (1.0 + math.cos(math.pi * (k - 1) / 12.0))
            s_val = math.sin(k * th + phases[k])
            if k <= 9:
                s_soft += (bow_notch * win / (k ** 1.88)) * s_val
            s_rich += (bow_notch * win / (k ** 1.56)) * s_val
        tab_soft[i] = s_soft
        tab_rich[i] = s_rich

    for tab in (tab_soft, tab_rich):
        rms = math.sqrt(sum(v * v for v in tab[:table_size]) / table_size)
        inv = 1.0 / max(rms, 1e-9)
        for i in range(table_size):
            tab[i] *= inv
        tab[table_size] = tab[0]

    return tab_soft, tab_rich


def _render_cello_track(chord_events, n_samples, sr, rng):
    """Render warm bowed cello / chamber strings entering on verse2, swelling on verse3,
    softening to a tender breathy drone on coda, and fading to silence on outro."""
    left = array("d", [0.0]) * n_samples
    right = array("d", [0.0]) * n_samples
    if not chord_events:
        return left, right

    block = 32
    n_blocks = (n_samples + block - 1) // block
    block_dt = block / sr

    events_norm = []
    for ev in chord_events:
        t0 = float(ev.get("start", 0.0))
        t1 = float(ev.get("end", t0 + 1.5))
        sec = _normalize_section(ev.get("section", "verse1"))
        chord = str(ev.get("chord", "Dm")).strip()
        intensity = max(0.1, min(1.2, float(ev.get("intensity", 0.55))))
        c_bass, c_harm = _lookup_cello_voicing(chord)
        events_norm.append((t0, t1, sec, chord, intensity, midi_to_hz(c_bass), midi_to_hz(c_harm)))

    has_cello = any(e[2] in ("verse2", "verse3", "coda") for e in events_norm)
    if not has_cello:
        return left, right

    tab_size = 2048
    tab_soft, tab_rich = _build_cello_wavetables(tab_size)

    # Voice 1 (primary solo cello bass + stereo detuned chamber pair +/-3.4 cents)
    # Voice 2 (warm upper fifth/third harmony entering tenderly in verse3 swell)
    ph1a = rng.uniform(0.0, tab_size)
    ph1b = rng.uniform(0.0, tab_size)
    ph1c = rng.uniform(0.0, tab_size)
    ph2a = rng.uniform(0.0, tab_size)
    ph2b = rng.uniform(0.0, tab_size)
    vib_ph1 = rng.uniform(0.0, 2.0 * math.pi)
    vib_ph2 = rng.uniform(0.0, 2.0 * math.pi)
    swell_ph = rng.uniform(0.0, 2.0 * math.pi)

    cur_f1 = events_norm[0][5]
    cur_f2 = events_norm[0][6]
    cur_g1 = 0.0
    cur_g2 = 0.0
    cur_bright = 0.18
    cur_rosin = 0.0

    # Subtle filtered rosin bow-hair air texture (bandpassed ~500-1200 Hz)
    rosin_lp1 = 0.0
    rosin_lp2 = 0.0
    rosin_hp = 0.0
    rosin_prev = 0.0
    a_r_lp = math.exp(-2.0 * math.pi * 1150.0 / sr)
    b_r_lp = 1.0 - a_r_lp
    a_r_hp = math.exp(-2.0 * math.pi * 500.0 / sr)
    g_r_hp = 0.5 * (1.0 + a_r_hp)

    ev_idx = 0
    n_ev = len(events_norm)
    last_ev_idx = -1
    note_age = 0.0
    prev_f1_target = cur_f1
    bow_dip = 1.0
    first_active_idx = n_samples

    alpha_pitch = 1.0 - math.exp(-block_dt / 0.028)    # ~55ms natural legato shift (never swoopy)
    alpha_gain_up = 1.0 - math.exp(-block_dt / 0.42)   # slow organic bow swell-in
    alpha_gain_dn = 1.0 - math.exp(-block_dt / 0.48)   # tender slow bow release
    alpha_dip_rec = 1.0 - math.exp(-block_dt / 0.11)   # smooth bow-change dip recovery

    det_up = 2.0 ** (3.4 / 1200.0)
    det_dn = 2.0 ** (-3.4 / 1200.0)
    inv_sr_tab = tab_size / sr
    rand_u = rng.uniform

    g2_l, g2_r = 0.56, 0.82

    for b_idx in range(n_blocks):
        s0 = b_idx * block
        s1 = s0 + block
        if s1 > n_samples:
            s1 = n_samples
        t_mid = (s0 + 0.5 * (s1 - s0)) / sr

        while ev_idx + 1 < n_ev and t_mid >= events_norm[ev_idx][1]:
            ev_idx += 1

        et0, et1, sec, chord, intensity, f1_tgt, f2_tgt = events_norm[ev_idx]
        if t_mid < et0:
            tgt_g1 = 0.0
            tgt_g2 = 0.0
            tgt_bright = 0.12
            tgt_rosin = 0.0
        else:
            ev_dur = max(0.2, et1 - et0)
            ev_pos = max(0.0, min(1.0, (t_mid - et0) / ev_dur))

            if ev_idx != last_ev_idx:
                if cur_g1 > 0.015:
                    if abs(f1_tgt - prev_f1_target) > 0.5:
                        # Distinct natural bow-direction articulation on chord changes
                        bow_dip = 0.72 if sec == "verse3" else 0.78
                        note_age = 0.0
                    elif sec == "verse3":
                        # Subtle live re-bow breath on sustained bars so V3 cello never feels pad-like
                        bow_dip = 0.85
                prev_f1_target = f1_tgt
                last_ev_idx = ev_idx

            if sec in ("intro", "verse1"):
                tgt_g1 = 0.0
                tgt_g2 = 0.0
                tgt_bright = 0.14
                tgt_rosin = 0.0
            elif sec == "verse2":
                # Enters gently & unmistakably on verse2 with warm bar-level bow phrasing
                bar_arc = 0.86 + 0.24 * math.sin(math.pi * ev_pos)
                tgt_g1 = 0.18 * (0.76 + 0.34 * min(1.0, intensity)) * bar_arc
                tgt_g2 = 0.062 * (0.65 + 0.45 * min(1.0, intensity)) * bar_arc
                tgt_bright = 0.28 + 0.20 * min(1.0, intensity)
                tgt_rosin = 0.015
            elif sec == "verse3":
                # Expressive live chamber cello swell on verse3 with breathing bow articulation
                swell_i = max(0.0, min(1.20, intensity))
                bar_arc = 0.82 + 0.32 * math.sin(math.pi * ev_pos)
                tgt_g1 = 0.25 * (0.78 + 0.38 * swell_i) * bar_arc
                tgt_g2 = 0.128 * (0.68 + 0.46 * swell_i) * bar_arc
                tgt_bright = 0.40 + 0.32 * min(1.0, swell_i)
                tgt_rosin = 0.020
            elif sec == "coda":
                # Gossamer breathy low cello whisper (-3.5 dB) cradling Aero's hushed reprise
                tgt_g1 = 0.075 * (0.90 - 0.24 * ev_pos)
                tgt_g2 = 0.022 * (0.85 - 0.25 * ev_pos)
                tgt_bright = 0.12
                tgt_rosin = 0.018
            else:  # outro: fade gracefully to silence
                fade = max(0.0, 1.0 - ev_pos * 1.55) if chord != "Dm_end" else 0.0
                tgt_g1 = 0.052 * fade
                tgt_g2 = 0.0
                tgt_bright = 0.10
                tgt_rosin = 0.010 * fade

        g1_a = alpha_gain_up if tgt_g1 > cur_g1 else alpha_gain_dn
        g2_a = alpha_gain_up if tgt_g2 > cur_g2 else alpha_gain_dn
        prev_g1 = cur_g1
        prev_g2 = cur_g2
        cur_g1 += g1_a * (tgt_g1 - cur_g1)
        cur_g2 += g2_a * (tgt_g2 - cur_g2)
        cur_bright += 0.014 * (tgt_bright - cur_bright)
        cur_rosin += 0.014 * (tgt_rosin - cur_rosin)
        bow_dip += alpha_dip_rec * (1.0 - bow_dip)

        if cur_g1 < 1e-5 and prev_g1 < 1e-5 and cur_g2 < 1e-5 and prev_g2 < 1e-5:
            cur_f1 = f1_tgt
            cur_f2 = f2_tgt
            continue

        if s0 < first_active_idx:
            first_active_idx = s0

        cur_f1 += alpha_pitch * (f1_tgt - cur_f1)
        cur_f2 += alpha_pitch * (f2_tgt - cur_f2)

        # Gentle natural cello vibrato (~4.7 Hz, delayed bloom, ~0.11 semitones)
        note_age += block_dt
        vib_env = min(1.0, max(0.0, (note_age - 0.18) / 0.50))
        vib_ph1 += 2.0 * math.pi * 4.65 * block_dt
        vib_ph2 += 2.0 * math.pi * 5.05 * block_dt
        swell_ph += 2.0 * math.pi * 0.38 * block_dt
        if vib_ph1 > 6.2831853:
            vib_ph1 -= 6.2831853
        if vib_ph2 > 6.2831853:
            vib_ph2 -= 6.2831853
        if swell_ph > 6.2831853:
            swell_ph -= 6.2831853

        v_mod1 = 1.0 + 0.0062 * vib_env * math.sin(vib_ph1)
        v_mod2 = 1.0 + 0.0072 * vib_env * math.sin(vib_ph2)
        breath_swell = 1.0 + 0.06 * math.sin(swell_ph)

        f1_inst = cur_f1 * v_mod1
        f2_inst = cur_f2 * v_mod2
        inc1a = f1_inst * inv_sr_tab
        inc1b = f1_inst * det_up * inv_sr_tab
        inc1c = f1_inst * det_dn * inv_sr_tab
        inc2a = f2_inst * inv_sr_tab
        inc2b = f2_inst * det_up * inv_sr_tab

        w_rich = cur_bright
        w_soft = 1.0 - w_rich
        blk_len = s1 - s0
        dg1 = ((cur_g1 - prev_g1) / blk_len) * bow_dip * breath_swell
        dg2 = ((cur_g2 - prev_g2) / blk_len) * bow_dip * breath_swell
        g1_cur = prev_g1 * bow_dip * breath_swell
        g2_cur = prev_g2 * bow_dip * breath_swell
        has_v2 = (g2_cur > 1e-5 or cur_g2 > 1e-5)
        rosin_lvl = cur_rosin * (g1_cur + g2_cur) * 1.6

        for i in range(s0, s1):
            g1_cur += dg1
            g2_cur += dg2

            # Voice 1: 3-strand velvety stereo chamber cello (center + L/R +/-3.4 cents)
            i1a = int(ph1a)
            fr1a = ph1a - i1a
            sa = (tab_soft[i1a] + fr1a * (tab_soft[i1a + 1] - tab_soft[i1a])) * w_soft + (
                tab_rich[i1a] + fr1a * (tab_rich[i1a + 1] - tab_rich[i1a])
            ) * w_rich

            i1b = int(ph1b)
            fr1b = ph1b - i1b
            sb = tab_soft[i1b] + fr1b * (tab_soft[i1b + 1] - tab_soft[i1b])

            i1c = int(ph1c)
            fr1c = ph1c - i1c
            sc = tab_soft[i1c] + fr1c * (tab_soft[i1c + 1] - tab_soft[i1c])

            ph1a += inc1a
            if ph1a >= tab_size:
                ph1a -= tab_size
            ph1b += inc1b
            if ph1b >= tab_size:
                ph1b -= tab_size
            ph1c += inc1c
            if ph1c >= tab_size:
                ph1c -= tab_size

            # Subtle bow-hair rosin air
            rn = rand_u(-1.0, 1.0)
            rosin_hp = g_r_hp * (rn - rosin_prev) + a_r_hp * rosin_hp
            rosin_prev = rn
            rosin_lp1 = b_r_lp * rosin_hp + a_r_lp * rosin_lp1
            rosin_lp2 = b_r_lp * rosin_lp1 + a_r_lp * rosin_lp2
            ros = rosin_lp2 * rosin_lvl

            out_l = (0.58 * sa + 0.30 * sb + 0.12 * sc) * g1_cur + ros
            out_r = (0.58 * sa + 0.12 * sb + 0.30 * sc) * g1_cur - ros * 0.85

            if has_v2:
                i2a = int(ph2a)
                fr2a = ph2a - i2a
                s2a = (tab_soft[i2a] + fr2a * (tab_soft[i2a + 1] - tab_soft[i2a])) * w_soft + (
                    tab_rich[i2a] + fr2a * (tab_rich[i2a + 1] - tab_rich[i2a])
                ) * w_rich

                i2b = int(ph2b)
                fr2b = ph2b - i2b
                s2b = tab_soft[i2b] + fr2b * (tab_soft[i2b + 1] - tab_soft[i2b])

                v2 = (0.72 * s2a + 0.28 * s2b) * g2_cur
                out_l += v2 * g2_l
                out_r += v2 * g2_r

                ph2a += inc2a
                if ph2a >= tab_size:
                    ph2a -= tab_size
                ph2b += inc2b
                if ph2b >= tab_size:
                    ph2b -= tab_size

            left[i] = out_l
            right[i] = out_r

    if first_active_idx < n_samples:
        # Resonant wooden cello body filter (~190 Hz chest/air, ~420 Hz corpus, ~780 Hz woody bridge)
        # + silky 1.9 kHz lowpass so warm bowed cello sings richly beneath Aero's vocal formants.
        cello_body_eq = [
            _biquad_highpass(48.0, 0.707, sr),
            _biquad_peaking(190.0, 2.2, 2.8, sr),
            _biquad_peaking(420.0, 2.0, 2.2, sr),
            _biquad_peaking(780.0, 1.8, 1.4, sr),
            _biquad_lowpass(1900.0, 0.65, sr),
        ]
        _apply_biquad_chain_inplace(left, cello_body_eq, start_idx=first_active_idx)
        _apply_biquad_chain_inplace(right, cello_body_eq, start_idx=first_active_idx)

    return left, right


# ---------------------------------------------------------------------------
# Public API 1: render_accompaniment
# ---------------------------------------------------------------------------

def render_accompaniment(chord_events, tempo_map, total_duration, sr=22050):
    """Render stereo acoustic accompaniment (fingerpicked guitar + warm bowed cello)
    with vocal-pocket EQ carved so Aero's voice sits crystal clear in front.

    Args:
        chord_events: list of dicts with keys bar, start, end, chord, section, intensity.
        tempo_map: optional tempo/rubato metadata (bar timing comes directly from event start/end).
        total_duration: total song length in seconds.
        sr: sample rate in Hz (default 22050).

    Returns:
        (acc_left, acc_right) tuple of array('d') of length int(total_duration * sr).
    """
    _ = tempo_map  # Bar timings use exact event["start"] / event["end"] to stay locked under rubato.
    n_samples = max(1, int(total_duration * sr))
    rng = random.Random(1670)

    g_left, g_right = _render_guitar_track(chord_events or [], n_samples, sr, rng)
    c_left, c_right = _render_cello_track(chord_events or [], n_samples, sr, rng)

    acc_left = array("d", [0.0]) * n_samples
    acc_right = array("d", [0.0]) * n_samples
    for i in range(n_samples):
        acc_left[i] = g_left[i] + c_left[i]
        acc_right[i] = g_right[i] + c_right[i]

    # Sculpted vocal pocket EQ on accompaniment:
    # - Gentle low-mid clarity scoop (-2.5 dB at 310 Hz) clears baritone chest masking
    # - Wide upper-mid pocket (-4.5 dB at 2150 Hz, Q=0.72) keeps vocal formants & consonants forward
    # - Silky top shelf trim (-2.2 dB at 4500 Hz) avoids sibilant competition
    pocket_eq = [
        _biquad_peaking(310.0, 0.85, -2.5, sr),
        _biquad_peaking(2150.0, 0.72, -4.5, sr),
        _biquad_highshelf(4500.0, -2.2, sr),
    ]
    _apply_biquad_chain_inplace(acc_left, pocket_eq)
    _apply_biquad_chain_inplace(acc_right, pocket_eq)

    return acc_left, acc_right


# ---------------------------------------------------------------------------
# Lush Warm Pure-Python Schroeder / Freeverb Stereo Hall Reverb
# ---------------------------------------------------------------------------

def _comb_accumulate(src, acc, delay, fb, damp):
    """Run one damped parallel comb filter and accumulate directly into `acc`."""
    n = len(src)
    d = max(8, int(delay))
    buf = [0.0] * d
    one_minus_damp = 1.0 - damp
    f_state = 0.0
    idx = 0
    for i in range(n):
        o = buf[idx]
        f_state = o * one_minus_damp + f_state * damp
        buf[idx] = src[i] + f_state * fb
        acc[i] += o
        idx += 1
        if idx == d:
            idx = 0


def _allpass_inplace(sig, delay, g=0.52):
    """Exact unity-magnitude Schroeder allpass diffuser in-place."""
    n = len(sig)
    d = max(4, int(delay))
    buf = [0.0] * d
    idx = 0
    for i in range(n):
        d_out = buf[idx]
        v = sig[i] + g * d_out
        buf[idx] = v
        sig[i] = d_out - g * v
        idx += 1
        if idx == d:
            idx = 0


def _stereo_room_reverb(
    in_left,
    in_right,
    sr=22050,
    predelay_ms=18.0,
    rt60=1.45,
    damp_fc=2400.0,
    is_mono_input=False,
):
    """Warm stone-and-timber hall reverb:
      - Warm send conditioning (140 Hz HP, 3.3 kHz LP — zero harsh sibilant ring)
      - 8 mutually-prime damped combs (28-59 ms) for mono vocal routed stereo-decorrelated,
        or 6 mutually-prime damped combs per channel (29-58 ms) for stereo accompaniment
      - 3 series exact unity-magnitude Schroeder allpass diffusers per channel
      - Dark warm stone/timber damping (damp_fc ~2250-2450 Hz) -> ZERO metallic ringing!
      - Fused stereo wooden-room early reflections + stereo cross-glue.

    Returns pure wet stereo buffers (wet_l, wet_r).
    """
    n = len(in_left)
    if n == 0:
        return [], []

    # Warm send conditioning: HP 140 Hz (clear bass) + LP 3300 Hz (silky non-sibilant hall)
    send_l = _apply_onepole_hp_lp(in_left, 140.0, 3300.0, sr)
    send_r = send_l if is_mono_input else _apply_onepole_hp_lp(in_right, 140.0, 3300.0, sr)

    pd = max(0, int(round(predelay_ms * 0.001 * sr)))
    if pd > 0 and pd < n:
        pd_l = [0.0] * pd + send_l[: n - pd]
        pd_r = pd_l if is_mono_input else ([0.0] * pd + send_r[: n - pd])
    else:
        pd_l = send_l
        pd_r = send_r

    scale = sr / 22050.0
    damp = math.exp(-2.0 * math.pi * min(damp_fc, 0.42 * sr) / sr)

    tank_l = [0.0] * n
    tank_r = [0.0] * n

    if is_mono_input:
        # 8 wide mutually-prime combs (28.0 ms to 56.9 ms): odd -> L, even -> R, then 35% cross-blend
        # so both ears hear all 8 smooth dense prime modes with true stereo envelopment!
        combs_odd = [max(16, int(round(c * scale))) for c in (617, 769, 953, 1181)]
        combs_evn = [max(16, int(round(c * scale))) for c in (683, 853, 1061, 1259)]
        for d in combs_odd:
            fb = min(0.94, 10.0 ** (-3.0 * d / max(0.2 * sr, rt60 * sr)))
            _comb_accumulate(pd_l, tank_l, d, fb, damp)
        for d in combs_evn:
            fb = min(0.94, 10.0 ** (-3.0 * d / max(0.2 * sr, rt60 * sr)))
            _comb_accumulate(pd_l, tank_r, d, fb, damp)
        # Cross-blend odd/even comb banks before allpass diffusion so each channel gets all 8 modes
        for i in range(n):
            tl = tank_l[i]
            tr = tank_r[i]
            tank_l[i] = 0.65 * tl + 0.35 * tr
            tank_r[i] = 0.65 * tr + 0.35 * tl
        tk_g = 0.80 / 4.0
    else:
        # 6 wide mutually-prime combs per channel (29.1 ms to 57.1 ms)
        combs_l = [max(16, int(round(c * scale))) for c in (641, 733, 839, 953, 1087, 1237)]
        combs_r = [max(16, int(round(c * scale))) for c in (659, 751, 863, 977, 1109, 1259)]
        for d in combs_l:
            fb = min(0.94, 10.0 ** (-3.0 * d / max(0.2 * sr, rt60 * sr)))
            _comb_accumulate(pd_l, tank_l, d, fb, damp)
        for d in combs_r:
            fb = min(0.94, 10.0 ** (-3.0 * d / max(0.2 * sr, rt60 * sr)))
            _comb_accumulate(pd_r, tank_r, d, fb, damp)
        tk_g = 0.80 / 6.0

    # 3 series exact Schroeder allpass diffusers per channel for silky, flutter-free room density
    ap_l = [max(8, int(round(a * scale))) for a in (113, 179, 277)]
    ap_r = [max(8, int(round(a * scale))) for a in (127, 193, 293)]
    for d in ap_l:
        _allpass_inplace(tank_l, d, 0.52)
    for d in ap_r:
        _allpass_inplace(tank_r, d, 0.52)

    # Fused single-pass stereo early reflections (4 taps per channel, 11-37 ms) + tank blend + cross-glue
    dl1 = int(round(0.0113 * sr))
    dl2 = int(round(0.0187 * sr))
    dl3 = int(round(0.0263 * sr))
    dl4 = int(round(0.0353 * sr))
    dr1 = int(round(0.0127 * sr))
    dr2 = int(round(0.0203 * sr))
    dr3 = int(round(0.0281 * sr))
    dr4 = int(round(0.0371 * sr))
    max_d = max(dl4, dr4)

    wet_l = [0.0] * n
    wet_r = [0.0] * n

    lim_head = min(n, max_d)
    for i in range(lim_head):
        el = 0.0
        if i >= dl1:
            el += 0.24 * send_l[i - dl1]
        if i >= dl2:
            el -= 0.18 * send_l[i - dl2]
        if i >= dl3:
            el += 0.14 * send_l[i - dl3]
        if i >= dl4:
            el -= 0.09 * send_l[i - dl4]
        er = 0.0
        if i >= dr1:
            er += 0.23 * send_r[i - dr1]
        if i >= dr2:
            er -= 0.17 * send_r[i - dr2]
        if i >= dr3:
            er += 0.13 * send_r[i - dr3]
        if i >= dr4:
            er -= 0.09 * send_r[i - dr4]
        wl = tk_g * tank_l[i] + 0.24 * el
        wr = tk_g * tank_r[i] + 0.24 * er
        wet_l[i] = 0.80 * wl + 0.20 * wr
        wet_r[i] = 0.80 * wr + 0.20 * wl

    for i in range(lim_head, n):
        el = (
            0.24 * send_l[i - dl1]
            - 0.18 * send_l[i - dl2]
            + 0.14 * send_l[i - dl3]
            - 0.09 * send_l[i - dl4]
        )
        er = (
            0.23 * send_r[i - dr1]
            - 0.17 * send_r[i - dr2]
            + 0.13 * send_r[i - dr3]
            - 0.09 * send_r[i - dr4]
        )
        wl = tk_g * tank_l[i] + 0.24 * el
        wr = tk_g * tank_r[i] + 0.24 * er
        wet_l[i] = 0.80 * wl + 0.20 * wr
        wet_r[i] = 0.80 * wr + 0.20 * wl

    return wet_l, wet_r


# ---------------------------------------------------------------------------
# Mastering Utilities (Active RMS, Transparent Ducking, Analog Soft-Limiter)
# ---------------------------------------------------------------------------

def _measure_active_rms(sig, sr, stereo_second=None):
    """Measure active-frame RMS (frames above -36 dB of peak) so long intros/silences
    do not artificially skew vocal-vs-accompaniment loudness balance."""
    n = len(sig)
    if n == 0:
        return 0.0
    frame = max(64, int(0.05 * sr))  # 50 ms analysis frames
    frame_rms = []
    if stereo_second is None:
        for i in range(0, n, frame):
            end = min(n, i + frame)
            s = 0.0
            for k in range(i, end):
                v = sig[k]
                s += v * v
            frame_rms.append(math.sqrt(s / (end - i)))
    else:
        for i in range(0, n, frame):
            end = min(n, i + frame)
            s = 0.0
            for k in range(i, end):
                vl = sig[k]
                vr = stereo_second[k]
                s += 0.5 * (vl * vl + vr * vr)
            frame_rms.append(math.sqrt(s / (end - i)))

    peak_f = max(frame_rms) if frame_rms else 0.0
    if peak_f < 1e-7:
        return 0.0
    thresh = peak_f * 0.03  # ~ -30 dB below loudest frame
    active = [r * r for r in frame_rms if r >= thresh]
    if not active:
        return peak_f
    return math.sqrt(sum(active) / len(active))


def _compute_gentle_vocal_duck_curve(vocal_dry, vocal_ref_rms, sr, max_duck_db=-1.5):
    """Compute an ultra-transparent, slow-attack/slow-release ducking gain envelope
    so guitar/cello bloom during intro/breaths/outro and nestle gently beneath singing."""
    n = len(vocal_dry)
    if vocal_ref_rms < 1e-6 or n == 0:
        return None
    block = 64  # ~2.9 ms control blocks
    n_blk = (n + block - 1) // block
    dt = block / sr
    a_att = 1.0 - math.exp(-dt / 0.065)   # 65 ms smooth attack
    a_rel = 1.0 - math.exp(-dt / 0.380)   # 380 ms velvety release
    min_gain = 10.0 ** (max_duck_db / 20.0)  # ~0.84 for -1.5 dB
    thresh = vocal_ref_rms * 0.16
    span = max(1e-6, vocal_ref_rms * 0.85)

    env = 0.0
    gains = [1.0] * n_blk
    for b in range(n_blk):
        s0 = b * block
        s1 = min(n, s0 + block)
        sq = 0.0
        for k in range(s0, s1):
            v = vocal_dry[k]
            sq += v * v
        rms = math.sqrt(sq / (s1 - s0))
        a = a_att if rms > env else a_rel
        env += a * (rms - env)
        if env > thresh:
            depth = min(1.0, (env - thresh) / span)
            gains[b] = 1.0 - depth * (1.0 - min_gain)
        else:
            gains[b] = 1.0
    return gains, block


def _soft_limit_and_normalize_stereo(left, right, target_peak=0.90, knee=0.76):
    """Apply transparent knee soft-clipping (pure linear below knee, C1 tanh glue above)
    and normalize stereo pair jointly to exact target_peak (-0.92 dBFS)."""
    n = len(left)
    if n == 0:
        return array("d"), array("d")

    # Sanitize NaN/Inf and remove tiny DC offset
    mean_l = 0.0
    mean_r = 0.0
    for i in range(n):
        vl = left[i]
        vr = right[i]
        if not math.isfinite(vl):
            vl = 0.0
            left[i] = 0.0
        if not math.isfinite(vr):
            vr = 0.0
            right[i] = 0.0
        mean_l += vl
        mean_r += vr
    mean_l /= n
    mean_r /= n

    raw_peak = 0.0
    for i in range(n):
        vl = left[i] - mean_l
        vr = right[i] - mean_r
        left[i] = vl
        right[i] = vr
        al = abs(vl)
        ar = abs(vr)
        if al > raw_peak:
            raw_peak = al
        if ar > raw_peak:
            raw_peak = ar

    if raw_peak < 1e-9:
        return array("d", [0.0]) * n, array("d", [0.0]) * n

    # Pre-scale gently so only extreme climax peaks kiss the analog knee (preserves hushed Coda dynamics!)
    pre_scale = 1.03 / raw_peak
    headroom = 1.0 - knee
    inv_hr = 1.0 / headroom

    out_l = array("d", [0.0]) * n
    out_r = array("d", [0.0]) * n
    post_peak = 0.0
    tanh_fn = math.tanh

    for i in range(n):
        xl = left[i] * pre_scale
        axl = abs(xl)
        if axl > knee:
            yl = (knee + headroom * tanh_fn((axl - knee) * inv_hr)) * (1.0 if xl >= 0.0 else -1.0)
        else:
            yl = xl

        xr = right[i] * pre_scale
        axr = abs(xr)
        if axr > knee:
            yr = (knee + headroom * tanh_fn((axr - knee) * inv_hr)) * (1.0 if xr >= 0.0 else -1.0)
        else:
            yr = xr

        out_l[i] = yl
        out_r[i] = yr
        ayl = abs(yl)
        ayr = abs(yr)
        if ayl > post_peak:
            post_peak = ayl
        if ayr > post_peak:
            post_peak = ayr

    final_scale = target_peak / max(post_peak, 1e-9)
    for i in range(n):
        vl = out_l[i] * final_scale
        vr = out_r[i] * final_scale
        if vl > 0.98:
            vl = 0.98
        elif vl < -0.98:
            vl = -0.98
        if vr > 0.98:
            vr = 0.98
        elif vr < -0.98:
            vr = -0.98
        out_l[i] = vl
        out_r[i] = vr

    return out_l, out_r


def _soft_limit_and_normalize_mono(sig, target_peak=0.88, knee=0.78):
    n = len(sig)
    if n == 0:
        return array("d")
    mean_v = 0.0
    for i in range(n):
        v = sig[i]
        if not math.isfinite(v):
            v = 0.0
            sig[i] = 0.0
        mean_v += v
    mean_v /= n

    raw_peak = 0.0
    for i in range(n):
        v = sig[i] - mean_v
        sig[i] = v
        av = abs(v)
        if av > raw_peak:
            raw_peak = av

    if raw_peak < 1e-9:
        return array("d", [0.0]) * n

    pre_scale = 1.04 / raw_peak
    headroom = 1.0 - knee
    inv_hr = 1.0 / headroom
    out = array("d", [0.0]) * n
    post_peak = 0.0
    tanh_fn = math.tanh

    for i in range(n):
        x = sig[i] * pre_scale
        ax = abs(x)
        if ax > knee:
            y = (knee + headroom * tanh_fn((ax - knee) * inv_hr)) * (1.0 if x >= 0.0 else -1.0)
        else:
            y = x
        out[i] = y
        ay = abs(y)
        if ay > post_peak:
            post_peak = ay

    final_scale = target_peak / max(post_peak, 1e-9)
    for i in range(n):
        v = out[i] * final_scale
        if v > 0.98:
            v = 0.98
        elif v < -0.98:
            v = -0.98
        out[i] = v
    return out


# ---------------------------------------------------------------------------
# Public API 2: mix_and_master
# ---------------------------------------------------------------------------

def mix_and_master(vocal_mono, acc_left, acc_right, sr=22050):
    """Mix Aero's vocal dead-center above stereo acoustic accompaniment in a cohesive
    warm stone/wood hall reverb, with analog glue soft-limiting to -0.9 dBFS (peak ~0.90).

    Returns:
        (mix_left, mix_right, vocal_wet_mono) as array('d') buffers.
    """
    n_v = len(vocal_mono) if vocal_mono is not None else 0
    n_al = len(acc_left) if acc_left is not None else 0
    n_ar = len(acc_right) if acc_right is not None else 0
    n = max(n_v, n_al, n_ar)
    if n == 0:
        return array("d"), array("d"), array("d")

    # Pad/copy cleanly into uniform-length working buffers & sanitize non-finite values
    v_buf = [0.0] * n
    al_buf = [0.0] * n
    ar_buf = [0.0] * n
    if vocal_mono is not None:
        for i in range(n_v):
            x = float(vocal_mono[i])
            v_buf[i] = x if math.isfinite(x) else 0.0
    if acc_left is not None:
        for i in range(n_al):
            x = float(acc_left[i])
            al_buf[i] = x if math.isfinite(x) else 0.0
    if acc_right is not None:
        for i in range(n_ar):
            x = float(acc_right[i])
            ar_buf[i] = x if math.isfinite(x) else 0.0

    # Gentle sub-rumble highpass on vocal (68 Hz) removes DC/plosive thump cleanly
    if n_v > 0:
        _apply_biquad_inplace(v_buf, _biquad_highpass(68.0, 0.707, sr))

    # Active-RMS loudness staging: place vocal ~+5.5 dB above accompaniment (voice clearly forward!)
    v_rms = _measure_active_rms(v_buf, sr)
    a_rms = _measure_active_rms(al_buf, sr, stereo_second=ar_buf)

    vocal_ref_rms = 0.20
    acc_target_ratio = 10.0 ** (-5.5 / 20.0)  # -5.5 dB below active vocal (~0.531)

    if v_rms > 1e-6:
        v_gain = vocal_ref_rms / v_rms
        for i in range(n):
            v_buf[i] *= v_gain
        if a_rms > 1e-6:
            a_gain = (vocal_ref_rms * acc_target_ratio) / a_rms
            for i in range(n):
                al_buf[i] *= a_gain
                ar_buf[i] *= a_gain
    elif a_rms > 1e-6:
        # Instrumental-only fallback (e.g., solo accompaniment test)
        a_gain = 0.16 / a_rms
        for i in range(n):
            al_buf[i] *= a_gain
            ar_buf[i] *= a_gain

    # Intimate warm timber/stone hall reverb on vocal (~18% wet, 18ms pre-delay, 2.45 kHz damping)
    if v_rms > 1e-6:
        v_rev_l, v_rev_r = _stereo_room_reverb(
            v_buf,
            v_buf,
            sr=sr,
            predelay_ms=18.0,
            rt60=1.42,
            damp_fc=2450.0,
            is_mono_input=True,
        )
    else:
        v_rev_l = [0.0] * n
        v_rev_r = [0.0] * n

    # Cohesive deeper hall reverb on accompaniment (~26% wet, 11ms pre-delay, 2.25 kHz warm damping)
    # so guitar & cello sit naturally behind Aero inside the same stone-and-timber room.
    if a_rms > 1e-6:
        a_rev_l, a_rev_r = _stereo_room_reverb(
            al_buf,
            ar_buf,
            sr=sr,
            predelay_ms=11.0,
            rt60=1.55,
            damp_fc=2250.0,
            is_mono_input=False,
        )
    else:
        a_rev_l = [0.0] * n
        a_rev_r = [0.0] * n

    # Transparent vocal-presence ducking on accompaniment (max -2.2 dB while singing, blooms in breaths/intro/outro)
    duck_info = _compute_gentle_vocal_duck_curve(v_buf, vocal_ref_rms, sr, max_duck_db=-2.2) if (v_rms > 1e-6 and a_rms > 1e-6) else None

    # Combine master stereo bus (with subtle shared-room ambient glue) & clean vocal_wet_mono bus
    v_wet_amt = 0.185
    a_wet_amt = 0.265
    mix_l_raw = [0.0] * n
    mix_r_raw = [0.0] * n
    vocal_wet_raw = [0.0] * n

    if duck_info is not None:
        duck_gains, duck_blk = duck_info
        n_dblk = len(duck_gains)
        for i in range(n):
            vb = v_buf[i]
            vrl = v_rev_l[i]
            vrr = v_rev_r[i]
            vocal_wet_raw[i] = vb + v_wet_amt * 0.5 * (vrl + vrr)

            b_idx = i // duck_blk
            if b_idx >= n_dblk:
                b_idx = n_dblk - 1
            dg = duck_gains[b_idx]
            # Subtle shared-hall glue blends wet tails organically without blurring dry intimacy
            room_l = v_wet_amt * vrl + dg * a_wet_amt * a_rev_l[i]
            room_r = v_wet_amt * vrr + dg * a_wet_amt * a_rev_r[i]
            mix_l_raw[i] = vb + dg * al_buf[i] + 0.92 * room_l + 0.08 * room_r
            mix_r_raw[i] = vb + dg * ar_buf[i] + 0.92 * room_r + 0.08 * room_l
    else:
        for i in range(n):
            vb = v_buf[i]
            vrl = v_rev_l[i]
            vrr = v_rev_r[i]
            vocal_wet_raw[i] = vb + v_wet_amt * 0.5 * (vrl + vrr)
            room_l = v_wet_amt * vrl + a_wet_amt * a_rev_l[i]
            room_r = v_wet_amt * vrr + a_wet_amt * a_rev_r[i]
            mix_l_raw[i] = vb + al_buf[i] + 0.92 * room_l + 0.08 * room_r
            mix_r_raw[i] = vb + ar_buf[i] + 0.92 * room_r + 0.08 * room_l

    # Dynamically transparent master bus soft-limiting (pure linear below 0.80 knee!)
    mix_left, mix_right = _soft_limit_and_normalize_stereo(mix_l_raw, mix_r_raw, target_peak=0.90, knee=0.80)
    vocal_wet_mono = _soft_limit_and_normalize_mono(vocal_wet_raw, target_peak=0.88, knee=0.82)

    return mix_left, mix_right, vocal_wet_mono


# ---------------------------------------------------------------------------
# Public API 3: write_wav
# ---------------------------------------------------------------------------

def write_wav(path, channels, sr=22050):
    """Write 16-bit PCM WAV from `[mono]` or `[left, right]` float buffers in [-1.0, 1.0].

    Applies subtle 16-bit TPDF dither so quiet harmonic tails fade cleanly without stepping.
    """
    if channels is None:
        raise ValueError("channels must not be None")

    # Accept single 1D buffer defensively as mono
    if len(channels) > 0 and isinstance(channels[0], (int, float)):
        ch_list = [channels]
    else:
        ch_list = list(channels)

    n_ch = len(ch_list)
    if n_ch not in (1, 2):
        raise ValueError(f"write_wav supports 1 or 2 channels, got {n_ch}")

    n_frames = min(len(c) for c in ch_list)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    rng = random.Random(2026)
    rand = rng.random
    pcm = array("h", [0]) * (n_frames * n_ch)

    if n_ch == 1:
        c0 = ch_list[0]
        for i in range(n_frames):
            x = c0[i]
            if not math.isfinite(x):
                x = 0.0
            elif x > 1.0:
                x = 1.0
            elif x < -1.0:
                x = -1.0
            # Subtle 1-LSB TPDF dither (zero-mean triangular PDF in [-1, 1])
            s = int(round(x * 32767.0 + (rand() - rand())))
            if s > 32767:
                s = 32767
            elif s < -32768:
                s = -32768
            pcm[i] = s
    else:
        c0, c1 = ch_list[0], ch_list[1]
        out_i = 0
        for i in range(n_frames):
            xl = c0[i]
            if not math.isfinite(xl):
                xl = 0.0
            elif xl > 1.0:
                xl = 1.0
            elif xl < -1.0:
                xl = -1.0
            sl = int(round(xl * 32767.0 + (rand() - rand())))
            if sl > 32767:
                sl = 32767
            elif sl < -32768:
                sl = -32768
            pcm[out_i] = sl

            xr = c1[i]
            if not math.isfinite(xr):
                xr = 0.0
            elif xr > 1.0:
                xr = 1.0
            elif xr < -1.0:
                xr = -1.0
            sr_i = int(round(xr * 32767.0 + (rand() - rand())))
            if sr_i > 32767:
                sr_i = 32767
            elif sr_i < -32768:
                sr_i = -32768
            pcm[out_i + 1] = sr_i
            out_i += 2

    if sys.byteorder != "little":
        pcm.byteswap()

    with wave.open(path, "wb") as wf:
        wf.setnchannels(n_ch)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(pcm.tobytes())


# ---------------------------------------------------------------------------
# Public API 4: extract_timeline_features
# ---------------------------------------------------------------------------

def _percentile(values, pct):
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[idx]


def _smooth_normalize_track(raw_vals, gamma=0.72, alpha_up=0.45, alpha_dn=0.22):
    """Robustly normalize into [0.0, 1.0] using 98th percentile + gentle perceptual gamma
    and asymmetric organic envelope smoothing."""
    if not raw_vals:
        return []
    nonzero = [v for v in raw_vals if v > 1e-9]
    ref = _percentile(nonzero, 98.0) if nonzero else 1.0
    if ref < 1e-9:
        return [0.0] * len(raw_vals)

    out = [0.0] * len(raw_vals)
    env = 0.0
    for i, v in enumerate(raw_vals):
        x = max(0.0, min(1.0, v / ref))
        if gamma != 1.0 and x > 0.0:
            x = x ** gamma
        a = alpha_up if x > env else alpha_dn
        env += a * (x - env)
        if env < 0.0:
            env = 0.0
        elif env > 1.0:
            env = 1.0
        out[i] = env
    return out


def _sample_track_slice(track, frame_idx, n_frames, voiced_only=False):
    """Gracefully sample an auxiliary track (sample-rate, frame-rate, arbitrary length, or None)."""
    if track is None:
        return 0.0
    m = len(track)
    if m == 0:
        return 0.0
    i0 = int((frame_idx * m) / n_frames)
    i1 = int(((frame_idx + 1) * m) / n_frames)
    if i1 <= i0:
        i1 = min(m, i0 + 1)
    if i0 >= m:
        i0 = m - 1
        i1 = m

    if voiced_only:
        total = 0.0
        cnt = 0
        span = max(1, i1 - i0)
        for k in range(i0, i1):
            val = track[k]
            if math.isfinite(val) and val > 20.0:
                total += val
                cnt += 1
        return (total / cnt) if (cnt > 0 and cnt >= 0.25 * span) else 0.0

    total = 0.0
    cnt = 0
    for k in range(i0, i1):
        val = track[k]
        if math.isfinite(val):
            total += max(0.0, float(val))
            cnt += 1
    return (total / cnt) if cnt > 0 else 0.0


def extract_timeline_features(
    vocal_mono,
    mix_left,
    mix_right,
    f0_track,
    breath_track,
    sr=22050,
    fps=30,
):
    """Compute smoothed 30fps normalized audio/vocal analysis frames for visual animation.

    Each frame dict has exact keys:
        {"t", "v_rms", "a_rms", "f0", "breath", "energy"}
    """
    n_v = len(vocal_mono) if vocal_mono is not None else 0
    n_l = len(mix_left) if mix_left is not None else 0
    n_r = len(mix_right) if mix_right is not None else 0
    n_samples = max(n_v, n_l, n_r)
    if n_samples == 0 or sr <= 0 or fps <= 0:
        return []

    duration = n_samples / float(sr)
    n_frames = max(1, int(math.ceil(duration * fps)))
    half_win = max(1, int(round(0.75 * sr / fps)))  # ~50 ms overlapping analysis window

    # Estimate linear gain of vocal_mono inside mix mid channel so a_rms isolates accompaniment + room
    k_vocal = 0.0
    if n_v > 0 and n_l > 0 and n_r > 0:
        n_common = min(n_v, n_l, n_r)
        step = max(1, n_common // 40000)  # Fast subsampled projection
        dot_mv = 0.0
        dot_vv = 0.0
        for i in range(0, n_common, step):
            v = vocal_mono[i]
            m = 0.5 * (mix_left[i] + mix_right[i])
            if math.isfinite(v) and math.isfinite(m):
                dot_mv += m * v
                dot_vv += v * v
        if dot_vv > 1e-8:
            k_vocal = max(0.0, min(2.5, dot_mv / dot_vv))

    v_raw = [0.0] * n_frames
    a_raw = [0.0] * n_frames
    e_raw = [0.0] * n_frames
    b_raw = [0.0] * n_frames
    f0_vals = [0.0] * n_frames

    for f in range(n_frames):
        t = f / float(fps)
        center = int(round(t * sr))
        i0 = max(0, center - half_win)
        i1 = min(n_samples, center + half_win)
        if i1 <= i0:
            i1 = min(n_samples, i0 + 1)
        count = max(1, i1 - i0)

        v_sq = 0.0
        a_sq = 0.0
        e_sq = 0.0
        for i in range(i0, i1):
            v = vocal_mono[i] if i < n_v else 0.0
            ml = mix_left[i] if i < n_l else 0.0
            mr = mix_right[i] if i < n_r else 0.0
            if not math.isfinite(v):
                v = 0.0
            if not math.isfinite(ml):
                ml = 0.0
            if not math.isfinite(mr):
                mr = 0.0
            v_sq += v * v
            e_sq += 0.5 * (ml * ml + mr * mr)
            rl = ml - k_vocal * v
            rr = mr - k_vocal * v
            a_sq += 0.5 * (rl * rl + rr * rr)

        v_raw[f] = math.sqrt(v_sq / count)
        a_raw[f] = math.sqrt(a_sq / count)
        e_raw[f] = math.sqrt(e_sq / count)
        f0_vals[f] = _sample_track_slice(f0_track, f, n_frames, voiced_only=True)
        b_raw[f] = _sample_track_slice(breath_track, f, n_frames, voiced_only=False)

    v_norm = _smooth_normalize_track(v_raw, gamma=0.72, alpha_up=0.48, alpha_dn=0.22)
    a_norm = _smooth_normalize_track(a_raw, gamma=0.75, alpha_up=0.35, alpha_dn=0.18)
    e_norm = _smooth_normalize_track(e_raw, gamma=0.72, alpha_up=0.42, alpha_dn=0.20)
    b_norm = _smooth_normalize_track(b_raw, gamma=0.78, alpha_up=0.50, alpha_dn=0.25)

    frames = []
    for f in range(n_frames):
        frames.append({
            "t": round(f / float(fps), 4),
            "v_rms": round(v_norm[f], 4),
            "a_rms": round(a_norm[f], 4),
            "f0": round(f0_vals[f], 2),
            "breath": round(b_norm[f], 4),
            "energy": round(e_norm[f], 4),
        })
    return frames


# ---------------------------------------------------------------------------
# Self-test & Tuning / Speed / Integrity Verification
# ---------------------------------------------------------------------------

def _measure_pitch_autocorr(sig, sr, expected_hz):
    """Estimate fundamental frequency via parabolic-interpolated autocorrelation around expected period."""
    start = int(0.08 * sr)
    win = min(len(sig) - start - 400, int(0.25 * sr))
    if win < 256:
        return expected_hz
    p_est = sr / expected_hz
    lag_min = max(12, int(math.floor(p_est * 0.90)))
    lag_max = min(win - 1, int(math.ceil(p_est * 1.10)))

    best_lag = lag_min
    best_r = -1e18
    corrs = {}
    for lag in range(lag_min, lag_max + 1):
        s = 0.0
        for i in range(start, start + win):
            s += sig[i] * sig[i + lag]
        corrs[lag] = s
        if s > best_r:
            best_r = s
            best_lag = lag

    # Parabolic interpolation around best_lag for sub-sample accuracy
    if best_lag > lag_min and best_lag < lag_max:
        y0 = corrs[best_lag - 1]
        y1 = corrs[best_lag]
        y2 = corrs[best_lag + 1]
        denom = y0 - 2.0 * y1 + y2
        delta = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-12 else 0.0
        exact_lag = best_lag + max(-0.5, min(0.5, delta))
    else:
        exact_lag = float(best_lag)
    return sr / exact_lag


def _self_test():
    import tempfile
    import time

    sr = 22050
    print("=== accompaniment.py self-test ===")

    # 1. Exact tuning verification across D Dorian acoustic guitar range
    rng = random.Random(42)
    test_notes = [
        ("D2", 38), ("A2", 45), ("C3", 48), ("D3", 50), ("F3", 53),
        ("G3", 55), ("A3", 57), ("B3", 59), ("C4", 60), ("D4", 62), ("E4", 64),
    ]
    max_cents_err = 0.0
    for name, midi in test_notes:
        f_exp = midi_to_hz(midi)
        sig = _synthesize_ks_pluck(f_exp, int(0.8 * sr), 0.8, sr, rng, pluck_pos=0.27, brightness=0.45)
        f_meas = _measure_pitch_autocorr(sig, sr, f_exp)
        cents = 1200.0 * math.log2(f_meas / f_exp)
        max_cents_err = max(max_cents_err, abs(cents))
        assert abs(cents) < 3.5, f"Tuning error too large on {name}: {cents:+.2f} cents"
    print(f"[PASS] KS fractional-delay tuning across D2..E4: max error = {max_cents_err:.2f} cents")

    # 2. Short 4-bar test (all sections/chords + synthetic vocal + reverb + WAV + features)
    bar_s = 1.56  # ~115.4 BPM in 3/4
    short_events = [
        {"bar": 1, "start": 0.0 * bar_s, "end": 1.0 * bar_s, "chord": "Dm",     "section": "intro",  "intensity": 0.45},
        {"bar": 2, "start": 1.0 * bar_s, "end": 2.0 * bar_s, "chord": "C",      "section": "verse2", "intensity": 0.65},
        {"bar": 3, "start": 2.0 * bar_s, "end": 3.0 * bar_s, "chord": "G",      "section": "verse3", "intensity": 0.90},
        {"bar": 4, "start": 3.0 * bar_s, "end": 4.5 * bar_s, "chord": "Dm_end", "section": "outro",  "intensity": 0.40},
    ]
    short_dur = 4.5 * bar_s
    t0 = time.perf_counter()
    acc_l, acc_r = render_accompaniment(short_events, None, short_dur, sr=sr)
    t_acc = time.perf_counter() - t0
    assert len(acc_l) == int(short_dur * sr) and len(acc_r) == int(short_dur * sr)

    # Create dummy vocal singing D3 -> A3 -> B3 -> D3
    n_short = len(acc_l)
    vocal = array("d", [0.0]) * n_short
    f0_trk = array("d", [0.0]) * n_short
    br_trk = array("d", [0.0]) * n_short
    for i in range(int(1.0 * bar_s * sr), int(3.0 * bar_s * sr)):
        t = i / sr
        f = 220.0 if t < 2.0 * bar_s else 246.94
        f0_trk[i] = f
        br_trk[i] = 0.25 + 0.15 * math.sin(2.0 * math.pi * 1.5 * t)
        vocal[i] = 0.22 * (math.sin(2.0 * math.pi * f * t) + 0.45 * math.sin(4.0 * math.pi * f * t))

    t1 = time.perf_counter()
    mix_l, mix_r, v_wet = mix_and_master(vocal, acc_l, acc_r, sr=sr)
    t_mix = time.perf_counter() - t1

    # Integrity checks: finite, peak ~0.90, zero clipping
    peak_l = max(abs(x) for x in mix_l)
    peak_r = max(abs(x) for x in mix_r)
    peak_m = max(peak_l, peak_r)
    rms_m = math.sqrt(sum(0.5 * (mix_l[i] ** 2 + mix_r[i] ** 2) for i in range(n_short)) / n_short)
    peak_vw = max(abs(x) for x in v_wet)
    assert all(math.isfinite(x) for x in mix_l) and all(math.isfinite(x) for x in mix_r)
    assert 0.88 <= peak_m <= 0.92, f"Unexpected master peak: {peak_m}"
    assert 0.85 <= peak_vw <= 0.91, f"Unexpected vocal_wet peak: {peak_vw}"

    # WAV write & read-back verification
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp_wav = tf.name
    try:
        write_wav(tmp_wav, [mix_l, mix_r], sr=sr)
        with wave.open(tmp_wav, "rb") as wf:
            assert wf.getnchannels() == 2
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == sr
            assert wf.getnframes() == n_short
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    # Feature extraction check
    feats = extract_timeline_features(vocal, mix_l, mix_r, f0_trk, br_trk, sr=sr, fps=30)
    assert len(feats) >= int(short_dur * 30)
    req_keys = {"t", "v_rms", "a_rms", "f0", "breath", "energy"}
    for fr in feats:
        assert set(fr.keys()) == req_keys
        for k in ("v_rms", "a_rms", "breath", "energy"):
            assert 0.0 <= fr[k] <= 1.0, f"Feature {k} out of range: {fr[k]}"

    print(
        f"[PASS] 4-bar test ({short_dur:.2f}s): acc={t_acc:.2f}s, mix={t_mix:.2f}s, "
        f"peak={peak_m:.4f}, rms={rms_m:.4f}, v_wet_peak={peak_vw:.4f}, frames={len(feats)}"
    )

    # 3. Full ~100s Scarborough Fair arrangement speed & stability benchmark
    full_events = []
    t_cur = 0.0
    bar_n = 1
    def add_bars(chords, section, base_int, dt_bar=1.55):
        nonlocal t_cur, bar_n
        for idx, ch in enumerate(chords):
            inten = min(1.0, base_int + 0.12 * math.sin(math.pi * idx / max(1, len(chords) - 1)))
            full_events.append({
                "bar": bar_n,
                "start": t_cur,
                "end": t_cur + dt_bar,
                "chord": ch,
                "section": section,
                "intensity": inten,
            })
            t_cur += dt_bar
            bar_n += 1

    verse_prog = [
        "Dm", "Dm", "C", "Dm",
        "Dm/F", "Dm", "G", "Dm", "Dm",
        "Dm", "C", "Dm", "C",
        "Dm", "C", "Dm", "Dm",
    ]
    add_bars(["Dm", "C", "Dm", "Dm"], "intro", 0.45, 1.56)
    add_bars(verse_prog, "verse1", 0.55, 1.54)
    add_bars(verse_prog, "verse2", 0.68, 1.54)
    add_bars(verse_prog, "verse3", 0.88, 1.56)
    add_bars(["Dm", "Dm", "C", "Dm", "Dm", "C", "Dm", "Dm"], "coda", 0.45, 1.66)
    add_bars(["Dm", "C", "Dm_end"], "outro", 0.35, 1.85)
    full_dur = t_cur + 1.5  # lingering tail

    tb0 = time.perf_counter()
    f_al, f_ar = render_accompaniment(full_events, None, full_dur, sr=sr)
    tb1 = time.perf_counter()
    # Lightweight synthetic vocal envelope for full mix benchmark
    n_full = len(f_al)
    f_voc = array("d", [0.0]) * n_full
    for i in range(int(6.2 * sr), int((full_dur - 5.0) * sr), 1):
        # Simple voiced proxy only in active region
        f_voc[i] = 0.18 * math.sin(2.0 * math.pi * 220.0 * (i / sr))
    tb2 = time.perf_counter()
    fm_l, fm_r, fv_w = mix_and_master(f_voc, f_al, f_ar, sr=sr)
    tb3 = time.perf_counter()
    f_feats = extract_timeline_features(f_voc, fm_l, fm_r, None, None, sr=sr, fps=30)
    tb4 = time.perf_counter()

    total_bench = (tb1 - tb0) + (tb3 - tb2) + (tb4 - tb3)
    f_peak = max(max(abs(x) for x in fm_l), max(abs(x) for x in fm_r))
    f_rms = math.sqrt(sum(0.5 * (fm_l[i] ** 2 + fm_r[i] ** 2) for i in range(n_full)) / n_full)
    print(
        f"[PASS] Full {full_dur:.1f}s song benchmark: acc={tb1-tb0:.2f}s, mix+reverb={tb3-tb2:.2f}s, "
        f"features={tb4-tb3:.2f}s, TOTAL={total_bench:.2f}s | peak={f_peak:.4f}, rms={f_rms:.4f}, frames={len(f_feats)}"
    )
    assert total_bench < 15.0, f"Too slow: {total_bench:.2f}s > 15s budget!"
    print("=== ALL SELF-TESTS PASSED ===")


if __name__ == "__main__":
    _self_test()
