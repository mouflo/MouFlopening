/* MouFlopening · éditeur audio : courbe du son, zoom, curseurs de découpe, fondus.
   Utilisation : MouEditor.open({token, name, id, title, onSaved}) — la copie de travail est préparée par le serveur (/api/edit/…). */
(function () {
  'use strict';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); };
  var CSS = '.aed-bg{position:fixed;inset:0;background:#080b1f;z-index:200;display:flex;align-items:stretch;justify-content:center}' +
    '.aed{background:#0a0f2c;color:#eaf0ff;width:min(900px,100%);height:100dvh;max-height:100dvh;display:flex;flex-direction:column;overflow:hidden;font-family:inherit}' +
    '.aed>*{flex:none}' +
    '.aed button{background:#16204f;color:#eaf0ff;border:0;border-radius:12px;font:inherit;cursor:pointer;padding:0;box-shadow:none;min-height:0}' +
    '.aed .aed-top{display:flex;align-items:center;gap:10px;padding:10px 12px}' +
    '.aed .aed-top .t{flex:1;min-width:0;font-weight:700;font-size:1.05rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.aed .aed-top .t small{display:block;font-weight:400;font-size:.72rem;color:#8a94c4;overflow:hidden;text-overflow:ellipsis}' +
    '.aed .aed-ic{background:none;border:0;color:#eaf0ff;font-size:1.5rem;cursor:pointer;padding:6px 10px;line-height:1}' +
    '.aed .aed-save{background:linear-gradient(135deg,#7a4dff,#2d9cff);color:#fff;border:0;border-radius:6px;padding:10px 16px;font:inherit;font-weight:800;letter-spacing:.03em;cursor:pointer}' +
    '.aed .aed-save:disabled{opacity:.5}' +
    '.aed .aed-hint{color:#8a94c4;font-size:.78rem;padding:0 14px 6px;text-align:center}' +
    '.aed .aed-wave{position:relative;flex:1 1 auto!important;min-height:200px;background:#1a2150;touch-action:none;user-select:none;-webkit-user-select:none;overflow:hidden}' +
    '.aed .aed-wave canvas{position:absolute;inset:0;width:100%;height:100%;display:block}' +
    '.aed .aed-pan{width:calc(100% - 28px);margin:6px 14px 0;accent-color:#2d9cff}' +
    '.aed .aed-steps{display:flex;justify-content:space-between;gap:8px;padding:10px 12px 0}' +
    '.aed .aed-pill{display:flex;align-items:center;background:#16204f;border-radius:12px;overflow:hidden}' +
    '.aed .aed-pill button{background:none;border:0;color:#eaf0ff;font-size:1.5rem;width:46px;height:46px;cursor:pointer;line-height:1}' +
    '.aed .aed-pill button:active{background:#24306e}' +
    '.aed .aed-pill .v{min-width:74px;text-align:center;font-variant-numeric:tabular-nums;font-size:.95rem}' +
    '.aed .aed-pill .v small{display:block;font-size:.65rem;color:#8a94c4}' +
    '.aed .aed-zoom{display:flex;gap:8px;padding:8px 12px 0;align-items:center}' +
    '.aed .aed-chip{background:#16204f;color:#eaf0ff;border:0;border-radius:18px;padding:10px 16px;font:inherit;font-size:.9rem;cursor:pointer}' +
    '.aed .aed-zoom .aed-pill button{width:48px;height:44px;font-size:1.2rem;padding:0;overflow:visible}' +
    '.aed .aed-chip:active{background:#24306e}' +
    '.aed .aed-dur{margin-left:auto;color:#8a94c4;font-size:.85rem}.aed-dur b{color:#eaf0ff}' +
    '.aed .aed-transport{display:flex;justify-content:center;align-items:center;gap:34px;padding:10px 0 4px}' +
    '.aed .aed-round{width:56px;height:56px;border-radius:50%;border:0;background:#16204f;color:#eaf0ff;font-size:1.4rem;cursor:pointer}' +
    '.aed .aed-round.big{width:72px;height:72px;background:#1e9bff;font-size:1.9rem}' +
    '.aed .aed-fades{display:flex;gap:10px;justify-content:space-between;padding:8px 12px 12px;background:#16204f;border-radius:16px 16px 0 0;margin-top:6px}' +
    '.aed .aed-fade{flex:1;text-align:center}.aed-fade .l{font-size:.78rem;color:#b7c0ea;margin-bottom:4px}' +
    '.aed .aed-fade .aed-pill{background:#0a0f2c;justify-content:center}' +
    '.aed .aed-fade input{width:44px;background:none;border:0;color:#eaf0ff;text-align:center;font:inherit;font-size:1rem;padding:0}' +
    '.aed .aed-msg{margin:6px 12px 0;padding:9px 12px;border-radius:8px;font-size:.88rem}.aed-msg.ok{background:rgba(82,181,75,.18);border:1px solid #52b54b}.aed-msg.err{background:rgba(229,83,75,.18);border:1px solid #e5534b}' +
    '@media(min-width:900px){.aed{height:min(100dvh,760px);margin:auto;border-radius:12px}}';

  function fmt(t) { t = Math.max(0, t); var m = Math.floor(t / 60), s = t - m * 60; return m + ':' + (s < 10 ? '0' : '') + s.toFixed(2); }

  async function api(url, opts) {
    var res = await fetch(url, opts), data = {};
    if (res.status === 401) { location.href = '/login'; throw new Error('Session expirée'); }
    try { data = await res.json(); } catch (e) {}
    if (!res.ok && !data.error) data.error = 'Erreur ' + res.status;
    return data;
  }

  function open(opt) {
    if (!document.getElementById('aedCss')) { var st = document.createElement('style'); st.id = 'aedCss'; st.textContent = CSS; document.head.appendChild(st); }
    var bg = document.createElement('div'); bg.className = 'aed-bg';
    bg.innerHTML = '<div class="aed" role="dialog" aria-label="Éditeur audio">' +
      '<div class="aed-top"><button class="aed-ic" id="aedX" aria-label="Fermer">←</button><div class="t">Éditer le thème<small>' + esc(opt.name || '') + '</small></div><button class="aed-save" id="aedSave">ENREGISTRER</button></div>' +
      '<div class="aed-hint">Tire les poignées · touche la courbe pour placer la lecture · pince pour zoomer</div>' +
      '<div class="aed-wave" id="aedWave"><canvas id="aedCv"></canvas></div>' +
      '<input class="aed-pan" id="aedPan" type="range" min="0" max="1000" value="0" aria-label="Défilement">' +
      '<div class="aed-steps"><div class="aed-pill"><button data-st="s-" aria-label="Début −0,1 s">−</button><div class="v"><span id="aedS">0:00.00</span><small>début</small></div><button data-st="s+" aria-label="Début +0,1 s">+</button></div>' +
      '<div class="aed-pill"><button data-st="e-" aria-label="Fin −0,1 s">−</button><div class="v"><span id="aedE">0:00.00</span><small>fin</small></div><button data-st="e+" aria-label="Fin +0,1 s">+</button></div></div>' +
      '<div class="aed-zoom"><button class="aed-chip" id="aedSetS">⏮ Début ici</button><button class="aed-chip" id="aedSetE">Fin ici ⏭</button><div class="aed-pill"><button id="aedZo" aria-label="Dézoomer">⊖</button><button id="aedZi" aria-label="Zoomer">⊕</button></div></div>' +
      '<div class="aed-zoom" style="padding-top:4px"><button class="aed-chip" id="aedFit">↔ Tout voir</button><div class="aed-dur">Durée gardée <b id="aedD">0:00.00</b></div></div>' +
      '<div class="aed-transport"><button class="aed-round" id="aedToS" aria-label="Aller au début">⏮</button><button class="aed-round big" id="aedPlay" aria-label="Écouter">▶</button><button class="aed-round" id="aedToE" aria-label="Écouter la fin">⏭</button></div>' +
      '<div id="aedMsg"></div>' +
      '<div class="aed-fades"><div class="aed-fade"><div class="l">Fondu d\'entrée</div><div class="aed-pill"><button data-fd="i-">−</button><input type="number" id="aedFi" min="0" max="20" step="0.5" value="0" inputmode="decimal"><span>s</span><button data-fd="i+">+</button></div></div>' +
      '<div class="aed-fade"><div class="l">Fondu de sortie</div><div class="aed-pill"><button data-fd="o-">−</button><input type="number" id="aedFo" min="0" max="20" step="0.5" value="0" inputmode="decimal"><span>s</span><button data-fd="o+">+</button></div></div></div></div>';
    document.body.appendChild(bg);
    var $ = function (id) { return bg.querySelector('#' + id); };
    var cv = $('aedCv'), wave = $('aedWave'), ctx = cv.getContext('2d');
    var audio = new Audio('/api/edit/' + opt.token + '/audio'); audio.preload = 'auto';
    var S = {dur: 0, bps: 100, peaks: null, pps: 50, view: 0, start: 0, end: 0, head: 0, playing: false, raf: 0, minPps: 1, maxPps: 400};
    var W = 0, H = 0;

    function close() { cancelAnimationFrame(S.raf); audio.pause(); audio.src = ''; document.removeEventListener('keydown', onKey); bg.remove(); document.body.style.overflow = ''; }
    document.body.style.overflow = 'hidden';
    $('aedX').onclick = close;
    function msg(t, kind) { $('aedMsg').innerHTML = t ? '<div class="aed-msg ' + (kind || 'ok') + '">' + esc(t) + '</div>' : ''; }

    function span() { return W / S.pps; }
    function clampView() { S.view = Math.max(0, Math.min(S.view, Math.max(0, S.dur - span()))); }
    function xOf(t) { return (t - S.view) * S.pps; }
    function tOf(x) { return S.view + x / S.pps; }

    function resize() {
      var r = wave.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
      W = Math.max(50, r.width); H = r.height; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      S.minPps = W / Math.max(S.dur, 1); if (S.pps < S.minPps) S.pps = S.minPps;
      clampView(); draw();
    }

    function draw() {
      if (!S.peaks) return;
      ctx.clearRect(0, 0, W, H);
      var top = 22, bot = 40, mid = top + (H - top - bot) / 2, amp = (H - top - bot) / 2 - 4, p = S.peaks, bps = S.bps;
      var xs = xOf(S.start), xe = xOf(S.end);
      // zone gardée plus claire
      ctx.fillStyle = 'rgba(120,150,255,.14)'; ctx.fillRect(Math.max(0, xs), top, Math.min(W, xe) - Math.max(0, xs), H - top - bot);
      // barres du son
      var barW = 3, gain = 127 / Math.max(S.peak || 127, 20);
      for (var x = 0; x < W; x += barW) {
        var t0 = S.view + x / S.pps, t1 = t0 + barW / S.pps;
        var b0 = Math.floor(t0 * bps), b1 = Math.max(b0, Math.ceil(t1 * bps) - 1), mx = 0;
        if (b0 * 2 >= p.length) break;
        for (var b = b0; b <= b1 && b * 2 < p.length; b++) { var a1 = Math.max(Math.abs(p[b * 2]), Math.abs(p[b * 2 + 1])); if (a1 > mx) mx = a1; }
        var h = Math.max(2, Math.min(1, (mx / 127) * gain) * amp);
        var inside = (x + 1) >= xs && (x + 1) <= xe;
        ctx.fillStyle = inside ? '#35a7ff' : '#4a5688';
        ctx.fillRect(x, mid - h, 2, h * 2);
      }
      // règle des temps (en haut)
      ctx.fillStyle = 'rgba(200,210,255,.55)'; ctx.font = '11px sans-serif';
      var step = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300].find(function (s) { return s * S.pps >= 70; }) || 600;
      for (var tt = Math.ceil(S.view / step) * step; tt < S.view + span(); tt += step) { var xx = xOf(tt); ctx.fillRect(xx, 14, 1, 8); ctx.fillText(fmt(tt).replace(/\.00$/, ''), xx + 3, 11); }
      // parties coupées assombries
      ctx.fillStyle = 'rgba(8,11,31,.62)';
      if (xs > 0) ctx.fillRect(0, top, Math.min(W, xs), H - top - bot);
      if (xe < W) ctx.fillRect(Math.max(0, xe), top, W - Math.max(0, xe), H - top - bot);
      // fondus (enveloppe)
      var fi = parseFloat($('aedFi').value) || 0, fo = parseFloat($('aedFo').value) || 0;
      ctx.strokeStyle = 'rgba(255,214,102,.95)'; ctx.lineWidth = 2;
      if (fi > 0) { ctx.beginPath(); ctx.moveTo(xs, H - bot); ctx.lineTo(xOf(S.start + fi), top + 6); ctx.stroke(); }
      if (fo > 0) { ctx.beginPath(); ctx.moveTo(xOf(S.end - fo), top + 6); ctx.lineTo(xe, H - bot); ctx.stroke(); }
      // poignées : trait + languette en bas
      handle(xs, '#2d9cff', -1); handle(xe, '#2d9cff', 1);
      // lecture
      var xh = xOf(S.head); if (xh >= 0 && xh <= W) { ctx.fillStyle = '#ff9d2e'; ctx.fillRect(xh - 1, top, 2, H - top - bot); ctx.beginPath(); ctx.arc(xh, top, 5, 0, 6.3); ctx.fill(); }
      $('aedS').textContent = fmt(S.start); $('aedE').textContent = fmt(S.end); $('aedD').textContent = fmt(S.end - S.start);
      var pan = $('aedPan'), room = S.dur - span(); pan.disabled = room <= 0.01; pan.value = room > 0 ? Math.round(1000 * S.view / room) : 0;
    }
    function handle(x, color, dir) {
      if (x < -30 || x > W + 30) return;
      var top = 22, bot = 40;
      ctx.fillStyle = color; ctx.fillRect(x - 1.5, top, 3, H - top - bot + 18);
      var w = 30, h = 36, y = H - bot - 4, x0 = dir < 0 ? x - w : x;          // languette : à gauche du trait pour le début, à droite pour la fin
      ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x0, y, w, h, 8) : ctx.rect(x0, y, w, h); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 26px sans-serif'; ctx.textAlign = 'center'; ctx.fillText(dir < 0 ? '‹' : '›', x0 + w / 2, y + 27); ctx.textAlign = 'start';
    }

    function zoom(f, center) {
      var c = center == null ? S.view + span() / 2 : center, rel = (c - S.view) / span();
      S.pps = Math.max(S.minPps, Math.min(S.maxPps, S.pps * f)); S.view = c - rel * span(); clampView(); draw();
    }
    $('aedZi').onclick = function () { zoom(1.6); }; $('aedZo').onclick = function () { zoom(1 / 1.6); };
    $('aedFit').onclick = function () { S.pps = S.minPps; S.view = 0; draw(); };
    $('aedPan').oninput = function () { var room = S.dur - span(); S.view = room > 0 ? room * this.value / 1000 : 0; draw(); };
    $('aedFi').oninput = $('aedFo').oninput = draw;
    bg.querySelectorAll('[data-st]').forEach(function (b) { b.onclick = function () {
      var k = b.dataset.st, d = k[1] === '+' ? 0.1 : -0.1;
      if (k[0] === 's') S.start = Math.max(0, Math.min(S.end - 0.5, S.start + d)); else S.end = Math.min(S.dur, Math.max(S.start + 0.5, S.end + d));
      S.head = S.start; draw(); }; });
    bg.querySelectorAll('[data-fd]').forEach(function (b) { b.onclick = function () {
      var k = b.dataset.fd, el = k[0] === 'i' ? $('aedFi') : $('aedFo'), v = (parseFloat(el.value) || 0) + (k[1] === '+' ? 0.5 : -0.5);
      el.value = Math.max(0, Math.min(20, Math.round(v * 2) / 2)); draw(); }; });
    wave.addEventListener('wheel', function (e) { e.preventDefault(); var r = wave.getBoundingClientRect(); zoom(e.deltaY < 0 ? 1.25 : 0.8, tOf(e.clientX - r.left)); }, {passive: false});

    // ----- doigt / souris : poignées, défilement, lecture, pincement -----
    var ptrs = {}, drag = null, pinch = null;
    wave.addEventListener('pointerdown', function (e) {
      wave.setPointerCapture(e.pointerId);
      var r = wave.getBoundingClientRect(), x = e.clientX - r.left; ptrs[e.pointerId] = {x: x};
      var ids = Object.keys(ptrs);
      if (ids.length === 2) { pinch = {d: Math.abs(ptrs[ids[0]].x - ptrs[ids[1]].x) || 1, pps: S.pps}; drag = null; return; }
      var ds = Math.abs(x - xOf(S.start)), de = Math.abs(x - xOf(S.end));
      if (Math.min(ds, de) < 26 || (e.clientY - r.top > H - 60 && Math.min(ds, de) < 44)) drag = {kind: ds <= de ? 'start' : 'end'};
      else drag = {kind: 'pan', x0: x, view0: S.view, moved: false};
    });
    wave.addEventListener('pointermove', function (e) {
      if (!ptrs[e.pointerId]) return;
      var r = wave.getBoundingClientRect(), x = e.clientX - r.left; ptrs[e.pointerId].x = x;
      var ids = Object.keys(ptrs);
      if (pinch && ids.length === 2) {
        var d = Math.abs(ptrs[ids[0]].x - ptrs[ids[1]].x) || 1, mid = (ptrs[ids[0]].x + ptrs[ids[1]].x) / 2, c = tOf(mid), rel = mid / W;
        S.pps = Math.max(S.minPps, Math.min(S.maxPps, pinch.pps * d / pinch.d)); S.view = c - rel * span(); clampView(); draw(); return;
      }
      if (!drag) return;
      if (drag.kind === 'pan') { if (Math.abs(x - drag.x0) > 5) drag.moved = true; S.view = drag.view0 - (x - drag.x0) / S.pps; clampView(); draw(); }
      else {
        var t = Math.max(0, Math.min(S.dur, tOf(x)));
        if (drag.kind === 'start') S.start = Math.min(t, S.end - 0.5); else S.end = Math.max(t, S.start + 0.5);
        if (S.head < S.start || S.head > S.end) { S.head = S.start; }
        draw();
      }
    });
    function up(e) {
      var r = wave.getBoundingClientRect(), x = e.clientX - r.left;
      if (drag && drag.kind === 'pan' && !drag.moved && ptrs[e.pointerId]) { S.head = Math.max(0, Math.min(S.dur, tOf(x))); audio.currentTime = S.head; draw(); }
      delete ptrs[e.pointerId]; if (Object.keys(ptrs).length < 2) pinch = null; if (!Object.keys(ptrs).length) drag = null;
    }
    wave.addEventListener('pointerup', up); wave.addEventListener('pointercancel', up);

    // ----- lecture de la partie gardée (avec aperçu des fondus) -----
    function setPlaying(on) { S.playing = on; $('aedPlay').textContent = on ? '⏸' : '▶'; if (!on) { audio.pause(); cancelAnimationFrame(S.raf); audio.volume = 1; } }
    function tick() {
      if (!S.playing) return;
      var t = audio.currentTime; S.head = t;
      if (t >= S.end - 0.02) { setPlaying(false); S.head = S.start; audio.currentTime = S.start; draw(); return; }
      var fi = parseFloat($('aedFi').value) || 0, fo = parseFloat($('aedFo').value) || 0, v = 1;
      if (fi > 0 && t - S.start < fi) v = Math.min(v, (t - S.start) / fi);
      if (fo > 0 && S.end - t < fo) v = Math.min(v, (S.end - t) / fo);
      audio.volume = Math.max(0, Math.min(1, v));
      if (xOf(t) > W * 0.9 || xOf(t) < 0) { S.view = t - span() * 0.1; clampView(); }
      draw(); S.raf = requestAnimationFrame(tick);
    }
    $('aedPlay').onclick = function () {
      if (S.playing) { setPlaying(false); return; }
      if (S.head < S.start || S.head >= S.end - 0.05) S.head = S.start;
      audio.currentTime = S.head; audio.play().then(function () { setPlaying(true); tick(); }).catch(function () { msg('La lecture a été refusée par le navigateur : réessaie.', 'err'); });
    };
    $('aedToS').onclick = function () { setPlaying(false); S.head = S.start; audio.currentTime = S.start; S.view = Math.max(0, S.start - span() * 0.1); clampView(); draw(); };
    $('aedToE').onclick = function () { setPlaying(false); S.head = Math.max(S.start, S.end - 4); audio.currentTime = S.head; S.view = S.end - span() * 0.9; clampView(); draw(); $('aedPlay').click(); };
    $('aedSetS').onclick = function () { if (S.head < S.end - 0.5) { S.start = S.head; draw(); } else msg('Le début doit être avant la fin.', 'err'); };
    $('aedSetE').onclick = function () { if (S.head > S.start + 0.5) { S.end = S.head; draw(); } else msg('La fin doit être après le début.', 'err'); };
    function onKey(e) { if (e.key === 'Escape') close(); else if (e.key === ' ' && e.target.tagName !== 'INPUT') { e.preventDefault(); $('aedPlay').click(); } }
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', resize);

    // ----- enregistrement -----
    $('aedSave').onclick = async function () {
      setPlaying(false);
      var btn = this; btn.disabled = true; msg('Envoi…', 'ok');
      var start = await api('/api/edit/' + opt.token + '/save', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
        id: opt.id, title: opt.title || '', start: S.start, end: S.end, fade_in: parseFloat($('aedFi').value) || 0, fade_out: parseFloat($('aedFo').value) || 0})});
      if (start.error) { btn.disabled = false; return msg(start.error, 'err'); }
      var since = 0, last = '';
      for (;;) {
        await new Promise(function (r) { setTimeout(r, 500); });
        var st; try { st = await api('/api/job/' + start.job + '?since=' + since); } catch (e) { continue; }
        if (st.error) { btn.disabled = false; return msg(st.error, 'err'); }
        since = st.next; if (st.steps.length) last = st.steps[st.steps.length - 1].text; if (!st.done) msg('⏳ ' + (last || 'En cours…'), 'ok');
        if (st.done) {
          var res = st.result && st.result[0] || {error: 'Réponse vide'};
          if (res.error) { btn.disabled = false; return msg(res.error, 'err'); }
          close(); if (opt.onSaved) opt.onSaved(res); return;
        }
      }
    };

    // ----- chargement de la courbe -----
    (async function () {
      msg('Chargement de la courbe…', 'ok');
      var d = await api('/api/edit/' + opt.token + '/peaks');
      if (d.error) return msg(d.error, 'err');
      S.dur = d.duration; S.bps = d.bins_per_sec; S.peaks = d.peaks; S.peak = 0; for (var i = 0; i < d.peaks.length; i++) { var q = Math.abs(d.peaks[i]); if (q > S.peak) S.peak = q; } S.start = 0; S.end = d.duration; S.head = 0;
      msg(''); S.pps = 0; resize(); S.pps = S.minPps; draw();
    })();
  }
  window.MouEditor = {open: open};
})();
