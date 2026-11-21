"""
song_spec.py — Complete musical score, D Dorian melody, rubato tempo map,
phonetic transcription, and visual timeline metadata for:
"Aero Sings Scarborough Fair" (Traditional English Ballad, Public Domain).

100% pure Python standard library.
"""

import math

SAMPLE_RATE = 22050
BEATS_PER_BAR = 3

# Exact equal-temperament frequencies (A4 = 440.0 Hz)
NOTE_HZ = {
    "C3": 130.8128,
    "D3": 146.8324,
    "E3": 164.8138,
    "F3": 174.6141,
    "G3": 195.9977,
    "A3": 220.0000,
    "B3": 246.9417,
    "C4": 261.6256,
    "D4": 293.6648,
    "E4": 329.6276,
}

# Herb keyword tagging for botanical animations
HERB_WORDS = {
    "parsley": "parsley",
    "sage": "sage",
    "rosemary": "rosemary",
    "thyme": "thyme",
}


def _clean_word_key(word):
    return "".join(ch for ch in word.lower() if ch.isalpha())


# =============================================================================
# SONG ARCHITECTURE: 66 BARS IN 3/4 TIME (D DORIAN)
# Intro (4) + Verse 1 (17) + Verse 2 (17) + Verse 3 (17) + Coda (8) + Outro (3)
# =============================================================================

def _build_bar_plan():
    """
    Returns list of 66 bar dicts:
      {"bar": idx, "section": str, "chord": str, "bpm": float, "intensity": float}
    Unhurried, breathing folk ballad tempo (~114-117 BPM verses, gentle cadence
    rubato ~106-110 BPM, heartfelt Coda ritardando 104->82 BPM).
    """
    bars = []

    def add_bars(section, spec_list):
        for chord, bpm, intensity in spec_list:
            bars.append({
                "bar": len(bars),
                "section": section,
                "chord": chord,
                "bpm": bpm,
                "intensity": intensity,
            })

    # --- INTRO (4 bars: Dm -> C -> Dm -> Dm) ---
    add_bars("intro", [
        ("Dm", 112.0, 0.50),
        ("C",  114.0, 0.54),
        ("Dm", 115.0, 0.58),
        ("Dm", 113.0, 0.60),
    ])

    def verse_chords(base_bpm, base_int, final_turnaround="C"):
        # 16 bars melody + 1 bar gentle turnaround/breath
        # NOTE: Bar 15 uses "Csus2" (C-D-G) so vocal F3 on "true" has ZERO
        # semitone/M7 clash with E, resolving warmly through E3-D3-C3 -> Dm!
        return [
            # Line 1: Are you going to Scarborough Fair? (Bars 1-4)
            ("Dm",    base_bpm - 1.0, base_int * 0.88),
            ("Dm",    base_bpm + 1.0, base_int * 0.96),
            ("C",     base_bpm - 0.5, base_int * 0.93),
            ("Dm",    base_bpm - 6.0, base_int * 0.82),
            # Line 2: Parsley, sage, rosemary and thyme (Bars 5-9)
            ("F",     base_bpm + 0.5, base_int * 0.95),
            ("Dm",    base_bpm + 1.5, base_int * 1.06),
            ("G",     base_bpm + 0.5, base_int * 1.03),
            ("Dm",    base_bpm - 3.5, base_int * 0.96),
            ("Dm",    base_bpm - 5.0, base_int * 0.85),
            # Line 3: Remember me to one who lives there (Bars 10-13)
            ("Dm",    base_bpm + 1.5, base_int * 1.10),
            ("C",     base_bpm + 1.0, base_int * 1.05),
            ("Dm",    base_bpm - 1.0, base_int * 0.96),
            ("C",     base_bpm - 6.0, base_int * 0.84),
            # Line 4: For once she was / Then she'll be a true love of mine (Bars 14-16)
            ("Dm",    base_bpm - 1.0, base_int * 0.94),
            ("Csus2", base_bpm - 4.0, base_int * 0.92),
            ("Dm",    base_bpm - 8.0, base_int * 0.80),
            # Breath / Turnaround (Bar 17)
            (final_turnaround, base_bpm - 4.5, base_int * 0.64),
        ]

    # --- VERSE 1 (Bars 4..20, intimate storytelling) ---
    add_bars("verse1", verse_chords(116.5, 0.78, final_turnaround="C"))

    # --- VERSE 2 (Bars 21..37, warmer growing devotion + cello enters) ---
    add_bars("verse2", verse_chords(117.5, 0.91, final_turnaround="C"))

    # --- VERSE 3 (Bars 38..54, passionate emotional climax) ---
    add_bars("verse3", verse_chords(118.0, 1.08, final_turnaround="Dm"))

    # --- CODA / REPRISE (Bars 55..62, 8 bars, genuinely hushed & tender ritardando) ---
    add_bars("coda", [
        ("Dm",    106.0, 0.52),   # Are you
        ("Dm",    105.0, 0.55),   # going to
        ("C",     102.0, 0.50),   # Scarborough
        ("Dm",     97.0, 0.46),   # Fair
        ("Dm",     96.0, 0.42),   # tender pause + "For"
        ("Dm",     95.0, 0.50),   # once she was a
        ("Csus2",  89.0, 0.47),   # true love of
        ("Dm",     80.0, 0.40),   # mine...
    ])

    # --- OUTRO (Bars 63..65, 3 bars fading harmonic guitar) ---
    add_bars("outro", [
        ("Dm",     76.0, 0.34),
        ("C",      71.0, 0.28),
        ("Dm_end", 64.0, 0.24),
    ])

    return bars


