#!/usr/bin/env python3
"""
build_html.py — Pure Python Stdlib Packager for "Aero Sings Scarborough Fair"

Embeds:
  - art_engine.js        (hand-drawn charcoal / graphite / ink / watercolor Canvas 2D engine)
  - art_scenes.js        (5-act story-driven emotional choreography synced to lyrics & audio)
  - build/timeline.json  (scenes, phrases, word timestamps, herb cues, audio telemetry frames)
  - build/song_full.wav  (base64 data:audio/wav;base64,... embedded audio)

Produces ONE 100% self-contained offline HTML file with ZERO external dependencies:
  ./scarborough_fair_aero.html
"""

import argparse
import base64
import io
import json
import math
import os
import re
import struct
import sys
import wave

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ROOT_DIR, "build")
OUT_HTML = os.path.join(ROOT_DIR, "scarborough_fair_aero.html")


def generate_mock_timeline():
    """Generate a realistic ~100s Scarborough Fair timeline matching the shared schema for early visual previews."""
    scenes = [
        {"id": "intro",  "start": 0.0,  "end": 9.0,   "mood": "wistful twilight",    "label": "I · The Twilight Path"},
        {"id": "verse1", "start": 9.0,  "end": 35.0,  "mood": "longing & memory",    "label": "II · Parsley, Sage, Rosemary & Thyme"},
        {"id": "verse2", "start": 35.0, "end": 61.0,  "mood": "tender impossible",   "label": "III · The Cambric Shirt"},
        {"id": "verse3", "start": 61.0, "end": 86.0,  "mood": "dramatic sea swell",  "label": "IV · Between Salt Water & Sea Strand"},
        {"id": "coda",   "start": 86.0, "end": 96.0,  "mood": "hushed farewell",     "label": "V · True Love of Mine"},
        {"id": "outro",  "start": 96.0, "end": 102.0, "mood": "fading stillness",    "label": "V · True Love of Mine"},
    ]

    phrase_specs = [
        # Verse 1
        ("verse1", 9.4,  15.2, "Are you going to Scarborough Fair?",      "wistful",  None),
        ("verse1", 15.8, 22.0, "Parsley, sage, rosemary and thyme",       "botanical", "all"),
        ("verse1", 22.6, 28.4, "Remember me to one who lives there",      "memory",   None),
        ("verse1", 28.8, 34.4, "For once she was a true love of mine",    "aching",   None),
        # Verse 2
        ("verse2", 35.6, 41.4, "Tell her to make me a cambric shirt",     "intimate", None),
        ("verse2", 42.0, 48.2, "Parsley, sage, rosemary and thyme",       "botanical", "all"),
        ("verse2", 48.8, 54.4, "Without no seams nor needlework",         "ethereal", None),
        ("verse2", 54.8, 60.4, "Then she'll be a true love of mine",      "longing",  None),
        # Verse 3
        ("verse3", 61.6, 67.4, "Tell her to find me an acre of land",     "swelling", None),
        ("verse3", 68.0, 74.0, "Parsley, sage, rosemary and thyme",       "botanical", "all"),
        ("verse3", 74.6, 80.2, "Between the salt water and the sea strand", "climax", None),
        ("verse3", 80.6, 85.4, "Then she'll be a true love of mine",      "aching",   None),
        # Coda
        ("coda",   86.6, 91.2, "Are you going to Scarborough Fair?",      "hushed",   None),
        ("coda",   91.6, 96.2, "For once she was a true love of mine",    "whisper",  None),
    ]

    phrases = []
    words = []
    herb_set = {"parsley", "sage", "rosemary", "thyme"}

    for idx, (sc, st, en, text, emo, h_tag) in enumerate(phrase_specs):
        phrases.append({
            "index": idx,
            "scene": sc,
            "start": round(st, 3),
            "end": round(en, 3),
            "text": text,
            "emotion": emo,
            "herb": h_tag,
        })
        toks = text.split()
        dur = en - st
        step = dur / max(1, len(toks))
        for wi, tok in enumerate(toks):
            clean = re.sub(r"[^a-z]", "", tok.lower())
            w_st = st + wi * step
            w_en = w_st + step * 0.92
            words.append({
                "word": tok,
                "start": round(w_st, 3),
                "end": round(w_en, 3),
                "phrase_index": idx,
                "pitch_hz": round(196.0 + 44.0 * math.sin(wi * 0.9 + idx * 0.5), 1),
                "stress": 0.85 if clean in herb_set else 0.55,
                "herb": clean if clean in herb_set else None,
            })

    duration = 102.0
    fps = 30
    frames = []
    total_frames = int(duration * fps) + 1
    for i in range(total_frames):
        t = i / float(fps)
        singing = any(p["start"] <= t <= p["end"] for p in phrases)
        pre_breath = any((p["start"] - 0.35) <= t < p["start"] for p in phrases)
        climax = 1.35 if 61.0 <= t <= 86.0 else (0.55 if t >= 86.0 else 1.0)
        v_rms = (0.38 + 0.24 * abs(math.sin(t * 2.8))) * climax if singing else 0.02
        a_rms = (0.28 + 0.14 * abs(math.sin(t * 3.14))) * (0.45 if t > 96.0 else 1.0)
        breath = 0.72 if pre_breath else (0.18 if singing else 0.08)
        energy = min(1.0, v_rms * 0.65 + a_rms * 0.45)
        f0 = (220.0 + 55.0 * math.sin(t * 1.4)) if singing else 0.0
        frames.append({
            "t": round(t, 3),
            "v_rms": round(v_rms, 3),
            "a_rms": round(a_rms, 3),
            "f0": round(f0, 1),
            "breath": round(breath, 3),
            "energy": round(energy, 3),
        })

    return {
        "title": "Scarborough Fair",
        "artist": "Aero",
        "duration": duration,
        "sample_rate": 22050,
        "fps": fps,
        "scenes": scenes,
        "phrases": phrases,
        "words": words,
        "frames": frames,
        "_mock": True,
    }


