/* ============================================================================
 * art_scenes.js — 5-Act Emotional Hand-Drawn Short Film Choreography
 * "Aero Sings Scarborough Fair" (Round 2 Fine-Art Master Upgrade)
 *
 * Pure Canvas 2D storytelling synced to timeline.json (scenes, phrases, words,
 * herb cues, vocal RMS, accompaniment RMS, F0 pitch, breath, and energy).
 * Zero external libraries, zero external assets, zero SVG.
 * Logical studio sheet: 1280 x 720.
 * ========================================================================== */
(function (global) {
  'use strict';

  const E = global.ArtEngine;
  const P = E.PALETTE;
  const clamp = E.clamp;
  const lerp = E.lerp;
  const smoothstep = E.smoothstep;

  const LOGICAL_W = 1280;
  const LOGICAL_H = 720;

  // ==========================================================================
  // 1. TIMELINE & AUDIO TELEMETRY SAMPLER
  // ==========================================================================
  function sampleFrameTelemetry(timeline, t) {
    const frames = timeline && timeline.frames;
    if (!frames || !frames.length) {
      return {
        v_rms: 0.25 + 0.12 * Math.sin(t * 2.1),
        a_rms: 0.22 + 0.08 * Math.sin(t * 3.1),
        f0: 220,
        breath: 0.15 + 0.1 * Math.sin(t * 0.8),
        energy: 0.3
      };
    }
    if (t <= frames[0].t) return frames[0];
    const last = frames[frames.length - 1];
    if (t >= last.t) return last;

    let lo = 0;
    let hi = frames.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (frames[mid].t <= t) lo = mid; else hi = mid;
    }
    const a = frames[lo];
    const b = frames[hi];
    const k = clamp((t - a.t) / ((b.t - a.t) || 1e-4), 0, 1);
    return {
      v_rms: lerp(a.v_rms || 0, b.v_rms || 0, k),
      a_rms: lerp(a.a_rms || 0, b.a_rms || 0, k),
      f0:    (a.f0 > 0 && b.f0 > 0) ? lerp(a.f0, b.f0, k) : (a.f0 || b.f0 || 0),
      breath: lerp(a.breath || 0, b.breath || 0, k),
      energy: lerp(a.energy || 0, b.energy || 0, k)
    };
  }

  function getSceneWeights(timeline, t) {
    const scenes = (timeline && timeline.scenes && timeline.scenes.length) ? timeline.scenes : [
      { id: 'intro',  start: 0,  end: 6.2, label: 'I · The Twilight Path' },
      { id: 'verse1', start: 6.2, end: 31.6, label: 'II · Parsley, Sage, Rosemary & Thyme' },
      { id: 'verse2', start: 31.6, end: 56.9, label: 'III · The Cambric Shirt' },
      { id: 'verse3', start: 56.9, end: 82.0, label: 'IV · Between Salt Water & Sea Strand' },
      { id: 'coda',   start: 82.0, end: 95.8, label: 'V · True Love of Mine' },
      { id: 'outro',  start: 95.8, end: 102.9, label: 'V · True Love of Mine' }
    ];

    const merged = [];
    for (let i = 0; i < scenes.length; i++) {
      const s = scenes[i];
      if (s.id === 'outro' && merged.length && merged[merged.length - 1].id === 'coda') {
        merged[merged.length - 1] = {
          id: 'coda',
          start: merged[merged.length - 1].start,
          codaEnd: merged[merged.length - 1].end,
          end: s.end,
          mood: merged[merged.length - 1].mood || s.mood,
          label: merged[merged.length - 1].label || 'V · True Love of Mine'
        };
      } else {
        merged.push({
          id: s.id,
          start: s.start,
          codaEnd: s.end,
          end: s.end,
          mood: s.mood || '',
          label: s.label || ''
        });
      }
    }

    const fade = 1.8;
    const active = [];
    let primary = merged[0];

    for (let i = 0; i < merged.length; i++) {
      const s = merged[i];
      const inStart = i === 0 ? -1 : s.start - fade * 0.5;
      const inEnd   = i === 0 ? 0.01 : s.start + fade * 0.5;
      const outStart = i === merged.length - 1 ? s.end + 999 : s.end - fade * 0.5;
      const outEnd   = i === merged.length - 1 ? s.end + 999 : s.end + fade * 0.5;

      const wIn  = i === 0 ? 1 : smoothstep(inStart, inEnd, t);
      const wOut = i === merged.length - 1 ? 1 : (1 - smoothstep(outStart, outEnd, t));
      const w = clamp(wIn * wOut, 0, 1);

      if (t >= s.start && (t < s.end || i === merged.length - 1)) primary = s;
      if (w > 0.008) {
        active.push({
          scene: s,
          weight: w,
          localT: Math.max(0, t - s.start),
          progress: clamp((t - s.start) / Math.max(0.1, s.end - s.start), 0, 1)
        });
      }
    }

    let sum = 0;
    for (let i = 0; i < active.length; i++) sum += active[i].weight;
    if (sum > 1) {
      for (let i = 0; i < active.length; i++) active[i].weight /= sum;
    }
    return { active: active, primary: primary, all: merged };
  }

  function getHerbTriggersForScene(timeline, sceneObj) {
    const out = { parsley: null, sage: null, rosemary: null, thyme: null };
    const s0 = sceneObj.start;
    const s1 = sceneObj.end;
    const words = (timeline && timeline.words) || [];
    for (let i = 0; i < words.length; i++) {
      const w = words[i];
      if (w.start >= s0 - 0.5 && w.start <= s1 + 0.5) {
        let h = w.herb;
        if (!h && w.word) {
          const clean = w.word.toLowerCase().replace(/[^a-z]/g, '');
          if (clean === 'parsley' || clean === 'sage' || clean === 'rosemary' || clean === 'thyme') h = clean;
        }
        if (h && out[h] === null) out[h] = w.start;
      }
    }
    const dur = Math.max(8, s1 - s0);
    if (out.parsley  === null) out.parsley  = s0 + dur * 0.24;
    if (out.sage     === null) out.sage     = s0 + dur * 0.30;
    if (out.rosemary === null) out.rosemary = s0 + dur * 0.36;
    if (out.thyme    === null) out.thyme    = s0 + dur * 0.43;
    return out;
  }

  function getActivePhrase(timeline, t) {
    const phrases = (timeline && timeline.phrases) || [];
    const words = (timeline && timeline.words) || [];
    if (!phrases.length) return null;

    let best = null;
    for (let i = 0; i < phrases.length; i++) {
      const p = phrases[i];
      if (t >= p.start - 0.55 && t <= p.end + 0.85) {
        best = p;
        if (t >= p.start && t <= p.end) break;
      }
    }
    if (!best) return null;

    const fadeIn = smoothstep(best.start - 0.52, best.start + 0.18, t);
    const fadeOut = 1 - smoothstep(best.end + 0.15, best.end + 0.82, t);
    const alpha = clamp(fadeIn * fadeOut, 0, 1);

    const pWords = [];
    for (let i = 0; i < words.length; i++) {
      if (words[i].phrase_index === best.index) pWords.push(words[i]);
    }
    return { phrase: best, alpha: alpha, words: pWords };
  }

  // ==========================================================================
  // 2. HAND-DRAWN BOTANICAL HERBARIUM ILLUSTRATIONS (Lush Fine-Art Ink & Wash)
  // ==========================================================================
  function drawParsley(ctx, x, y, scale, rot, unfurl, alpha, t, boil, seed) {
    if (unfurl <= 0.01 || alpha <= 0.01) return;
    const sway = Math.sin(t * 1.45 + seed * 0.7) * 0.055;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot + sway);
    ctx.scale(scale, scale);

    const stemPts = [[0, 0], [3, -36], [-4, -78], [2, -116]];
    E.pencilStroke(ctx, stemPts, {
      medium: 'ink', color: P.oliveMoss, width: 2.0, alpha: alpha * 0.86,
      seed: seed + 1, boil: boil, progress: clamp(unfurl * 1.6, 0, 1)
    });

    const branches = [
      { base: [1, -38], tip: [-42, -72], ang: -0.72, delay: 0.14, sz: 1.05 },
      { base: [-1, -64], tip: [46, -92],  ang: 0.65,  delay: 0.24, sz: 1.0 },
      { base: [-2, -84], tip: [-30, -124], ang: -0.34, delay: 0.34, sz: 0.92 },
      { base: [1, -100], tip: [12, -142], ang: 0.12,  delay: 0.42, sz: 1.08 }
    ];

    for (let b = 0; b < branches.length; b++) {
      const br = branches[b];
      const bp = smoothstep(br.delay, br.delay + 0.44, unfurl);
      if (bp <= 0.02) continue;
      E.pencilStroke(ctx, [br.base, [(br.base[0] + br.tip[0]) * 0.5, (br.base[1] + br.tip[1]) * 0.5 - 6], br.tip], {
        medium: 'ink', color: P.oliveMoss, width: 1.25, alpha: alpha * 0.8 * bp,
        seed: seed + 20 + b * 7, boil: boil, progress: bp
      });

      const lp = smoothstep(br.delay + 0.1, br.delay + 0.52, unfurl);
      if (lp <= 0.02) continue;
      ctx.save();
      ctx.translate(br.tip[0], br.tip[1]);
      ctx.rotate(br.ang);
      ctx.scale(br.sz * (0.35 + 0.65 * lp), br.sz * (0.35 + 0.65 * lp));

      const lobes = [-0.64, 0, 0.64];
      for (let l = 0; l < lobes.length; l++) {
        ctx.save();
        ctx.rotate(lobes[l]);
        const leafPoly = [
          [0, 2], [-7, -8], [-13, -16], [-9, -22], [-12, -29],
          [-4, -28], [0, -36], [5, -28], [12, -29], [9, -21],
          [13, -15], [7, -8]
        ];
        E.watercolorPolygon(ctx, leafPoly, l === 1 ? P.sage : P.sageLight, {
          alpha: alpha * 0.60 * lp, gradColor: P.oliveMoss, edgeRim: 0.45
        });
        E.pencilStroke(ctx, leafPoly.concat([[0, 2]]), {
          medium: 'ink', color: P.pineDark, width: 0.9, alpha: alpha * 0.74 * lp,
          seed: seed + 140 + b * 13 + l * 5, boil: boil
        });
        E.pencilStroke(ctx, [[0, 0], [0, -26]], {
          medium: 'ink', color: P.pineDark, width: 0.6, alpha: alpha * 0.5 * lp,
          seed: seed + 180 + b * 11 + l, boil: boil
        });
        ctx.restore();
      }
      ctx.restore();
    }
    ctx.restore();
  }

  function drawSage(ctx, x, y, scale, rot, unfurl, alpha, t, boil, seed) {
    if (unfurl <= 0.01 || alpha <= 0.01) return;
    const sway = Math.sin(t * 1.2 + seed) * 0.05;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot + sway);
    ctx.scale(scale, scale);

    const stem = [[0, 0], [6, -42], [2, -88], [-8, -134], [-14, -166]];
    E.pencilStroke(ctx, stem, {
      medium: 'graphite', color: P.sepia, width: 2.0, alpha: alpha * 0.84,
      seed: seed + 2, boil: boil, progress: clamp(unfurl * 1.5, 0, 1)
    });

    const leaves = [
      { px: 4, py: -36, ang: -0.95, len: 50, wid: 15, d: 0.12 },
      { px: 5, py: -42, ang:  0.88, len: 48, wid: 14, d: 0.16 },
      { px: 3, py: -78, ang: -0.78, len: 56, wid: 16, d: 0.26 },
      { px: 2, py: -84, ang:  0.76, len: 52, wid: 15, d: 0.30 },
      { px: -5, py: -118, ang: -0.62, len: 46, wid: 13, d: 0.40 },
      { px: -6, py: -122, ang:  0.60, len: 42, wid: 12, d: 0.44 },
      { px: -12, py: -156, ang: -0.14, len: 40, wid: 12, d: 0.54 }
    ];

    for (let i = 0; i < leaves.length; i++) {
      const lf = leaves[i];
      const lp = smoothstep(lf.d, lf.d + 0.42, unfurl);
      if (lp <= 0.02) continue;
      ctx.save();
      ctx.translate(lf.px, lf.py);
      ctx.rotate(lf.ang);
      ctx.scale(0.32 + 0.68 * lp, 0.32 + 0.68 * lp);

      const L = lf.len, W = lf.wid;
      const poly = [
        [0, 0], [-W * 0.72, -L * 0.25], [-W, -L * 0.56],
        [-W * 0.52, -L * 0.84], [0, -L], [W * 0.52, -L * 0.84],
        [W, -L * 0.56], [W * 0.72, -L * 0.25]
      ];
      E.watercolorPolygon(ctx, poly, i % 2 === 0 ? P.sageLight : P.sage, {
        alpha: alpha * 0.58 * lp, gradColor: P.lavenderMist, edgeRim: 0.45
      });
      E.pencilStroke(ctx, poly.concat([[0, 0]]), {
        medium: 'ink', color: P.oliveMoss, width: 0.95, alpha: alpha * 0.72 * lp,
        seed: seed + 260 + i * 11, boil: boil
      });
      E.pencilStroke(ctx, [[0, -2], [0, -L * 0.88]], {
        medium: 'ink', color: P.oliveMoss, width: 0.7, alpha: alpha * 0.55 * lp,
        seed: seed + 300 + i * 5, boil: boil
      });
      E.chalkHighlight(ctx, [[-W * 0.45, -L * 0.28], [-W * 0.65, -L * 0.58], [-W * 0.22, -L * 0.84]], {
        width: 1.1, alpha: alpha * 0.36 * lp, seed: seed + 340 + i, boil: boil
      });
      ctx.restore();
    }
    ctx.restore();
  }

  function drawRosemary(ctx, x, y, scale, rot, unfurl, alpha, t, boil, seed) {
    if (unfurl <= 0.01 || alpha <= 0.01) return;
    const sway = Math.sin(t * 1.35 + seed * 1.3) * 0.055;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot + sway);
    ctx.scale(scale, scale);

    const stemPts = [[0, 0], [-5, -45], [4, -98], [-2, -150], [5, -190]];
    const stemS = E.sampleSpline(stemPts, 6, false);
    E.pencilStroke(ctx, stemPts, {
      medium: 'ink', color: P.rawUmber, width: 2.2, alpha: alpha * 0.88,
      seed: seed + 3, boil: boil, progress: clamp(unfurl * 1.45, 0, 1)
    });

    const needleNodes = 17;
    for (let i = 1; i < needleNodes; i++) {
      const frac = i / needleNodes;
      const np = smoothstep(frac * 0.60, frac * 0.60 + 0.36, unfurl);
      if (np <= 0.02) continue;

      const idx = Math.min(stemS.length - 1, Math.floor(frac * (stemS.length - 1)));
      const pt = stemS[idx];
      const len = (25 + Math.sin(frac * Math.PI) * 18) * np;

      for (let side = -1; side <= 1; side += 2) {
        const ang = -Math.PI * 0.5 + side * (0.58 + (i % 3) * 0.14);
        const mx = pt.x + Math.cos(ang) * len * 0.55;
        const my = pt.y + Math.sin(ang) * len * 0.55 - 3;
        const ex = pt.x + Math.cos(ang - side * 0.18) * len;
        const ey = pt.y + Math.sin(ang - side * 0.18) * len;

        E.pencilStroke(ctx, [[pt.x, pt.y], [mx, my], [ex, ey]], {
          medium: 'ink', color: i % 2 === 0 ? P.pineDark : P.sage,
          width: 2.0, alpha: alpha * 0.78 * np,
          seed: seed + 400 + i * 13 + side * 5, boil: boil
        });
      }

      if (i % 4 === 2 && i > 3 && i < needleNodes - 2) {
        const bx = pt.x + (i % 8 === 2 ? -8 : 8);
        const by = pt.y - 6;
        E.watercolorBloom(ctx, bx, by, 7.5 * np, 6.0 * np, P.lavenderMist, {
          alpha: alpha * 0.62 * np, seed: seed + 510 + i, dabs: 1, multiply: false
        });
        E.watercolorBloom(ctx, bx + 1.5, by - 1.5, 4.2 * np, 3.8 * np, P.indigo, {
          alpha: alpha * 0.52 * np, seed: seed + 520 + i, dabs: 1, multiply: false
        });
      }
    }
    ctx.restore();
  }

  function drawThyme(ctx, x, y, scale, rot, unfurl, alpha, t, boil, seed) {
    if (unfurl <= 0.01 || alpha <= 0.01) return;
    const sway = Math.sin(t * 1.55 + seed * 0.9) * 0.06;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot + sway);
    ctx.scale(scale, scale);

    const twigs = [
      [[0, 0], [-6, -38], [-19, -78], [-28, -118]],
      [[0, -14], [11, -52], [20, -96], [28, -134]],
      [[-4, -38], [2, -80], [-4, -124], [3, -160]]
    ];

    for (let tw = 0; tw < twigs.length; tw++) {
      const pts = twigs[tw];
      const sp = E.sampleSpline(pts, 7, false);
      const tp = smoothstep(tw * 0.12, tw * 0.12 + 0.55, unfurl);
      if (tp <= 0.02) continue;

      E.pencilStroke(ctx, pts, {
        medium: 'ink', color: P.sepia, width: 1.25, alpha: alpha * 0.80 * tp,
        seed: seed + 600 + tw * 17, boil: boil, progress: tp
      });

      for (let i = 2; i < sp.length - 1; i += 2) {
        const frac = i / sp.length;
        if (frac > tp) break;
        const p = sp[i];
        const lA = alpha * 0.72 * smoothstep(frac - 0.12, frac + 0.1, tp);
        for (let side = -1; side <= 1; side += 2) {
          ctx.save();
          ctx.translate(p.x + side * (5.5 + (i % 3)), p.y - 3);
          ctx.rotate(side * 0.55);
          ctx.fillStyle = E.rgba(i % 4 === 0 ? P.oliveMoss : P.sage, lA);
          ctx.beginPath();
          ctx.ellipse(0, 0, 5.0, 2.8, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = E.rgba(P.pineDark, lA * 0.78);
          ctx.lineWidth = 0.6;
          ctx.stroke();
          ctx.restore();
        }
      }

      if (tp > 0.72) {
        const tip = sp[sp.length - 1];
        const flA = alpha * smoothstep(0.72, 1.0, tp);
        E.watercolorBloom(ctx, tip.x, tip.y - 4, 11, 9, P.roseDust, {
          alpha: flA * 0.65, seed: seed + 700 + tw * 11, dabs: 1, multiply: false
        });
        E.inkSplatter(ctx, tip.x, tip.y - 4, 8, 6, P.roseRust, flA * 0.68, seed + 730 + tw);
      }
    }
    ctx.restore();
  }

  function drawDriftingHerbs(ctx, t, alpha, windX, count, seed) {
    if (alpha <= 0.01) return;
    const rng = E.mulberry32(seed || 3311);
    ctx.save();
    for (let i = 0; i < count; i++) {
      const startX = rng() * LOGICAL_W;
      const startY = 80 + rng() * (LOGICAL_H - 180);
      const speed = 26 + rng() * 34;
      const phase = rng() * Math.PI * 2;
      const x = ((startX + t * speed * windX) % (LOGICAL_W + 140) + (LOGICAL_W + 140)) % (LOGICAL_W + 140) - 70;
      const y = startY + Math.sin(t * (0.9 + rng() * 0.8) + phase) * (24 + rng() * 26) + Math.cos(t * 0.4 + phase) * 12;
      const rot = t * (0.55 + rng() * 0.75) * (i % 2 ? 1 : -1) + phase;
      const sz = 4.5 + rng() * 5.2;
      const col = i % 4 === 0 ? P.sage : i % 4 === 1 ? P.oliveMoss : i % 4 === 2 ? P.sageLight : P.roseDust;

      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(rot);
      ctx.fillStyle = E.rgba(col, alpha * (0.42 + (i % 3) * 0.14));
      ctx.beginPath();
      ctx.ellipse(0, 0, sz, sz * 0.42, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = E.rgba(P.ironGall, alpha * 0.44);
      ctx.lineWidth = 0.6;
      ctx.beginPath();
      ctx.moveTo(-sz * 0.85, 0);
      ctx.lineTo(sz * 0.85, 0);
      ctx.stroke();
      ctx.restore();
    }
    ctx.restore();
  }

  function drawBotanicalMarginNote(ctx, label, x, y, alpha) {
    if (alpha <= 0.02) return;
    ctx.save();
    ctx.font = 'italic 16px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = E.rgba(P.ironGall, alpha * 0.76);
    ctx.fillText(label, x, y);
    ctx.restore();
  }

  // ==========================================================================
  // 3. SHARED FINE-ART LANDSCAPE ELEMENTS
  //    (Medieval Scarborough Fair Architectural Silhouette, Crescent Moon, Grass)
  // ==========================================================================
  function drawCrescentMoon(ctx, x, y, r, alpha, boil, seed) {
    if (alpha <= 0.01) return;
    ctx.save();
    // Luminous lifted paper glow around crescent moon
    const glow = ctx.createRadialGradient(x, y, r * 0.25, x, y, r * 4.8);
    glow.addColorStop(0, E.rgba(P.chalk, alpha * 0.68));
    glow.addColorStop(0.32, E.rgba(P.candleCore, alpha * 0.26));
    glow.addColorStop(1, E.rgba(P.paperLight, 0));
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, r * 4.8, 0, Math.PI * 2);
    ctx.fill();

    const pts = [];
    for (let i = 0; i <= 14; i++) {
      const a = -Math.PI * 0.62 + (i / 14) * Math.PI * 1.24;
      pts.push([x + Math.cos(a) * r, y + Math.sin(a) * r]);
    }
    for (let i = 14; i >= 0; i--) {
      const a = -Math.PI * 0.62 + (i / 14) * Math.PI * 1.24;
      pts.push([x + Math.cos(a) * r * 0.72 + r * 0.42, y + Math.sin(a) * r * 0.86 - r * 0.08]);
    }
    E.watercolorPolygon(ctx, pts, P.chalk, {
      alpha: alpha * 0.94, multiply: false, granulate: false, smooth: true
    });
    E.chalkHighlight(ctx, pts.slice(0, 15), {
      width: 1.8, alpha: alpha * 0.8, seed: (seed || 402) + 7, boil: boil
    });
    ctx.restore();
  }

  // Authentic Medieval Architectural Ink Silhouette of Scarborough Fair (NO caterpillar blob!)
  function drawScarboroughTown(ctx, cx, cy, scale, t, alpha, boil, seed) {
    if (alpha <= 0.01) return;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);

    // Warm golden atmospheric haze rising from the fairground lanterns
    const pulse = 0.88 + 0.12 * Math.sin(t * 2.2 + 0.5);
    E.watercolorBloom(ctx, 4, -14, 155, 66, P.amberGlow, {
      alpha: alpha * 0.34 * pulse, seed: seed + 1, dabs: 2, multiply: false
    });
    E.watercolorBloom(ctx, -10, -8, 95, 42, P.burntSienna, {
      alpha: alpha * 0.16 * pulse, seed: seed + 2, dabs: 1, multiply: true
    });

    // Helper for crisp architectural silhouette polygons (no corner rounding!)
    function archShape(pts, col, a) {
      ctx.fillStyle = E.rgba(col, a);
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      ctx.closePath();
      ctx.fill();
    }

    // 1. Distant Scarborough Castle Keep on right crag + Medieval Town Gables + Gothic Parish Spire
    const silhouette = [
      [-136, 16], [-128, 10], [-116, 2], [-104, 10], [-98, 10],
      [-94, -4], [-80, -14], [-66, -4], [-66, 8],
      [-58, 8], [-54, -8], [-42, -16], [-30, -8], [-28, 5],
      // Fairground pavilion tent with slender finial
      [-22, 5], [-10, -10], [2, 5],
      // Tall parish church nave & slender gothic steeple!
      [10, 5], [12, -14], [17, -14], [21, -54], [25, -14], [30, -14], [32, 4],
      // Timbered town houses descending toward harbor
      [38, 4], [42, -10], [56, -18], [70, -8], [72, 6],
      [80, 6], [86, -6], [96, -12], [108, -4], [112, 8],
      // Ruined castle keep on far headland crag (battlements)
      [118, 8], [120, -12], [125, -12], [125, -8], [130, -8], [130, -12], [136, -12], [138, 14],
      [142, 22], [-142, 22]
    ];
    archShape(silhouette, P.indigoDeep, alpha * 0.62);
    archShape(silhouette, P.sepia, alpha * 0.36);

    // Crisp fine dip-pen roofline highlights & tiny chimney stacks
    E.pencilStroke(ctx, [[-128, 10], [-116, 2], [-104, 10]], { medium: 'ink', color: P.ironGall, width: 1.0, alpha: alpha * 0.65, seed: seed + 10, boil: boil });
    E.pencilStroke(ctx, [[-94, -4], [-80, -14], [-66, -4]], { medium: 'ink', color: P.ironGall, width: 1.1, alpha: alpha * 0.72, seed: seed + 11, boil: boil });
    E.pencilStroke(ctx, [[-54, -8], [-42, -16], [-30, -8]], { medium: 'ink', color: P.ironGall, width: 1.1, alpha: alpha * 0.72, seed: seed + 12, boil: boil });
    E.pencilStroke(ctx, [[17, -14], [21, -56], [25, -14]], { medium: 'ink', color: P.charcoal, width: 1.2, alpha: alpha * 0.80, seed: seed + 13, boil: boil });
    E.pencilStroke(ctx, [[42, -10], [56, -18], [70, -8]], { medium: 'ink', color: P.ironGall, width: 1.1, alpha: alpha * 0.72, seed: seed + 14, boil: boil });

    // Tiny fluttering crimson-ochre fairground pennants atop pavilion tents!
    const pf = Math.sin(t * 3.4) * 3.5;
    E.pencilStroke(ctx, [[-10, -10], [-10, -21]], { medium: 'ink', color: P.ironGall, width: 0.9, alpha: alpha * 0.7, seed: seed + 15, boil: boil });
    E.pencilStroke(ctx, [[-10, -20], [1, -21 + pf * 0.4], [8, -19 + pf]], { medium: 'ink', color: P.burntSienna, width: 1.3, alpha: alpha * 0.75, seed: seed + 16, boil: boil });
    E.pencilStroke(ctx, [[96, -12], [96, -22]], { medium: 'ink', color: P.ironGall, width: 0.85, alpha: alpha * 0.65, seed: seed + 17, boil: boil });
    E.pencilStroke(ctx, [[96, -21], [106, -22 - pf * 0.4]], { medium: 'ink', color: P.burntSienna, width: 1.2, alpha: alpha * 0.7, seed: seed + 18, boil: boil });

    // Soft curling chimney smoke wisps
    for (let s = 0; s < 3; s++) {
      const sx = -78 + s * 68;
      const sy = -14 - (s === 1 ? 6 : 0);
      const drift = Math.sin(t * 0.65 + s * 2.1) * 9;
      E.dryBrushStreak(ctx, [
        [sx, sy], [sx + 8 + drift * 0.3, sy - 18], [sx + 20 + drift, sy - 38], [sx + 34 + drift * 1.3, sy - 54]
      ], 4.5, P.chalk, alpha * 0.28, seed + 30 + s * 7, boil);
    }

    // Crisp pinpoint candlelit medieval windows & warm fairground string lanterns!
    const lights = [
      [-115, 11, 2.2], [-86, 4, 2.8], [-76, 8, 2.4], [-48, 2, 3.0], [-36, 9, 2.3],
      [-14, 7, 3.2], [-4, 11, 2.6], [16, 4, 2.5], [27, 8, 2.8], [49, 2, 3.1],
      [62, 9, 2.6], [89, 5, 2.5], [102, 10, 2.2], [128, 3, 2.4]
    ];
    for (let i = 0; i < lights.length; i++) {
      const ln = lights[i];
      const flk = 0.76 + 0.24 * Math.sin(t * (2.8 + i * 0.61) + i * 1.7);
      const r = ln[2];
      const g = ctx.createRadialGradient(ln[0], ln[1], 0.4, ln[0], ln[1], r * 4.8);
      g.addColorStop(0, E.rgba(P.candleCore, alpha * 0.94 * flk));
      g.addColorStop(0.28, E.rgba(P.amberGlow, alpha * 0.48 * flk));
      g.addColorStop(1, E.rgba(P.burntSienna, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(ln[0], ln[1], r * 4.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = E.rgba(P.chalk, alpha * 0.95 * flk);
      ctx.fillRect(ln[0] - 1.1, ln[1] - 1.3, 2.2, 2.6);
    }

    // Soft feathered valley mist hugging the base of the town so it sits naturally in the hills
    E.mistVeil(ctx, 0, 24, 165, 22, alpha * 0.48, seed + 45);
    ctx.restore();
  }

  function drawWindsweptGrass(ctx, baseX, baseY, spreadW, count, wind, t, alpha, boil, seed, heightScale) {
    if (alpha <= 0.01) return;
    const rng = E.mulberry32(seed || 771);
    const hS = heightScale || 1.0;
    for (let i = 0; i < count; i++) {
      const gx = baseX + (rng() - 0.5) * spreadW;
      const gy = baseY + (rng() - 0.5) * 28;
      const h = (32 + rng() * 76) * hS;
      const bend = (16 + rng() * 34) * wind + Math.sin(t * (1.6 + rng() * 1.1) + i * 0.8) * (7 + rng() * 9);
      const col = i % 3 === 0 ? P.charcoal : i % 3 === 1 ? P.sepia : P.oliveMoss;
      E.pencilStroke(ctx, [
        [gx, gy],
        [gx + bend * 0.35, gy - h * 0.48],
        [gx + bend, gy - h]
      ], {
        medium: i % 2 === 0 ? 'ink' : 'graphite',
        color: col,
        width: 1.0 + rng() * 1.25,
        alpha: alpha * (0.50 + rng() * 0.40),
        seed: seed + i * 19,
        boil: boil,
        boilAmp: 0.55,
        taperStart: 0.04,
        taperEnd: 0.68
      });
    }
  }

  // ==========================================================================
  // 4. SCENE 0: COVER / READY TITLE PLATE (Museum Bookplate Edition)
  // ==========================================================================
  const COVER_PLAY_BTN = { x: 805, y: 455, r: 48 };

  function drawCoverScene(ctx, t, boil, hoverPlay) {
    // 1. Continuous luminous twilight sky wash (ZERO overlapping Venn ovals!)
    E.atmosphericSkyWash(ctx, LOGICAL_W, LOGICAL_H, [
      [0.0,  P.indigo, 0.34],
      [0.30, P.duskViolet, 0.22],
      [0.54, P.roseDust, 0.16],
      [0.72, P.ochre, 0.14],
      [1.0,  P.paperLight, 0.0]
    ], {
      y0: 0, y1: 540,
      clouds: [
        { x: 960, y: 155, rx: 320, ry: 120, color: P.indigo, alpha: 0.20, seed: 101 },
        { x: 540, y: 195, rx: 280, ry: 105, color: P.duskViolet, alpha: 0.14, seed: 102 },
        { x: 315, y: 310, rx: 240, ry: 145, color: P.ochre, alpha: 0.22, multiply: false, seed: 103 }
      ]
    });

    // Subtle feathery dusk cloud veil & glowing crescent moon upper-right
    E.mistVeil(ctx, 900, 178, 225, 36, 0.22, 107, P.indigo);
    E.mistVeil(ctx, 810, 325, 340, 165, 0.46, 108);
    drawCrescentMoon(ctx, 1095, 128, 26, 0.90, boil, 109);

    // 2. Continuous receding misty Yorkshire coastal hills (ALL full-width — ZERO vertical clip seams!)
    const farRidge = [[-40, 505], [140, 466], [340, 456], [560, 492], [790, 520], [1040, 496], [1320, 474]];
    E.paintTerrainLayer(ctx, farRidge, 740, P.indigo, {
      alpha: 0.24, gradColor: P.sepia, endAlpha: 0.16, seed: 112, mistBase: 0.32
    });

    // Delicate architectural Scarborough Fair nestled in the distant misty valley!
    drawScarboroughTown(ctx, 565, 498, 0.68, t, 0.85, boil, 118);

    // Midground full-width moorland swell running cleanly behind foreHill
    const midRight = [[-40, 568], [260, 588], [520, 574], [740, 554], [980, 538], [1180, 546], [1320, 558]];
    E.paintTerrainLayer(ctx, midRight, 750, P.rawUmber, {
      alpha: 0.26, gradColor: P.sepia, endAlpha: 0.34, seed: 115
    });

    // Foreground warm raw-umber hillside crest on the left supporting the weathered lantern post
    const foreHill = [[-40, 548], [95, 512], [238, 498], [385, 534], [545, 616], [765, 748]];
    E.paintTerrainLayer(ctx, foreHill, 755, P.rawUmber, {
      alpha: 0.46, gradColor: P.sepia, endAlpha: 0.58, seed: 118
    });
    E.shadeStrokes(ctx, foreHill.concat([[740, 745], [-40, 745]]), {
      angle: -0.32, spacing: 9.5, alpha: 0.18, color: P.sepia, seed: 119, boil: boil
    });
    E.pencilStroke(ctx, foreHill, {
      medium: 'charcoal', color: P.charcoal, width: 2.2, alpha: 0.68, seed: 120, boil: boil, ghost: 0.22
    });

    // 3. Weathered coastal timber post & swaying hanging iron lantern (left focal point!)
    const lx = 262;
    const postTop = 212;
    const postBot = 548;
    E.paintOpaqueUndercoat(ctx, [[lx - 7, postBot], [lx - 5, postTop], [lx + 7, postTop], [lx + 10, postBot]], 0.85, P.paperWarm, false);
    E.watercolorPolygon(ctx, [[lx - 7, postBot], [lx - 5, postTop], [lx + 7, postTop - 2], [lx + 10, postBot]], P.sepia, {
      alpha: 0.72, gradColor: P.charcoal, smooth: false
    });
    E.pencilStroke(ctx, [[lx - 7, postBot], [lx - 6, 360], [lx - 5, postTop]], {
      medium: 'charcoal', color: P.charcoal, width: 2.4, alpha: 0.88, seed: 131, boil: boil, ghost: 0.2
    });
    E.pencilStroke(ctx, [[lx + 8, postBot], [lx + 7, 365], [lx + 6, postTop]], {
      medium: 'graphite', color: P.graphite, width: 1.7, alpha: 0.75, seed: 132, boil: boil
    });
    E.pencilStroke(ctx, [[lx - 14, postTop + 20], [lx + 58, postTop + 14], [lx + 106, postTop + 18]], {
      medium: 'charcoal', color: P.charcoal, width: 3.0, alpha: 0.88, seed: 133, boil: boil, ghost: 0.2
    });
    E.pencilStroke(ctx, [[lx + 7, postTop + 68], [lx + 36, postTop + 42], [lx + 64, postTop + 16]], {
      medium: 'ink', color: P.ironGall, width: 1.7, alpha: 0.78, seed: 134, boil: boil
    });

    const swing = Math.sin(t * 1.15) * 0.08;
    const hookX = lx + 92;
    const hookY = postTop + 18;
    const lanternX = hookX + Math.sin(swing) * 52;
    const lanternY = hookY + Math.cos(swing) * 52;
    const glowPulse = 0.88 + 0.12 * Math.sin(t * 3.6) + 0.04 * Math.sin(t * 7.3);

    // Warm layered candlelight bloom
    const cg = ctx.createRadialGradient(lanternX, lanternY + 18, 4, lanternX, lanternY + 18, 175 * glowPulse);
    cg.addColorStop(0, E.rgba(P.candleCore, 0.90 * glowPulse));
    cg.addColorStop(0.24, E.rgba(P.amberGlow, 0.44 * glowPulse));
    cg.addColorStop(0.58, E.rgba(P.burntSienna, 0.12 * glowPulse));
    cg.addColorStop(1, E.rgba(P.burntSienna, 0));
    ctx.fillStyle = cg;
    ctx.beginPath();
    ctx.arc(lanternX, lanternY + 18, 175 * glowPulse, 0, Math.PI * 2);
    ctx.fill();

    E.pencilStroke(ctx, [[hookX, hookY], [lanternX, lanternY - 12]], {
      medium: 'ink', color: P.ironGall, width: 1.4, alpha: 0.86, seed: 136, boil: boil
    });
    const capPts = [[lanternX - 18, lanternY], [lanternX - 9, lanternY - 11], [lanternX, lanternY - 15], [lanternX + 9, lanternY - 11], [lanternX + 18, lanternY]];
    E.watercolorPolygon(ctx, capPts, P.charcoal, { alpha: 0.72, smooth: false });
    E.pencilStroke(ctx, capPts.concat([[lanternX - 18, lanternY]]), {
      medium: 'ink', color: P.charcoal, width: 1.6, alpha: 0.90, seed: 138, boil: boil
    });
    const glassPts = [[lanternX - 14, lanternY + 1], [lanternX + 14, lanternY + 1], [lanternX + 10, lanternY + 36], [lanternX - 10, lanternY + 36]];
    E.watercolorPolygon(ctx, glassPts, P.candleCore, { alpha: 0.86, multiply: false, gradColor: P.amberGlow, smooth: false });
    E.pencilStroke(ctx, glassPts.concat([[lanternX - 14, lanternY + 1]]), {
      medium: 'ink', color: P.ironGall, width: 1.45, alpha: 0.88, seed: 140, boil: boil
    });
    E.pencilStroke(ctx, [[lanternX, lanternY + 1], [lanternX, lanternY + 36]], {
      medium: 'ink', color: P.ironGall, width: 0.95, alpha: 0.65, seed: 141, boil: boil
    });
    ctx.fillStyle = E.rgba(P.chalk, 0.96);
    ctx.beginPath();
    ctx.ellipse(lanternX + Math.sin(t * 6) * 0.7, lanternY + 18, 3.2, 6.2 * glowPulse, 0, 0, Math.PI * 2);
    ctx.fill();

    // Windswept hillside grass around post
    drawWindsweptGrass(ctx, 215, 560, 410, 30, 0.72, t, 0.80, boil, 145, 1.05);
    drawWindsweptGrass(ctx, 88, 625, 220, 16, 0.85, t, 0.62, boil, 148, 1.18);

    // Lush botanical sprigs framing top-left and lower-right corners
    drawRosemary(ctx, 82, 275, 1.02, 0.48, 1.0, 0.82, t, boil, 152);
    drawParsley(ctx, 132, 232, 0.72, 0.88, 1.0, 0.68, t, boil, 153);
    drawSage(ctx, 1188, 692, 1.06, -0.42, 1.0, 0.80, t, boil, 155);
    drawThyme(ctx, 1102, 712, 0.96, -0.74, 1.0, 0.76, t, boil, 158);
    drawDriftingHerbs(ctx, t, 0.56, 0.7, 10, 160);

    // 4. Calligraphic Bookplate Title & Hand-Sketched Play Medallion
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.font = 'italic 58px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.fillStyle = E.rgba(P.ironGall, 0.93);
    ctx.fillText('Scarborough Fair', 805, 252);

    E.drawInkFlourish(ctx, 805, 294, 134, 0.64, boil, 170, P.sepia);

    ctx.font = 'italic 21px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.fillStyle = E.rgba(P.sepia, 0.86);
    ctx.fillText('Sung by Aero  ·  An Ink & Watercolor Ballad', 805, 334);

    ctx.font = 'italic 15.5px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.fillStyle = E.rgba(P.graphiteSoft, 0.78);
    ctx.fillText('“Parsley, sage, rosemary and thyme — remember me to one who lives there”', 805, 370);

    const bx = COVER_PLAY_BTN.x;
    const by = COVER_PLAY_BTN.y;
    const br = COVER_PLAY_BTN.r * (hoverPlay ? 1.07 : 1.0 + 0.022 * Math.sin(t * 2.2));

    // Feathered soft ochre watercolor bloom behind sketched ring (NO hard oval edge!)
    E.watercolorBloom(ctx, bx, by, br * 1.48, br * 1.42, hoverPlay ? P.amberGlow : P.ochre, {
      alpha: hoverPlay ? 0.36 : 0.22, seed: 180, dabs: 2, multiply: true
    });

    const ringPts = [];
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * Math.PI * 2;
      ringPts.push([bx + Math.cos(a) * br, by + Math.sin(a) * br]);
    }
    E.pencilStroke(ctx, ringPts, {
      medium: 'charcoal', color: P.ironGall, width: hoverPlay ? 2.6 : 2.1, alpha: 0.88,
      seed: 181, boil: boil, closed: true, ghost: 0.24
    });

    const tri = [[bx - 12, by - 17], [bx + 19, by + 1], [bx - 12, by + 17], [bx - 12, by - 17]];
    E.watercolorPolygon(ctx, tri.slice(0, 3), P.ironGall, { alpha: hoverPlay ? 0.88 : 0.72, smooth: false });
    E.pencilStroke(ctx, tri, { medium: 'ink', color: P.charcoal, width: 1.8, alpha: 0.92, seed: 184, boil: boil });

    ctx.font = 'italic 16px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.fillStyle = E.rgba(P.sepia, hoverPlay ? 0.96 : 0.80);
    ctx.fillText('listen & watch', bx, by + br + 28);
    ctx.restore();
  }

  // ==========================================================================
  // 5. SCENE 1: INTRO — TWILIGHT PATH TO SCARBOROUGH
  // ==========================================================================
  function drawIntroScene(ctx, t, localT, progress, tel, weight, boil) {
    const washReveal = smoothstep(0.0, 1.5, localT);
    const lineReveal = smoothstep(0.2, 2.7, localT);
    const a = weight;

    // 1. Full-bleed wet-on-wet twilight coastal sky (ZERO horizontal pill capsules!)
    E.atmosphericSkyWash(ctx, LOGICAL_W, LOGICAL_H, [
      [0.0,  P.indigoDeep, 0.36],
      [0.24, P.indigo, 0.32],
      [0.48, P.duskViolet, 0.24],
      [0.72, P.roseDust, 0.22],
      [0.92, P.amberGlow, 0.24],
      [1.0,  P.paperLight, 0.05]
    ], {
      y0: 0, y1: 450, alpha: a * washReveal,
      clouds: [
        { x: 280, y: 125, rx: 320, ry: 95, color: P.indigo, alpha: 0.22, seed: 201 },
        { x: 840, y: 145, rx: 360, ry: 110, color: P.duskViolet, alpha: 0.18, seed: 202 },
        { x: 760, y: 345, rx: 340, ry: 110, color: P.amberGlow, alpha: 0.22, multiply: false, seed: 203 }
      ]
    });

    // Soft feathered twilight cloud veils & crescent moon
    E.mistVeil(ctx, 360, 168, 225, 34, a * 0.26 * washReveal, 205);
    E.mistVeil(ctx, 920, 144, 240, 32, a * 0.24 * washReveal, 206);
    drawCrescentMoon(ctx, 1020, 126, 29, a * 0.94 * washReveal, boil, 208);

    // 2. Receding misty Yorkshire moors (continuous full-width — ZERO partial rectangular overlays!)
    const veryFar = [[-40, 392], [180, 358], [410, 366], [680, 398], [940, 376], [1145, 352], [1320, 378]];
    E.paintTerrainLayer(ctx, veryFar, 560, P.indigoMid, {
      alpha: a * 0.22 * washReveal, gradColor: P.slateTeal, endAlpha: 0.12, seed: 210, mistBase: 0.55
    });

    const farHeadland = [[-40, 412], [150, 376], [355, 362], [580, 394], [780, 416], [965, 392], [1120, 368], [1245, 390], [1320, 404]];
    E.paintTerrainLayer(ctx, farHeadland, 620, P.indigo, {
      alpha: a * 0.30 * washReveal, gradColor: P.sepia, endAlpha: 0.18, seed: 212, mistBase: 0.48
    });
    E.pencilStroke(ctx, farHeadland, {
      medium: 'graphite', color: P.indigoDeep, width: 1.2, alpha: a * 0.36 * lineReveal,
      seed: 213, boil: boil, progress: lineReveal
    });

    // 3. Detailed Medieval Scarborough Fair Silhouette & Warm Lanterns in the Misty Valley!
    drawScarboroughTown(ctx, 868, 412, 0.96, t, a * smoothstep(0.5, 2.4, localT), boil, 218);

    // Soft valley mist bank drifting across the lower town
    const mistDrift = Math.sin(t * 0.35) * 24;
    E.mistVeil(ctx, 815 + mistDrift, 456, 260, 52, a * 0.48 * washReveal, 220);
    E.mistVeil(ctx, 515 - mistDrift * 0.6, 488, 220, 46, a * 0.34 * washReveal, 221);

    // 4. Midground & Foreground Rolling Moorland Slopes (continuous edge-to-edge!)
    const midRidge = [[-40, 466], [175, 434], [395, 456], [625, 502], [845, 506], [1055, 468], [1320, 476]];
    E.paintTerrainLayer(ctx, midRidge, 750, P.rawUmber, {
      alpha: a * 0.44 * washReveal, gradColor: P.sepia, endAlpha: 0.56, seed: 222
    });
    E.shadeStrokes(ctx, midRidge.concat([[1320, 750], [-40, 750]]), {
      angle: -0.26, spacing: 10, alpha: a * 0.16 * lineReveal, color: P.sepia, seed: 223, boil: boil
    });

    // 5. Organic S-Curving Moorland Dirt Track winding naturally from bottom-left into the valley!
    const trackPoly = [
      [115, 740], [218, 668], [358, 622], [492, 594], [552, 562], [588, 532], [678, 502], [778, 478], [826, 452],
      [838, 454], [798, 486], [712, 518], [634, 554], [608, 592], [534, 636], [428, 682], [352, 740]
    ];
    E.paintOpaqueUndercoat(ctx, trackPoly, a * 0.52 * washReveal, P.paperLight, true);
    E.watercolorPolygon(ctx, trackPoly, P.ochre, {
      alpha: a * 0.28 * washReveal, gradColor: P.rawUmber, edgeRim: 0.2, smooth: true
    });
    E.pencilStroke(ctx, [[122, 735], [220, 668], [358, 622], [492, 594], [552, 562], [588, 532], [678, 502], [778, 478], [825, 452]], {
      medium: 'charcoal', color: P.sepia, width: 1.9, alpha: a * 0.62 * lineReveal,
      seed: 231, boil: boil, ghost: 0.22, progress: lineReveal
    });
    E.pencilStroke(ctx, [[348, 735], [430, 682], [536, 636], [608, 592], [634, 554], [712, 518], [798, 486], [836, 454]], {
      medium: 'graphite', color: P.sepia, width: 1.5, alpha: a * 0.52 * lineReveal,
      seed: 232, boil: boil, progress: lineReveal
    });
    E.dryBrushStreak(ctx, [[232, 725], [375, 650], [525, 608], [605, 552], [735, 500]], 14, P.rawUmber, a * 0.22 * lineReveal, 233, boil);

    // 6. Crumbled Organic Yorkshire Dry-Stone Wall & Rustic Lantern Post nestled in wild grass (NO rounded capsule ground strip!)
    const rngW = E.mulberry32(236);
    // Soft broken dry-brush earth & shadow footing under wall
    E.dryBrushStreak(ctx, [[-12, 540], [72, 536], [168, 544], [255, 554], [295, 560]], 16, P.sepia, a * 0.24 * washReveal, 234, boil);
    // Organic irregular weathered fieldstones (varied heights, natural gaps, mossy sepia-slate tones)
    let wx = -8;
    for (let s = 0; s < 17 && wx < 282; s++) {
      const sw = 13 + rngW() * 14;
      const sh = 7 + rngW() * 7;
      const baseY = 516 + (wx / 290) * 26;
      const sy = baseY + (s % 2 === 0 ? 0 : 10) + (rngW() - 0.5) * 4;
      const stPoly = [[wx, sy + 2], [wx + sw * 0.48, sy], [wx + sw, sy + 2], [wx + sw - 1, sy + sh], [wx + 1, sy + sh]];
      E.watercolorPolygon(ctx, stPoly, s % 3 === 0 ? P.graphiteSoft : P.rawUmber, { alpha: a * 0.42 * washReveal, smooth: true });
      E.pencilStroke(ctx, stPoly.concat([stPoly[0]]), {
        medium: 'graphite', color: P.charcoal, width: 0.9, alpha: a * 0.50 * lineReveal, seed: 236 + s, boil: boil
      });
      wx += sw * (s % 2 === 0 ? 0.78 : 1.02);
    }
    // Wild moorland grass tufts growing organically up around and through the weathered stones
    drawWindsweptGrass(ctx, 138, 558, 305, 24, 0.72, t, a * 0.68 * lineReveal, boil, 255, 0.56);

    // Small weathered wooden lantern post by the path curve (echoes Cover motif!)
    const px = 285, pyTop = 376, pyBot = 548;
    E.pencilStroke(ctx, [[px, pyBot], [px + 2, 460], [px + 3, pyTop]], {
      medium: 'charcoal', color: P.charcoal, width: 4.0, alpha: a * 0.80 * lineReveal, seed: 238, boil: boil
    });
    E.pencilStroke(ctx, [[px - 4, pyTop + 14], [px + 44, pyTop + 10]], {
      medium: 'charcoal', color: P.charcoal, width: 2.4, alpha: a * 0.78 * lineReveal, seed: 239, boil: boil
    });
    const flk = 0.85 + 0.15 * Math.sin(t * 3.8);
    const lg = ctx.createRadialGradient(px + 38, pyTop + 34, 2, px + 38, pyTop + 34, 62 * flk);
    lg.addColorStop(0, E.rgba(P.candleCore, a * 0.88 * flk * lineReveal));
    lg.addColorStop(0.32, E.rgba(P.amberGlow, a * 0.36 * flk * lineReveal));
    lg.addColorStop(1, E.rgba(P.burntSienna, 0));
    ctx.fillStyle = lg;
    ctx.beginPath();
    ctx.arc(px + 38, pyTop + 34, 62 * flk, 0, Math.PI * 2);
    ctx.fill();
    E.pencilStroke(ctx, [[px + 38, pyTop + 11], [px + 38, pyTop + 26]], {
      medium: 'ink', color: P.ironGall, width: 1.1, alpha: a * 0.8 * lineReveal, seed: 240, boil: boil
    });
    E.watercolorPolygon(ctx, [[px + 32, pyTop + 26], [px + 44, pyTop + 26], [px + 42, pyTop + 42], [px + 34, pyTop + 42]], P.candleCore, {
      alpha: a * 0.85 * lineReveal, multiply: false, smooth: false
    });
    E.pencilStroke(ctx, [[px + 31, pyTop + 26], [px + 38, pyTop + 20], [px + 45, pyTop + 26], [px + 42, pyTop + 42], [px + 34, pyTop + 42], [px + 31, pyTop + 26]], {
      medium: 'ink', color: P.charcoal, width: 1.2, alpha: a * 0.82 * lineReveal, seed: 241, boil: boil
    });

    // Ridge contour lines & lush windswept moorland grasses swaying with the guitar waltz
    E.pencilStroke(ctx, [[-10, 466], [175, 434], [395, 456], [600, 496]], {
      medium: 'charcoal', color: P.charcoal, width: 2.0, alpha: a * 0.58 * lineReveal, seed: 242, boil: boil, ghost: 0.2, progress: lineReveal
    });
    E.pencilStroke(ctx, [[855, 504], [1055, 468], [1300, 476]], {
      medium: 'charcoal', color: P.charcoal, width: 1.9, alpha: a * 0.55 * lineReveal, seed: 243, boil: boil, ghost: 0.2, progress: lineReveal
    });

    const guitarSway = 0.65 + tel.a_rms * 0.8;
    drawWindsweptGrass(ctx, 130, 682, 340, 32, guitarSway, t, a * 0.82 * lineReveal, boil, 245, 1.28);
    drawWindsweptGrass(ctx, 1075, 650, 380, 34, guitarSway * 0.9, t, a * 0.78 * lineReveal, boil, 249, 1.18);
    drawDriftingHerbs(ctx, t, a * 0.42 * lineReveal, 0.8, 8, 258);
  }

  // ==========================================================================
  // 6. SCENE 2: VERSE 1 — LONE TRAVELER, FOUR BOTANICAL HERBS & MEMORY PORTRAIT
  // ==========================================================================
  function drawTravelerPortrait(ctx, t, tel, alpha, boil) {
    if (alpha <= 0.01) return;
    const breathLift = -tel.breath * 4.8 - Math.sin(t * 1.1) * 1.5;
    const singOpen = clamp(tel.v_rms * 6.5, 0, 4.8);
    const wind = 0.75 + tel.energy * 0.5 + Math.sin(t * 1.8) * 0.2;
    const hy = breathLift * 0.42;

    ctx.save();
    ctx.translate(0, breathLift * 0.4);

    // --- 1. EXACT OPAQUE WARM-PAPER UNDERCOAT (Zero background bleed AND zero white halo outside profile!) ---
    const cloakPoly = [
      [-15, 740], [18, 558], [68, 466 + hy], [136, 412 + hy], [198, 386 + hy],
      [254, 378 + hy], [308, 398 + hy], [356, 456 + hy], [386, 562], [404, 740]
    ];
    const facePoly = [
      [214, 382 + hy], [206, 326 + hy], [206, 266 + hy], [228, 214 + hy], [272, 206 + hy],
      [304, 228 + hy], [310, 253 + hy], [306, 265 + hy], [325, 293 + hy], [313, 302 + hy],
      [316, 311 + hy - singOpen * 0.14], [310, 316 + hy], [315, 322 + hy + singOpen * 0.45],
      [311, 329 + hy + singOpen * 0.32], [313, 342 + hy + singOpen * 0.28], [304, 352 + hy + singOpen * 0.18],
      [288, 354 + hy + singOpen * 0.14], [274, 350 + hy], [274, 384 + hy], [244, 392 + hy]
    ];
    const hairMass = [
      [300, 224 + hy], [286, 200 + hy], [250, 190 + hy], [208, 202 + hy],
      [180, 236 + hy], [172, 286 + hy], [178, 336 + hy], [192, 370 + hy],
      [218, 362 + hy], [230, 326 + hy], [238, 288 + hy], [258, 260 + hy],
      [282, 238 + hy], [300, 232 + hy]
    ];
    E.paintOpaqueUndercoat(ctx, cloakPoly, alpha * 0.96, P.paperLight, true);
    E.paintOpaqueUndercoat(ctx, facePoly, alpha * 0.96, P.paperLight, true);
    E.paintOpaqueUndercoat(ctx, hairMass, alpha * 0.96, P.paperLight, true);

    // --- 2. Gracefully Draped Heavy Traveling Cloak & Loosely Wrapped Scarf (Deep sculptural folds & tonal shading!) ---
    E.watercolorPolygon(ctx, cloakPoly, P.indigoDeep, {
      alpha: alpha * 0.72, gradColor: P.charcoal, gradDir: 'h', smooth: true
    });
    // Rich sculptural charcoal drapery shadow valleys & warm lifted wool ridges across the cloak!
    E.charcoalTone(ctx, 118, 565, 138, 178, 0.25, P.charcoal, alpha * 0.56, 311);
    E.charcoalTone(ctx, 245, 590, 88, 155, -0.15, P.indigoDeep, alpha * 0.42, 313);
    E.shadeStrokes(ctx, [[-10, 735], [38, 505], [182, 416], [248, 560], [254, 735]], {
      angle: -1.16, spacing: 7.5, alpha: alpha * 0.34, color: P.charcoal, seed: 312, boil: boil, curve: 0.24
    });

    // Organic flowing draped wool fold troughs + soft moonlit ridge highlights!
    const cloakFolds = [
      [[192, 412 + hy], [140, 496], [92, 610], [60, 725]],
      [[224, 418 + hy], [198, 520], [180, 635], [172, 728]],
      [[264, 416 + hy], [282, 515], [294, 630], [300, 728]],
      [[294, 414 + hy], [334, 495], [356, 608], [368, 724]]
    ];
    for (let i = 0; i < cloakFolds.length; i++) {
      E.dryBrushStreak(ctx, cloakFolds[i], 15, P.charcoal, alpha * 0.28, 314 + i * 7, boil);
      E.pencilStroke(ctx, cloakFolds[i], {
        medium: 'charcoal', color: P.charcoal, width: 2.1 - i * 0.15, alpha: alpha * 0.68,
        seed: 316 + i * 5, boil: boil
      });
      if (i >= 1) {
        const ridge = cloakFolds[i].map(function (pt) { return [pt[0] + 12, pt[1] + 4]; });
        E.chalkHighlight(ctx, ridge, { color: P.paperLight, width: 2.2, alpha: alpha * 0.24, seed: 340 + i * 3, boil: boil });
      }
    }

    // Soft loosely knotted warm burnt-sienna wool scarf hugging his upturned collar (draping naturally downward!)
    const sWave = Math.sin(t * 2.1) * 7 * wind;
    const scarfWrap = [
      [182, 396 + hy], [214, 378 + hy], [262, 374 + hy], [298, 388 + hy],
      [296, 424 + hy], [252, 434 + hy], [206, 426 + hy], [176, 416 + hy]
    ];
    const scarfTail = [
      [194, 414 + hy], [156, 436 + hy + sWave * 0.3], [116, 476 + sWave * 0.7], [86, 516 + sWave],
      [112, 524 + sWave * 0.9], [148, 488 + sWave * 0.5], [192, 444 + hy], [224, 426 + hy]
    ];
    E.watercolorPolygon(ctx, scarfTail, P.burntSienna, { alpha: alpha * 0.66, gradColor: P.sepia, smooth: true });
    E.watercolorPolygon(ctx, scarfWrap, P.burntSienna, { alpha: alpha * 0.76, gradColor: P.sepia, smooth: true });
    E.pencilStroke(ctx, [[184, 396 + hy], [218, 378 + hy], [262, 375 + hy], [298, 390 + hy]], {
      medium: 'charcoal', color: P.ironGall, width: 2.2, alpha: alpha * 0.85, seed: 318, boil: boil
    });
    E.pencilStroke(ctx, [[178, 416 + hy], [218, 430 + hy], [266, 432 + hy], [298, 418 + hy]], {
      medium: 'graphite', color: P.sepia, width: 1.7, alpha: alpha * 0.76, seed: 319, boil: boil
    });
    E.pencilStroke(ctx, [[194, 416 + hy], [156, 438 + hy + sWave * 0.3], [116, 478 + sWave * 0.7], [88, 516 + sWave]], {
      medium: 'charcoal', color: P.ironGall, width: 1.8, alpha: alpha * 0.74, seed: 320, boil: boil
    });

    // Outer cloak silhouette contour + moonlit chalk rim-light along right shoulder
    E.pencilStroke(ctx, [[16, 560], [68, 466 + hy], [138, 412 + hy], [196, 386 + hy]], {
      medium: 'charcoal', color: P.charcoal, width: 2.6, alpha: alpha * 0.86, seed: 321, boil: boil, ghost: 0.2
    });
    E.pencilStroke(ctx, [[296, 392 + hy], [352, 452 + hy], [384, 560], [402, 730]], {
      medium: 'charcoal', color: P.charcoal, width: 2.6, alpha: alpha * 0.86, seed: 322, boil: boil, ghost: 0.2
    });
    E.chalkHighlight(ctx, [[304, 398 + hy], [348, 452 + hy], [378, 554], [392, 665]], {
      color: P.candleCore, width: 2.5, alpha: alpha * 0.62, seed: 323, boil: boil
    });

    // --- 3. Sculpted Anatomical Side-Profile Head & Neck (Rich portrait charcoal modeling!) ---
    E.watercolorPolygon(ctx, facePoly, P.skinWarm, {
      alpha: alpha * 0.62, gradColor: P.skinShadow, gradDir: 'h', smooth: true
    });
    // Velvety hand-shaded charcoal tonal planes: cheekbone hollow, brow socket, underside of jaw & neck shadow!
    E.charcoalTone(ctx, 276, 304 + hy, 24, 18, -0.35, P.sepia, alpha * 0.28, 325);
    E.charcoalTone(ctx, 256, 336 + hy, 36, 26, 0.24, P.sepia, alpha * 0.44, 326);
    E.charcoalTone(ctx, 248, 368 + hy, 28, 24, 0.12, P.charcoal, alpha * 0.42, 327);
    E.charcoalTone(ctx, 294, 268 + hy, 16, 12, 0.0, P.sepia, alpha * 0.34, 328);
    // Delicate portrait graphite contour hatching along lower jaw & neck shadow
    E.shadeStrokes(ctx, [[226, 326 + hy], [276, 344 + hy], [274, 386 + hy], [218, 384 + hy]], {
      angle: 0.72, spacing: 5.5, alpha: alpha * 0.26, color: P.sepia, seed: 354, boil: boil, curve: 0.16
    });

    // Smooth sensitive profile contour (balanced brow -> nose -> serene parted lips -> smooth chin -> jaw!)
    E.pencilStroke(ctx, [
      [294, 218 + hy], [305, 232 + hy], [310, 253 + hy], [305, 265 + hy],
      [325, 293 + hy], [313, 302 + hy], [316, 311 + hy - singOpen * 0.14], [309, 316 + hy + singOpen * 0.1]
    ], { medium: 'charcoal', color: P.ironGall, width: 2.0, alpha: alpha * 0.92, seed: 329, boil: boil, ghost: 0.14 });
    E.pencilStroke(ctx, [
      [310, 318 + hy + singOpen * 0.18], [315, 322 + hy + singOpen * 0.45],
      [311, 329 + hy + singOpen * 0.32], [313, 342 + hy + singOpen * 0.28],
      [304, 352 + hy + singOpen * 0.18], [286, 353 + hy + singOpen * 0.14],
      [266, 345 + hy], [250, 324 + hy]
    ], { medium: 'charcoal', color: P.ironGall, width: 1.85, alpha: alpha * 0.88, seed: 330, boil: boil });
    E.pencilStroke(ctx, [[274, 352 + hy], [276, 384 + hy]], {
      medium: 'graphite', color: P.sepia, width: 1.6, alpha: alpha * 0.78, seed: 331, boil: boil
    });
    // Ear & subtle cheekbone / throat line
    E.pencilStroke(ctx, [[246, 286 + hy], [239, 296 + hy], [242, 312 + hy], [250, 315 + hy]], {
      medium: 'graphite', color: P.sepia, width: 1.2, alpha: alpha * 0.64, seed: 332, boil: boil
    });

    // Expressive contemplative eye looking out toward distant Scarborough Fair
    E.pencilStroke(ctx, [[284, 256 + hy], [297, 252 + hy], [308, 256 + hy]], {
      medium: 'charcoal', color: P.charcoal, width: 2.0, alpha: alpha * 0.86, seed: 333, boil: boil
    });
    E.pencilStroke(ctx, [[287, 270 + hy], [297, 267 + hy], [305, 272 + hy]], {
      medium: 'ink', color: P.charcoal, width: 1.8, alpha: alpha * 0.92, seed: 334, boil: boil
    });
    E.pencilStroke(ctx, [[290, 276 + hy], [299, 276 + hy], [304, 274 + hy]], {
      medium: 'graphite', color: P.graphiteSoft, width: 0.95, alpha: alpha * 0.6, seed: 335, boil: boil
    });
    ctx.fillStyle = E.rgba(P.charcoal, alpha * 0.9);
    ctx.beginPath();
    ctx.ellipse(300.5, 271.5 + hy, 2.8, 3.5, 0.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = E.rgba(P.chalk, alpha * 0.94);
    ctx.beginPath();
    ctx.arc(301.8, 270.3 + hy, 1.05, 0, Math.PI * 2);
    ctx.fill();

    // Nostril & subtle singing mouth parting
    E.pencilStroke(ctx, [[310, 296 + hy], [314, 295 + hy]], {
      medium: 'graphite', color: P.sepia, width: 1.0, alpha: alpha * 0.62, seed: 336, boil: boil
    });
    if (singOpen > 0.7) {
      ctx.fillStyle = E.rgba(P.ironGall, alpha * 0.45);
      ctx.beginPath();
      ctx.ellipse(311.5, 316.5 + hy + singOpen * 0.2, 2.2, singOpen * 0.42, 0.1, 0, Math.PI * 2);
      ctx.fill();
    }

    // Golden-ochre moonlight rim along forehead, nose bridge & chin
    E.chalkHighlight(ctx, [[299, 231 + hy], [309, 253 + hy], [307, 266 + hy], [324, 293 + hy]], {
      color: P.candleCore, width: 1.9, alpha: alpha * 0.74, seed: 338, boil: boil
    });

    // --- 4. Thick, Natural Wavy Wind-Tossed Hair (ZERO porcupine spikes!) ---
    const hSway = Math.sin(t * 2.2) * 5 * wind;
    E.watercolorPolygon(ctx, hairMass, P.charcoal, {
      alpha: alpha * 0.84, gradColor: P.sepia, smooth: true
    });
    // Soft curving layered hair locks tumbling naturally around his crown, ear & nape
    const locks = [
      [[294, 218 + hy], [268, 202 + hy], [224, 204 + hy], [192, 232 + hy], [178, 278 + hy]],
      [[276, 212 + hy], [234, 222 + hy], [202, 256 + hy], [188, 312 + hy], [194, 366 + hy]],
      [[254, 228 + hy], [226, 262 + hy], [212, 314 + hy], [204, 364 + hy]],
      [[182, 288 + hy], [168, 322 + hy + hSway * 0.3], [160, 356 + hy + hSway * 0.6]],
      [[186, 330 + hy], [172, 360 + hy + hSway * 0.4], [156, 382 + hy + hSway * 0.7]],
      [[288, 218 + hy], [304, 222 + hy - hSway * 0.15], [312, 234 + hy - hSway * 0.2]]
    ];
    for (let i = 0; i < locks.length; i++) {
      E.pencilStroke(ctx, locks[i], {
        medium: 'charcoal', color: i % 2 === 0 ? P.charcoal : P.sepia,
        width: 2.6 - i * 0.18, alpha: alpha * 0.82, seed: 345 + i * 7, boil: boil
      });
    }
    // Subtle warm moonlight sheen across top wave of hair
    E.chalkHighlight(ctx, [[224, 202 + hy], [258, 198 + hy], [286, 210 + hy]], {
      color: P.candleCore, width: 1.8, alpha: alpha * 0.38, seed: 353, boil: boil
    });

    ctx.restore();
  }

  // Museum-Grade Ethereal Vine-Charcoal & Sepia Memory Portrait of the Beloved
  // (ZERO bullseye concentric circles! ZERO cow-spot blotches! ZERO stiff wire hair!)
  function drawBelovedMemory(ctx, t, memAlpha, dissolve, boil) {
    if (memAlpha <= 0.015) return;
    const a = memAlpha * (1 - dissolve * 0.88);
    if (a <= 0.01) return;

    const cx = 876;
    const cy = 266 + Math.sin(t * 0.65) * 3.5;
    ctx.save();

    // 1. Seamless feathered atmospheric memory haze (soft warm rose-ochre & luminous mist — NO bullseye ovals!)
    E.watercolorBloom(ctx, cx + 10, cy + 8, 210, 175, P.roseDust, {
      alpha: a * 0.24, seed: 360, dabs: 2, multiply: true
    });
    E.watercolorBloom(ctx, cx - 20, cy - 8, 165, 138, P.amberGlow, {
      alpha: a * 0.24, seed: 361, dabs: 2, multiply: false
    });
    E.mistVeil(ctx, cx - 14, cy + 2, 118, 112, a * 0.58, 362);

    // 2. Soft lush feathered hair mist dissolving organically into twilight (NO crisp closed polygon fin!)
    const hFlow = Math.sin(t * 1.1) * 11;
    E.watercolorBloom(ctx, cx + 18, cy - 34, 88, 66, P.sepia, { alpha: a * 0.34, seed: 363, dabs: 2 });
    E.watercolorBloom(ctx, cx + 82, cy - 10 + hFlow * 0.4, 118, 62, P.sepia, { alpha: a * 0.28, angle: 0.14, seed: 364, dabs: 2 });
    E.watercolorBloom(ctx, cx + 68, cy + 48 + hFlow * 0.3, 98, 56, P.duskViolet, { alpha: a * 0.22, angle: -0.18, seed: 365, dabs: 2 });
    E.watercolorBloom(ctx, cx - 44, cy + 16, 42, 72, P.sepia, { alpha: a * 0.24, seed: 366, dabs: 1 });
    E.charcoalTone(ctx, cx + 44, cy - 18, 66, 62, -0.25, P.sepia, a * 0.28, 367);

    // 3. Soft luminous ivory cheek/forehead plane + velvety smooth vine-charcoal facial modeling (NO blotches!)
    const faceOval = [
      [cx - 40, cy - 48], [cx - 12, cy - 68], [cx + 28, cy - 54], [cx + 44, cy - 16],
      [cx + 36, cy + 26], [cx + 6, cy + 56], [cx - 22, cy + 58], [cx - 44, cy + 30], [cx - 48, cy - 10]
    ];
    E.paintOpaqueUndercoat(ctx, faceOval, a * 0.62, P.paperLight, true);
    E.watercolorPolygon(ctx, faceOval, P.skinWarm, {
      alpha: a * 0.34, gradColor: P.roseDust, smooth: true
    });
    // Velvety smooth vine-charcoal tonal planes: malar cheekbones, side of nose, orbital shadow, lower-lip dimple & neck!
    E.charcoalTone(ctx, cx + 22, cy + 16, 30, 40, 0.24, P.sepia, a * 0.34, 364);
    E.charcoalTone(ctx, cx - 34, cy + 14, 16, 24, -0.18, P.roseRust, a * 0.20, 368);
    E.charcoalTone(ctx, cx - 10, cy + 2, 10, 19, 0.12, P.sepia, a * 0.26, 369);
    E.charcoalTone(ctx, cx - 28, cy - 17, 17, 11, -0.1, P.sepia, a * 0.28, 365);
    E.charcoalTone(ctx, cx + 10, cy - 16, 19, 12, 0.08, P.sepia, a * 0.28, 366);
    E.charcoalTone(ctx, cx - 16, cy + 43, 12, 6, 0.0, P.sepia, a * 0.24, 370);
    E.charcoalTone(ctx, cx + 8, cy + 78, 28, 24, 0.0, P.sepia, a * 0.26, 367);
    // Warm luminous lifted chalk glow on forehead, cheekbone & chin
    E.mistVeil(ctx, cx - 22, cy + 6, 22, 16, a * 0.26, 371);
    E.mistVeil(ctx, cx - 8, cy - 38, 26, 16, a * 0.22, 372);

    // Delicate facial contour, slender neck & flowing shawl collarbone fading softly into mist
    E.pencilStroke(ctx, [
      [cx - 38, cy - 48], [cx - 47, cy - 12], [cx - 43, cy + 26], [cx - 22, cy + 56], [cx + 8, cy + 52], [cx + 34, cy + 20]
    ], { medium: 'charcoal', color: P.sepia, width: 1.55, alpha: a * 0.72, seed: 368, boil: boil, ghost: 0.18 });
    E.pencilStroke(ctx, [[cx - 12, cy + 56], [cx - 10, cy + 94], [cx - 46, cy + 118]], {
      medium: 'graphite', color: P.sepia, width: 1.4, alpha: a * 0.54, seed: 369, boil: boil
    });
    E.pencilStroke(ctx, [[cx + 22, cy + 40], [cx + 26, cy + 88], [cx + 78, cy + 118]], {
      medium: 'graphite', color: P.sepia, width: 1.4, alpha: a * 0.52, seed: 370, boil: boil
    });

    // Soulful, softer feathered 3/4 eyes & brows gazing gently leftward toward the traveler
    // Left eye
    E.pencilStroke(ctx, [[cx - 41, cy - 23], [cx - 29, cy - 27], [cx - 17, cy - 24]], {
      medium: 'graphite', color: P.sepia, width: 1.2, alpha: a * 0.62, seed: 371, boil: boil
    });
    E.pencilStroke(ctx, [[cx - 39, cy - 11], [cx - 29, cy - 15], [cx - 18, cy - 10]], {
      medium: 'charcoal', color: P.ironGall, width: 1.6, alpha: a * 0.80, seed: 372, boil: boil
    });
    E.pencilStroke(ctx, [[cx - 37, cy - 7], [cx - 28, cy - 6], [cx - 20, cy - 9]], {
      medium: 'graphite', color: P.sepia, width: 0.85, alpha: a * 0.48, seed: 373, boil: boil
    });
    ctx.fillStyle = E.rgba(P.ironGall, a * 0.80);
    ctx.beginPath();
    ctx.ellipse(cx - 30.5, cy - 11, 3.5, 3.3, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = E.rgba(P.chalk, a * 0.94);
    ctx.beginPath();
    ctx.arc(cx - 31.8, cy - 12.2, 1.1, 0, Math.PI * 2);
    ctx.fill();

    // Right eye
    E.pencilStroke(ctx, [[cx - 4, cy - 24], [cx + 12, cy - 28], [cx + 27, cy - 22]], {
      medium: 'graphite', color: P.sepia, width: 1.25, alpha: a * 0.64, seed: 374, boil: boil
    });
    E.pencilStroke(ctx, [[cx - 2, cy - 10], [cx + 11, cy - 15], [cx + 24, cy - 9]], {
      medium: 'charcoal', color: P.ironGall, width: 1.65, alpha: a * 0.82, seed: 375, boil: boil
    });
    E.pencilStroke(ctx, [[cx, cy - 6], [cx + 11, cy - 5], [cx + 22, cy - 8]], {
      medium: 'graphite', color: P.sepia, width: 0.85, alpha: a * 0.50, seed: 376, boil: boil
    });
    ctx.fillStyle = E.rgba(P.ironGall, a * 0.82);
    ctx.beginPath();
    ctx.ellipse(cx + 9.5, cy - 10.5, 4.0, 3.7, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = E.rgba(P.chalk, a * 0.94);
    ctx.beginPath();
    ctx.arc(cx + 8.0, cy - 11.8, 1.2, 0, Math.PI * 2);
    ctx.fill();

    // Delicate nose plane & warm chalk nose-bridge highlight
    E.pencilStroke(ctx, [[cx - 13, cy - 14], [cx - 18, cy + 7], [cx - 23, cy + 16], [cx - 14, cy + 19]], {
      medium: 'graphite', color: P.sepia, width: 1.3, alpha: a * 0.72, seed: 377, boil: boil
    });
    E.chalkHighlight(ctx, [[cx - 15, cy - 10], [cx - 20, cy + 12]], {
      width: 1.6, alpha: a * 0.55, seed: 378, boil: boil
    });

    // Soft wistful rose-tinted lips
    E.watercolorBloom(ctx, cx - 16, cy + 34, 15, 7, P.roseRust, {
      alpha: a * 0.36, seed: 379, dabs: 1, multiply: true
    });
    E.pencilStroke(ctx, [[cx - 30, cy + 32], [cx - 21, cy + 30], [cx - 16, cy + 32], [cx - 9, cy + 30], [cx - 1, cy + 33]], {
      medium: 'ink', color: P.ironGall, width: 1.3, alpha: a * 0.76, seed: 380, boil: boil
    });
    E.pencilStroke(ctx, [[cx - 26, cy + 37], [cx - 16, cy + 39], [cx - 5, cy + 36]], {
      medium: 'graphite', color: P.sepia, width: 1.0, alpha: a * 0.56, seed: 381, boil: boil
    });

    // 4. Sweeping S-Curved Flowing Charcoal Hair Waves Dissolving Into Mist (NO stiff spider-leg sticks!)
    const waves = [
      [[cx - 38, cy - 50], [cx - 12, cy - 76], [cx + 32, cy - 72], [cx + 76, cy - 42], [cx + 124, cy - 28 + hFlow * 0.5], [cx + 174, cy - 38 + hFlow]],
      [[cx - 24, cy - 64], [cx + 22, cy - 62], [cx + 58, cy - 24], [cx + 98, cy + 4 + hFlow * 0.5], [cx + 156, cy - 2 + hFlow * 0.9]],
      [[cx + 34, cy - 42], [cx + 58, cy - 4], [cx + 88, cy + 34 + hFlow * 0.4], [cx + 142, cy + 42 + hFlow * 0.8]],
      [[cx + 32, cy + 4],  [cx + 48, cy + 52], [cx + 84, cy + 78 + hFlow * 0.3], [cx + 132, cy + 72 + hFlow * 0.6]],
      [[cx - 42, cy - 44], [cx - 56, cy - 4], [cx - 58, cy + 44], [cx - 44, cy + 86]]
    ];
    for (let i = 0; i < waves.length; i++) {
      E.dryBrushStreak(ctx, waves[i], 10 - i * 1.1, i % 2 === 0 ? P.sepia : P.charcoal, a * 0.30, 383 + i * 7, boil);
      E.pencilStroke(ctx, waves[i], {
        medium: 'charcoal', color: i % 2 === 0 ? P.charcoal : P.sepia,
        width: 2.2 - i * 0.2, alpha: a * (0.64 - i * 0.06), seed: 390 + i * 7, boil: boil
      });
    }

    // Gentle misty dissolution sweeps as "true love of mine" fades
    if (dissolve > 0.04) {
      for (let w = 0; w < 5; w++) {
        E.mistVeil(ctx, cx - 25 + dissolve * 85 + Math.sin(w * 2) * 32, cy - 62 + w * 34, 130 * dissolve, 34, dissolve * 0.72, 396 + w);
      }
    }
    ctx.restore();
  }

  function drawVerse1Scene(ctx, t, localT, progress, tel, weight, boil, timeline, sceneObj) {
    const a = weight;

    // 1. Seamless full-bleed twilight sky & receding valley landscape (smooth fade well below hills — zero seam!)
    E.atmosphericSkyWash(ctx, LOGICAL_W, LOGICAL_H, [
      [0.0,  P.indigoDeep, 0.36],
      [0.24, P.indigo, 0.28],
      [0.48, P.duskViolet, 0.20],
      [0.68, P.roseDust, 0.16],
      [0.84, P.amberGlow, 0.16],
      [1.0,  P.paperLight, 0.0]
    ], {
      y0: 0, y1: 560, alpha: a,
      clouds: [
        { x: 640, y: 120, rx: 380, ry: 95, color: P.indigo, alpha: 0.20, seed: 301 },
        { x: 960, y: 245, rx: 310, ry: 120, color: P.roseDust, alpha: 0.16, seed: 302 }
      ]
    });

    drawCrescentMoon(ctx, 1118, 114, 24, a * 0.88, boil, 304);

    // Continuous receding misty Yorkshire hills + detailed Scarborough Fair town below!
    const farRidge = [[-40, 468], [260, 444], [520, 434], [740, 462], [980, 440], [1180, 414], [1320, 432]];
    E.paintTerrainLayer(ctx, farRidge, 740, P.indigoMid, {
      alpha: a * 0.32, gradColor: P.rawUmber, endAlpha: 0.24, seed: 305, mistBase: 0.35
    });
    drawScarboroughTown(ctx, 725, 462, 0.80, t, a * 0.88, boil, 306);

    // Foreground moorland slope spanning bottom cleanly
    const foreSlope = [[-40, 540], [210, 512], [440, 534], [690, 588], [970, 568], [1320, 535]];
    E.paintTerrainLayer(ctx, foreSlope, 740, P.rawUmber, {
      alpha: a * 0.38, gradColor: P.sepia, endAlpha: 0.48, seed: 307
    });

    // 2. Beloved's Ethereal Charcoal Memory Portrait (Phrases 3–4)
    const memIn = smoothstep(0.46, 0.62, progress);
    const memDissolve = smoothstep(0.84, 1.0, progress);
    drawBelovedMemory(ctx, t, a * memIn, memDissolve, boil);

    // 3. Lone Traveler Side-Profile Portrait (with opaque warm-paper undercoat!)
    drawTravelerPortrait(ctx, t, tel, a, boil);

    // Windswept hillside grass along foreground right
    drawWindsweptGrass(ctx, 970, 692, 460, 26, 0.78 + tel.v_rms * 0.35, t, a * 0.66, boil, 351, 1.08);

    // 4. Lush Botanical Herbarium (All 4 herbs larger, richer & ALL 4 labeled cleanly!)
    const herbs = getHerbTriggersForScene(timeline, sceneObj);
    const pUnfurl = smoothstep(herbs.parsley  - 0.15, herbs.parsley  + 1.35, t);
    const sUnfurl = smoothstep(herbs.sage     - 0.15, herbs.sage     + 1.35, t);
    const rUnfurl = smoothstep(herbs.rosemary - 0.15, herbs.rosemary + 1.35, t);
    const tUnfurl = smoothstep(herbs.thyme    - 0.15, herbs.thyme    + 1.35, t);
    const herbFade = 1 - smoothstep(0.58, 0.80, progress) * 0.42;
    // Keep all 4 botanical ink labels visible throughout the herb phrase (~6.5s..9.2s after entry)
    const lblFade = 1 - smoothstep(herbs.thyme + 2.8, herbs.thyme + 5.2, t);

    if (pUnfurl > 0.01) {
      drawParsley(ctx, 505, 658, 1.12, 0.18, pUnfurl, a * 0.90 * herbFade, t, boil, 381);
      drawBotanicalMarginNote(ctx, 'parsley', 518, 444, a * 0.84 * pUnfurl * lblFade);
    }
    if (sUnfurl > 0.01) {
      drawSage(ctx, 646, 682, 1.12, -0.14, sUnfurl, a * 0.90 * herbFade, t, boil, 382);
      drawBotanicalMarginNote(ctx, 'sage', 636, 446, a * 0.84 * sUnfurl * lblFade);
    }
    if (tUnfurl > 0.01) {
      drawThyme(ctx, 1005, 688, 1.12, -0.18, tUnfurl, a * 0.90 * herbFade, t, boil, 384);
      drawBotanicalMarginNote(ctx, 'thyme', 984, 492, a * 0.84 * tUnfurl * lblFade);
    }
    if (rUnfurl > 0.01) {
      drawRosemary(ctx, 1146, 676, 1.16, -0.26, rUnfurl, a * 0.90 * herbFade, t, boil, 383);
      drawBotanicalMarginNote(ctx, 'rosemary', 1102, 434, a * 0.84 * rUnfurl * lblFade);
    }

    const driftA = smoothstep(herbs.parsley, herbs.parsley + 2.2, t);
    drawDriftingHerbs(ctx, t, a * (0.28 + 0.56 * driftA), 1.0, 14, 389);
  }

  // ==========================================================================
  // 7. SCENE 3: VERSE 2 — RECOGNIZABLE SHEER CAMBRIC SHIRT & SLENDER HANDS
  // ==========================================================================
  function drawSlenderLeftHand(ctx, bx, by, lift, alpha, boil) {
    // Graceful slender forearm & hand emerging softly from bottom-left margin (NO boxy brown block!)
    ctx.save();
    ctx.translate(bx, by + lift);
    ctx.rotate(-0.18);

    // Soft linen sleeve cuff feathering gently off the left edge
    const sleevePts = [[-320, 62], [-152, 18], [-112, 12], [-96, 56], [-138, 72], [-300, 134]];
    E.paintOpaqueUndercoat(ctx, sleevePts, alpha * 0.86, P.paperWarm, true);
    E.watercolorPolygon(ctx, sleevePts, P.indigo, { alpha: alpha * 0.28, gradColor: P.sepia, smooth: true });
    E.pencilStroke(ctx, [[-114, 12], [-104, 34], [-96, 56]], {
      medium: 'graphite', color: P.sepia, width: 1.5, alpha: alpha * 0.7, seed: 421, boil: boil
    });
    E.pencilStroke(ctx, [[-260, 44], [-150, 18], [-112, 12]], {
      medium: 'graphite', color: P.sepia, width: 1.5, alpha: alpha * 0.65, seed: 422, boil: boil
    });

    // Slender tapered wrist & metacarpal palm silhouette (soft organic anatomy)
    const handBase = [
      [-108, 18], [-58, 10], [-14, 4], [28, -4], [62, -2], [74, 12],
      [62, 30], [34, 46], [-16, 52], [-66, 52], [-102, 54]
    ];
    E.paintOpaqueUndercoat(ctx, handBase, alpha * 0.92, P.paperLight, true);
    E.watercolorPolygon(ctx, handBase, P.skinWarm, {
      alpha: alpha * 0.56, gradColor: P.skinShadow, smooth: true
    });
    E.charcoalTone(ctx, 4, 38, 42, 14, -0.1, P.sepia, alpha * 0.28, 423);

    // Natural relaxed opposable thumb curving gently forward-inward to cradle the gathered cuff (NO backward bend!)
    const thumb = [[10, 2], [38, -12], [68, -18], [84, -14], [78, -4], [52, 2], [26, 10]];
    E.paintOpaqueUndercoat(ctx, thumb, alpha * 0.9, P.paperLight, true);
    E.watercolorPolygon(ctx, thumb, P.skinWarm, { alpha: alpha * 0.56, gradColor: P.skinShadow, smooth: true });
    E.pencilStroke(ctx, [[10, 2], [38, -12], [68, -18], [84, -14], [78, -5], [52, 2]], {
      medium: 'charcoal', color: P.ironGall, width: 1.45, alpha: alpha * 0.82, seed: 424, boil: boil
    });

    // Four slender, cleanly separated articulated fingers curving softly under the cambric cuff
    const fingers = [
      [[56, -2], [88, -10], [116, -12], [134, -7],  [128, 1],   [106, -1],  [80, 2],   [58, 7]],
      [[64, 7],  [98, 3],   [130, 3],   [146, 9],   [139, 17],  [114, 14],  [86, 14],  [64, 16]],
      [[60, 17], [92, 17],  [118, 22],  [130, 29],  [122, 35],  [98, 29],   [74, 26],  [58, 26]],
      [[52, 27], [76, 32],  [96, 39],   [104, 45],  [96, 49],   [76, 43],   [52, 37]]
    ];
    for (let i = 0; i < fingers.length; i++) {
      const f = fingers[i];
      E.paintOpaqueUndercoat(ctx, f, alpha * 0.88, P.paperLight, true);
      E.watercolorPolygon(ctx, f, P.skinWarm, { alpha: alpha * 0.52, gradColor: P.skinShadow, smooth: true });
      E.pencilStroke(ctx, f.slice(0, 4), {
        medium: 'charcoal', color: P.ironGall, width: 1.35 - i * 0.08, alpha: alpha * 0.80, seed: 430 + i * 4, boil: boil
      });
      E.pencilStroke(ctx, f.slice(3), {
        medium: 'graphite', color: P.sepia, width: 1.15, alpha: alpha * 0.68, seed: 431 + i * 4, boil: boil
      });
    }

    // Continuous graceful wrist & back-of-hand contour + subtle moonlight rim
    E.pencilStroke(ctx, [[-108, 18], [-54, 10], [2, 3], [52, -2]], {
      medium: 'charcoal', color: P.ironGall, width: 1.6, alpha: alpha * 0.82, seed: 446, boil: boil, ghost: 0.14
    });
    E.pencilStroke(ctx, [[-102, 54], [-46, 52], [22, 46], [56, 36]], {
      medium: 'charcoal', color: P.ironGall, width: 1.6, alpha: alpha * 0.80, seed: 447, boil: boil
    });
    E.chalkHighlight(ctx, [[-44, 11], [14, 1], [62, -16]], { width: 1.5, alpha: alpha * 0.54, seed: 448, boil: boil });
    ctx.restore();
  }

  function drawSlenderRightHand(ctx, bx, by, releaseAmt, alpha, boil) {
    // Graceful slender right forearm & hand entering softly from right margin — cleanly separated fingers!
    ctx.save();
    ctx.translate(bx, by);
    const rot = 0.12 + releaseAmt * 0.12;
    ctx.rotate(rot);
    const open = releaseAmt;

    // Soft sleeve cuff feathering gently off right margin
    const sleevePts = [[320, 68], [156, 18], [116, 12], [102, 54], [144, 68], [310, 128]];
    E.paintOpaqueUndercoat(ctx, sleevePts, alpha * 0.86, P.paperWarm, true);
    E.watercolorPolygon(ctx, sleevePts, P.sepia, { alpha: alpha * 0.24, gradColor: P.indigo, smooth: true });
    E.pencilStroke(ctx, [[116, 12], [108, 34], [102, 54]], {
      medium: 'graphite', color: P.sepia, width: 1.4, alpha: alpha * 0.68, seed: 451, boil: boil
    });

    // Slender wrist & gracefully arched feminine palm
    const palm = [
      [112, 16], [62, 8], [16, 1], [-28, -2], [-50, 12], [-44, 34], [-12, 48], [44, 52], [106, 52]
    ];
    E.paintOpaqueUndercoat(ctx, palm, alpha * 0.92, P.paperLight, true);
    E.watercolorPolygon(ctx, palm, P.skinWarm, { alpha: alpha * 0.54, gradColor: P.skinShadow, smooth: true });
    E.charcoalTone(ctx, -4, 36, 38, 13, 0.1, P.sepia, alpha * 0.28, 452);

    // Cleanly separated slender fingers (graceful index poised toward silver thread, cascading middle/ring/pinky — ZERO overlap!)
    const fingers = [
      // Index (gracefully extended upper arch pinching/guiding thread)
      [[-28, -2], [-64, -14 - open * 10], [-98, -16 - open * 16], [-116, -6 - open * 20], [-108, 2 - open * 14], [-74, -4 - open * 6], [-34, 6]],
      // Middle (poised gently below index with clear daylight between fingertips)
      [[-32, 6],  [-70, 2 - open * 6],    [-106, 4 - open * 8],   [-124, 14 - open * 8], [-115, 22 - open * 6], [-78, 13 - open * 2], [-38, 15]],
      // Ring (softly trailing below middle)
      [[-30, 17], [-66, 18],              [-98, 24],              [-112, 34],            [-102, 40],            [-72, 29],            [-34, 25]],
      // Pinky (delicate lower curve)
      [[-24, 28], [-54, 32],              [-80, 40 + open * 3],   [-90, 49 + open * 4],  [-80, 54 + open * 4],  [-54, 43],            [-26, 36]]
    ];
    for (let i = 3; i >= 0; i--) {
      const f = fingers[i];
      E.paintOpaqueUndercoat(ctx, f, alpha * 0.88, P.paperLight, true);
      E.watercolorPolygon(ctx, f, P.skinWarm, { alpha: alpha * 0.52, gradColor: P.skinShadow, smooth: true });
      E.pencilStroke(ctx, f.slice(0, 4), {
        medium: 'charcoal', color: P.ironGall, width: 1.35 - i * 0.08, alpha: alpha * 0.80, seed: 460 + i * 4, boil: boil
      });
      E.pencilStroke(ctx, f.slice(3), {
        medium: 'graphite', color: P.sepia, width: 1.12, alpha: alpha * 0.68, seed: 461 + i * 4, boil: boil
      });
    }

    // Opposable slender thumb tucked gently across lower palm side (cleanly below index!)
    const thX = lerp(-86, -74, open);
    const thY = lerp(22, 42, open);
    const thumb = [[-12, 34], [-38, 38 + open * 6], [-64, 34 + open * 10], [thX, thY], [-74, thY - 9], [-48, 24 + open * 4], [-18, 24]];
    E.paintOpaqueUndercoat(ctx, thumb, alpha * 0.9, P.paperLight, true);
    E.watercolorPolygon(ctx, thumb, P.skinWarm, { alpha: alpha * 0.56, gradColor: P.skinShadow, smooth: true });
    E.pencilStroke(ctx, thumb.slice(0, 5), {
      medium: 'charcoal', color: P.ironGall, width: 1.4, alpha: alpha * 0.82, seed: 454, boil: boil
    });

    E.pencilStroke(ctx, [[112, 16], [56, 7], [6, 0], [-28, -2]], {
      medium: 'charcoal', color: P.ironGall, width: 1.6, alpha: alpha * 0.82, seed: 474, boil: boil, ghost: 0.14
    });
    E.pencilStroke(ctx, [[106, 52], [44, 52], [-14, 48], [-40, 38]], {
      medium: 'charcoal', color: P.ironGall, width: 1.6, alpha: alpha * 0.80, seed: 475, boil: boil
    });
    E.chalkHighlight(ctx, [[56, 7], [-24, -4], [-76, -15 - open * 10], [-110, -10 - open * 16]], {
      width: 1.5, alpha: alpha * 0.56, seed: 476, boil: boil
    });
    ctx.restore();

    const lx = lerp(-112, -104, open);
    const ly = lerp(-4, -18, open);
    return {
      x: bx + lx * Math.cos(rot) - ly * Math.sin(rot),
      y: by + lx * Math.sin(rot) + ly * Math.cos(rot)
    };
  }

  function drawVerse2Scene(ctx, t, localT, progress, tel, weight, boil, timeline, sceneObj) {
    const a = weight;
    const w1 = Math.sin(t * 1.45) * 11 + tel.v_rms * 16;
    const w2 = Math.cos(t * 1.15 + 0.7) * 9 + tel.a_rms * 12;

    // 1. Seamless candlelit twilight-indigo & warm sepia interior backdrop
    E.atmosphericSkyWash(ctx, LOGICAL_W, LOGICAL_H, [
      [0.0,  P.indigo, 0.34],
      [0.35, P.duskViolet, 0.24],
      [0.68, P.sepia, 0.24],
      [1.0,  P.rawUmber, 0.28]
    ], {
      y0: 0, y1: LOGICAL_H, alpha: a,
      clouds: [
        { x: 240, y: 200, rx: 320, ry: 210, color: P.indigo, alpha: 0.22, seed: 401 },
        { x: 1020, y: 240, rx: 310, ry: 220, color: P.sepia, alpha: 0.20, seed: 402 },
        { x: 640, y: 340, rx: 360, ry: 240, color: P.amberGlow, alpha: 0.16, multiply: false, seed: 403 }
      ]
    });

    // Soft horizontally-feathered glowing window moonbeam slicing diagonally across the shirt
    ctx.save();
    ctx.translate(650, 340);
    ctx.rotate(-0.26);
    const beamG = ctx.createLinearGradient(-340, 0, 340, 0);
    beamG.addColorStop(0.0, E.rgba(P.chalk, 0));
    beamG.addColorStop(0.24, E.rgba(P.chalk, a * 0.16));
    beamG.addColorStop(0.50, E.rgba(P.candleCore, a * 0.28));
    beamG.addColorStop(0.76, E.rgba(P.chalk, a * 0.14));
    beamG.addColorStop(1.0, E.rgba(P.chalk, 0));
    ctx.fillStyle = beamG;
    ctx.fillRect(-350, -540, 700, 1080);
    ctx.restore();

    // 2. ASYMMETRIC WIND-CAUGHT SHEER CAMBRIC LINEN SHIRT (Painted gouache folds, soft gathered cuffs, whisper-light edges!)
    const sx = 632;
    const sy = 152 + w1 * 0.25;

    // A) Left sleeve: draped slightly lower & gathered delicately into a ruffled cuff cradled by the left hand
    const leftSleeve = [
      [sx - 84, sy + 26],
      [sx - 156, sy + 64 - w2 * 0.4],
      [sx - 218, sy + 156 - w1 * 0.25],
      [sx - 252, sy + 244 + w2 * 0.2],  // tapered gathered wrist cuff!
      [sx - 274, sy + 272 + w2 * 0.22], // flared sheer cuff ruffle held by hand
      [sx - 226, sy + 292 + w1 * 0.2],
      [sx - 208, sy + 256 + w2 * 0.2],
      [sx - 144, sy + 224 + w2 * 0.3],
      [sx - 104, sy + 174 + w1 * 0.2]
    ];

    // B) Right sleeve: lifted & billowed higher rightward by the diagonal twilight breeze!
    const rightSleeve = [
      [sx + 84, sy + 22],
      [sx + 174, sy + 22 - w1 * 0.5],
      [sx + 258, sy + 78 - w2 * 0.45],
      [sx + 298, sy + 162 + w1 * 0.25], // lifted windswept right cuff
      [sx + 266, sy + 216 + w2 * 0.3],
      [sx + 222, sy + 196 + w1 * 0.25],
      [sx + 156, sy + 186 + w1 * 0.22],
      [sx + 112, sy + 158 + w2 * 0.2]
    ];

    // C) Asymmetric billowing translucent pleated bodice drifting gently rightward in wind!
    const bodice = [
      [sx - 86, sy + 26],
      [sx - 44, sy + 4],
      [sx - 12, sy + 26],
      [sx + 18, sy + 22],
      [sx + 48, sy + 4],
      [sx + 86, sy + 22],
      [sx + 118, sy + 158 + w2 * 0.2],
      [sx + 162, sy + 286 + w1 * 0.45],
      [sx + 198, sy + 356 + w2 * 0.5],  // wind-swept lifting right hem!
      [sx + 106, sy + 378 + w1 * 0.4],
      [sx + 14,  sy + 360 + w2 * 0.35],
      [sx - 74,  sy + 394 + w1 * 0.3],
      [sx - 144, sy + 376 + w2 * 0.3],
      [sx - 114, sy + 268 + w1 * 0.25],
      [sx - 104, sy + 166 + w2 * 0.18]
    ];

    // Sheer luminous gouache ivory washes + delicate cool-indigo shadow depth (painted feel, NOT flat fill!)
    E.paintOpaqueUndercoat(ctx, leftSleeve, a * 0.56, P.chalk, true);
    E.paintOpaqueUndercoat(ctx, rightSleeve, a * 0.52, P.chalk, true);
    E.paintOpaqueUndercoat(ctx, bodice, a * 0.68, P.gouacheWhite, true);

    E.watercolorPolygon(ctx, leftSleeve, P.linenMid, { alpha: a * 0.26, gradColor: P.indigo, smooth: true });
    E.watercolorPolygon(ctx, rightSleeve, P.linenMid, { alpha: a * 0.22, gradColor: P.indigo, smooth: true });
    E.watercolorPolygon(ctx, bodice, P.paperLight, { alpha: a * 0.42, gradColor: P.linenMid, multiply: false, smooth: true });

    // Rich painted charcoal/indigo vertical linen drapery shadow valleys + soft directional shading!
    E.charcoalTone(ctx, sx - 172, sy + 182, 56, 78, 0.32, P.indigo, a * 0.16, 408);
    E.charcoalTone(ctx, sx + 188, sy + 132, 62, 68, -0.38, P.indigo, a * 0.15, 409);
    E.charcoalTone(ctx, sx + 48, sy + 245, 76, 118, -0.14, P.linenShadow, a * 0.20, 410);

    const pleats = [
      [[sx - 44, sy + 16], [sx - 66, sy + 150], [sx - 96, sy + 275 + w1 * 0.2], [sx - 114, sy + 376 + w2 * 0.28]],
      [[sx - 18, sy + 32], [sx - 24, sy + 172], [sx - 40, sy + 298 + w2 * 0.22], [sx - 46, sy + 384 + w1 * 0.28]],
      [[sx + 16, sy + 34], [sx + 30, sy + 178], [sx + 56, sy + 296 + w1 * 0.28], [sx + 84, sy + 374 + w2 * 0.34]],
      [[sx + 50, sy + 18], [sx + 84, sy + 152], [sx + 128, sy + 272 + w2 * 0.3], [sx + 166, sy + 356 + w1 * 0.38]],
      // Soft gathered sleeve folds
      [[sx - 112, sy + 56], [sx - 172, sy + 142 - w1 * 0.2], [sx - 224, sy + 246 + w2 * 0.2]],
      [[sx - 148, sy + 102], [sx - 196, sy + 184], [sx - 238, sy + 258 + w2 * 0.2]],
      [[sx + 114, sy + 44], [sx + 194, sy + 96 - w2 * 0.25], [sx + 266, sy + 174 + w1 * 0.2]],
      [[sx + 132, sy + 88], [sx + 206, sy + 136 - w1 * 0.2], [sx + 256, sy + 198 + w2 * 0.22]]
    ];
    for (let i = 0; i < pleats.length; i++) {
      E.dryBrushStreak(ctx, pleats[i], 13, P.indigo, a * 0.15, 412 + i * 7, boil);
      E.pencilStroke(ctx, pleats[i], {
        medium: 'graphite', color: P.graphiteSoft, width: 1.05, alpha: a * 0.42, seed: 418 + i * 5, boil: boil
      });
      const ridge = pleats[i].map(function (pt) { return [pt[0] + 9, pt[1] - 4]; });
      E.chalkHighlight(ctx, ridge, { width: 2.5, alpha: a * 0.66, seed: 424 + i * 5, boil: boil });
    }
    // Delicate gathered cuff wrist-tie creases on left & right sleeves!
    E.pencilStroke(ctx, [[sx - 250, sy + 246 + w2 * 0.2], [sx - 228, sy + 256 + w2 * 0.2], [sx - 208, sy + 256 + w2 * 0.2]], {
      medium: 'graphite', color: P.sepia, width: 1.15, alpha: a * 0.56, seed: 429, boil: boil
    });
    E.pencilStroke(ctx, [[sx + 286, sy + 168 + w1 * 0.25], [sx + 264, sy + 184 + w1 * 0.25], [sx + 242, sy + 196 + w1 * 0.25]], {
      medium: 'graphite', color: P.sepia, width: 1.1, alpha: a * 0.50, seed: 430, boil: boil
    });

    // Soft shaded inner collar hollow & fluttering neckline tie ribbons
    const collarHollow = [[sx - 44, sy + 4], [sx - 12, sy + 26], [sx + 18, sy + 22], [sx + 48, sy + 4], [sx + 20, sy - 6], [sx - 18, sy - 6]];
    E.watercolorPolygon(ctx, collarHollow, P.indigo, { alpha: a * 0.26, gradColor: P.sepia, smooth: true });
    E.pencilStroke(ctx, [[sx - 44, sy + 4], [sx - 14, sy + 26], [sx + 2, sy + 72], [sx + 18, sy + 22], [sx + 48, sy + 4]], {
      medium: 'graphite', color: P.ironGall, width: 1.45, alpha: a * 0.72, seed: 432, boil: boil
    });
    E.pencilStroke(ctx, [[sx - 8, sy + 32], [sx - 24, sy + 62 + w1 * 0.2], [sx - 14, sy + 88 + w2 * 0.3]], {
      medium: 'graphite', color: P.sepia, width: 1.0, alpha: a * 0.62, seed: 433, boil: boil
    });
    E.pencilStroke(ctx, [[sx + 12, sy + 30], [sx + 32, sy + 58 - w2 * 0.2], [sx + 26, sy + 84 + w1 * 0.25]], {
      medium: 'graphite', color: P.sepia, width: 1.0, alpha: a * 0.62, seed: 434, boil: boil
    });

    // Whisper-soft broken painterly perimeter edges + luminous white gouache rim light (sheer cloth, NOT cartoon outline!)
    E.pencilStroke(ctx, leftSleeve, { medium: 'graphite', color: P.graphiteSoft, width: 1.05, alpha: a * 0.38, seed: 435, boil: boil, ghost: 0.14 });
    E.pencilStroke(ctx, rightSleeve, { medium: 'graphite', color: P.graphiteSoft, width: 1.05, alpha: a * 0.36, seed: 436, boil: boil, ghost: 0.14 });
    E.pencilStroke(ctx, bodice.slice(5), { medium: 'graphite', color: P.graphiteSoft, width: 1.1, alpha: a * 0.42, seed: 437, boil: boil, ghost: 0.14 });
    E.pencilStroke(ctx, [bodice[0], bodice[1], bodice[2], bodice[3], bodice[4], bodice[5]], {
      medium: 'graphite', color: P.ironGall, width: 1.15, alpha: a * 0.56, seed: 438, boil: boil
    });
    E.chalkHighlight(ctx, [leftSleeve[0], leftSleeve[1], leftSleeve[2]], { width: 2.8, alpha: a * 0.64, seed: 439, boil: boil });
    E.chalkHighlight(ctx, [rightSleeve[0], rightSleeve[1], rightSleeve[2], rightSleeve[3]], { width: 2.8, alpha: a * 0.64, seed: 440, boil: boil });
    E.chalkHighlight(ctx, [bodice[8], bodice[9], bodice[10], bodice[11], bodice[12]], { width: 2.2, alpha: a * 0.54, seed: 441, boil: boil });

    // 3. Graceful Slender Human Hands (Left lifting the sleeve hem, Right guiding phantom thread!)
    const leftLift = Math.sin(t * 1.45) * 6 + tel.breath * -4;
    drawSlenderLeftHand(ctx, 296, 444, leftLift, a, boil);

    const releaseAmt = smoothstep(0.68, 0.94, progress);
    const rightHoverY = Math.cos(t * 1.25) * 7 - releaseAmt * 14;
    const pinchPt = drawSlenderRightHand(ctx, 974, 386 + rightHoverY, releaseAmt, a, boil);

    // 4. Fragile Silver-Chalk Thread ("Without no seams nor needlework" -> curls & dissolves into dust motes!)
    const threadIn = smoothstep(0.42, 0.56, progress);
    const threadDissolve = smoothstep(0.68, 0.92, progress);
    const threadAlpha = a * threadIn * (1 - threadDissolve * 0.85);
    if (threadAlpha > 0.015) {
      const tw = Math.sin(t * 2.0) * 14;
      const threadPts = [
        [pinchPt.x, pinchPt.y],
        [pinchPt.x - 56, pinchPt.y - 36 + tw * 0.3],
        [pinchPt.x - 134, pinchPt.y - 12 - tw * 0.5],
        [pinchPt.x - 216, pinchPt.y - 54 + tw * 0.6],
        [pinchPt.x - 294, pinchPt.y - 28 - tw * 0.7],
        [pinchPt.x - 368, pinchPt.y - 78 + tw * 0.8]
      ];
      E.chalkHighlight(ctx, threadPts, {
        color: P.chalk, width: 2.0, alpha: threadAlpha * 0.94,
        seed: 491, boil: boil, progress: smoothstep(0.42, 0.62, progress)
      });
      E.pencilStroke(ctx, threadPts, {
        medium: 'ink', color: P.candleCore, width: 0.9, alpha: threadAlpha * 0.68,
        seed: 492, boil: boil, progress: smoothstep(0.42, 0.62, progress)
      });

      // Tiny ghostly chalk dust motes lifting off the dissolving thread (no seams!)
      const sp = E.sampleSpline(threadPts, 11, false);
      const rng = E.mulberry32(495);
      for (let i = 3; i < sp.length; i += 2) {
        const pt = sp[i];
        const scatter = (0.25 + threadDissolve) * (16 + rng() * 48);
        const mx = pt.x + (rng() - 0.5) * scatter + Math.sin(t * 1.6 + i) * 5;
        const my = pt.y - (0.2 + threadDissolve) * (12 + rng() * 42);
        ctx.fillStyle = E.rgba(P.chalk, a * threadIn * (0.48 + 0.44 * (1 - threadDissolve)));
        ctx.beginPath();
        ctx.arc(mx, my, 1.1 + rng() * 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 5. Lush Botanical Herbs Framing the Four Corners
    const herbs = getHerbTriggersForScene(timeline, sceneObj);
    drawParsley(ctx, 118, 255, 0.92, 0.56, smoothstep(herbs.parsley - 0.1, herbs.parsley + 1.3, t), a * 0.82, t, boil, 496);
    drawSage(ctx, 1175, 245, 0.95, -0.72, smoothstep(herbs.sage - 0.1, herbs.sage + 1.3, t), a * 0.82, t, boil, 497);
    drawRosemary(ctx, 1152, 680, 0.98, -0.42, smoothstep(herbs.rosemary - 0.1, herbs.rosemary + 1.3, t), a * 0.82, t, boil, 498);
    drawThyme(ctx, 98, 675, 0.94, 0.40, smoothstep(herbs.thyme - 0.1, herbs.thyme + 1.3, t), a * 0.80, t, boil, 499);
    drawDriftingHerbs(ctx, t, a * 0.48, 0.85, 11, 500);
  }

  // ==========================================================================
  // 8. SCENE 4: VERSE 3 — CRASHING SUMI-INK SEA WAVES, WET SHORE & TALL FIGURE
  // ==========================================================================
  function drawTallSeaTraveler(ctx, x, y, gale, t, alpha, boil) {
    // Tall poetic windswept human figure (~238px tall) standing on wet tidal sand:
    // long wool greatcoat draped down near naturally tapered boots, sculpted wavy hair (zero spikes!), rich wet-sand reflection!
    ctx.save();
    ctx.translate(x, y);

    const flap = Math.sin(t * 3.1) * 14 * gale;
    const flap2 = Math.cos(t * 2.5 + 0.6) * 9 * gale;

    // Rich shimmering broken wet-sand reflection + soft grounded contact shadow beneath his boots!
    E.charcoalTone(ctx, 0, 3, 28, 7, -0.1, P.charcoal, alpha * 0.34, 539);
    ctx.save();
    ctx.scale(1, -0.56);
    ctx.translate(0, -8);
    E.charcoalTone(ctx, -18, -108, 34, 108, 0.06, P.indigoDeep, alpha * 0.30, 540);
    E.dryBrushStreak(ctx, [[-10, -14], [-18, -92], [-12, -186]], 26, P.indigoDeep, alpha * 0.22, 541, boil);
    E.dryBrushStreak(ctx, [[8, -16], [4, -106], [8, -168]], 14, P.charcoal, alpha * 0.16, 542, boil);
    ctx.restore();

    // Naturally tapered trousers & soft weathered boots planted slightly staggered on wet tide sand
    const legL = [[-13, -58], [-15, -30], [-14, -8], [-25, -1], [-18, 2], [-7, 0], [-6, -28], [-2, -58]];
    const legR = [[4, -58], [8, -28], [11, -7], [5, 2], [17, 3], [21, -2], [17, -28], [15, -58]];
    E.watercolorPolygon(ctx, legL, P.charcoal, { alpha: alpha * 0.80, gradColor: P.sepia, smooth: true });
    E.watercolorPolygon(ctx, legR, P.charcoal, { alpha: alpha * 0.82, gradColor: P.sepia, smooth: true });
    E.pencilStroke(ctx, [[-13, -58], [-15, -30], [-14, -8], [-24, -1], [-8, 0]], {
      medium: 'charcoal', color: P.charcoal, width: 1.5, alpha: alpha * 0.88, seed: 544, boil: boil
    });
    E.pencilStroke(ctx, [[15, -58], [17, -28], [20, -1], [6, 2]], {
      medium: 'charcoal', color: P.charcoal, width: 1.5, alpha: alpha * 0.88, seed: 545, boil: boil
    });

    // Long heavy wool greatcoat draped closer to calves & billowing dramatically leftward in sea gale!
    const coatPoly = [
      [-12, -196], [10, -195], [22, -178], [25, -142], [22, -104], [26, -42],
      [6, -38], [-22 - flap * 0.3, -36],
      [-76 - flap * 0.95, -32 + flap2 * 0.35],
      [-94 - flap * 1.1, -68 + flap2 * 0.5],
      [-58 - flap * 0.55, -118 + flap2 * 0.2],
      [-26, -158], [-20, -180]
    ];
    E.paintOpaqueUndercoat(ctx, coatPoly, alpha * 0.90, P.paperLight, true);
    E.watercolorPolygon(ctx, coatPoly, P.indigoDeep, {
      alpha: alpha * 0.88, gradColor: P.charcoal, smooth: true
    });
    E.shadeStrokes(ctx, coatPoly, { angle: -1.05, spacing: 7.5, alpha: alpha * 0.26, color: P.charcoal, seed: 546, boil: boil });
    E.pencilStroke(ctx, [[-14, -174], [-34, -122], [-66 - flap * 0.65, -54 + flap2 * 0.3]], {
      medium: 'charcoal', color: P.charcoal, width: 2.0, alpha: alpha * 0.72, seed: 547, boil: boil
    });
    E.pencilStroke(ctx, [[10, -174], [14, -112], [16, -44]], {
      medium: 'charcoal', color: P.charcoal, width: 1.5, alpha: alpha * 0.65, seed: 548, boil: boil
    });
    E.pencilStroke(ctx, coatPoly.concat([coatPoly[0]]), {
      medium: 'charcoal', color: P.charcoal, width: 1.9, alpha: alpha * 0.90, seed: 549, boil: boil, ghost: 0.16
    });

    // Soft flowing S-curved burnt-sienna wool scarf trailing gracefully in the salt gale
    const scarfTop = [[-6, -193], [-32, -184 + flap * 0.2], [-66 - flap * 0.45, -190 + flap2 * 0.4], [-104 - flap * 0.75, -174 + flap2 * 0.6]];
    const scarfBot = [[-6, -186], [-34, -175 + flap * 0.18], [-68 - flap * 0.45, -178 + flap2 * 0.35], [-102 - flap * 0.72, -162 + flap2 * 0.55]];
    E.dryBrushStreak(ctx, scarfTop, 9, P.burntSienna, alpha * 0.68, 550, boil);
    E.dryBrushStreak(ctx, scarfBot, 8, P.sepia, alpha * 0.56, 551, boil);
    E.pencilStroke(ctx, scarfTop, {
      medium: 'graphite', color: P.ironGall, width: 1.05, alpha: alpha * 0.54, seed: 556, boil: boil
    });

    // Sculpted neck & sensitive side-profile head with natural soft wavy hair mass (ZERO stiff spikes!)
    const headPoly = [
      [-6, -195], [-10, -206], [-17, -210], [-16, -215], [-21, -221], [-17, -228],
      [-14, -236], [-2, -242], [12, -238], [18, -226], [16, -210], [8, -195]
    ];
    E.paintOpaqueUndercoat(ctx, headPoly, alpha * 0.90, P.paperLight, true);
    E.watercolorPolygon(ctx, headPoly, P.charcoal, { alpha: alpha * 0.86, gradColor: P.sepia, smooth: true });
    E.pencilStroke(ctx, headPoly.concat([headPoly[0]]), {
      medium: 'charcoal', color: P.charcoal, width: 1.55, alpha: alpha * 0.90, seed: 552, boil: boil
    });
    // Soft wind-tossed wavy hair mass hugging nape (NO sharp antenna sticks!)
    E.dryBrushStreak(ctx, [[4, -239], [16, -232], [20, -216], [14, -202]], 7, P.charcoal, alpha * 0.72, 553, boil);

    // Crisp luminous storm-light chalk rim along his seaward (left) silhouette!
    E.chalkHighlight(ctx, [[-17, -228], [-21, -220], [-15, -200], [-22, -172], [-56 - flap * 0.55, -118], [-90 - flap * 1.05, -66]], {
      color: P.chalk, width: 1.9, alpha: alpha * 0.78, seed: 555, boil: boil
    });
    ctx.restore();
  }

  function drawVerse3Scene(ctx, t, localT, progress, tel, weight, boil, timeline, sceneObj) {
    const a = weight;
    const storm = 0.68 + tel.energy * 0.7 + tel.v_rms * 0.52;
    const surge = Math.sin(t * 1.48) * 30 + Math.sin(t * 0.68) * 14;

    // 1. Full-bleed dramatic storm-break sky
    E.atmosphericSkyWash(ctx, LOGICAL_W, LOGICAL_H, [
      [0.0,  P.indigoDeep, 0.50],
      [0.34, P.prussian, 0.40],
      [0.64, P.slateTeal, 0.26],
      [0.86, P.ochre, 0.28],
      [1.0,  P.burntSienna, 0.18]
    ], {
      y0: 0, y1: 350, alpha: a,
      clouds: [
        { x: 260, y: 112, rx: 380, ry: 105, color: P.indigoDeep, alpha: 0.32, seed: 501 },
        { x: 920, y: 124, rx: 360, ry: 115, color: P.prussian, alpha: 0.26, seed: 502 },
        { x: 540, y: 274, rx: 360, ry: 90, color: P.amberGlow, alpha: 0.30, multiply: false, seed: 503 }
      ]
    });
    E.mistVeil(ctx, 420, 145, 340, 42, a * 0.22, 504, P.indigoDeep);
    E.mistVeil(ctx, 880, 175, 310, 38, a * 0.20, 505, P.chalk);

    // Distant dark Yorkshire headland sitting CLEANLY ON the sea horizon (y=328)
    const headland = [[780, 332], [875, 324], [985, 294], [1125, 268], [1250, 274], [1320, 288]];
    E.paintTerrainLayer(ctx, headland, 336, P.indigoDeep, { alpha: a * 0.56, seed: 506, granulate: false });
    const bPulse = 0.72 + 0.28 * Math.sin(t * 2.5);
    const bg = ctx.createRadialGradient(1132, 264, 1, 1132, 264, 26 * bPulse);
    bg.addColorStop(0, E.rgba(P.candleCore, a * 0.94 * bPulse));
    bg.addColorStop(0.35, E.rgba(P.amberGlow, a * 0.42 * bPulse));
    bg.addColorStop(1, E.rgba(P.amberGlow, 0));
    ctx.fillStyle = bg;
    ctx.beginPath();
    ctx.arc(1132, 264, 26 * bPulse, 0, Math.PI * 2);
    ctx.fill();

    // 2. Full-Width Deep Ocean + Secondary Distant Swell + Horizontal Sea-Surface Brushwork
    E.paintTerrainLayer(ctx, [[-40, 328], [420, 326], [880, 328], [1320, 326]], 750, P.prussian, {
      alpha: a * 0.62, gradColor: P.slateTeal, endAlpha: 0.52, seed: 508
    });
    // Subtle textured horizontal sumi-ink & chalk sea-surface swells across open water
    for (let i = 0; i < 12; i++) {
      const wy = 338 + i * 9;
      const wx = 20 + ((i * 183 + Math.round(t * 14)) % 980);
      const wlen = 65 + (i % 4) * 38;
      E.dryBrushStreak(ctx, [[wx, wy], [wx + wlen, wy + 1.5]], 4, i % 3 === 0 ? P.chalk : P.indigoDeep, a * (i % 3 === 0 ? 0.34 : 0.22), 509 + i, boil);
    }
    // Secondary trailing midground ocean swell with distant breaking whitewater foam!
    const swell2 = [[-40, 374], [140, 368], [320, 382], [540, 366], [710, 356 - storm * 5], [890, 374], [1140, 368], [1320, 364]];
    E.paintTerrainLayer(ctx, swell2, 620, P.slateTeal, { alpha: a * 0.38, gradColor: P.prussian, seed: 518 });
    E.dryBrushStreak(ctx, [[560, 368], [710, 356 - storm * 5], [840, 372]], 10, P.chalk, a * 0.56, 519, boil);

    // 3. DRAMATIC ASYMMETRIC CURLING SUMI-INK BREAKING WAVE (Deep shadowed concave lip trough + boiling whitewater roll!)
    const wShift = Math.sin(t * 1.35) * 18;
    const breakerCrest = [
      [-40, 446], [85, 434], [192, 408], [286, 374 - storm * 14], [362, 360 - storm * 17 + wShift * 0.25],
      [414, 378 - storm * 11 + wShift * 0.35], [468, 424 + wShift * 0.25], [610, 438], [860, 428], [1320, 418]
    ];
    E.paintTerrainLayer(ctx, breakerCrest, 750, P.slateTeal, {
      alpha: a * 0.66, gradColor: P.prussian, midAlpha: 0.54, endAlpha: 0.42, seed: 520
    });
    // Deep dramatic indigo-charcoal concave barrel shadow tucked directly beneath the curling right-facing wave lip!
    const barrelShadow = [
      [255, 398 - storm * 8], [358, 372 - storm * 14 + wShift * 0.25], [422, 388 - storm * 8 + wShift * 0.35],
      [464, 434 + wShift * 0.2], [388, 456], [284, 448], [218, 426]
    ];
    E.watercolorPolygon(ctx, barrelShadow, P.indigoDeep, { alpha: a * 0.72, gradColor: P.charcoal, smooth: true });
    E.charcoalTone(ctx, 362, 418 - storm * 6, 86, 34, 0.16, P.charcoal, a * 0.46, 521);
    // Curved barrel-following dark sumi-ink & turquoise water-flow strokes inside the rising face
    E.dryBrushStreak(ctx, [[120, 452], [225, 424], [326, 390 - storm * 12], [398, 398 - storm * 6]], 14, P.indigoDeep, a * 0.44, 528, boil);
    E.dryBrushStreak(ctx, [[165, 466], [278, 446], [392, 440], [505, 452]], 12, P.prussian, a * 0.42, 529, boil);

    // Expressive curled ink crest lip + ragged frothy breaking dry-brush white gouache foam & boiling lower whitewater!
    E.pencilStroke(ctx, [[185, 410], [286, 374 - storm * 14], [362, 360 - storm * 17 + wShift * 0.25], [418, 380 - storm * 10 + wShift * 0.35], [470, 424]], {
      medium: 'charcoal', color: P.indigoDeep, width: 2.3, alpha: a * 0.76, seed: 522, boil: boil
    });
    E.dryBrushStreak(ctx, [
      [182, 408], [288, 374 - storm * 14], [366, 359 - storm * 17 + wShift * 0.25], [428, 386 - storm * 9 + wShift * 0.35], [488, 428], [625, 444]
    ], 18, P.chalk, a * 0.90, 523, boil);
    E.chalkHighlight(ctx, [
      [230, 394 - storm * 10], [312, 368 - storm * 15], [372, 360 - storm * 17 + wShift * 0.25], [422, 382 - storm * 10 + wShift * 0.35]
    ], { width: 3.4, alpha: a * 0.94, seed: 524, boil: boil });
    // Churning whitewater foam roll exploding at the base of the breaking lip!
    E.mistVeil(ctx, 432, 424, 92, 26, a * 0.62, 535);
    E.dryBrushStreak(ctx, [[345, 448], [448, 440], [568, 446], [685, 452]], 14, P.chalk, a * 0.68, 536, boil);
    E.mistVeil(ctx, 398, 370 - storm * 12, 130, 34, a * 0.48, 525);
    E.inkSplatter(ctx, 385, 364 - storm * 12, 68, 34, P.chalk, a * 0.86, 526 + boil, 1.25, -0.45);
    E.inkSplatter(ctx, 485, 412, 54, 24, P.chalk, a * 0.78, 527 + boil, 1.0, -0.35);

    // 3. Reflective Wet Golden-Ochre Sea Strand Sweeping Smoothly Across Right & Bottom (Overlaps sea cleanly!)
    const shoreRidge = [[-40, 745], [220, 704], [475, 616], [735, 514], [1005, 414], [1235, 356], [1320, 344]];
    E.paintOpaqueUndercoat(ctx, shoreRidge.concat([[1320, 755], [-40, 755]]), a * 0.94, P.paperWarm, false);
    E.paintTerrainLayer(ctx, shoreRidge, 755, P.ochre, {
      alpha: a * 0.46, gradColor: P.rawUmber, endAlpha: 0.56, seed: 512
    });
    // Glossy wet indigo sky sheen mirroring onto tidal sand
    E.watercolorBloom(ctx, 880, 565, 330, 128, P.slateTeal, {
      alpha: a * 0.22, angle: -0.32, seed: 513, dabs: 2, multiply: true
    });

    // 4. Barefoot Footprints Along the Wet Sand (softly dissolving where surging tidal foam laps!)
    const footprints = [
      [1085, 614, -0.42], [1042, 590, -0.44], [998, 566, -0.40], [954, 546, -0.45],
      [908, 530, -0.46],  [858, 516, -0.42], [808, 504, -0.48], [758, 496, -0.44]
    ];
    const tideReachX = 768 + surge * 1.4;
    for (let i = 0; i < footprints.length; i++) {
      const fp = footprints[i];
      const washed = smoothstep(fp[0] - 58, fp[0] + 45, tideReachX);
      const fpA = a * (0.72 - washed * 0.52);
      if (fpA <= 0.04) continue;
      ctx.save();
      ctx.translate(fp[0], fp[1]);
      ctx.rotate(fp[2]);
      E.watercolorBloom(ctx, 0, 0, 13 + washed * 7, 6 + washed * 3, washed > 0.3 ? P.slateTeal : P.sepia, {
        alpha: fpA * 0.48, seed: 516 + i, dabs: 1
      });
      ctx.fillStyle = E.rgba(P.sepia, fpA * 0.66);
      ctx.beginPath();
      ctx.ellipse(-6, 0, 4.6, 2.9, 0, 0, Math.PI * 2);
      ctx.ellipse(4, 0, 5.4, 3.5, 0, 0, Math.PI * 2);
      ctx.fill();
      for (let toe = 0; toe < 4; toe++) {
        ctx.beginPath();
        ctx.arc(11 - toe * 0.55, -2.4 + toe * 1.65, 1.1 - toe * 0.1, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }

    // 5. Organic Sweeping Tidal Swash & Lacy White Seafoam Lapping Smoothly Along the Diagonal Beach (NO V-boomerang!)
    const swashCurve = [
      [-40, 742], [180 + surge * 0.4, 704], [395 + surge * 0.7, 646], [595 + surge * 0.95, 578],
      [755 + surge * 1.15, 512], [930 + surge * 0.9, 444], [1125 + surge * 0.5, 384], [1320, 344]
    ];
    // Translucent shallow foaming sea sheet sweeping up the diagonal beach
    const swashSheet = swashCurve.concat([[1320, 336], [1080, 376], [760, 466], [340, 560], [-40, 620]]);
    E.watercolorPolygon(ctx, swashSheet, P.slateTeal, { alpha: a * 0.44, gradColor: P.prussian, smooth: true });
    // Delicate dry-brush white seafoam lace hugging the organic wet diagonal shoreline!
    E.dryBrushStreak(ctx, swashCurve.slice(1, 7), 18, P.chalk, a * 0.78, 530, boil);
    E.chalkHighlight(ctx, swashCurve.slice(1, 7), { width: 2.8, alpha: a * 0.88, seed: 531, boil: boil });
    // Secondary retreating seafoam lace filaments rippling behind the lead edge
    E.dryBrushStreak(ctx, [
      [80, 690], [295 + surge * 0.5, 628], [520 + surge * 0.8, 558], [710 + surge * 0.9, 494]
    ], 11, P.chalk, a * 0.48, 532, boil);
    E.inkSplatter(ctx, 690 + surge * 1.0, 530, 64, 24, P.chalk, a * 0.72, 533 + boil, 0.75, -0.25);

    // 6. Tall Poignant Windswept Human Figure Standing at the Tideline!
    drawTallSeaTraveler(ctx, 932, 534, storm, t, a, boil);

    // 8. Fine Slanting Charcoal Rain / Sea-Mist Strokes Responding to Vocal Climax
    const rainCount = Math.round(20 + storm * 24);
    const rng = E.mulberry32(560 + boil * 13);
    ctx.save();
    for (let i = 0; i < rainCount; i++) {
      const rx = rng() * (LOGICAL_W + 200) - 100;
      const ry = rng() * (LOGICAL_H * 0.76);
      const rLen = 28 + rng() * 64;
      ctx.strokeStyle = E.rgba(i % 3 === 0 ? P.chalk : P.indigoDeep, a * (0.10 + rng() * 0.13) * clamp(storm, 0.5, 1.35));
      ctx.lineWidth = 0.7 + rng() * 0.75;
      ctx.beginPath();
      ctx.moveTo(rx, ry);
      ctx.lineTo(rx - rLen * 0.42, ry + rLen);
      ctx.stroke();
    }
    ctx.restore();

    // 9. Wind-swept Botanical Herbs in the Storm Gale
    const herbs = getHerbTriggersForScene(timeline, sceneObj);
    const hAlpha = a * 0.78 * (1 - smoothstep(0.68, 0.92, progress) * 0.42);
    drawParsley(ctx, 1132, 688, 0.96, -0.62, smoothstep(herbs.parsley - 0.1, herbs.parsley + 1.2, t), hAlpha, t, boil, 571);
    drawSage(ctx, 1218, 650, 0.98, -0.78, smoothstep(herbs.sage - 0.1, herbs.sage + 1.2, t), hAlpha, t, boil, 572);
    drawRosemary(ctx, 88, 224, 0.92, 1.08, smoothstep(herbs.rosemary - 0.1, herbs.rosemary + 1.2, t), hAlpha, t, boil, 573);
    drawThyme(ctx, 1170, 212, 0.88, -1.16, smoothstep(herbs.thyme - 0.1, herbs.thyme + 1.2, t), hAlpha, t, boil, 574);
    drawDriftingHerbs(ctx, t, a * 0.66, -1.55, 16, 579);
  }

  // ==========================================================================
  // 9. SCENE 5: CODA & OUTRO — TWO EXPRESSIVE REACHING HUMAN FIGURES IN DUSK MIST
  //    (Complete Fine-Art Rebuild — ZERO salt-shakers, ZERO stick arms, ZERO potatoes!)
  // ==========================================================================
  function drawCodaTraveler(ctx, x, y, reach, sketchFade, alpha, t, boil) {
    // Museum-grade standing traveler (~226px tall) facing right: long draped greatcoat, tapered boots in soft grass shadow,
    // sculpted profile head & wavy hair, anatomical gently-bent elbow & slender upturned open reaching hand (ZERO rubber-hose dip!)
    ctx.save();
    ctx.translate(x, y);

    const breeze = Math.sin(t * 1.15) * 6;
    const washA = alpha * (1 - sketchFade * 0.88);
    const lineA = alpha * (1 - sketchFade * 0.50);

    // Soft grounded hillside shadow under boots
    if (washA > 0.02) {
      E.charcoalTone(ctx, -4, 3, 34, 7, 0, P.charcoal, washA * 0.34, 619);
    }

    // Naturally staggered tapered boots emerging modestly beneath long greatcoat hem
    const bootBack = [[-16, -42], [-18, -16], [-22, -1], [-8, 1], [-5, -18], [-3, -42]];
    const bootFront = [[2, -42], [7, -18], [9, 1], [23, 2], [20, -4], [14, -20], [13, -42]];
    if (washA > 0.02) {
      E.watercolorPolygon(ctx, bootBack, P.charcoal, { alpha: washA * 0.78, smooth: true });
      E.watercolorPolygon(ctx, bootFront, P.charcoal, { alpha: washA * 0.82, smooth: true });
    }
    E.pencilStroke(ctx, [[-16, -42], [-18, -16], [-21, -1], [-8, 1]], {
      medium: 'graphite', color: P.charcoal, width: lerp(1.45, 0.85, sketchFade), alpha: lineA * 0.84, seed: 620, boil: boil
    });
    E.pencilStroke(ctx, [[13, -42], [15, -18], [22, 1], [9, 1]], {
      medium: 'graphite', color: P.charcoal, width: lerp(1.45, 0.85, sketchFade), alpha: lineA * 0.84, seed: 621, boil: boil
    });

    // Long gracefully draped greatcoat & anatomical angled reaching right arm (crisp elbow & forearm — NO U-curve dip!)
    const elX = 36 + reach * 6;
    const elY = -142 - reach * 2;
    const wrX = 76 + reach * 16;
    const wrY = -152 - reach * 10 + breeze * 0.2;
    const coatAndArm = [
      [-11, -176], [9, -176], [19, -164],
      [elX + 3, elY - 6], [wrX, wrY - 4],          // upper shoulder -> elbow -> wrist top
      [wrX + 10, wrY - 6], [wrX + 19, wrY - 6],    // slender upturned palm & reaching index!
      [wrX + 20, wrY - 2], [wrX + 15, wrY + 2],    // delicate finger curve
      [wrX + 4, wrY + 4], [wrX - 2, wrY + 3],      // wrist bottom
      [elX - 2, elY + 6], [16, -142],              // elbow underside -> chest
      [19, -104], [24, -36], [2, -34],             // long draped coat hem reaching calves!
      [-26, -30], [-54 - breeze * 0.55, -28], [-44 - breeze * 0.35, -96], [-24, -156]
    ];
    if (washA > 0.02) {
      E.paintOpaqueUndercoat(ctx, coatAndArm, washA * 0.84, P.paperLight, false);
      E.watercolorPolygon(ctx, coatAndArm, P.indigoDeep, { alpha: washA * 0.78, gradColor: P.sepia, smooth: false });
      E.shadeStrokes(ctx, coatAndArm, { angle: -1.1, spacing: 7.5, alpha: washA * 0.24, color: P.charcoal, seed: 622, boil: boil, smooth: false });
    }
    // Crisp continuous anatomical contour lines along coat & articulated arm!
    E.pencilStroke(ctx, [[-24, -156], [-44 - breeze * 0.35, -96], [-54 - breeze * 0.55, -28], [-22, -30], [24, -36], [19, -104], [16, -142]], {
      medium: sketchFade > 0.45 ? 'graphite' : 'charcoal',
      color: sketchFade > 0.45 ? P.graphiteSoft : P.charcoal,
      width: lerp(1.75, 0.9, sketchFade), alpha: lineA * 0.88, seed: 623, boil: boil, ghost: 0.14
    });
    E.pencilStroke(ctx, [[16, -166], [elX + 3, elY - 6], [wrX, wrY - 4], [wrX + 18, wrY - 6]], {
      medium: 'charcoal', color: P.charcoal, width: lerp(1.5, 0.85, sketchFade), alpha: lineA * 0.86, seed: 626, boil: boil
    });
    E.pencilStroke(ctx, [[16, -144], [elX - 2, elY + 6], [wrX - 1, wrY + 3], [wrX + 15, wrY + 2]], {
      medium: 'graphite', color: P.sepia, width: lerp(1.3, 0.8, sketchFade), alpha: lineA * 0.78, seed: 627, boil: boil
    });
    // Draped coat wool fold lines
    E.pencilStroke(ctx, [[-12, -152], [-26, -98], [-38 - breeze * 0.3, -34]], {
      medium: 'graphite', color: P.charcoal, width: lerp(1.25, 0.75, sketchFade), alpha: lineA * 0.58, seed: 624, boil: boil
    });
    E.pencilStroke(ctx, [[4, -146], [8, -90], [10, -36]], {
      medium: 'graphite', color: P.charcoal, width: lerp(1.15, 0.7, sketchFade), alpha: lineA * 0.52, seed: 629, boil: boil
    });

    // Sculpted sensitive male profile head & soft wavy hair mass looking tenderly across toward her
    const headPts = [
      [-6, -176], [-9, -188], [-15, -200], [-11, -214], [1, -220], [13, -215],
      [16, -204], [20, -196], [16, -190], [17, -184], [11, -177]
    ];
    if (washA > 0.02) {
      E.paintOpaqueUndercoat(ctx, headPts, washA * 0.84, P.paperLight, true);
      E.watercolorPolygon(ctx, headPts, P.charcoal, { alpha: washA * 0.80, gradColor: P.sepia, smooth: true });
      E.dryBrushStreak(ctx, [[-4, -219], [-14, -208], [-15, -190]], 6, P.charcoal, washA * 0.64, 618, boil);
    }
    E.pencilStroke(ctx, headPts.concat([headPts[0]]), {
      medium: 'graphite', color: P.charcoal, width: lerp(1.5, 0.85, sketchFade), alpha: lineA * 0.90, seed: 625, boil: boil
    });

    // Warm golden dusk rim-light along his facing profile, lifted arm & coat front!
    if (washA > 0.04) {
      E.chalkHighlight(ctx, [[13, -214], [19, -196], [18, -166], [elX + 4, elY - 6], [wrX + 16, wrY - 6]], {
        color: P.candleCore, width: 1.7, alpha: washA * 0.74, seed: 628, boil: boil
      });
    }
    ctx.restore();
  }

  function drawCodaBeloved(ctx, x, y, reach, sketchFade, alpha, t, boil) {
    // Museum-grade graceful feminine standing figure (~214px tall) facing left:
    // sculpted profile head, cascading S-curved hair waves melting into gossamer trailing veil (ZERO straight hair sticks!),
    // articulated bent elbow & slender upturned open hand (ZERO rubber-hose U-dip, ZERO wrist dot!)
    ctx.save();
    ctx.translate(x, y);

    const breeze = Math.sin(t * 1.2 + 1.1) * 8;
    const washA = alpha * (1 - sketchFade * 0.92);
    const lineA = alpha * (1 - sketchFade * 0.62);

    // Soft grounded shadow under dress hem
    if (washA > 0.02) {
      E.charcoalTone(ctx, 12, 5, 42, 7, 0, P.sepia, washA * 0.30, 630);
    }

    // Gossamer S-curved diaphanous veil/shawl trailing softly behind her shoulders
    const veilTop = [[6, -158], [38, -152 + breeze * 0.22], [76 + breeze * 0.55, -138 + breeze * 0.42], [116 + breeze * 0.85, -142 + breeze * 0.55]];
    const veilMid = [[8, -148], [44, -136 + breeze * 0.28], [84 + breeze * 0.65, -118 + breeze * 0.48], [122 + breeze * 0.95, -120 + breeze * 0.62]];
    const veilBot = [[10, -138], [38, -120 + breeze * 0.24], [76 + breeze * 0.55, -102 + breeze * 0.44], [108 + breeze * 0.8, -100 + breeze * 0.54]];
    if (washA > 0.02) {
      E.dryBrushStreak(ctx, veilTop, 16, P.roseDust, washA * 0.36, 634, boil);
      E.dryBrushStreak(ctx, veilMid, 20, P.roseRust, washA * 0.28, 635, boil);
      E.dryBrushStreak(ctx, veilBot, 14, P.lavenderMist, washA * 0.24, 636, boil);
    }
    E.pencilStroke(ctx, veilTop, { medium: 'graphite', color: P.roseRust, width: lerp(1.05, 0.65, sketchFade), alpha: lineA * 0.56, seed: 637, boil: boil });
    E.pencilStroke(ctx, veilBot, { medium: 'graphite', color: P.sepia, width: lerp(0.95, 0.58, sketchFade), alpha: lineA * 0.44, seed: 638, boil: boil });

    // Unified feminine dress + naturally angled reaching left arm (crisp gentle elbow bend -> lifted forearm -> slender hand!)
    const elX = -34 - reach * 6;
    const elY = -140 - reach * 2;
    const wrX = -74 - reach * 16;
    const wrY = -150 - reach * 9 - breeze * 0.18;
    const dressAndArm = [
      [-10, -166], [8, -166], [14, -144], [10, -118],
      [28, -82], [48 + breeze * 0.45, -34], [66 + breeze * 0.85, 4],
      [20 + breeze * 0.25, 6], [-22, 4], [-26, -34], [-18, -88], [-11, -118], [-13, -140],
      [elX + 2, elY + 5], [wrX + 2, wrY + 3], [wrX - 4, wrY + 4],
      [wrX - 14, wrY + 2], [wrX - 19, wrY - 2], [wrX - 18, wrY - 6], [wrX - 9, wrY - 6],
      [wrX, wrY - 4], [elX - 2, elY - 5], [-15, -156]
    ];
    if (washA > 0.02) {
      E.paintOpaqueUndercoat(ctx, dressAndArm, washA * 0.84, P.paperLight, false);
      E.watercolorPolygon(ctx, dressAndArm, P.duskViolet, { alpha: washA * 0.72, gradColor: P.roseRust, smooth: false });
      E.shadeStrokes(ctx, dressAndArm, { angle: 0.72, spacing: 7.5, alpha: washA * 0.22, color: P.sepia, seed: 631, boil: boil, smooth: false });
    }
    // Crisp continuous contours for bodice/pleated skirt + clean slender arm (NO dark wrist smudge!)
    E.pencilStroke(ctx, [[8, -166], [14, -144], [10, -118], [28, -82], [48 + breeze * 0.45, -34], [66 + breeze * 0.85, 4], [-22, 4], [-26, -34], [-18, -88], [-11, -118], [-13, -140]], {
      medium: sketchFade > 0.4 ? 'graphite' : 'charcoal',
      color: sketchFade > 0.4 ? P.graphiteSoft : P.ironGall,
      width: lerp(1.65, 0.85, sketchFade), alpha: lineA * 0.86, seed: 632, boil: boil, ghost: 0.14
    });
    E.pencilStroke(ctx, [[-14, -156], [elX - 2, elY - 5], [wrX, wrY - 4], [wrX - 18, wrY - 6]], {
      medium: 'graphite', color: P.ironGall, width: lerp(1.4, 0.82, sketchFade), alpha: lineA * 0.84, seed: 644, boil: boil
    });
    E.pencilStroke(ctx, [[-13, -140], [elX + 2, elY + 5], [wrX + 1, wrY + 3], [wrX - 15, wrY + 2]], {
      medium: 'graphite', color: P.sepia, width: lerp(1.2, 0.75, sketchFade), alpha: lineA * 0.76, seed: 645, boil: boil
    });
    // Flowing skirt pleat folds
    E.pencilStroke(ctx, [[-4, -114], [4, -56], [14 + breeze * 0.25, 4]], {
      medium: 'graphite', color: P.sepia, width: lerp(1.15, 0.68, sketchFade), alpha: lineA * 0.56, seed: 633, boil: boil
    });
    E.pencilStroke(ctx, [[6, -114], [24, -52], [44 + breeze * 0.55, 2]], {
      medium: 'graphite', color: P.sepia, width: lerp(1.15, 0.68, sketchFade), alpha: lineA * 0.54, seed: 643, boil: boil
    });

    // Sculpted turned feminine side-profile head + soft S-curved cascading dark hair waves (ZERO stiff straight sticks!)
    const headPts = [
      [-6, -166], [-11, -175], [-15, -180], [-18, -187], [-14, -195], [-11, -201], [0, -206], [12, -199], [14, -183], [6, -167]
    ];
    if (washA > 0.02) {
      E.paintOpaqueUndercoat(ctx, headPts, washA * 0.84, P.paperLight, true);
      E.watercolorPolygon(ctx, headPts, P.sepia, { alpha: washA * 0.78, gradColor: P.charcoal, smooth: true });
      // Soft S-curved cascading dark sepia hair waves curling gracefully down over her back into the veil
      E.dryBrushStreak(ctx, [[4, -202], [16, -190], [22, -172], [38 + breeze * 0.25, -158 + breeze * 0.2]], 10, P.sepia, washA * 0.66, 640, boil);
      E.dryBrushStreak(ctx, [[10, -194], [20, -174], [36 + breeze * 0.2, -156], [58 + breeze * 0.4, -148 + breeze * 0.25]], 8, P.charcoal, washA * 0.42, 641, boil);
    }
    E.pencilStroke(ctx, headPts.concat([headPts[0]]), {
      medium: 'graphite', color: P.ironGall, width: lerp(1.45, 0.82, sketchFade), alpha: lineA * 0.88, seed: 639, boil: boil
    });

    // Golden dusk rim-light kissing her left-facing profile, outstretched arm & pleated gown
    if (washA > 0.04) {
      E.chalkHighlight(ctx, [[-11, -200], [-17, -187], [-14, -156], [elX - 2, elY - 5], [wrX - 16, wrY - 6]], {
        color: P.candleCore, width: 1.7, alpha: washA * 0.74, seed: 642, boil: boil
      });
      E.chalkHighlight(ctx, [[-16, -134], [-18, -86], [-24, -22]], {
        color: P.candleCore, width: 1.55, alpha: washA * 0.56, seed: 647, boil: boil
      });
    }
    ctx.restore();
  }

  function drawCodaScene(ctx, t, localT, progress, tel, weight, boil, sceneObj) {
    const totalDur = Math.max(4, sceneObj.end - sceneObj.start);
    const codaSplit = sceneObj.codaEnd ? clamp((sceneObj.codaEnd - sceneObj.start) / totalDur, 0.5, 0.85) : 0.68;
    const outroFade = smoothstep(codaSplit, 0.97, progress);
    const fullFade = smoothstep(0.88, 1.0, progress);
    const a = weight;
    const washKeep = a * (1 - outroFade * 0.86);

    // 1. Full-bleed tender amber-rose-violet dusk sky (gradually lifting softly back to bare cotton paper!)
    if (washKeep > 0.015) {
      E.atmosphericSkyWash(ctx, LOGICAL_W, LOGICAL_H, [
        [0.0,  P.indigo, 0.36],
        [0.28, P.duskViolet, 0.30],
        [0.56, P.roseRust, 0.24],
        [0.82, P.amberGlow, 0.30],
        [1.0,  P.paperLight, 0.05]
      ], {
        y0: 0, y1: 560, alpha: washKeep,
        clouds: [
          { x: 320, y: 145, rx: 340, ry: 105, color: P.duskViolet, alpha: 0.22, seed: 601 },
          { x: 960, y: 150, rx: 340, ry: 105, color: P.duskViolet, alpha: 0.20, seed: 602 },
          { x: 640, y: 392, rx: 380, ry: 175, color: P.amberGlow, alpha: 0.34, multiply: false, seed: 603 }
        ]
      });
    }

    drawCrescentMoon(ctx, 640, 128, 24, a * (1 - outroFade * 0.78) * 0.86, boil, 604);

    // 2. ONE Continuous Misty Yorkshire Valley Ridge (edge-to-edge — NO twin potatoes with a V-notch!)
    const farHills = [[-40, 498], [220, 476], [470, 502], [640, 526], [810, 500], [1060, 474], [1320, 492]];
    if (washKeep > 0.015) {
      E.paintTerrainLayer(ctx, farHills, 740, P.indigoMid, {
        alpha: washKeep * 0.28, gradColor: P.sepia, endAlpha: 0.22, seed: 605
      });
    }

    // Distant finely sketched Scarborough Fair lanterns glowing far down in the central misty saddle
    drawScarboroughTown(ctx, 640, 514, 0.62, t, washKeep * 0.82, boil, 609);

    const foreHills = [[-40, 534], [190, 518], [415, 530], [565, 558], [640, 574], [715, 558], [865, 528], [1090, 516], [1320, 530]];
    if (washKeep > 0.015) {
      E.paintTerrainLayer(ctx, foreHills, 750, P.sepia, {
        alpha: washKeep * 0.44, gradColor: P.indigoDeep, endAlpha: 0.52, seed: 606
      });
      E.shadeStrokes(ctx, foreHills.concat([[1320, 750], [-40, 750]]), {
        angle: -0.22, spacing: 11, alpha: washKeep * 0.16, color: P.charcoal, seed: 607, boil: boil
      });
    }
    E.pencilStroke(ctx, foreHills, {
      medium: 'graphite', color: P.sepia, width: 1.7, alpha: a * (1 - outroFade * 0.72) * 0.65, seed: 608, boil: boil
    });

    // Subtle wind-bent moorland grass tufts beneath both figures
    drawWindsweptGrass(ctx, 370, 552, 240, 14, 0.55, t, a * (1 - outroFade * 0.72) * 0.65, boil, 612, 0.65);
    drawWindsweptGrass(ctx, 905, 548, 240, 14, 0.55, t, a * (1 - outroFade * 0.72) * 0.65, boil, 615, 0.65);

    // 3. Two Deeply Expressive Human Figures Reaching Gently Across Luminous Mist!
    const reach = smoothstep(0.06, 0.48, progress);
    const belovedFade = smoothstep(codaSplit - 0.08, 0.92, progress);
    const travelerFade = smoothstep(codaSplit + 0.04, 0.96, progress);

    drawCodaTraveler(ctx, 436, 538, reach, travelerFade, a * (1 - fullFade * 0.58), t, boil);
    drawCodaBeloved(ctx, 844, 536, reach, belovedFade, a * (1 - fullFade * 0.82), t, boil);

    // 4. Feathery Luminous Twilight Mist Drifting Between Their Outstretched Hands
    const mistDrift = Math.sin(t * 0.42) * 24;
    const mistA = a * (1 - outroFade * 0.62);
    if (mistA > 0.02) {
      E.mistVeil(ctx, 640 + mistDrift, 452, 245, 74, mistA * 0.56, 650);
      E.mistVeil(ctx, 595 - mistDrift * 0.7, 396, 175, 56, mistA * 0.42, 651);
      E.mistVeil(ctx, 685 + mistDrift * 0.6, 514, 265, 64, mistA * 0.48, 652);
    }

    // 5. Warm Floating Lantern Embers Rising Gently Between Them
    const rng = E.mulberry32(665);
    const emberVis = a * (1 - fullFade * 0.70);
    if (emberVis > 0.02) {
      for (let i = 0; i < 24; i++) {
        const bx = 460 + rng() * 360;
        const speed = 15 + rng() * 25;
        const phase = rng() * 12;
        const life = ((t * speed + phase * 35) % 410) / 410;
        const ex = bx + Math.sin(t * (0.9 + rng() * 0.7) + phase) * (18 + rng() * 20);
        const ey = 562 - life * 420;
        const env = Math.sin(life * Math.PI);
        const r = (1.5 + rng() * 2.5) * (0.6 + 0.4 * env);
        const eA = emberVis * env * (0.65 + 0.35 * Math.sin(t * 4.2 + i));

        const g = ctx.createRadialGradient(ex, ey, 0.3, ex, ey, r * 4.4);
        g.addColorStop(0, E.rgba(P.candleCore, eA));
        g.addColorStop(0.38, E.rgba(P.amberGlow, eA * 0.52));
        g.addColorStop(1, E.rgba(P.burntSienna, 0));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(ex, ey, r * 4.4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 6. Quiet Botanical Rosemary & Thyme Sprig Blooming Gently During Outro Stillness
    const finalSprigA = a * smoothstep(codaSplit - 0.04, codaSplit + 0.22, progress) * (1 - smoothstep(0.96, 1.0, progress) * 0.25);
    if (finalSprigA > 0.02) {
      const spProg = smoothstep(codaSplit - 0.04, codaSplit + 0.24, progress);
      drawRosemary(ctx, 646, 628, 1.02, 0.16, spProg, finalSprigA * 0.84, t, boil, 680);
      drawThyme(ctx, 622, 634, 0.86, -0.32, spProg, finalSprigA * 0.76, t, boil, 681);
    }
  }

  // ==========================================================================
  // 10. CLEAN MANUSCRIPT CHAPTER TITLE & NATURAL PAPER-VIGNETTE LYRIC CAPTIONS
  //     (ZERO grey box behind title! ZERO glowing tight white oval behind lyrics!)
  // ==========================================================================
  const CHAPTER_TITLES = {
    intro:  'I · The Twilight Path',
    verse1: 'II · Parsley, Sage, Rosemary & Thyme',
    verse2: 'III · The Cambric Shirt',
    verse3: 'IV · Between Salt Water & Sea Strand',
    coda:   'V · True Love of Mine',
    outro:  'V · True Love of Mine'
  };

  function drawChapterHeader(ctx, primaryScene, localT, boil) {
    if (!primaryScene) return;
    const title = CHAPTER_TITLES[primaryScene.id] || primaryScene.label || '';
    if (!title) return;
    const alpha = clamp(smoothstep(0.2, 1.6, localT) * 0.80, 0, 0.80);
    if (alpha <= 0.02) return;

    ctx.save();
    ctx.font = 'italic 16.5px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const tw = ctx.measureText(title).width;

    // ZERO box or rectangle — pure organic italic ink with subtle warm-paper letter-edge lift!
    ctx.shadowColor = E.rgba(P.paperLight, alpha * 0.9);
    ctx.shadowBlur = 10;
    ctx.fillStyle = E.rgba(P.ironGall, alpha);
    ctx.fillText(title, 54, 48);
    ctx.shadowBlur = 0;

    E.pencilStroke(ctx, [[54, 61], [54 + Math.min(185, tw * 0.82), 61]], {
      medium: 'ink', color: P.sepia, width: 0.85, alpha: alpha * 0.56, seed: 801, boil: boil
    });
    ctx.restore();
  }

  function drawLyricCaptions(ctx, timeline, t, boil) {
    const active = getActivePhrase(timeline, t);
    if (!active || active.alpha <= 0.015) return;

    const p = active.phrase;
    const a = active.alpha;
    const baseY = 666;

    ctx.save();
    ctx.font = 'italic 27px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';

    // Ultra-smooth full-width warm-cotton lower page vignette (ZERO seam, ZERO glowing pill!)
    const botGrad = ctx.createLinearGradient(0, 520, 0, LOGICAL_H);
    botGrad.addColorStop(0.0,  E.rgba(P.paperLight, 0));
    botGrad.addColorStop(0.28, E.rgba(P.paperLight, a * 0.08));
    botGrad.addColorStop(0.56, E.rgba(P.paperLight, a * 0.36));
    botGrad.addColorStop(0.82, E.rgba(P.paperLight, a * 0.68));
    botGrad.addColorStop(1.0,  E.rgba(P.paperWarm, a * 0.80));
    ctx.fillStyle = botGrad;
    ctx.fillRect(0, 520, LOGICAL_W, LOGICAL_H - 520);

    const fullW = ctx.measureText(p.text).width;
    E.drawInkFlourish(ctx, LOGICAL_W * 0.5, baseY - 26, Math.min(110, fullW * 0.22), a * 0.44, boil, 850, P.sepia);

    const words = active.words;
    if (words && words.length > 0) {
      const tokens = [];
      let totalW = 0;
      const spaceW = ctx.measureText(' ').width;
      for (let i = 0; i < words.length; i++) {
        const txt = words[i].word;
        const w = ctx.measureText(txt).width;
        tokens.push({ item: words[i], txt: txt, w: w });
        totalW += w + (i < words.length - 1 ? spaceW : 0);
      }
      let curX = (LOGICAL_W - totalW) * 0.5;
      for (let i = 0; i < tokens.length; i++) {
        const tk = tokens[i];
        const wObj = tk.item;
        const isCurrent = t >= wObj.start - 0.06 && t <= wObj.end + 0.14;
        const isSung = t > wObj.end + 0.14;
        const bloom = isCurrent ? smoothstep(wObj.start - 0.06, wObj.start + 0.12, t) : (isSung ? 0.55 : 0);

        const herbName = wObj.herb || (function () {
          const c = tk.txt.toLowerCase().replace(/[^a-z]/g, '');
          return (c === 'parsley' || c === 'sage' || c === 'rosemary' || c === 'thyme') ? c : null;
        })();
        if (herbName && (isCurrent || isSung)) {
          const herbCol = herbName === 'thyme' ? P.roseDust : (herbName === 'rosemary' ? P.lavenderMist : P.sage);
          E.watercolorBloom(ctx, curX + tk.w * 0.5, baseY + 5, tk.w * 0.58, 12, herbCol, {
            alpha: a * (isCurrent ? 0.34 : 0.18), seed: 860 + i, dabs: 1, multiply: true
          });
        }

        const inkAlpha = a * (isCurrent ? lerp(0.58, 0.96, bloom) : (isSung ? 0.80 : 0.46));
        const inkCol = isCurrent ? P.charcoal : P.ironGall;
        const liftY = isCurrent ? -1.4 * Math.sin(clamp((t - wObj.start) / Math.max(0.15, wObj.end - wObj.start), 0, 1) * Math.PI) : 0;

        ctx.fillStyle = E.rgba(P.paperLight, inkAlpha * 0.48);
        ctx.fillText(tk.txt, curX + 0.7, baseY + liftY + 0.7);
        ctx.fillStyle = E.rgba(inkCol, inkAlpha);
        ctx.fillText(tk.txt, curX, baseY + liftY);
        curX += tk.w + spaceW;
      }
    } else {
      ctx.textAlign = 'center';
      ctx.fillStyle = E.rgba(P.ironGall, a * 0.88);
      ctx.fillText(p.text, LOGICAL_W * 0.5, baseY);
    }
    ctx.restore();
  }

  // ==========================================================================
  // 11. MASTER FILM RENDERER
  // ==========================================================================
  function renderFilmFrame(ctx, viewW, viewH, state) {
    const t = state.t || 0;
    const boil = E.boilIndex(t, 8.5);

    E.drawPaperBackdrop(ctx, viewW, viewH);

    const scale = Math.min(viewW / LOGICAL_W, viewH / LOGICAL_H);
    const ox = (viewW - LOGICAL_W * scale) * 0.5;
    const oy = (viewH - LOGICAL_H * scale) * 0.5;

    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(scale, scale);

    if (state.mode === 'cover') {
      drawCoverScene(ctx, t, boil, !!state.hoverPlay);
      E.drawSketchFrame(ctx, LOGICAL_W, LOGICAL_H, boil, 0.18);
    } else {
      const timeline = state.timeline || {};
      const clampedT = clamp(t, 0, timeline.duration || 105);
      const tel = sampleFrameTelemetry(timeline, clampedT);
      const sw = getSceneWeights(timeline, clampedT);

      for (let i = 0; i < sw.active.length; i++) {
        const entry = sw.active[i];
        const sid = entry.scene.id;
        if (sid === 'intro') {
          drawIntroScene(ctx, clampedT, entry.localT, entry.progress, tel, entry.weight, boil);
        } else if (sid === 'verse1') {
          drawVerse1Scene(ctx, clampedT, entry.localT, entry.progress, tel, entry.weight, boil, timeline, entry.scene);
        } else if (sid === 'verse2') {
          drawVerse2Scene(ctx, clampedT, entry.localT, entry.progress, tel, entry.weight, boil, timeline, entry.scene);
        } else if (sid === 'verse3') {
          drawVerse3Scene(ctx, clampedT, entry.localT, entry.progress, tel, entry.weight, boil, timeline, entry.scene);
        } else {
          drawCodaScene(ctx, clampedT, entry.localT, entry.progress, tel, entry.weight, boil, entry.scene);
        }
      }

      const primaryEntry = sw.active.find(function (e) { return e.scene.id === sw.primary.id; }) || sw.active[0];
      drawChapterHeader(ctx, sw.primary, primaryEntry ? primaryEntry.localT : 1, boil);
      drawLyricCaptions(ctx, timeline, clampedT, boil);
      E.drawSketchFrame(ctx, LOGICAL_W, LOGICAL_H, boil, 0.18);

      if (state.mode === 'ended') {
        const rx = LOGICAL_W * 0.5;
        const ry = 355;
        ctx.save();
        ctx.textAlign = 'center';
        ctx.font = 'italic 34px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
        ctx.fillStyle = E.rgba(P.ironGall, 0.84);
        ctx.fillText('Scarborough Fair', rx, ry - 48);
        ctx.font = 'italic 17px Georgia, "Palatino Linotype", "Book Antiqua", Palatino, serif';
        ctx.fillStyle = E.rgba(P.sepia, 0.74);
        ctx.fillText('sung by Aero  ·  click anywhere to listen again', rx, ry - 8);
        E.drawInkFlourish(ctx, rx, ry + 18, 90, 0.5, boil, 955, P.sepia);
        ctx.restore();
      }
    }

    ctx.restore();
    E.applyPaperToothOverlay(ctx, viewW, viewH, 0.32);

    return {
      scale: scale,
      offsetX: ox,
      offsetY: oy,
      playBtnScreen: {
        x: ox + COVER_PLAY_BTN.x * scale,
        y: oy + COVER_PLAY_BTN.y * scale,
        r: COVER_PLAY_BTN.r * scale
      }
    };
  }

  global.ArtScenes = {
    LOGICAL_W: LOGICAL_W,
    LOGICAL_H: LOGICAL_H,
    COVER_PLAY_BTN: COVER_PLAY_BTN,
    sampleFrameTelemetry: sampleFrameTelemetry,
    getSceneWeights: getSceneWeights,
    getActivePhrase: getActivePhrase,
    renderFilmFrame: renderFilmFrame
  };
})(window);