def _compute_bar_timings(bars):
    """Assign exact start/end times (seconds) to every bar."""
    t = 0.0
    for b in bars:
        bar_dur = BEATS_PER_BAR * (60.0 / b["bpm"])
        b["start"] = t
        b["end"] = t + bar_dur
        t += bar_dur
    return t


class TempoMap:
    """Smooth piecewise-continuous beat-to-second converter locked to bar timings."""

    def __init__(self, bars):
        self.bars = bars
        self.total_beats = len(bars) * BEATS_PER_BAR
        self.total_duration = bars[-1]["end"]

    def beat_to_time(self, beat):
        if beat <= 0.0:
            return 0.0
        if beat >= self.total_beats:
            extra = beat - self.total_beats
            return self.total_duration + extra * (60.0 / self.bars[-1]["bpm"])
        bar_idx = int(beat // BEATS_PER_BAR)
        local_beat = beat - bar_idx * BEATS_PER_BAR
        b = self.bars[bar_idx]
        frac = local_beat / float(BEATS_PER_BAR)
        return b["start"] + frac * (b["end"] - b["start"])

    def to_dict(self):
        return {
            "beats_per_bar": BEATS_PER_BAR,
            "base_bpm": 116.0,
            "total_duration": round(self.total_duration, 4),
            "bars": [
                {
                    "bar": b["bar"],
                    "bpm": b["bpm"],
                    "start": round(b["start"], 5),
                    "end": round(b["end"], 5),
                }
                for b in self.bars
            ],
        }


# =============================================================================
# SYLLABLE SPEC HELPERS
# =============================================================================

def _herb_refrain_syllables(bar_offset, intensity=1.0, vib_scale=1.0, vib_delay=0.20, breath_extra=0.0):
    """
    Bars 5..9 of each verse: "Parsley, sage, rosemary and thyme"
    Melody: rest(1) A3(1) C4(1) | D4(2) C4(1) | A3(1) B3(1) G3(1) | A3(4.05)
    """
    b = bar_offset * 3.0
    return [
        (b + 13.0, 1.00, "A3", "Parsley,", "Pars-", ["P", "AA", "R", "S"],
         {"stress": 0.90, "scoop": -0.65, "breath_before": 0.24, "breathiness": breath_extra,
          "vib_delay": vib_delay, "dyn": 0.92 * intensity}),
        (b + 14.0, 1.00, "C4", "Parsley,", "-ley", ["L", "IY"],
         {"cont": True, "stress": 0.52, "breathiness": breath_extra,
          "vib_delay": vib_delay, "dyn": 0.88 * intensity}),
        (b + 15.0, 1.92, "D4", "sage,", "sage", ["S", "EY", "JH"],
         {"stress": 1.00, "scoop": -0.50, "vibrato": 1.10 * vib_scale, "vib_delay": vib_delay,
          "breathiness": breath_extra, "dyn": 1.08 * intensity}),
        (b + 17.0, 1.00, "C4", "rosemary", "rose-", ["R", "OW", "Z"],
         {"stress": 0.86, "breathiness": breath_extra, "vib_delay": vib_delay,
          "dyn": 0.98 * intensity}),
        (b + 18.0, 1.00, "A3", "rosemary", "-ma-", ["M", "EH"],
         {"cont": True, "stress": 0.62, "breathiness": breath_extra,
          "vib_delay": vib_delay, "dyn": 0.90 * intensity}),
        (b + 19.0, 1.00, "B3", "rosemary", "-ry", ["R", "IY"],
         {"cont": True, "stress": 0.90, "scoop": -0.30, "breathiness": breath_extra,
          "vib_delay": vib_delay, "dyn": 1.02 * intensity}),
        (b + 20.0, 1.00, "G3", "and", "and", ["AE", "N"],
         {"stress": 0.40, "breathiness": breath_extra, "vib_delay": vib_delay,
          "dyn": 0.80 * intensity}),
        # "thyme" is pronounced /t aɪ m/ (exact rhyme with "time")
        (b + 21.0, 4.05, "A3", "thyme", "thyme", ["T", "AY", "M"],
         {"stress": 1.00, "scoop": -0.55, "vibrato": 1.30 * vib_scale, "vib_delay": vib_delay,
          "breathiness": breath_extra + 0.03, "release_fade": 0.42,
          "legato": False, "dyn": 1.02 * intensity}),
    ]


def _line4_for_once(bar_offset, intensity=1.0, coda_mode=False):
    """
    "For once she was a true love of mine"
    """
    b = bar_offset * 3.0
    vib = 0.62 if coda_mode else 1.15
    vdel = 0.28 if coda_mode else 0.22
    br = 0.30 if coda_mode else 0.02
    mine_dur = 3.85 if coda_mode else 2.85
    return [
        (b - 0.50, 0.50, "D3", "For",  "For",  ["F", "AO", "R"],
         {"stress": 0.45, "breath_before": 0.22, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.78 * intensity}),
        (b + 0.00, 1.00, "D3", "once", "once", ["W", "AH", "N", "S"],
         {"stress": 0.88, "scoop": -0.50, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.94 * intensity}),
        (b + 1.00, 1.00, "A3", "she",  "she",  ["SH", "IY"],
         {"stress": 0.84, "scoop": -0.65, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.98 * intensity}),
        (b + 2.00, 0.52, "G3", "was",  "was",  ["W", "AH", "Z"],
         {"stress": 0.50, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.84 * intensity}),
        (b + 2.52, 0.48, "G3", "a",    "a",    ["AX"],
         {"stress": 0.32, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.76 * intensity}),
        (b + 3.00, 1.00, "F3", "true", "true", ["T", "R", "UW"],
         {"stress": 0.98, "scoop": -0.45, "breathiness": br, "vib_delay": vdel,
          "dyn": 1.06 * intensity}),
        (b + 4.00, 1.00, [("E3", 0.52), ("D3", 0.48)], "love", "love", ["L", "AH", "V"],
         {"stress": 0.96, "breathiness": br + 0.03, "vib_delay": vdel,
          "dyn": 1.00 * intensity}),
        (b + 5.00, 1.00, "C3", "of",   "of",   ["AH", "V"],
         {"stress": 0.48, "breathiness": br + 0.06, "vib_delay": vdel,
          "dyn": 0.80 * intensity}),
        (b + 6.00, mine_dur, "D3", "mine", "mine", ["M", "AY", "N"],
         {"stress": 1.00, "scoop": -0.55, "vibrato": vib, "vib_delay": vdel,
          "breathiness": br + 0.10, "release_fade": 0.55 if coda_mode else 0.42,
          "legato": False, "dyn": 0.92 * intensity}),
    ]


def _line4_then_shell(bar_offset, intensity=1.0, vib_scale=1.15, vib_delay=0.19):
    """
    "Then she'll be a true love of mine"
    """
    b = bar_offset * 3.0
    return [
        (b + 0.00, 1.00, "D3", "Then",   "Then",   ["DH", "EH", "N"],
         {"stress": 0.84, "scoop": -0.45, "breath_before": 0.24, "vib_delay": vib_delay,
          "dyn": 0.90 * intensity}),
        (b + 1.00, 1.00, "A3", "she'll", "she'll", ["SH", "IY", "DL"],
         {"stress": 0.92, "scoop": -0.65, "vib_delay": vib_delay,
          "dyn": 1.02 * intensity}),
        (b + 2.00, 0.52, "G3", "be",     "be",     ["B", "IY"],
         {"stress": 0.54, "vib_delay": vib_delay, "dyn": 0.88 * intensity}),
        (b + 2.52, 0.48, "G3", "a",      "a",      ["AX"],
         {"stress": 0.32, "vib_delay": vib_delay, "dyn": 0.78 * intensity}),
        (b + 3.00, 1.00, "F3", "true",   "true",   ["T", "R", "UW"],
         {"stress": 0.98, "scoop": -0.45, "vib_delay": vib_delay,
          "dyn": 1.08 * intensity}),
        (b + 4.00, 1.00, [("E3", 0.52), ("D3", 0.48)], "love", "love", ["L", "AH", "V"],
         {"stress": 0.96, "vib_delay": vib_delay, "dyn": 1.02 * intensity}),
        (b + 5.00, 1.00, "C3", "of",     "of",     ["AH", "V"],
         {"stress": 0.48, "breathiness": 0.04, "vib_delay": vib_delay,
          "dyn": 0.82 * intensity}),
        (b + 6.00, 2.85, "D3", "mine",   "mine",   ["M", "AY", "N"],
         {"stress": 1.00, "scoop": -0.55, "vibrato": 1.25 * vib_scale, "vib_delay": vib_delay,
          "breathiness": 0.06, "release_fade": 0.44, "legato": False,
          "dyn": 0.94 * intensity}),
    ]


def _line1_scarborough(bar_offset, intensity=1.0, coda_mode=False):
    """
    "Are you going to Scarborough Fair?"
    """
    b = bar_offset * 3.0
    br = 0.28 if coda_mode else 0.02
    vib = 0.58 if coda_mode else 0.95
    vdel = 0.28 if coda_mode else 0.23
    return [
        (b + 0.00, 2.00, "D3", "Are",         "Are",    ["AA", "R"],
         {"stress": 0.90, "scoop": -0.75, "breath_before": 0.24, "breathiness": br,
          "vibrato": 0.85 * vib, "vib_delay": vdel, "dyn": 0.90 * intensity}),
        (b + 2.00, 1.00, "D3", "you",         "you",    ["Y", "UW"],
         {"stress": 0.60, "breathiness": br, "vib_delay": vdel, "dyn": 0.84 * intensity}),
        (b + 3.00, 1.50, "A3", "going",       "go-",    ["G", "OW"],
         {"stress": 0.96, "scoop": -0.65, "breathiness": br, "vibrato": 0.80 * vib,
          "vib_delay": vdel, "dyn": 1.04 * intensity}),
        (b + 4.50, 0.50, "A3", "going",       "-ing",   ["IH", "NG"],
         {"cont": True, "stress": 0.44, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.86 * intensity}),
        (b + 5.00, 1.00, "A3", "to",          "to",     ["T", "UW"],
         {"stress": 0.48, "breathiness": br, "vib_delay": vdel, "dyn": 0.88 * intensity}),
        (b + 6.00, 1.50, "E3", "Scarborough", "Scar-",  ["S", "KU", "AA", "R"],
         {"stress": 0.96, "breathiness": br, "vib_delay": vdel, "dyn": 1.00 * intensity}),
        (b + 7.50, 0.50, "F3", "Scarborough", "-bo-",   ["B", "AX"],
         {"cont": True, "stress": 0.45, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.88 * intensity}),
        (b + 8.00, 1.00, "E3", "Scarborough", "-rough", ["R", "OW"],
         {"cont": True, "stress": 0.60, "breathiness": br, "vib_delay": vdel,
          "dyn": 0.88 * intensity}),
        (b + 9.00, 2.75, "D3", "Fair?",       "Fair",   ["F", "EH", "AX", "R"],
         {"stress": 1.00, "scoop": -0.45, "vibrato": 1.15 * vib, "vib_delay": vdel,
          "breathiness": br + 0.08, "release_fade": 0.44, "legato": False,
          "dyn": 0.94 * intensity}),
    ]


def build_song_spec():
    """Build complete musical score, timeline metadata, chords, and phoneme spec."""
    bars = _build_bar_plan()
    total_duration = _compute_bar_timings(bars)
    tmap = TempoMap(bars)

    scene_defs = [
        ("intro",  0,  4,  "wistful",    "Twilight Ridge"),
        ("verse1", 4,  21, "longing",    "Scarborough Fair"),
        ("verse2", 21, 38, "devotion",   "The Cambric Shirt"),
        ("verse3", 38, 55, "tempest",    "Salt Water & Sea Strand"),
        ("coda",   55, 63, "tender",     "Fading Memory"),
        ("outro",  63, 66, "stillness",  "Dusk Embers"),
    ]
    scenes = []
    for sid, b_start, b_end, mood, label in scene_defs:
        scenes.append({
            "id": sid,
            "start": round(bars[b_start]["start"], 4),
            "end": round(bars[b_end - 1]["end"], 4),
            "mood": mood,
            "label": label,
            "bar_start": b_start,
            "bar_end": b_end,
        })

    phrase_groups = []

    def add_phrase(scene_id, text, emotion, herb_tag, raw_syllables):
        phrase_groups.append({
            "scene": scene_id,
            "text": text,
            "emotion": emotion,
            "herb": herb_tag,
            "raw": raw_syllables,
        })

    # === VERSE 1 (Starts at bar 4 — intimate, wistful, gentle vibrato) ===
    v1 = 4
    add_phrase(
        "verse1", "Are you going to Scarborough Fair?", "wistful", None,
        _line1_scarborough(v1, intensity=0.80, coda_mode=False)
    )
    add_phrase(
        "verse1", "Parsley, sage, rosemary and thyme", "botanical", "herbs",
        _herb_refrain_syllables(v1, intensity=0.84, vib_scale=0.92, vib_delay=0.23, breath_extra=0.03)
    )
    b_v1 = v1 * 3.0
    add_phrase(
        "verse1", "Remember me to one who lives there", "aching", None,
        [
            (b_v1 + 26.0, 1.00, "D4", "Remember", "Re-",   ["R", "IH"],
             {"stress": 0.52, "breath_before": 0.22, "vib_delay": 0.23, "dyn": 0.78}),
            (b_v1 + 27.0, 2.00, "D4", "Remember", "-mem-", ["M", "EH", "M"],
             {"cont": True, "stress": 1.00, "scoop": -0.45, "vibrato": 1.00, "vib_delay": 0.22, "dyn": 0.90}),
            (b_v1 + 29.0, 1.00, "D4", "Remember", "-ber",  ["B", "ER"],
             {"cont": True, "stress": 0.50, "vib_delay": 0.23, "dyn": 0.80}),
            (b_v1 + 30.0, 2.00, "C4", "me",       "me",    ["M", "IY"],
             {"stress": 0.92, "vibrato": 1.05, "vib_delay": 0.22, "dyn": 0.88}),
            (b_v1 + 32.0, 1.00, "A3", "to",       "to",    ["T", "UW"],
             {"stress": 0.45, "vib_delay": 0.23, "dyn": 0.76}),
            (b_v1 + 33.0, 1.00, "A3", "one",      "one",   ["W", "AH", "N"],
             {"stress": 0.88, "vib_delay": 0.23, "dyn": 0.86}),
            (b_v1 + 34.0, 1.00, "G3", "who",      "who",   ["HH", "UW"],
             {"stress": 0.52, "vib_delay": 0.23, "dyn": 0.80}),
            (b_v1 + 35.0, 1.00, "F3", "lives",    "lives", ["L", "IH", "V", "Z"],
             {"stress": 0.88, "vib_delay": 0.23, "dyn": 0.84}),
            (b_v1 + 36.0, 1.95, "E3", "there",    "there", ["DH", "EH", "AX", "R"],
             {"stress": 0.94, "vibrato": 1.00, "vib_delay": 0.22, "breathiness": 0.06,
              "release_fade": 0.42, "legato": False, "dyn": 0.80}),
        ]
    )
    add_phrase(
        "verse1", "For once she was a true love of mine", "tender", None,
        _line4_for_once(v1 + 13, intensity=0.82, coda_mode=False)
    )

    # === VERSE 2 (Starts at bar 21 — fuller warmth & devotion) ===
    v2 = 21
    b_v2 = v2 * 3.0
    add_phrase(
        "verse2", "Tell her to make me a cambric shirt", "earnest", None,
        [
            (b_v2 + 0.00, 1.50, "D3", "Tell",    "Tell",  ["T", "EH", "DL"],
             {"stress": 0.92, "scoop": -0.65, "breath_before": 0.24, "vib_delay": 0.20, "dyn": 0.90}),
            (b_v2 + 1.50, 0.50, "D3", "her",     "her",   ["HH", "ER"],
             {"stress": 0.52, "vib_delay": 0.20, "dyn": 0.82}),
            (b_v2 + 2.00, 1.00, "D3", "to",      "to",    ["T", "UW"],
             {"stress": 0.48, "vib_delay": 0.20, "dyn": 0.84}),
            (b_v2 + 3.00, 1.50, "A3", "make",    "make",  ["M", "EY", "K"],
             {"stress": 0.98, "scoop": -0.65, "vibrato": 0.95, "vib_delay": 0.19, "dyn": 1.02}),
            (b_v2 + 4.50, 0.50, "A3", "me",      "me",    ["M", "IY"],
             {"stress": 0.55, "vib_delay": 0.20, "dyn": 0.90}),
            (b_v2 + 5.00, 1.00, "A3", "a",       "a",     ["AX"],
             {"stress": 0.34, "vib_delay": 0.20, "dyn": 0.80}),
            (b_v2 + 6.00, 2.00, [("E3", 1.48), ("F3", 0.52)], "cambric", "cam-", ["K", "AE", "M"],
             {"stress": 0.96, "vib_delay": 0.20, "dyn": 0.98}),
            (b_v2 + 8.00, 1.00, "E3", "cambric", "-bric", ["B", "R", "IH", "K"],
             {"cont": True, "stress": 0.62, "vib_delay": 0.20, "dyn": 0.90}),
            (b_v2 + 9.00, 2.75, "D3", "shirt",   "shirt", ["SH", "ER", "T"],
             {"stress": 1.00, "scoop": -0.45, "vibrato": 1.15, "vib_delay": 0.19,
              "breathiness": 0.05, "release_fade": 0.42, "legato": False, "dyn": 0.94}),
        ]
    )
    add_phrase(
        "verse2", "Parsley, sage, rosemary and thyme", "botanical", "herbs",
        _herb_refrain_syllables(v2, intensity=0.95, vib_scale=1.10, vib_delay=0.19)
    )
    add_phrase(
        "verse2", "Without no seams nor needlework", "yearning", None,
        [
            (b_v2 + 26.0, 1.00, "D4", "Without",    "With-", ["W", "IH"],
             {"stress": 0.52, "breath_before": 0.22, "vib_delay": 0.20, "dyn": 0.88}),
            (b_v2 + 27.0, 2.00, "D4", "Without",    "-out",  ["DH", "AW", "T"],
             {"cont": True, "stress": 0.98, "scoop": -0.45, "vibrato": 1.12, "vib_delay": 0.19, "dyn": 1.02}),
            (b_v2 + 29.0, 1.00, "D4", "no",         "no",    ["N", "OW"],
             {"stress": 0.76, "vib_delay": 0.20, "dyn": 0.94}),
            (b_v2 + 30.0, 2.00, "C4", "seams",      "seams", ["S", "IY", "M", "Z"],
             {"stress": 0.96, "vibrato": 1.15, "vib_delay": 0.19, "dyn": 1.00}),
            (b_v2 + 32.0, 1.00, "A3", "nor",        "nor",   ["N", "AO", "R"],
             {"stress": 0.62, "vib_delay": 0.20, "dyn": 0.88}),
            (b_v2 + 33.0, 2.00, [("A3", 1.00), ("G3", 1.00)], "needlework", "nee-", ["N", "IY"],
             {"stress": 0.94, "vib_delay": 0.20, "dyn": 0.96}),
            (b_v2 + 35.0, 1.00, "F3", "needlework", "-dle-", ["D", "AX", "DL"],
             {"cont": True, "stress": 0.50, "vib_delay": 0.20, "dyn": 0.86}),
            (b_v2 + 36.0, 2.00, "E3", "needlework", "-work", ["W", "ER", "K"],
             {"cont": True, "stress": 0.92, "vibrato": 1.08, "vib_delay": 0.19,
              "breathiness": 0.05, "release_fade": 0.40, "legato": False, "dyn": 0.90}),
        ]
    )
    add_phrase(
        "verse2", "Then she'll be a true love of mine", "devotion", None,
        _line4_then_shell(v2 + 13, intensity=0.94, vib_scale=1.10, vib_delay=0.19)
    )

    # === VERSE 3 (Starts at bar 38 — deepest emotional swell & passionate ring) ===
    v3 = 38
    b_v3 = v3 * 3.0
    add_phrase(
        "verse3", "Tell her to find me an acre of land", "passionate", None,
        [
            (b_v3 + 0.00, 1.50, "D3", "Tell", "Tell", ["T", "EH", "DL"],
             {"stress": 0.96, "scoop": -0.70, "breath_before": 0.24, "vib_delay": 0.17, "dyn": 1.06}),
            (b_v3 + 1.50, 0.50, "D3", "her",  "her",  ["HH", "ER"],
             {"stress": 0.54, "vib_delay": 0.18, "dyn": 0.96}),
            (b_v3 + 2.00, 1.00, "D3", "to",   "to",   ["T", "UW"],
             {"stress": 0.52, "vib_delay": 0.18, "dyn": 0.98}),
            (b_v3 + 3.00, 1.50, "A3", "find", "find", ["F", "AY", "N", "D"],
             {"stress": 1.00, "scoop": -0.70, "vibrato": 1.15, "vib_delay": 0.17, "dyn": 1.18}),
            (b_v3 + 4.50, 0.50, "A3", "me",   "me",   ["M", "IY"],
             {"stress": 0.56, "vib_delay": 0.18, "dyn": 1.04}),
            (b_v3 + 5.00, 1.00, "A3", "an",   "an",   ["AE", "N"],
             {"stress": 0.44, "vib_delay": 0.18, "dyn": 0.96}),
            (b_v3 + 6.00, 1.50, "E3", "acre", "a-",   ["EY"],
             {"stress": 0.96, "vib_delay": 0.18, "dyn": 1.10}),
            (b_v3 + 7.50, 0.50, "F3", "acre", "-cre", ["K", "ER"],
             {"cont": True, "stress": 0.60, "vib_delay": 0.18, "dyn": 1.02}),
            (b_v3 + 8.00, 1.00, "E3", "of",   "of",   ["AH", "V"],
             {"stress": 0.48, "vib_delay": 0.18, "dyn": 0.96}),
            (b_v3 + 9.00, 2.75, "D3", "land", "land", ["L", "AE", "N", "D"],
             {"stress": 1.00, "scoop": -0.50, "vibrato": 1.28, "vib_delay": 0.17,
              "breathiness": 0.03, "release_fade": 0.42, "legato": False, "dyn": 1.12}),
        ]
    )
    add_phrase(
        "verse3", "Parsley, sage, rosemary and thyme", "botanical", "herbs",
        _herb_refrain_syllables(v3, intensity=1.12, vib_scale=1.28, vib_delay=0.17)
    )
    add_phrase(
        "verse3", "Between the salt water and the sea strand", "climax", None,
        [
            (b_v3 + 26.0, 1.00, "D4", "Between", "Be-",    ["B", "IH"],
             {"stress": 0.58, "breath_before": 0.24, "vib_delay": 0.17, "dyn": 1.04}),
            (b_v3 + 27.0, 2.00, "D4", "Between", "-tween", ["T", "W", "IY", "N"],
             {"cont": True, "stress": 1.00, "scoop": -0.55, "vibrato": 1.25, "vib_delay": 0.17, "dyn": 1.18}),
            (b_v3 + 29.0, 1.00, "D4", "the",     "the",    ["DH", "AX"],
             {"stress": 0.42, "vib_delay": 0.18, "dyn": 0.98}),
            (b_v3 + 30.0, 1.00, "C4", "salt",    "salt",   ["S", "AO", "DL", "T"],
             {"stress": 0.98, "vib_delay": 0.17, "dyn": 1.16}),
            (b_v3 + 31.0, 1.00, "C4", "water",   "wa-",    ["W", "AO"],
             {"stress": 0.96, "vib_delay": 0.17, "dyn": 1.14}),
            (b_v3 + 32.0, 1.00, "A3", "water",   "-ter",   ["T", "ER"],
             {"cont": True, "stress": 0.62, "vib_delay": 0.18, "dyn": 1.02}),
            (b_v3 + 33.0, 1.00, "A3", "and",     "and",    ["AE", "N"],
             {"stress": 0.46, "vib_delay": 0.18, "dyn": 0.96}),
            (b_v3 + 34.0, 1.00, "G3", "the",     "the",    ["DH", "AX"],
             {"stress": 0.42, "vib_delay": 0.18, "dyn": 0.94}),
            (b_v3 + 35.0, 1.00, "F3", "sea",     "sea",    ["S", "IY"],
             {"stress": 0.96, "vib_delay": 0.18, "dyn": 1.08}),
            (b_v3 + 36.0, 2.05, "E3", "strand",  "strand", ["S", "TU", "R", "AE", "N", "D"],
             {"stress": 1.00, "vibrato": 1.25, "vib_delay": 0.17, "breathiness": 0.04,
              "release_fade": 0.42, "legato": False, "dyn": 1.10}),
        ]
    )
    add_phrase(
        "verse3", "Then she'll be a true love of mine", "devotion", None,
        _line4_then_shell(v3 + 13, intensity=1.08, vib_scale=1.22, vib_delay=0.17)
    )

    # === CODA / REPRISE (Starts at bar 55 — genuinely hushed, intimate, whispered baritone) ===
    coda_bar = 55
    add_phrase(
        "coda", "Are you going to Scarborough Fair?", "hushed", None,
        _line1_scarborough(coda_bar, intensity=0.52, coda_mode=True)
    )
    add_phrase(
        "coda", "For once she was a true love of mine", "whispered", None,
        _line4_for_once(coda_bar + 5, intensity=0.49, coda_mode=True)
    )

    # -------------------------------------------------------------------------
    # EXPAND SYLLABLES, PHRASES, AND MERGED WORDS WITH EXACT TIMESTAMPS
    # -------------------------------------------------------------------------
    syllables = []
    phrases = []
    words = []

    for p_idx, pg in enumerate(phrase_groups):
        p_start = None
        p_end = None

        for raw in pg["raw"]:
            beat_start, dur_beats, pitch_spec, word_text, syll_text, phones, opts = raw
            opts = opts or {}
            t_start = tmap.beat_to_time(beat_start)
            t_end = tmap.beat_to_time(beat_start + dur_beats)

            if isinstance(pitch_spec, str):
                pitch_points = [(0.0, NOTE_HZ[pitch_spec])]
                main_hz = NOTE_HZ[pitch_spec]
            else:
                pitch_points = []
                acc_b = 0.0
                for n_name, n_beats in pitch_spec:
                    frac = acc_b / dur_beats
                    pitch_points.append((frac, NOTE_HZ[n_name]))
                    acc_b += n_beats
                main_hz = pitch_points[0][1]

            if p_start is None or t_start < p_start:
                p_start = t_start
            if p_end is None or t_end > p_end:
                p_end = t_end

            herb = HERB_WORDS.get(_clean_word_key(word_text), None)

            syll_obj = {
                "phrase_index": p_idx,
                "scene": pg["scene"],
                "beat_start": beat_start,
                "dur_beats": dur_beats,
                "start": t_start,
                "end": t_end,
                "pitch_hz": main_hz,
                "pitch_points": pitch_points,
                "word": word_text,
                "syllable": syll_text,
                "phones": list(phones),
                "cont": bool(opts.get("cont", False)),
                "stress": float(opts.get("stress", 0.7)),
                "scoop": float(opts.get("scoop", 0.0)),
                "breath_before": float(opts.get("breath_before", 0.0)),
                "vibrato": float(opts.get("vibrato", 0.85)),
                "vib_delay": float(opts.get("vib_delay", 0.20)),
                "breathiness": float(opts.get("breathiness", 0.0)),
                "release_fade": float(opts.get("release_fade", 0.14)),
                "legato": bool(opts.get("legato", True)),
                "dyn": float(opts.get("dyn", 0.90)),
                "herb": herb,
            }
            syllables.append(syll_obj)

            if syll_obj["cont"] and words and words[-1]["phrase_index"] == p_idx:
                words[-1]["end"] = round(t_end, 4)
                words[-1]["stress"] = max(words[-1]["stress"], round(syll_obj["stress"], 3))
            else:
                words.append({
                    "word": word_text,
                    "start": round(t_start, 4),
                    "end": round(t_end, 4),
                    "phrase_index": p_idx,
                    "pitch_hz": round(main_hz, 2),
                    "stress": round(syll_obj["stress"], 3),
                    "herb": herb,
                })

        phrases.append({
            "index": p_idx,
            "scene": pg["scene"],
            "start": round(p_start, 4),
            "end": round(p_end, 4),
            "text": pg["text"],
            "emotion": pg["emotion"],
            "herb": pg["herb"],
        })

    chord_events = [
        {
            "bar": b["bar"],
            "start": b["start"],
            "end": b["end"],
            "chord": b["chord"],
            "section": b["section"],
            "intensity": b["intensity"],
        }
        for b in bars
    ]

    return {
        "title": "Scarborough Fair",
        "artist": "Aero",
        "sample_rate": SAMPLE_RATE,
        "duration": total_duration,
        "bars": bars,
        "chord_events": chord_events,
        "tempo_map": tmap.to_dict(),
        "scenes": scenes,
        "phrases": phrases,
        "syllables": syllables,
        "words": words,
    }


if __name__ == "__main__":
    spec = build_song_spec()
    print(f"Song: {spec['artist']} — {spec['title']}")
    print(f"Total bars: {len(spec['bars'])}, Duration: {spec['duration']:.2f}s")
    for sc in spec["scenes"]:
        print(f"  {sc['id']:8s} [{sc['start']:6.2f}s .. {sc['end']:6.2f}s]")