def generate_mock_wav_bytes(duration_sec=102.0, sr=8000):
    """Generate a compact valid WAV (gentle quiet D-Dorian harp-pad placeholder) strictly for --mock visual previews."""
    buf = io.BytesIO()
    n_samples = int(duration_sec * sr)
    # 8-bit unsigned PCM keeps a 102s mock preview WAV compact (~816 KB) while remaining 100% standard WAV
    freqs = (146.83, 220.0, 293.66, 349.23)  # Dm chord (D3, A3, D4, F4)
    samples = bytearray(n_samples)
    two_pi = 2.0 * math.pi
    for i in range(n_samples):
        t = i / float(sr)
        env = min(1.0, t / 1.5) * min(1.0, max(0.0, (duration_sec - t) / 3.0))
        pulse = 0.55 + 0.45 * math.sin(two_pi * (t / 1.55))
        val = 0.0
        for fi, f in enumerate(freqs):
            val += math.sin(two_pi * f * t) * (0.28 / (fi + 1))
        val = val * env * pulse * 0.35
        samples[i] = max(0, min(255, int(128 + val * 110)))

    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)
        wf.setframerate(sr)
        wf.writeframes(bytes(samples))
    return buf.getvalue()


def escape_inline_script(js_text):
    """Prevent accidental </script> sequence inside embedded JS/JSON."""
    return js_text.replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")


