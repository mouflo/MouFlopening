/* MouFlux · outils communs de la page ⚙️ Réglages (fichier identique dans les trois dépôts) */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
async function api(url, opts) {
    const res = await fetch(url, opts); let data = {};
    if (res.status === 401) { location.href = '/login'; throw new Error('Session expirée'); }
    try { data = await res.json(); } catch (e) {}
    if (!res.ok && !data.error) data.error = 'Erreur ' + res.status;
    return data;
}
const post = (url, body) => api(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
const say = (id, text, ok) => { $(id).innerHTML = text ? `<div class="note ${ok === 'warn' ? 'warn' : ok ? 'ok' : 'err'}">${esc(text)}</div>` : ''; };

// formulaire d'une clé API : Tester / Enregistrer
function keyForm(prefix, endpoint) {
    const state = async () => { const s = await api(endpoint); $(prefix + 'KeyState').textContent = s.configured ? 'Clé actuelle : ' + (s.hint || 'définie') : 'Aucune clé définie'; };
    $(prefix + 'KeyTest').addEventListener('click', async () => { say(prefix + 'KeyMsg', 'Test…', true); const r = await post(endpoint, {api_key: $(prefix + 'Key').value, test: true}); say(prefix + 'KeyMsg', r.message || r.error, r.ok); });
    $(prefix + 'KeySave').addEventListener('click', async () => {
        say(prefix + 'KeyMsg', 'Vérification…', true); const r = await post(endpoint, {api_key: $(prefix + 'Key').value});
        say(prefix + 'KeyMsg', r.message || r.error, r.ok); if (r.ok) { $(prefix + 'Key').value = ''; state(); }
    });
    return state();
}


// formulaire « un nombre » ou « un texte » enregistré par une route POST
function simpleSave(btnId, msgId, url, bodyFn, after) {
    $(btnId).addEventListener('click', async () => { const r = await post(url, bodyFn()); say(msgId, r.message || r.error, r.ok); if (r.ok && after) after(r); });
}
