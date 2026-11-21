"""
render_song.py — End-to-end pure-Python rendering pipeline for
"Aero Sings Scarborough Fair".

Integrates:
  - song_spec.py       (D Dorian score, rubato timing, lyrics, phonemes, metadata)
  - voice_synth.py     (5-formant physical-modeling baritone-tenor singing voice)
  - accompaniment.py   (Karplus-Strong fingerpicked guitar, bowed cello, reverb, mastering)

Outputs in build/:
  - vocal_solo.wav     (22050 Hz mono, warm room-reverbed solo voice)
  - song_full.wav      (22050 Hz stereo, full mastered mix)
  - verse_1.wav        (22050 Hz mono voice clip — Verse 1)
  - verse_2.wav        (22050 Hz mono voice clip — Verse 2)
  - verse_3.wav        (22050 Hz mono voice clip — Verse 3)
  - coda.wav           (22050 Hz mono voice clip — Coda)
  - verse_1_mix.wav    (22050 Hz stereo full mix clip — Verse 1)
  - timeline.json      (30fps synced lyrics, herbs, scenes, audio features)
"""

import array
import json
import math
import os
import time

from song_spec import SAMPLE_RATE, build_song_spec
from voice_synth import synthesize_vocals
from accompaniment import (
    extract_timeline_features,
    mix_and_master,
    render_accompaniment,
    write_wav,
)