def build_html_document(art_engine_js, art_scenes_js, timeline_obj, wav_b64, is_mock=False):
    timeline_json = escape_inline_script(json.dumps(timeline_obj, separators=(",", ":")))
    engine_safe = escape_inline_script(art_engine_js)
    scenes_safe = escape_inline_script(art_scenes_js)
    title_str = str(timeline_obj.get("title", "Scarborough Fair"))
    artist_str = str(timeline_obj.get("artist", "Aero"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_str} — Sung by {artist_str}</title>
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-user-select: none;
    user-select: none;
  }}
  html, body {{
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #e9decb;
    font-family: Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif;
    color: #241c17;
  }}
  #stage {{
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
  }}
  #artCanvas {{
    display: block;
    width: 100%;
    height: 100%;
    cursor: default;
  }}
  #artCanvas.clickable {{
    cursor: pointer;
  }}
  /* Minimal vintage parchment-ink transport bar — completely disappears during playback */
  #controls {{
    position: fixed;
    left: 50%;
    bottom: 14px;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 7px 20px;
    border-radius: 999px;
    background: radial-gradient(ellipse at center, rgba(244, 236, 224, 0.88) 0%, rgba(235, 223, 203, 0.78) 100%);
    border: 1px solid rgba(91, 66, 48, 0.28);
    box-shadow: 0 3px 16px rgba(36, 28, 23, 0.12);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.45s ease;
    z-index: 10;
  }}
  #controls.visible {{
    opacity: 1;
    pointer-events: auto;
  }}
  #controls.force-hidden {{
    opacity: 0 !important;
    pointer-events: none !important;
    transition: none !important;
  }}
  .ink-btn {{
    background: none;
    border: none;
    color: #241c17;
    font-family: Georgia, "Palatino Linotype", serif;
    font-size: 14px;
    line-height: 1;
    padding: 4px 6px;
    cursor: pointer;
    opacity: 0.78;
    transition: opacity 0.2s ease, transform 0.2s ease;
  }}
  .ink-btn:hover {{
    opacity: 1;
    transform: scale(1.08);
  }}
  #scrubberWrap {{
    position: relative;
    width: min(360px, 42vw);
    height: 18px;
    display: flex;
    align-items: center;
    cursor: pointer;
  }}
  #scrubberTrack {{
    width: 100%;
    height: 1.5px;
    background: rgba(91, 66, 48, 0.34);
    border-radius: 2px;
    position: relative;
  }}
  #scrubberFill {{
    position: absolute;
    left: 0;
    top: -0.5px;
    height: 2.5px;
    width: 0%;
    background: #3d2c20;
    border-radius: 2px;
  }}
  #scrubberDot {{
    position: absolute;
    top: 50%;
    left: 0%;
    width: 9px;
    height: 9px;
    margin-left: -4.5px;
    margin-top: -4.5px;
    border-radius: 50%;
    background: #241c17;
    box-shadow: 0 0 0 2px rgba(244, 236, 224, 0.85);
  }}
  #timeReadout {{
    font-size: 12.5px;
    font-style: italic;
    letter-spacing: 0.04em;
    color: #5b4230;
    min-width: 78px;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }}
</style>
</head>
<body>
<div id="stage">
  <canvas id="artCanvas" aria-label="{title_str} — Hand-drawn animated film"></canvas>
  <div id="controls" role="group" aria-label="Playback controls">
    <button id="playPauseBtn" class="ink-btn" title="Play / Pause (Space)">&#9654;</button>
    <div id="scrubberWrap" title="Seek">
      <div id="scrubberTrack">
        <div id="scrubberFill"></div>
        <div id="scrubberDot"></div>
      </div>
    </div>
    <span id="timeReadout">0:00 / 0:00</span>
    <button id="replayBtn" class="ink-btn" title="Replay (R)">&#8634;</button>
  </div>
</div>

<audio id="songAudio" preload="auto" src="data:audio/wav;base64,{wav_b64}"></audio>

