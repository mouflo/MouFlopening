/* MouFlopening · éditeur audio : courbe du son, zoom, curseurs de découpe, fondus.
   Utilisation : MouEditor.open({token, name, id, title, onSaved}) — la copie de travail est préparée par le serveur (/api/edit/…). */
(function () {
  'use strict';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); };
  var CSS = '.aed-bg{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:200;display:flex;align-items:center;justify-content:center;padding:8px}' +
    '.aed{background:var(--card,#1c1d20);color:var(--text,#eee);border-radius:10px;width:min(980px,100%);max-height:100%;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}' +
    '.aed h3{margin:0;font-size:1.05rem;display:flex;justify-content:space-between;gap:8px;align-items:center}' +
    '.aed .sub{color:var(--muted,#999);font-size:.85rem}' +
    '.aed-wave{position:relative;background:#101113;border-radius:6px;height:170px;touch-action:none;user-select:none;-webkit-user-select:none;overflow:hidden}' +
    '.aed-wave canvas{width:100%;height:100%;display:block}' +
    '.aed-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}' +
    '.aed-row .b{padding:9px 14px;border:0;border-radius:4px;background:var(--field,#2a2b2f);color:var(--text,#eee);cursor:pointer;font:inherit;font-weight:500}' +
    '.aed-row .b.go{background:var(--accent,#52b54b);color:#fff;font-weight:600}' +
    '.aed-row .b:disabled{opacity:.5;cursor:not-allowed}' +
    '.aed-row label{display:flex;align-items:center;gap:6px;color:var(--muted,#999);font-size:.9rem}' +
    '.aed-row input[type=number]{width:70px;background:var(--field,#2a2b2f);color:var(--text,#eee);border:1px solid var(--line,#3a3b3f);border-radius:4px;padding:8px;font:inherit}' +
    '.aed-pan{width:100%;accent-color:var(--accent,#52b54b)}' +
    '.aed-info{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:.85rem}' +
    '.aed-info div{background:var(--field,#2a2b2f);border-radius:6px;padding:8px;text-align:center}' +
    '.aed-info b{display:block;font-size:1rem}' +
    '.aed-msg{padding:9px 12px;border-radius:4px;font-size:.9rem}' +
    '.aed-msg.ok{background:rgba(82,181,75,.15);border:1px solid var(--accent,#52b54b)}.aed-msg.err{background:rgba(229,83,75,.15);border:1px solid var(--err,#e5534b)}' +
    '@media(max-width:700px){.aed{padding:10px}.aed-row .b{flex:1 1 auto}.aed-wave{height:150px}}';

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
      '<h3><span>✂️ Éditer le thème <span class="sub">· ' + esc(opt.name || '') + '</span></span><button class="b" id="aedX" style="background:none;border:0;color:inherit;font-size:1.3rem;cursor:pointer" aria-label="Fermer">✕</button></h3>' +
      '<div class="sub">Glisse la courbe pour la faire défiler, pince ou utilise ➕ ➖ pour zoomer, touche la courbe pour placer la lecture, tire les poignées <b style="color:#52b54b">verte</b> (début) et <b style="color:#e5534b">rouge</b> (fin). La partie hors des poignées est coupée.</div>' +
      '<div class="aed-wave" id="aedWave"><canvas id="aedCv"></canvas></div>' +
      '<input class="aed-pan" id="aedPan" type="range" min="0" max="1000" value="0" aria-label="Défilement">' +
      '<div class="aed-info"><div>Début<b id="aedS">0:00.00</b></div><div>Fin<b id="aedE">0:00.00</b></div><div>Durée gardée<b id="aedD">0:00.00</b></div></div>' +
      '<div class="aed-row"><button class="b go" id="aedPlay">▶ Écouter</button><button class="b" id="aedSetS">⏮ Début ici</button><button class="b" id="aedSetE">Fin ici ⏭</button>' +
      '<button class="b" id="aedZo" aria-label="Dézoomer">➖</button><button class="b" id="aedZi" aria-label="Zoomer">➕</button><button class="b" id="aedFit">↔ Tout voir</button></div>' +
      '<div class="aed-row"><label>Fondu d\'entrée <input type="number" id="aedFi" min="0" max="20" step="0.5" value="0"> s</label><label>Fondu de sortie <input type="number" id="aedFo" min="0" max="20" step="0.5" value="0"> s</label></div>' +
      '<div id="aedMsg"></div>' +
      '<div class="aed-row"><button class="b go" id="aedSave">💾 Enregistrer ce thème</button><button class="b" id="aedCancel">Annuler</button></div>' +
      '<div class="sub">Le thème en place n\'est remplacé qu\'à l\'enregistrement (l\'ancien est mis de côté, pas supprimé) ; le volume est remis au niveau habituel.</div></div>';
    document.body.appendChild(bg);
    var $ = function (id) { return bg.querySelector('#' + id); };
    var cv = $('aedCv'), wave = $('aedWave'), ctx = cv.getContext('2d');
    var audio = new Audio('/api/edit/' + opt.token + '/audio'); audio.preload = 'auto';
    var S = {dur: 0, bps: 100, peaks: null, pps: 50, view: 0, start: 0, end: 0, head: 0, playing: false, raf: 0, minPps: 1, maxPps: 400};
    var W = 0, H = 0;

    function close() { cancelAnimationFrame(S.raf); audio.pause(); audio.src = ''; document.removeEventListener('keydown', onKey); bg.remove(); document.body.style.overflow = ''; }
    document.body.style.overflow = 'hidden';
    $('aedX').onclick = $('aedCancel').onclick = close;
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
      var mid = H / 2, amp = H / 2 - 6, p = S.peaks, bps = S.bps;
      // courbe
      ctx.fillStyle = '#4a9fd5';
      for (var x = 0; x < W; x++) {
        var t0 = S.view + x / S.pps, t1 = t0 + 1 / S.pps;
        var b0 = Math.floor(t0 * bps), b1 = Math.max(b0, Math.ceil(t1 * bps) - 1), mn = 127, mx = -127;
        if (b0 * 2 >= p.length) break;
        for (var b = b0; b <= b1 && b * 2 < p.length; b++) { if (p[b * 2] < mn) mn = p[b * 2]; if (p[b * 2 + 1] > mx) mx = p[b * 2 + 1]; }
        var y0 = mid - (mx / 127) * amp, y1 = mid - (mn / 127) * amp;
        ctx.fillRect(x, y0, 1, Math.max(1, y1 - y0));
      }
      // repères de temps
      ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.font = '11px sans-serif';
      var step = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300].find(function (s) { return s * S.pps >= 70; }) || 600;
      for (var tt = Math.ceil(S.view / step) * step; tt < S.view + span(); tt += step) { var xx = xOf(tt); ctx.fillRect(xx, H - 14, 1, 14); ctx.fillText(fmt(tt).replace(/\.00$/, ''), xx + 3, H - 3); }
      // parties coupées
      ctx.fillStyle = 'rgba(0,0,0,.62)';
      var xs = xOf(S.start), xe = xOf(S.end);
      if (xs > 0) ctx.fillRect(0, 0, Math.min(W, xs), H);
      if (xe < W) ctx.fillRect(Math.max(0, xe), 0, W - Math.max(0, xe), H);
      // fondus (enveloppe)
      var fi = parseFloat($('aedFi').value) || 0, fo = parseFloat($('aedFo').value) || 0;
      ctx.strokeStyle = 'rgba(255,214,102,.9)'; ctx.lineWidth = 1.5;
      if (fi > 0) { ctx.beginPath(); ctx.moveTo(xs, H - 8); ctx.lineTo(xOf(S.start + fi), 8); ctx.stroke(); }
      if (fo > 0) { ctx.beginPath(); ctx.moveTo(xOf(S.end - fo), 8); ctx.lineTo(xe, H - 8); ctx.stroke(); }
      // poignées
      handle(xs, '#52b54b'); handle(xe, '#e5534b');
      // lecture
      var xh = xOf(S.head); if (xh >= 0 && xh <= W) { ctx.fillStyle = '#fff'; ctx.fillRect(xh - 1, 0, 2, H); }
      $('aedS').textContent = fmt(S.start); $('aedE').textContent = fmt(S.end); $('aedD').textContent = fmt(S.end - S.start);
      var pan = $('aedPan'), room = S.dur - span(); pan.disabled = room <= 0.01; pan.value = room > 0 ? Math.round(1000 * S.view / room) : 0;
    }
    function handle(x, color) {
      if (x < -20 || x > W + 20) return;
      ctx.fillStyle = color; ctx.fillRect(x - 1.5, 0, 3, H);
      ctx.beginPath(); ctx.arc(x, 14, 9, 0, 6.3); ctx.fill();
    }

    function zoom(f, center) {
      var c = center == null ? S.view + span() / 2 : center, rel = (c - S.view) / span();
      S.pps = Math.max(S.minPps, Math.min(S.maxPps, S.pps * f)); S.view = c - rel * span(); clampView(); draw();
    }
    $('aedZi').onclick = function () { zoom(1.6); }; $('aedZo').onclick = function () { zoom(1 / 1.6); };
    $('aedFit').onclick = function () { S.pps = S.minPps; S.view = 0; draw(); };
    $('aedPan').oninput = function () { var room = S.dur - span(); S.view = room > 0 ? room * this.value / 1000 : 0; draw(); };
    $('aedFi').oninput = $('aedFo').oninput = draw;
    wave.addEventListener('wheel', function (e) { e.preventDefault(); var r = wave.getBoundingClientRect(); zoom(e.deltaY < 0 ? 1.25 : 0.8, tOf(e.clientX - r.left)); }, {passive: false});

    // ----- doigt / souris : poignées, défilement, lecture, pincement -----
    var ptrs = {}, drag = null, pinch = null;
    wave.addEventListener('pointerdown', function (e) {
      wave.setPointerCapture(e.pointerId);
      var r = wave.getBoundingClientRect(), x = e.clientX - r.left; ptrs[e.pointerId] = {x: x};
      var ids = Object.keys(ptrs);
      if (ids.length === 2) { pinch = {d: Math.abs(ptrs[ids[0]].x - ptrs[ids[1]].x) || 1, pps: S.pps}; drag = null; return; }
      var ds = Math.abs(x - xOf(S.start)), de = Math.abs(x - xOf(S.end));
      if (Math.min(ds, de) < 18) drag = {kind: ds <= de ? 'start' : 'end'};
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
    function setPlaying(on) { S.playing = on; $('aedPlay').textContent = on ? '⏸ Pause' : '▶ Écouter'; if (!on) { audio.pause(); cancelAnimationFrame(S.raf); audio.volume = 1; } }
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
      S.dur = d.duration; S.bps = d.bins_per_sec; S.peaks = d.peaks; S.start = 0; S.end = d.duration; S.head = 0;
      msg(''); S.pps = 0; resize(); S.pps = S.minPps; draw();
    })();
  }
  window.MouEditor = {open: open};
})();