def _slice_with_fade(buf, s0, s1, fade_samples=440):
    """Extract slice [s0:s1] with gentle cosine edge fades (no hard click cuts)."""
    n = len(buf)
    s0 = max(0, min(n, s0))
    s1 = max(s0, min(n, s1))
    seg = array.array("d", buf[s0:s1])
    m = len(seg)
    f = min(fade_samples, m // 4)
    if f > 0:
        half_pi = 0.5 * math.pi
        for i in range(f):
            g = math.sin(half_pi * (i / float(f)))
            seg[i] *= g
            seg[m - 1 - i] *= g
    return seg


def _buf_stats(buf):
    n = len(buf)
    if n == 0:
        return 0.0, 0.0, 0
    peak = 0.0
    sq_sum = 0.0
    bad = 0
    for x in buf:
        if math.isnan(x) or math.isinf(x):
            bad += 1
            continue
        ax = abs(x)
        if ax > peak:
            peak = ax
        sq_sum += x * x
    rms = math.sqrt(sq_sum / n)
    return peak, rms, bad


def render_all(out_dir=None, sr=SAMPLE_RATE):
    t_total_start = time.perf_counter()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if out_dir is None:
        out_dir = os.path.join(base_dir, "build")
    os.makedirs(out_dir, exist_ok=True)

    # Remove temporary dry test clip if present so build/ stays clean
    dry_test = os.path.join(out_dir, "verse_1_dry_test.wav")
    if os.path.exists(dry_test):
        try:
            os.remove(dry_test)
        except OSError:
            pass

    # 1. Build song specification
    spec = build_song_spec()
    duration = spec["duration"]
    print(f"[render] Spec built: {spec['artist']} — {spec['title']} ({duration:.2f}s, {len(spec['syllables'])} syllables)")

    # 2. Synthesize singing vocals
    t0 = time.perf_counter()
    vocal_mono, f0_track, breath_track = synthesize_vocals(spec, sr=sr)
    t_voc = time.perf_counter() - t0
    v_pk, v_rms, v_bad = _buf_stats(vocal_mono)
    print(f"[render] Vocals synthesized in {t_voc:.2f}s | peak={v_pk:.4f} rms={v_rms:.4f} bad={v_bad}")
    if v_bad > 0 or v_pk < 0.01:
        raise RuntimeError(f"Vocal buffer invalid: peak={v_pk}, bad={v_bad}")

    # 3. Synthesize acoustic accompaniment (guitar + cello)
    t0 = time.perf_counter()
    acc_left, acc_right = render_accompaniment(
        spec["chord_events"],
        spec["tempo_map"],
        duration,
        sr=sr,
    )
    t_acc = time.perf_counter() - t0
    a_pk, a_rms, a_bad = _buf_stats(acc_left)
    print(f"[render] Accompaniment rendered in {t_acc:.2f}s | peak={a_pk:.4f} rms={a_rms:.4f} bad={a_bad}")
    if a_bad > 0:
        raise RuntimeError(f"Accompaniment buffer has {a_bad} NaN/Inf samples")

    # Align buffer lengths cleanly if rounding differed by 1 sample
    target_len = min(len(vocal_mono), len(acc_left), len(acc_right))
    if len(vocal_mono) != target_len:
        vocal_mono = vocal_mono[:target_len]
        f0_track = f0_track[:target_len]
        breath_track = breath_track[:target_len]
    if len(acc_left) != target_len:
        acc_left = acc_left[:target_len]
    if len(acc_right) != target_len:
        acc_right = acc_right[:target_len]

    # 4. Mix, room reverb, and warm master limiting
    t0 = time.perf_counter()
    mix_left, mix_right, vocal_wet = mix_and_master(vocal_mono, acc_left, acc_right, sr=sr)
    t_mix = time.perf_counter() - t0
    m_pk_l, m_rms_l, m_bad_l = _buf_stats(mix_left)
    m_pk_r, m_rms_r, m_bad_r = _buf_stats(mix_right)
    vw_pk, vw_rms, vw_bad = _buf_stats(vocal_wet)
    print(
        f"[render] Mixed & mastered in {t_mix:.2f}s | "
        f"mix peak=({m_pk_l:.4f}, {m_pk_r:.4f}) rms=({m_rms_l:.4f}, {m_rms_r:.4f}) "
        f"vocal_wet peak={vw_pk:.4f} bad={m_bad_l + m_bad_r + vw_bad}"
    )
    if (m_bad_l + m_bad_r + vw_bad) > 0:
        raise RuntimeError("NaN/Inf detected after mix_and_master")
    if max(m_pk_l, m_pk_r) > 1.001 or vw_pk > 1.001:
        raise RuntimeError(f"Clipping detected: mix=({m_pk_l}, {m_pk_r}), vocal={vw_pk}")

    # 5. Write full WAV deliverables
    vocal_solo_path = os.path.join(out_dir, "vocal_solo.wav")
    song_full_path = os.path.join(out_dir, "song_full.wav")
    write_wav(vocal_solo_path, [vocal_wet], sr=sr)
    write_wav(song_full_path, [mix_left, mix_right], sr=sr)

    # 6. Write compact section clips for detailed audio inspection by critics
    # Slice tightly around each section's own phrases so next-verse onsets NEVER bleed in!
    scene_map = {sc["id"]: sc for sc in spec["scenes"]}
    phrases_by_scene = {}
    for p in spec["phrases"]:
        phrases_by_scene.setdefault(p["scene"], []).append(p)

    # Also build ordered list of phrase start times to enforce hard anti-bleed ceiling
    all_phrase_starts = sorted(p["start"] for p in spec["phrases"])

    def _safe_section_bounds(sc_id, pre_s=0.38, post_s=0.85):
        plist = phrases_by_scene.get(sc_id)
        if plist:
            t_start = max(0.0, plist[0]["start"] - pre_s)
            t_end = plist[-1]["end"] + post_s
            # Strictly cap before the next phrase's inhale/onset (~0.35s before next phrase start)
            last_end = plist[-1]["end"]
            for nxt_st in all_phrase_starts:
                if nxt_st > last_end + 0.05:
                    t_end = min(t_end, nxt_st - 0.36)
                    break
        else:
            sc = scene_map[sc_id]
            t_start = sc["start"]
            t_end = sc["end"]
        return int(t_start * sr), min(len(vocal_wet), int(t_end * sr))

    section_clips = [
        ("verse1", "verse_1.wav"),
        ("verse2", "verse_2.wav"),
        ("verse3", "verse_3.wav"),
        ("coda",   "coda.wav"),
    ]
    for sc_id, fname in section_clips:
        s0, s1 = _safe_section_bounds(sc_id, pre_s=0.36, post_s=0.90)
        clip = _slice_with_fade(vocal_wet, s0, s1)
        write_wav(os.path.join(out_dir, fname), [clip], sr=sr)

    # Verse 1 stereo full-mix clip (includes gentle guitar pickup from end of intro, zero V2 bleed!)
    m_s0, m_s1 = _safe_section_bounds("verse1", pre_s=1.25, post_s=0.85)
    v1_mix_l = _slice_with_fade(mix_left, m_s0, m_s1)
    v1_mix_r = _slice_with_fade(mix_right, m_s0, m_s1)
    write_wav(os.path.join(out_dir, "verse_1_mix.wav"), [v1_mix_l, v1_mix_r], sr=sr)

    # 7. Extract 30fps timeline features & write build/timeline.json
    fps = 30
    frames = extract_timeline_features(
        vocal_mono, mix_left, mix_right, f0_track, breath_track, sr=sr, fps=fps
    )

    timeline = {
        "title": spec["title"],
        "artist": spec["artist"],
        "duration": round(target_len / float(sr), 4),
        "sample_rate": sr,
        "fps": fps,
        "scenes": [
            {
                "id": sc["id"],
                "start": sc["start"],
                "end": sc["end"],
                "mood": sc["mood"],
                "label": sc["label"],
            }
            for sc in spec["scenes"]
        ],
        "phrases": spec["phrases"],
        "words": spec["words"],
        "frames": frames,
    }
    timeline_path = os.path.join(out_dir, "timeline.json")
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, separators=(",", ":"))

    t_total = time.perf_counter() - t_total_start
    print(f"[render] Done in {t_total:.2f}s! Generated outputs in {out_dir}:")
    for fname in [
        "vocal_solo.wav",
        "song_full.wav",
        "verse_1.wav",
        "verse_2.wav",
        "verse_3.wav",
        "coda.wav",
        "verse_1_mix.wav",
        "timeline.json",
    ]:
        fpath = os.path.join(out_dir, fname)
        sz_kb = os.path.getsize(fpath) / 1024.0
        print(f"  - {fname:18s} ({sz_kb:7.1f} KB)")


if __name__ == "__main__":
    render_all()