<script id="timeline-data" type="application/json">{timeline_json}</script>
<script>
{engine_safe}
</script>
<script>
{scenes_safe}
</script>
<script>
(function () {{
  'use strict';

  const IS_MOCK_AUDIO = {str(bool(is_mock)).lower()};
  const timeline = JSON.parse(document.getElementById('timeline-data').textContent);
  const canvas = document.getElementById('artCanvas');
  const ctx = canvas.getContext('2d');
  const audio = document.getElementById('songAudio');
  const controlsEl = document.getElementById('controls');
  const playPauseBtn = document.getElementById('playPauseBtn');
  const replayBtn = document.getElementById('replayBtn');
  const scrubberWrap = document.getElementById('scrubberWrap');
  const scrubberFill = document.getElementById('scrubberFill');
  const scrubberDot = document.getElementById('scrubberDot');
  const timeReadout = document.getElementById('timeReadout');

  let viewW = 1280;
  let viewH = 720;
  let dpr = 1;
  let mode = 'cover'; // 'cover' | 'play' | 'ended'
  let coverClock = 0;
  let currentTime = 0;
  let lastRafTs = 0;
  let hoverPlay = false;
  let lastLayout = null;
  let controlsTimer = null;
  let forceHideControls = false;
  let isManualRender = false;
  let audioErrorMsg = null;

  audio.addEventListener('error', function () {{
    audioErrorMsg = audio.error ? ('Audio error code ' + audio.error.code) : 'Unknown audio error';
  }});

  function getDuration() {{
    const ad = (audio.duration && isFinite(audio.duration) && audio.duration > 0) ? audio.duration : 0;
    const td = (timeline && timeline.duration > 0) ? timeline.duration : 102;
    return ad || td;
  }}

  function formatTime(sec) {{
    const s = Math.max(0, Math.floor(sec || 0));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return m + ':' + (r < 10 ? '0' : '') + r;
  }}

  function resizeCanvas() {{
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    viewW = Math.max(320, window.innerWidth || 1280);
    viewH = Math.max(200, window.innerHeight || 720);
    canvas.width = Math.round(viewW * dpr);
    canvas.height = Math.round(viewH * dpr);
    canvas.style.width = viewW + 'px';
    canvas.style.height = viewH + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }}

  function updateControlsUI() {{
    if (forceHideControls || mode === 'cover') {{
      controlsEl.classList.remove('visible');
      return;
    }}
    const dur = getDuration();
    const frac = Math.max(0, Math.min(1, currentTime / (dur || 1)));
    scrubberFill.style.width = (frac * 100).toFixed(2) + '%';
    scrubberDot.style.left = (frac * 100).toFixed(2) + '%';
    timeReadout.textContent = formatTime(currentTime) + ' / ' + formatTime(dur);
    playPauseBtn.innerHTML = (audio.paused || mode === 'ended') ? '&#9654;' : '&#10074;&#10074;';
  }}

  function revealControlsBriefly() {{
    if (forceHideControls || mode === 'cover') return;
    controlsEl.classList.add('visible');
    if (controlsTimer) clearTimeout(controlsTimer);
    if (!audio.paused && mode === 'play') {{
      controlsTimer = setTimeout(function () {{
        if (!audio.paused && mode === 'play') controlsEl.classList.remove('visible');
      }}, 2400);
    }}
  }}

  function drawCurrentFrame() {{
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lastLayout = window.ArtScenes.renderFilmFrame(ctx, viewW, viewH, {{
      mode: mode,
      t: mode === 'cover' ? coverClock : currentTime,
      timeline: timeline,
      hoverPlay: hoverPlay
    }});
  }}

  function startPlayback(fromStart) {{
    isManualRender = false;
    forceHideControls = false;
    controlsEl.classList.remove('force-hidden');
    if (fromStart || mode === 'ended') {{
      audio.currentTime = 0;
      currentTime = 0;
    }}
    mode = 'play';
    canvas.classList.remove('clickable');
    const p = audio.play();
    if (p && typeof p.catch === 'function') {{
      p.catch(function () {{
        // Browser autoplay policy blocked; remain in paused play view with controls visible
        controlsEl.classList.add('visible');
      }});
    }}
    updateControlsUI();
    revealControlsBriefly();
  }}

  function togglePlayPause() {{
    if (mode === 'cover' || mode === 'ended') {{
      startPlayback(true);
      return;
    }}
    if (audio.paused) {{
      isManualRender = false;
      audio.play().catch(function () {{}});
      revealControlsBriefly();
    }} else {{
      audio.pause();
      controlsEl.classList.add('visible');
    }}
    updateControlsUI();
  }}

  function seekTo(sec) {{
    const dur = getDuration();
    const clamped = Math.max(0, Math.min(dur, sec));
    currentTime = clamped;
    try {{
      audio.currentTime = clamped;
    }} catch (e) {{}}
    if (mode === 'cover' || mode === 'ended') mode = 'play';
    drawCurrentFrame();
    updateControlsUI();
  }}

  audio.addEventListener('ended', function () {{
    mode = 'ended';
    currentTime = getDuration();
    canvas.classList.add('clickable');
    controlsEl.classList.add('visible');
    updateControlsUI();
    drawCurrentFrame();
  }});

  audio.addEventListener('loadedmetadata', function () {{
    updateControlsUI();
  }});

  // Pointer & keyboard interaction
  function isOverCoverPlay(clientX, clientY) {{
    if (mode !== 'cover' || !lastLayout || !lastLayout.playBtnScreen) return false;
    const b = lastLayout.playBtnScreen;
    return Math.hypot(clientX - b.x, clientY - b.y) <= b.r * 1.45;
  }}

  canvas.addEventListener('mousemove', function (ev) {{
    if (mode === 'cover') {{
      const over = isOverCoverPlay(ev.clientX, ev.clientY);
      if (over !== hoverPlay) {{
        hoverPlay = over;
        canvas.classList.toggle('clickable', true);
      }}
    }} else {{
      revealControlsBriefly();
    }}
  }});

  canvas.addEventListener('click', function () {{
    if (mode === 'cover') {{
      startPlayback(true);
    }} else if (mode === 'ended') {{
      startPlayback(true);
    }} else {{
      revealControlsBriefly();
    }}
  }});

  playPauseBtn.addEventListener('click', function (ev) {{
    ev.stopPropagation();
    togglePlayPause();
  }});

  replayBtn.addEventListener('click', function (ev) {{
    ev.stopPropagation();
    startPlayback(true);
  }});

  scrubberWrap.addEventListener('click', function (ev) {{
    ev.stopPropagation();
    const rect = scrubberWrap.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / (rect.width || 1)));
    seekTo(frac * getDuration());
    revealControlsBriefly();
  }});

  window.addEventListener('keydown', function (ev) {{
    if (ev.code === 'Space') {{
      ev.preventDefault();
      togglePlayPause();
    }} else if (ev.code === 'ArrowRight') {{
      ev.preventDefault();
      seekTo(currentTime + 5);
      revealControlsBriefly();
    }} else if (ev.code === 'ArrowLeft') {{
      ev.preventDefault();
      seekTo(currentTime - 5);
      revealControlsBriefly();
    }} else if (ev.key === 'r' || ev.key === 'R') {{
      startPlayback(true);
    }}
  }});

  window.addEventListener('resize', function () {{
    resizeCanvas();
    drawCurrentFrame();
  }});

  // Main animation loop
  function tick(ts) {{
    if (!lastRafTs) lastRafTs = ts;
    const dt = Math.min(0.1, (ts - lastRafTs) / 1000);
    lastRafTs = ts;

    if (!isManualRender) {{
      if (mode === 'cover') {{
        coverClock += dt;
        drawCurrentFrame();
      }} else if (mode === 'play') {{
        if (!audio.paused && !audio.ended) {{
          // Smooth clock follow tied tightly to audio.currentTime
          const at = audio.currentTime;
          if (Math.abs(at - currentTime) > 0.14 || at < currentTime) {{
            currentTime = at;
          }} else {{
            currentTime = currentTime + (at - currentTime) * 0.45 + dt * 0.55;
          }}
        }}
        drawCurrentFrame();
        updateControlsUI();
      }}
    }}
    window.requestAnimationFrame(tick);
  }}

  // Deterministic preview & verification API for @visual-critic & tooling
  window.__AERO_ART__ = {{
    renderAt: function (seconds) {{
      audio.pause();
      isManualRender = true;
      forceHideControls = true;
      controlsEl.classList.add('force-hidden');
      controlsEl.classList.remove('visible');
      if (seconds === 'cover' || seconds < 0) {{
        mode = 'cover';
        coverClock = 1.6;
        hoverPlay = false;
      }} else {{
        mode = 'play';
        currentTime = Math.max(0, Math.min(getDuration(), Number(seconds) || 0));
      }}
      drawCurrentFrame();
      const sw = window.ArtScenes.getSceneWeights(timeline, currentTime);
      const ph = window.ArtScenes.getActivePhrase(timeline, currentTime);
      return {{
        mode: mode,
        t: mode === 'cover' ? coverClock : currentTime,
        scene: mode === 'cover' ? 'cover' : (sw.primary ? sw.primary.id : null),
        phrase: ph && ph.phrase ? ph.phrase.text : null,
        width: viewW,
        height: viewH
      }};
    }},
    showCover: function () {{
      return window.__AERO_ART__.renderAt('cover');
    }},
    seekTo: function (seconds) {{
      seekTo(Number(seconds) || 0);
      return currentTime;
    }},
    play: function () {{
      startPlayback(false);
    }},
    pause: function () {{
      audio.pause();
      updateControlsUI();
    }},
    getInfo: function () {{
      const sw = window.ArtScenes.getSceneWeights(timeline, currentTime);
      return {{
        title: timeline.title,
        artist: timeline.artist,
        duration: timeline.duration,
        scenes: timeline.scenes || [],
        phrasesCount: (timeline.phrases || []).length,
        wordsCount: (timeline.words || []).length,
        framesCount: (timeline.frames || []).length,
        audioReady: audio.readyState >= 1,
        audioDuration: (audio.duration && isFinite(audio.duration)) ? Number(audio.duration.toFixed(3)) : null,
        audioError: audioErrorMsg,
        isMockAudio: IS_MOCK_AUDIO,
        width: viewW,
        height: viewH,
        currentTime: currentTime,
        currentScene: mode === 'cover' ? 'cover' : (sw.primary ? sw.primary.id : null),
        mode: mode
      }};
    }}
  }};

  // Initial boot (honors optional ?t=seconds or ?cover=1 query params for clean headless capture)
  resizeCanvas();
  canvas.classList.add('clickable');
  const params = new URLSearchParams(window.location.search);
  if (params.has('cover')) {{
    window.__AERO_ART__.showCover();
  }} else if (params.has('t')) {{
    window.__AERO_ART__.renderAt(parseFloat(params.get('t')));
  }} else {{
    drawCurrentFrame();
  }}
  window.requestAnimationFrame(tick);
}})();
</script>
</body>
</html>
"""
    return html


def verify_zero_external_urls(html_text):
    """Fail if any external http:// or https:// reference exists in the deliverable HTML."""
    matches = re.findall(r"https?://[^\s\"'<>]+", html_text)
    return matches


