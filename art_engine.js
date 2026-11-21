/* ============================================================================
 * art_engine.js — Traditional Hand-Drawn Media Engine (Pure HTML5 Canvas 2D)
 * "Aero Sings Scarborough Fair" (Round 2 Fine-Art Master Upgrade)
 *
 * Zero external libraries. Zero external assets. Zero SVG/vector aesthetics.
 * Authentic cold-press cotton rag paper, continuous fluid variable-pressure
 * dip-pen / graphite / vine-charcoal strokes (uniform arc-length tapered
 * ribbons — ZERO beaded segmentation), seamless full-bleed wet-on-wet
 * watercolor skies & feathered pigment blooms (ZERO hard ovals/pills),
 * velvety vine-charcoal tonal shading, form-following contour hatching,
 * opaque gouache/paper underpainting, and ~8.5 fps traditional animation boil.
 * ========================================================================== */
(function (global) {
  'use strict';

  // --------------------------------------------------------------------------
  // 1. Fine-Art Natural Pigment Palette
  // --------------------------------------------------------------------------
  const PALETTE = {
    paperLight:   '#f4ece0',
    paperWarm:    '#e9decb',
    paperDeep:    '#d8c7aa',
    paperShadow:  '#c5b08f',
    graphite:     '#2c2723',
    graphiteSoft: '#554d45',
    charcoal:     '#1b1715',
    ironGall:     '#251d17',
    indigo:       '#2a405a',
    indigoMid:    '#3b526d',
    indigoDeep:   '#182739',
    prussian:     '#1c3c4f',
    slateTeal:    '#355f69',
    seaMist:      '#6c888e',
    sepia:        '#5b4230',
    rawUmber:     '#6e5740',
    burntSienna:  '#914d30',
    ochre:        '#c0914e',
    amberGlow:    '#e0ab58',
    candleCore:   '#f8e0b6',
    sage:         '#5d745b',
    sageLight:    '#869b80',
    oliveMoss:    '#41563f',
    pineDark:     '#2c4031',
    roseRust:     '#90574e',
    roseDust:     '#bb8275',
    duskViolet:   '#4d3f5a',
    lavenderMist: '#7b6c85',
    linenShadow:  '#87827b',
    linenMid:     '#cfc7ba',
    skinWarm:     '#d3b196',
    skinShadow:   '#926c56',
    chalk:        '#fbf6ec',
    gouacheWhite: '#f6f0e5'
  };

  // --------------------------------------------------------------------------
  // 2. Color & Math Utilities
  // --------------------------------------------------------------------------
  const _rgbCache = Object.create(null);

  function hexToRgb(hex) {
    if (_rgbCache[hex]) return _rgbCache[hex];
    let h = hex.charAt(0) === '#' ? hex.slice(1) : hex;
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    const n = parseInt(h, 16);
    const out = { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
    _rgbCache[hex] = out;
    return out;
  }

  function rgba(hex, alpha) {
    const c = hexToRgb(hex);
    const a = alpha < 0 ? 0 : alpha > 1 ? 1 : alpha;
    return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + a.toFixed(4) + ')';
  }

  function mixHex(hexA, hexB, t) {
    const a = hexToRgb(hexA);
    const b = hexToRgb(hexB);
    const k = t < 0 ? 0 : t > 1 ? 1 : t;
    const r = Math.round(a.r + (b.r - a.r) * k);
    const g = Math.round(a.g + (b.g - a.g) * k);
    const bl = Math.round(a.b + (b.b - a.b) * k);
    return '#' + ((1 << 24) + (r << 16) + (g << 8) + bl).toString(16).slice(1);
  }

  function darkenHex(hex, amount) {
    return mixHex(hex, '#14100d', amount);
  }

  function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function smoothstep(edge0, edge1, x) {
    const t = clamp((x - edge0) / (edge1 - edge0 || 1e-6), 0, 1);
    return t * t * (3 - 2 * t);
  }

  // --------------------------------------------------------------------------
  // 3. Deterministic Seeded PRNG & Smooth 2D Organic Noise
  // --------------------------------------------------------------------------
  function mulberry32(seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a |= 0;
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hash2i(ix, iy, seed) {
    let h = (ix * 374761393 + iy * 668265263 + (seed || 0) * 1442695041) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    h = h ^ (h >>> 16);
    return (h >>> 0) / 4294967296;
  }

  function valueNoise2D(x, y, seed) {
    const ix = Math.floor(x);
    const iy = Math.floor(y);
    const fx = x - ix;
    const fy = y - iy;
    const ux = fx * fx * (3 - 2 * fx);
    const uy = fy * fy * (3 - 2 * fy);
    const a = hash2i(ix, iy, seed);
    const b = hash2i(ix + 1, iy, seed);
    const c = hash2i(ix, iy + 1, seed);
    const d = hash2i(ix + 1, iy + 1, seed);
    return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
  }

  function fbm2D(x, y, octaves, seed) {
    let sum = 0;
    let amp = 0.5;
    let freq = 1;
    let norm = 0;
    const n = octaves || 3;
    for (let i = 0; i < n; i++) {
      sum += amp * valueNoise2D(x * freq, y * freq, (seed || 0) + i * 97);
      norm += amp;
      amp *= 0.5;
      freq *= 2.03;
    }
    return sum / (norm || 1);
  }

  function boilIndex(t, fps) {
    return Math.floor(Math.max(0, t) * (fps || 8.5));
  }

  // --------------------------------------------------------------------------
  // 4. Procedural Cold-Press Cotton Paper & Fine Painterly Brush Stamps
  // --------------------------------------------------------------------------
  const _cache = {
    tile: null,
    toothOverlayTile: null,
    washMottleTile: null,
    tintedClouds: Object.create(null),
    tintedChalk: null,
    backdrop: null,
    backdropW: 0,
    backdropH: 0
  };

  function makeOffscreen(w, h) {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    return c;
  }

  function tileNoise(x, y, period, seed) {
    const ix = Math.floor(x);
    const iy = Math.floor(y);
    const fx = x - ix;
    const fy = y - iy;
    const ux = fx * fx * (3 - 2 * fx);
    const uy = fy * fy * (3 - 2 * fy);
    const x0 = ((ix % period) + period) % period;
    const y0 = ((iy % period) + period) % period;
    const x1 = (x0 + 1) % period;
    const y1 = (y0 + 1) % period;
    const a = hash2i(x0, y0, seed);
    const b = hash2i(x1, y0, seed);
    const c = hash2i(x0, y1, seed);
    const d = hash2i(x1, y1, seed);
    return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
  }

  function ensureProceduralTextures() {
    if (_cache.tile) return _cache;

    // A) 256x256 seamless cold-press cotton rag paper tile + tooth overlay + watercolor granulation tile
    const S = 256;
    const tile = makeOffscreen(S, S);
    const tctx = tile.getContext('2d');
    const img = tctx.createImageData(S, S);
    const d = img.data;

    const tooth = makeOffscreen(S, S);
    const gctx = tooth.getContext('2d');
    const gimg = gctx.createImageData(S, S);
    const gd = gimg.data;

    const mottle = makeOffscreen(S, S);
    const mctx = mottle.getContext('2d');
    const mimg = mctx.createImageData(S, S);
    const md = mimg.data;

    for (let y = 0; y < S; y++) {
      for (let x = 0; x < S; x++) {
        const coarse = tileNoise(x / 32, y / 32, 8, 11);
        const medium = tileNoise(x / 8, y / 8, 32, 37);
        const fine   = tileNoise(x / 2.2, y / 2.2, 116, 73);
        const hFiber = tileNoise(x / 32, y / 2.5, 102, 131);
        const vFiber = tileNoise(x / 2.8, y / 32, 92, 179);
        const micro  = hash2i(x, y, 211);

        const h0 = coarse * 0.35 + medium * 0.40 + fine * 0.25;
        const hR = tileNoise((x + 1.5) / 8, (y + 1.5) / 8, 32, 37);
        const relief = (h0 - hR) * 14;
        const fiber = (hFiber - 0.5) * 4.5 + (vFiber - 0.5) * 3.5;
        const grain = (micro - 0.5) * 6.5 + (coarse - 0.5) * 6.5 + (medium - 0.5) * 7.5 + relief + fiber;

        const idx = (y * S + x) * 4;
        d[idx]     = clamp(Math.round(244 + grain * 0.85), 218, 253);
        d[idx + 1] = clamp(Math.round(236 + grain * 0.90), 208, 248);
        d[idx + 2] = clamp(Math.round(221 + grain * 0.98), 192, 238);
        d[idx + 3] = 255;

        // Cold-press tooth multiply texture
        const tv = clamp(Math.round(247 + (medium - 0.52) * 20 + (fine - 0.5) * 18 + relief * 0.75 + (micro - 0.5) * 12), 216, 255);
        gd[idx]     = clamp(tv + 2, 212, 255);
        gd[idx + 1] = tv;
        gd[idx + 2] = clamp(tv - 4, 204, 255);
        gd[idx + 3] = 255;

        // Organic wet-pigment granulation mottle (soft neutral multiply)
        const gran = tileNoise(x / 32, y / 32, 8, 311) * 0.45 + tileNoise(x / 10, y / 10, 25, 409) * 0.35 + fine * 0.20;
        const mv = clamp(Math.round(234 + (gran - 0.5) * 44), 204, 255);
        md[idx] = mv; md[idx + 1] = mv; md[idx + 2] = mv; md[idx + 3] = 255;
      }
    }
    tctx.putImageData(img, 0, 0);
    gctx.putImageData(gimg, 0, 0);
    mctx.putImageData(mimg, 0, 0);

    // Subtle laid cotton rag fibers
    const rng = mulberry32(90421);
    tctx.save();
    for (let i = 0; i < 60; i++) {
      const fx = rng() * S;
      const fy = rng() * S;
      const len = 4 + rng() * 14;
      const ang = (rng() - 0.5) * Math.PI;
      tctx.strokeStyle = rng() > 0.35 ? 'rgba(148,122,92,0.06)' : 'rgba(255,250,240,0.14)';
      tctx.lineWidth = 0.5 + rng() * 0.55;
      tctx.beginPath();
      tctx.moveTo(fx, fy);
      tctx.quadraticCurveTo(
        fx + Math.cos(ang + 0.3) * len * 0.5,
        fy + Math.sin(ang + 0.3) * len * 0.5,
        fx + Math.cos(ang) * len,
        fy + Math.sin(ang) * len
      );
      tctx.stroke();
    }
    tctx.restore();

    _cache.tile = tile;
    _cache.toothOverlayTile = tooth;
    _cache.washMottleTile = mottle;
    return _cache;
  }

  // Generate a feathered, organically ragged wet-watercolor cloud/bloom stamp tinted to `hex`
  // (ZERO hard geometric outline! Soft irregular feathered perimeter + natural pigment granulation!)
  function getWatercolorBloomStamp(hex) {
    if (_cache.tintedClouds[hex]) return _cache.tintedClouds[hex];
    const S = 128;
    const c = makeOffscreen(S, S);
    const ctx = c.getContext('2d');
    const img = ctx.createImageData(S, S);
    const d = img.data;
    const rgb = hexToRgb(hex);
    const seed = (rgb.r * 31 + rgb.g * 17 + rgb.b * 7) & 0xFFFF;

    for (let y = 0; y < S; y++) {
      for (let x = 0; x < S; x++) {
        const nx = (x - S * 0.5) / (S * 0.46);
        const ny = (y - S * 0.5) / (S * 0.46);
        const dist = Math.hypot(nx, ny);
        // Warp radius with smooth multi-octave organic noise so edge is ragged wet watercolor, NEVER an oval!
        const warp = (fbm2D(x * 0.048, y * 0.048, 4, seed) - 0.5) * 0.62;
        const rEff = dist + warp;
        let a = 1 - smoothstep(0.18, 0.98, rEff);
        if (a > 0.002) {
          // Subtle soft capillary pigment modulation + fine cotton-tooth granulation (never blotchy cow spots!)
          const gran = 0.78 + 0.28 * fbm2D(x * 0.14, y * 0.14, 3, seed + 59);
          const fine = 0.88 + 0.18 * valueNoise2D(x * 0.45, y * 0.45, seed + 131);
          const rimBoost = 1 + 0.22 * smoothstep(0.55, 0.82, rEff) * (1 - smoothstep(0.82, 0.98, rEff));
          a = clamp(a * gran * fine * rimBoost, 0, 1);
        }
        const idx = (y * S + x) * 4;
        d[idx]     = rgb.r;
        d[idx + 1] = rgb.g;
        d[idx + 2] = rgb.b;
        d[idx + 3] = Math.round(a * 255);
      }
    }
    ctx.putImageData(img, 0, 0);
    _cache.tintedClouds[hex] = c;
    return c;
  }

  function getPaperBackdrop(w, h) {
    ensureProceduralTextures();
    if (_cache.backdrop && _cache.backdropW === w && _cache.backdropH === h) {
      return _cache.backdrop;
    }
    const c = makeOffscreen(w, h);
    const ctx = c.getContext('2d');
    const pat = ctx.createPattern(_cache.tile, 'repeat');
    ctx.fillStyle = pat;
    ctx.fillRect(0, 0, w, h);

    // Subtle organic parchment warm aging across sheet
    const rng = mulberry32(41781);
    ctx.save();
    for (let i = 0; i < 5; i++) {
      const sx = rng() * w;
      const sy = rng() * h;
      const sr = Math.max(w, h) * (0.34 + rng() * 0.28);
      const grad = ctx.createRadialGradient(sx, sy, sr * 0.08, sx, sy, sr);
      const warm = i % 2 === 0 ? 'rgba(206, 181, 145,' : 'rgba(186, 168, 144,';
      grad.addColorStop(0, warm + '0.07)');
      grad.addColorStop(1, warm + '0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);
    }

    // Soft warm aged deckled-edge vignette
    const vig = ctx.createRadialGradient(w * 0.5, h * 0.48, Math.min(w, h) * 0.36, w * 0.5, h * 0.5, Math.max(w, h) * 0.74);
    vig.addColorStop(0, 'rgba(244, 236, 224, 0)');
    vig.addColorStop(0.74, 'rgba(195, 173, 140, 0.12)');
    vig.addColorStop(1, 'rgba(145, 118, 86, 0.34)');
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();

    _cache.backdrop = c;
    _cache.backdropW = w;
    _cache.backdropH = h;
    return c;
  }

  function drawPaperBackdrop(ctx, w, h) {
    ctx.drawImage(getPaperBackdrop(w, h), 0, 0, w, h);
  }

  function applyPaperToothOverlay(ctx, w, h, alpha) {
    ensureProceduralTextures();
    ctx.save();
    ctx.globalCompositeOperation = 'multiply';
    ctx.globalAlpha = alpha !== undefined ? alpha : 0.32;
    ctx.fillStyle = ctx.createPattern(_cache.toothOverlayTile, 'repeat');
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  // --------------------------------------------------------------------------
  // 5. Uniform Arc-Length Catmull-Rom Spline Sampler (Kills segmented beading!)
  // --------------------------------------------------------------------------
  function sampleSplineUniform(pts, stepPx, closed) {
    const n = pts.length;
    if (n < 2) return pts.map(function (p) { return { x: p[0], y: p[1], u: 0, nx: 0, ny: -1 }; });

    // Dense raw spline evaluation first
    const raw = [];
    const segCount = closed ? n : n - 1;
    for (let i = 0; i < segCount; i++) {
      const p0 = pts[closed ? (i - 1 + n) % n : Math.max(0, i - 1)];
      const p1 = pts[i];
      const p2 = pts[(i + 1) % n];
      const p3 = pts[closed ? (i + 2) % n : Math.min(n - 1, i + 2)];
      const dist = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
      const sub = Math.max(3, Math.min(28, Math.ceil(dist / (stepPx || 5))));
      for (let j = 0; j < sub; j++) {
        const t = j / sub;
        const t2 = t * t;
        const t3 = t2 * t;
        const x = 0.5 * (
          (2 * p1[0]) +
          (-p0[0] + p2[0]) * t +
          (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
          (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
        );
        const y = 0.5 * (
          (2 * p1[1]) +
          (-p0[1] + p2[1]) * t +
          (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
          (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
        );
        raw.push({ x: x, y: y });
      }
    }
    if (!closed) {
      raw.push({ x: pts[n - 1][0], y: pts[n - 1][1] });
    } else {
      raw.push({ x: raw[0].x, y: raw[0].y });
    }

    // Compute cumulative arc length & unit normals
    let total = 0;
    const lens = [0];
    for (let i = 1; i < raw.length; i++) {
      total += Math.hypot(raw[i].x - raw[i - 1].x, raw[i].y - raw[i - 1].y);
      lens.push(total);
    }
    const inv = total > 1e-5 ? 1 / total : 0;
    const out = [];
    for (let i = 0; i < raw.length; i++) {
      const prev = raw[Math.max(0, i - 1)];
      const next = raw[Math.min(raw.length - 1, i + 1)];
      const dx = next.x - prev.x;
      const dy = next.y - prev.y;
      const d = Math.hypot(dx, dy) || 1;
      out.push({
        x: raw[i].x,
        y: raw[i].y,
        u: lens[i] * inv,
        s: lens[i],
        nx: -dy / d,
        ny: dx / d
      });
    }
    out.totalLength = total;
    return out;
  }

  // --------------------------------------------------------------------------
  // 6. Fluid Continuous Variable-Pressure Hand-Drawn Stroke (ZERO beading!)
  //    Draws a continuous calligraphic/graphite tapered ribbon + subtle tooth
  // --------------------------------------------------------------------------
  function pencilStroke(ctx, pts, opts) {
    if (!pts || pts.length < 2) return;
    const o = opts || {};
    const progress = o.progress !== undefined ? clamp(o.progress, 0, 1) : 1;
    if (progress <= 0.005) return;

    const medium = o.medium || 'graphite';
    const baseColor = o.color || (
      medium === 'charcoal' ? PALETTE.charcoal :
      medium === 'ink'      ? PALETTE.ironGall :
      medium === 'chalk'    ? PALETTE.chalk :
                              PALETTE.graphite
    );
    const width = o.width !== undefined ? o.width : (medium === 'charcoal' ? 2.6 : medium === 'ink' ? 1.4 : 1.7);
    const alpha = o.alpha !== undefined ? o.alpha : (medium === 'ink' ? 0.88 : 0.78);
    if (alpha <= 0.008) return;

    const seed = o.seed !== undefined ? o.seed : 101;
    const boil = o.boil !== undefined ? o.boil : 0;
    const boilAmp = o.boilAmp !== undefined ? o.boilAmp : (medium === 'ink' ? 0.45 : 0.82);
    const roughness = o.roughness !== undefined ? o.roughness : (medium === 'charcoal' ? 0.85 : medium === 'ink' ? 0.35 : 0.6);
    const taperStart = o.taperStart !== undefined ? o.taperStart : 0.14;
    const taperEnd = o.taperEnd !== undefined ? o.taperEnd : 0.18;
    const closed = !!o.closed;

    const sampled = sampleSplineUniform(pts, 4.5, closed);
    if (sampled.length < 2) return;
    const maxIdx = Math.max(2, Math.floor(sampled.length * progress));

    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Build smoothly hand-perturbed center spine with continuous boil
    const spine = new Array(maxIdx);
    const pSeed = seed + boil * 53;
    for (let i = 0; i < maxIdx; i++) {
      const pt = sampled[i];
      // Low-frequency smooth hand drift (NO spiky high-freq zigzags!)
      const drift = (valueNoise2D(pt.s * 0.016, boil * 0.61, pSeed) - 0.5) * 2 * boilAmp +
                    (valueNoise2D(pt.s * 0.065, boil * 1.13, pSeed + 29) - 0.5) * roughness;
      const u = pt.u / (progress || 1);
      let press = 1.0;
      if (!closed && taperStart > 0 && u < taperStart) press *= smoothstep(0, taperStart, u);
      if (!closed && taperEnd > 0 && u > 1 - taperEnd) press *= smoothstep(1, 1 - taperEnd, u);
      // Smooth organic hand-pressure swell along stroke length
      press *= (0.76 + 0.38 * valueNoise2D(pt.s * 0.014, seed * 0.07, seed + 71));
      spine[i] = {
        x: pt.x + pt.nx * drift,
        y: pt.y + pt.ny * drift,
        nx: pt.nx,
        ny: pt.ny,
        hw: Math.max(0.18, width * 0.5 * press)
      };
    }

    // 1) Optional faint human construction / gesture under-sketch line (single smooth continuous stroke!)
    if (o.ghost) {
      const gAlpha = (typeof o.ghost === 'number' ? o.ghost : 0.18) * alpha;
      ctx.strokeStyle = rgba(baseColor, gAlpha);
      ctx.lineWidth = Math.max(0.55, width * 0.48);
      ctx.beginPath();
      for (let i = 0; i < maxIdx; i++) {
        const gOff = (valueNoise2D(sampled[i].s * 0.012, (seed + 917) * 0.11, seed + 917) - 0.5) * (2.6 + width * 0.55);
        const gx = spine[i].x + spine[i].nx * gOff;
        const gy = spine[i].y + spine[i].ny * gOff;
        if (i === 0) ctx.moveTo(gx, gy); else ctx.lineTo(gx, gy);
      }
      ctx.stroke();
    }

    // 2) Continuous tapered variable-width stroke polygon (ZERO segment seams! Silky dip-pen / graphite!)
    ctx.fillStyle = rgba(baseColor, alpha * (medium === 'charcoal' ? 0.82 : 0.92));
    ctx.beginPath();
    for (let i = 0; i < maxIdx; i++) {
      const sp = spine[i];
      const lx = sp.x + sp.nx * sp.hw;
      const ly = sp.y + sp.ny * sp.hw;
      if (i === 0) ctx.moveTo(lx, ly); else ctx.lineTo(lx, ly);
    }
    for (let i = maxIdx - 1; i >= 0; i--) {
      const sp = spine[i];
      ctx.lineTo(sp.x - sp.nx * sp.hw, sp.y - sp.ny * sp.hw);
    }
    ctx.closePath();
    ctx.fill();

    // 3) Subtle organic dry-grain bristle pass for charcoal / chalk / graphite (continuous fine hair strand)
    if (medium === 'charcoal' || medium === 'chalk' || (medium === 'graphite' && width >= 1.5)) {
      const bCount = medium === 'charcoal' ? 2 : 1;
      for (let b = 0; b < bCount; b++) {
        const side = b === 0 ? 1 : -1;
        ctx.strokeStyle = rgba(baseColor, alpha * (medium === 'charcoal' ? 0.32 : 0.24));
        ctx.lineWidth = Math.max(0.5, width * 0.34);
        ctx.beginPath();
        for (let i = 0; i < maxIdx; i++) {
          const sp = spine[i];
          const off = side * (sp.hw * 0.85 + (valueNoise2D(sampled[i].s * 0.04, b * 3.1, pSeed + 19) - 0.5) * width * 0.35);
          const bx = sp.x + sp.nx * off;
          const by = sp.y + sp.ny * off;
          if (i === 0) ctx.moveTo(bx, by); else ctx.lineTo(bx, by);
        }
        ctx.stroke();
      }
    }

    ctx.restore();
  }

  // --------------------------------------------------------------------------
  // 7. TRUE FULL-BLEED ATMOSPHERIC WATERCOLOR SKIES, FEATHERED BLOOMS & TERRAIN
  //    (ZERO floating pill capsules, ZERO Venn ovals, ZERO rounded potatoes!)
  // --------------------------------------------------------------------------

  // Seamless full-bleed multi-stop atmospheric watercolor sky/background wash with granulation!
  function atmosphericSkyWash(ctx, w, h, stops, opts) {
    ensureProceduralTextures();
    const o = opts || {};
    const alpha = o.alpha !== undefined ? o.alpha : 1.0;
    if (alpha <= 0.005) return;
    const y0 = o.y0 !== undefined ? o.y0 : 0;
    const y1 = o.y1 !== undefined ? o.y1 : h;

    ctx.save();
    ctx.globalCompositeOperation = o.multiply === false ? 'source-over' : 'multiply';
    ctx.globalAlpha = alpha;

    const grad = ctx.createLinearGradient(0, y0, 0, y1);
    for (let i = 0; i < stops.length; i++) {
      grad.addColorStop(stops[i][0], rgba(stops[i][1], stops[i][2]));
    }
    ctx.fillStyle = grad;
    ctx.fillRect(-40, y0 - 20, w + 80, (y1 - y0) + 40);

    // Subtle organic watercolor granulation cloudiness across sky (breaks any digital gradient uniformity!)
    if (o.clouds && o.clouds.length) {
      for (let i = 0; i < o.clouds.length; i++) {
        const cl = o.clouds[i];
        watercolorBloom(ctx, cl.x, cl.y, cl.rx, cl.ry, cl.color, {
          alpha: (cl.alpha || 0.2) * alpha,
          angle: cl.angle || 0,
          multiply: cl.multiply !== undefined ? cl.multiply : true,
          seed: cl.seed || (700 + i * 29)
        });
      }
    }
    ctx.restore();
  }

  // Truly soft feathered wet-on-wet watercolor bloom (uses ragged procedural alpha stamp — ZERO oval lines!)
  function watercolorBloom(ctx, cx, cy, rx, ry, color, opts) {
    const o = opts || {};
    const alpha = o.alpha !== undefined ? o.alpha : 0.25;
    if (alpha <= 0.004 || rx <= 2 || ry <= 2) return;
    ensureProceduralTextures();
    const stamp = getWatercolorBloomStamp(color);
    const rng = mulberry32(o.seed || 313);
    const dabs = o.dabs || 2;

    ctx.save();
    if (o.multiply !== false) ctx.globalCompositeOperation = 'multiply';
    ctx.translate(cx, cy);
    ctx.rotate(o.angle || 0);

    for (let i = 0; i < dabs; i++) {
      const ox = (rng() - 0.5) * rx * 0.28;
      const oy = (rng() - 0.5) * ry * 0.28;
      const sx = rx * (0.88 + rng() * 0.34);
      const sy = ry * (0.88 + rng() * 0.34);
      ctx.save();
      ctx.translate(ox, oy);
      ctx.rotate((rng() - 0.5) * 0.35);
      ctx.globalAlpha = clamp((alpha / (dabs * 0.68)), 0, 1);
      ctx.drawImage(stamp, -sx, -sy, sx * 2, sy * 2);
      ctx.restore();
    }
    ctx.restore();
  }

  // Continuous edge-to-edge terrain / hill / sea layer (follows smooth upper ridge, drops straight to bottom — NO potato rounding!)
  function paintTerrainLayer(ctx, ridgePts, bottomY, color, opts) {
    if (!ridgePts || ridgePts.length < 2) return;
    const o = opts || {};
    const alpha = o.alpha !== undefined ? o.alpha : 0.45;
    if (alpha <= 0.005) return;
    ensureProceduralTextures();

    const sampled = sampleSplineUniform(ridgePts, 10, false);
    const seed = o.seed || 141;
    let minY = Infinity;
    for (let i = 0; i < sampled.length; i++) {
      if (sampled[i].y < minY) minY = sampled[i].y;
    }

    ctx.save();
    if (o.multiply !== false) ctx.globalCompositeOperation = 'multiply';

    ctx.beginPath();
    ctx.moveTo(sampled[0].x, sampled[0].y);
    for (let i = 1; i < sampled.length; i++) {
      const p = sampled[i];
      const jag = (valueNoise2D(p.x * 0.025, seed * 0.13, seed) - 0.5) * (o.roughness !== undefined ? o.roughness : 2.6);
      ctx.lineTo(p.x, p.y + jag);
    }
    ctx.lineTo(sampled[sampled.length - 1].x, bottomY);
    ctx.lineTo(sampled[0].x, bottomY);
    ctx.closePath();

    const grad = ctx.createLinearGradient(0, minY, 0, bottomY);
    grad.addColorStop(0, rgba(color, alpha));
    grad.addColorStop(0.55, rgba(o.gradColor || color, alpha * (o.midAlpha !== undefined ? o.midAlpha : 0.85)));
    grad.addColorStop(1, rgba(o.bottomColor || o.gradColor || color, alpha * (o.endAlpha !== undefined ? o.endAlpha : 0.65)));
    ctx.fillStyle = grad;
    ctx.fill();

    // Wet pigment granulation clipped cleanly inside terrain
    if (o.granulate !== false) {
      ctx.clip();
      ctx.globalCompositeOperation = 'multiply';
      ctx.globalAlpha = clamp(alpha * 0.55, 0, 0.45);
      ctx.fillStyle = ctx.createPattern(_cache.washMottleTile, 'repeat');
      ctx.fillRect(-40, minY - 20, 1380, bottomY - minY + 40);

      // Optional soft mist lift along the base for atmospheric depth
      if (o.mistBase) {
        ctx.globalCompositeOperation = 'source-over';
        ctx.globalAlpha = 1;
        const mg = ctx.createLinearGradient(0, bottomY - 120, 0, bottomY);
        mg.addColorStop(0, rgba(PALETTE.paperLight, 0));
        mg.addColorStop(1, rgba(PALETTE.paperLight, o.mistBase));
        ctx.fillStyle = mg;
        ctx.fillRect(-40, bottomY - 120, 1380, 130);
      }
    }
    ctx.restore();
  }

  // Clean polygon tracing for figures, garments, leaves & cloth (smooth spline without corner blow-up!)
  function traceOrganicPoly(ctx, pts, smooth) {
    if (!pts || pts.length < 3) return;
    if (smooth === false) {
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      ctx.closePath();
      return;
    }
    const sampled = sampleSplineUniform(pts, 6, true);
    ctx.beginPath();
    ctx.moveTo(sampled[0].x, sampled[0].y);
    for (let i = 1; i < sampled.length; i++) ctx.lineTo(sampled[i].x, sampled[i].y);
    ctx.closePath();
  }

  // Opaque warm cotton-paper underpainting mask (prevents background sky bands bleeding through characters!)
  function paintOpaqueUndercoat(ctx, pts, alpha, color, smooth) {
    if (!pts || pts.length < 3 || alpha <= 0.01) return;
    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    traceOrganicPoly(ctx, pts, smooth !== false);
    ctx.fillStyle = rgba(color || PALETTE.paperLight, alpha);
    ctx.fill();
    ctx.restore();
  }

  // Watercolor figure/garment/leaf fill with soft gradient & pigment granulation (NO hard cartoon rim!)
  function watercolorPolygon(ctx, pts, color, opts) {
    if (!pts || pts.length < 3) return;
    const o = opts || {};
    const alpha = o.alpha !== undefined ? o.alpha : 0.42;
    if (alpha <= 0.005) return;
    ensureProceduralTextures();

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < pts.length; i++) {
      if (pts[i][0] < minX) minX = pts[i][0];
      if (pts[i][1] < minY) minY = pts[i][1];
      if (pts[i][0] > maxX) maxX = pts[i][0];
      if (pts[i][1] > maxY) maxY = pts[i][1];
    }

    ctx.save();
    if (o.multiply !== false) ctx.globalCompositeOperation = 'multiply';
    traceOrganicPoly(ctx, pts, o.smooth !== false);

    if (o.gradColor) {
      const horiz = o.gradDir === 'h';
      const gr = ctx.createLinearGradient(
        horiz ? minX : minX,
        horiz ? (minY + maxY) * 0.5 : minY,
        horiz ? maxX : minX,
        horiz ? (minY + maxY) * 0.5 : maxY
      );
      gr.addColorStop(0, rgba(color, alpha));
      gr.addColorStop(1, rgba(o.gradColor, alpha * (o.gradEndAlpha !== undefined ? o.gradEndAlpha : 0.88)));
      ctx.fillStyle = gr;
    } else {
      ctx.fillStyle = rgba(color, alpha);
    }
    ctx.fill();

    // Subtle soft wet granulation texture clipped to shape
    if (o.granulate !== false) {
      ctx.clip();
      ctx.globalCompositeOperation = 'multiply';
      ctx.globalAlpha = clamp(alpha * 0.42, 0, 0.35);
      ctx.fillStyle = ctx.createPattern(_cache.washMottleTile, 'repeat');
      ctx.fillRect(minX - 6, minY - 6, (maxX - minX) + 12, (maxY - minY) + 12);
    }

    // Very delicate capillary pigment edge only when explicitly requested (subtle!)
    if (o.edgeRim && o.edgeRim > 0.05) {
      ctx.globalCompositeOperation = o.multiply !== false ? 'multiply' : 'source-over';
      ctx.globalAlpha = 1;
      traceOrganicPoly(ctx, pts, o.smooth !== false);
      ctx.strokeStyle = rgba(darkenHex(color, 0.22), alpha * 0.24 * o.edgeRim);
      ctx.lineWidth = o.edgeWidth || 1.3;
      ctx.stroke();
    }
    ctx.restore();
  }

  // Backward-compatible watercolorWash alias routed cleanly to feathered watercolorBloom!
  function watercolorWash(ctx, cx, cy, rx, ry, color, opts) {
    watercolorBloom(ctx, cx, cy, rx, ry, color, opts);
  }

  // --------------------------------------------------------------------------
  // 8. Velvety Vine-Charcoal Tonal Shading & Form-Following Contour Hatching
  //    (ZERO cow spots! ZERO graph-paper cross-grids!)
  // --------------------------------------------------------------------------
  function charcoalTone(ctx, cx, cy, rx, ry, angle, color, alpha, seed) {
    if (alpha <= 0.005 || rx <= 1 || ry <= 1) return;
    const col = color || PALETTE.charcoal;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle || 0);
    ctx.scale(1, ry / (rx || 1));
    const g = ctx.createRadialGradient(0, 0, rx * 0.05, 0, 0, rx);
    g.addColorStop(0, rgba(col, alpha * 0.62));
    g.addColorStop(0.5, rgba(col, alpha * 0.28));
    g.addColorStop(0.82, rgba(col, alpha * 0.08));
    g.addColorStop(1, rgba(col, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(0, 0, rx, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // Soft directional form-following pencil shading strokes (curved, tapered at ends — NEVER graph paper!)
  function shadeStrokes(ctx, polyPts, opts) {
    if (!polyPts || polyPts.length < 3) return;
    const o = opts || {};
    const alpha = o.alpha !== undefined ? o.alpha : 0.26;
    if (alpha <= 0.01) return;
    const color = o.color || PALETTE.graphite;
    const spacing = Math.max(4.0, o.spacing || 7.5);
    const angle = o.angle !== undefined ? o.angle : -0.58;
    const width = o.width || 0.9;
    const seed = o.seed || 223;
    const boil = o.boil || 0;
    const curve = o.curve !== undefined ? o.curve : 0.14;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < polyPts.length; i++) {
      if (polyPts[i][0] < minX) minX = polyPts[i][0];
      if (polyPts[i][1] < minY) minY = polyPts[i][1];
      if (polyPts[i][0] > maxX) maxX = polyPts[i][0];
      if (polyPts[i][1] > maxY) maxY = polyPts[i][1];
    }
    const cx = (minX + maxX) * 0.5;
    const cy = (minY + maxY) * 0.5;
    const diag = Math.hypot(maxX - minX, maxY - minY) * 0.58;

    ctx.save();
    traceOrganicPoly(ctx, polyPts, o.smooth !== false);
    ctx.clip();

    const cosA = Math.cos(angle);
    const sinA = Math.sin(angle);
    const nx = -sinA;
    const ny = cosA;
    const rng = mulberry32(seed + boil * 23);
    ctx.lineCap = 'round';

    let d = -diag;
    let count = 0;
    while (d <= diag && count < 180) {
      const step = spacing * (0.82 + rng() * 0.44);
      const mx = cx + nx * d;
      const my = cy + ny * d;
      const half = diag * (0.76 + rng() * 0.3);
      const x0 = mx - cosA * half;
      const y0 = my - sinA * half;
      const x1 = mx + cosA * half;
      const y1 = my + sinA * half;
      const bend = (curve + (rng() - 0.5) * 0.14) * half * 0.45;

      // Soft gradient along each stroke so hatch fades naturally at tips
      const lg = ctx.createLinearGradient(x0, y0, x1, y1);
      const aStroke = alpha * (0.55 + rng() * 0.5);
      lg.addColorStop(0, rgba(color, 0));
      lg.addColorStop(0.22, rgba(color, aStroke));
      lg.addColorStop(0.78, rgba(color, aStroke * 0.9));
      lg.addColorStop(1, rgba(color, 0));
      ctx.strokeStyle = lg;
      ctx.lineWidth = width * (0.7 + rng() * 0.55);
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.quadraticCurveTo(mx + nx * bend, my + ny * bend, x1, y1);
      ctx.stroke();

      d += step;
      count++;
    }
    ctx.restore();
  }

  // --------------------------------------------------------------------------
  // 9. Lifted White Chalk / Gouache Highlights, Mist Veils & Ink Splatters
  // --------------------------------------------------------------------------
  function chalkHighlight(ctx, pts, opts) {
    const o = opts || {};
    pencilStroke(ctx, pts, {
      medium: 'chalk',
      color: o.color || PALETTE.chalk,
      width: o.width !== undefined ? o.width : 2.3,
      alpha: o.alpha !== undefined ? o.alpha : 0.72,
      seed: o.seed || 809,
      boil: o.boil || 0,
      boilAmp: o.boilAmp !== undefined ? o.boilAmp : 0.7,
      roughness: o.roughness !== undefined ? o.roughness : 0.75,
      taperStart: o.taperStart !== undefined ? o.taperStart : 0.18,
      taperEnd: o.taperEnd !== undefined ? o.taperEnd : 0.24,
      progress: o.progress
    });
  }

  // Soft feathery atmospheric mist/cloud veil (uses ragged watercolor bloom in chalk — ZERO sharp blobs!)
  function mistVeil(ctx, cx, cy, rx, ry, alpha, seed, color) {
    watercolorBloom(ctx, cx, cy, rx, ry, color || PALETTE.chalk, {
      alpha: alpha, seed: seed || 991, dabs: 2, multiply: false
    });
  }

  // Wide dry-brush bristle streak (for seafoam trails, windswept clouds, atmospheric washes)
  function dryBrushStreak(ctx, pts, width, color, alpha, seed, boil) {
    if (!pts || pts.length < 2 || alpha <= 0.008) return;
    const rng = mulberry32((seed || 441) + (boil || 0) * 17);
    const strands = Math.max(4, Math.min(11, Math.round(width * 0.7)));
    const sampled = sampleSplineUniform(pts, 7, false);
    ctx.save();
    ctx.lineCap = 'round';
    for (let s = 0; s < strands; s++) {
      const frac = (s / (strands - 1 || 1)) - 0.5;
      const off = frac * width;
      const sAlpha = alpha * (0.28 + rng() * 0.52) * (1 - Math.abs(frac) * 0.7);
      const startI = Math.floor(rng() * Math.min(4, sampled.length - 2));
      const endI = sampled.length - Math.floor(rng() * Math.min(4, sampled.length - 2));
      ctx.strokeStyle = rgba(color, sAlpha);
      ctx.lineWidth = Math.max(0.6, (width / strands) * (0.7 + rng() * 0.85));
      ctx.beginPath();
      for (let i = startI; i < endI; i++) {
        const p = sampled[i];
        const j = (valueNoise2D(p.s * 0.03, s * 2.3, (seed || 441) + s * 13) - 0.5) * width * 0.35;
        const px = p.x + p.nx * (off + j);
        const py = p.y + p.ny * (off + j);
        if (i === startI) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function inkSplatter(ctx, cx, cy, radius, count, color, alpha, seed, dirX, dirY) {
    if (alpha <= 0.005 || count <= 0) return;
    const rng = mulberry32(seed || 515);
    const col = color || PALETTE.ironGall;
    const dx = dirX || 0;
    const dy = dirY || 0;
    ctx.save();
    for (let i = 0; i < count; i++) {
      const ang = rng() * Math.PI * 2;
      const dist = Math.pow(rng(), 0.65) * radius;
      const x = cx + Math.cos(ang) * dist + dx * (dist * 0.45);
      const y = cy + Math.sin(ang) * dist + dy * (dist * 0.45);
      const r = 0.55 + Math.pow(rng(), 2.1) * 2.2;
      ctx.fillStyle = rgba(col, alpha * (0.35 + rng() * 0.65));
      ctx.beginPath();
      ctx.ellipse(x, y, r * (1 + Math.abs(dx) * 0.6), r * (0.75 + rng() * 0.45), ang, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  // --------------------------------------------------------------------------
  // 10. Delicate Sketchbook Margin & Calligraphic Flourish
  // --------------------------------------------------------------------------
  function drawSketchFrame(ctx, w, h, boil, alpha) {
    const a = alpha !== undefined ? alpha : 0.18;
    if (a <= 0.01) return;
    const m = Math.round(Math.min(w, h) * 0.022);
    const col = PALETTE.sepia;
    pencilStroke(ctx, [[m + 18, m], [w * 0.5, m + 0.6], [w - m - 18, m]], {
      medium: 'graphite', color: col, width: 0.75, alpha: a, seed: 9101, boil: boil, boilAmp: 0.35
    });
    pencilStroke(ctx, [[m + 18, h - m], [w * 0.5, h - m - 0.6], [w - m - 18, h - m]], {
      medium: 'graphite', color: col, width: 0.75, alpha: a, seed: 9102, boil: boil, boilAmp: 0.35
    });
    pencilStroke(ctx, [[m, m + 18], [m - 0.5, h * 0.5], [m, h - m - 18]], {
      medium: 'graphite', color: col, width: 0.7, alpha: a * 0.85, seed: 9103, boil: boil, boilAmp: 0.35
    });
    pencilStroke(ctx, [[w - m, m + 18], [w - m + 0.5, h * 0.5], [w - m, h - m - 18]], {
      medium: 'graphite', color: col, width: 0.7, alpha: a * 0.85, seed: 9104, boil: boil, boilAmp: 0.35
    });
  }

  function drawInkFlourish(ctx, cx, cy, halfWidth, alpha, boil, seed, color) {
    if (alpha <= 0.01) return;
    const col = color || PALETTE.sepia;
    pencilStroke(ctx, [
      [cx - halfWidth, cy + 0.8],
      [cx - halfWidth * 0.45, cy - 1.8],
      [cx, cy + 1.0],
      [cx + halfWidth * 0.45, cy - 1.8],
      [cx + halfWidth, cy + 0.8]
    ], {
      medium: 'ink', color: col, width: 1.05, alpha: alpha, seed: seed || 8821, boil: boil, boilAmp: 0.3
    });
    ctx.save();
    ctx.fillStyle = rgba(col, alpha * 0.85);
    ctx.beginPath();
    ctx.ellipse(cx, cy, 2.2, 1.4, 0.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  global.ArtEngine = {
    PALETTE: PALETTE,
    hexToRgb: hexToRgb,
    rgba: rgba,
    mixHex: mixHex,
    darkenHex: darkenHex,
    clamp: clamp,
    lerp: lerp,
    smoothstep: smoothstep,
    mulberry32: mulberry32,
    hash2i: hash2i,
    valueNoise2D: valueNoise2D,
    fbm2D: fbm2D,
    boilIndex: boilIndex,
    ensureProceduralTextures: ensureProceduralTextures,
    drawPaperBackdrop: drawPaperBackdrop,
    applyPaperToothOverlay: applyPaperToothOverlay,
    sampleSpline: sampleSplineUniform,
    pencilStroke: pencilStroke,
    atmosphericSkyWash: atmosphericSkyWash,
    watercolorBloom: watercolorBloom,
    watercolorWash: watercolorWash,
    paintTerrainLayer: paintTerrainLayer,
    traceOrganicPoly: traceOrganicPoly,
    paintOpaqueUndercoat: paintOpaqueUndercoat,
    watercolorPolygon: watercolorPolygon,
    charcoalTone: charcoalTone,
    charcoalSmudge: charcoalTone,
    shadeStrokes: shadeStrokes,
    crossHatch: shadeStrokes,
    chalkHighlight: chalkHighlight,
    mistVeil: mistVeil,
    chalkDab: mistVeil,
    dryBrushStreak: dryBrushStreak,
    inkSplatter: inkSplatter,
    drawSketchFrame: drawSketchFrame,
    drawInkFlourish: drawInkFlourish
  };
})(window);