def main():
    parser = argparse.ArgumentParser(description="Package Aero Sings Scarborough Fair into a single standalone HTML file.")
    parser.add_argument("--mock", action="store_true", help="Use mock timeline + mock WAV if real build artifacts are not present yet.")
    parser.add_argument("--out", default=OUT_HTML, help="Output standalone HTML path.")
    args = parser.parse_args()

    engine_path = os.path.join(ROOT_DIR, "art_engine.js")
    scenes_path = os.path.join(ROOT_DIR, "art_scenes.js")
    timeline_path = os.path.join(BUILD_DIR, "timeline.json")
    wav_path = os.path.join(BUILD_DIR, "song_full.wav")

    for req in (engine_path, scenes_path):
        if not os.path.exists(req):
            print(f"ERROR: Missing required art file: {req}", file=sys.stderr)
            sys.exit(1)

    with open(engine_path, "r", encoding="utf-8") as f:
        art_engine_js = f.read()
    with open(scenes_path, "r", encoding="utf-8") as f:
        art_scenes_js = f.read()

    using_mock = False
    if os.path.exists(timeline_path) and os.path.exists(wav_path):
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline_obj = json.load(f)
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        print(f"Loaded REAL audio artifacts: {timeline_path} & {wav_path} ({len(wav_bytes):,} bytes)")
    elif args.mock:
        using_mock = True
        timeline_obj = generate_mock_timeline()
        wav_bytes = generate_mock_wav_bytes(duration_sec=timeline_obj["duration"])
        print(f"Using --mock preview timeline ({timeline_obj['duration']}s) and mock WAV ({len(wav_bytes):,} bytes)")
    else:
        print(
            f"ERROR: Missing {timeline_path} or {wav_path}. Run voice pipeline first or pass --mock for visual preview.",
            file=sys.stderr,
        )
        sys.exit(1)

    wav_b64 = base64.b64encode(wav_bytes).decode("ascii")
    html = build_html_document(art_engine_js, art_scenes_js, timeline_obj, wav_b64, is_mock=using_mock)

    ext_urls = verify_zero_external_urls(html)
    if ext_urls:
        print(f"ERROR: Found forbidden external URLs in packaged HTML: {ext_urls}", file=sys.stderr)
        sys.exit(2)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(args.out) / 1024.0
    print(f"Packaged standalone HTML: {args.out} ({size_kb:.1f} KB, zero external URLs, mock={using_mock})")
    print(f"Scenes: {[s.get('id') for s in timeline_obj.get('scenes', [])]} | Phrases: {len(timeline_obj.get('phrases', []))} | Words: {len(timeline_obj.get('words', []))} | Frames: {len(timeline_obj.get('frames', []))}")


if __name__ == "__main__":
    main()
