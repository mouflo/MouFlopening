"""
Lot de nuit : chaque nuit à l'heure choisie, l'appli cherche les thèmes manquants (mêmes règles que le bouton « Télécharger tous les
thèmes manquants ») puis envoie un compte rendu par Telegram.

- Réglages (activé / heure) dans data/nightly.json
- Jeton du bot et identifiant de discussion : data/secrets.env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID), jamais sur GitHub
  (à défaut, on reprend ceux de MouFlanimeXer s'ils existent sur la même machine)
- Le jeton n'est jamais écrit dans le Journal ni renvoyé à la page
"""
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

from .netfix import repair_urllib3

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")
_CHAT_RE = re.compile(r"^(-?\d{3,20}|@[A-Za-z0-9_]{4,64})$")
_FALLBACK = Path("/opt/mouflanimexer/telegram_config.json")
_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_ICON = {"movie": "🎬", "series": "📺", "anime": "🎌"}
_NAME = {"movie": "Films", "series": "Séries", "anime": "Animes"}

_file = None
_lock = threading.Lock()


def init(path):
    global _file
    _file = Path(path)


def settings():
    try:
        d = json.loads(_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"enabled": bool(d.get("enabled", False)), "hour": min(23, max(0, int(d.get("hour", 3)))),
            "seasons": bool(d.get("seasons", True)), "last_run": d.get("last_run", ""), "last_summary": d.get("last_summary", ""),
            "retry_days": max(0, int(d.get("retry_days", 30) or 0))}


def save(**changes):
    with _lock:
        d = settings(); d.update(changes)
        _file.parent.mkdir(parents=True, exist_ok=True)
        tmp = _file.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, _file)


# ---------------------------------------------------------------- Telegram
def telegram_config():
    """(jeton, identifiant de discussion, origine) ; origine = « ici » ou « MouFlanimeXer » ; jeton vide si rien n'est réglé."""
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if tok and chat:
        return tok, chat, "ici"
    try:
        d = json.loads(_FALLBACK.read_text(encoding="utf-8"))
        if d.get("bot_token") and d.get("chat_id"):
            return str(d["bot_token"]), str(d["chat_id"]), "MouFlanimeXer"
    except (OSError, ValueError):
        pass
    return "", "", ""


def valid_thread(t):
    return bool(re.match(r"^\d{1,12}$", t or ""))


def telegram_thread():
    """Sujet du groupe Telegram (facultatif). Propre à MouFlopening : jamais repris de MouFlanimeXer."""
    t = os.getenv("TELEGRAM_THREAD_ID", "").strip()
    return t if valid_thread(t) and os.getenv("TELEGRAM_BOT_TOKEN", "").strip() else ""


def detect_group(token):
    """(ok, identifiant du groupe, numéro du sujet, erreur) d'après le dernier message écrit dans un sujet."""
    repair_urllib3()
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/getUpdates", json={"limit": 50, "timeout": 0}, timeout=15)
        if r.status_code != 200 and "webhook" in r.text.lower():
            return False, "", "", WEBHOOK
        maj = r.json().get("result", []) if r.status_code == 200 else []
    except (requests.exceptions.RequestException, ValueError) as e:
        return False, "", "", "Telegram injoignable : " + type(e).__name__
    for m in reversed(maj):
        msg = m.get("message") or {}
        c = msg.get("chat") or {}
        if c.get("type") == "supergroup" and c.get("id") and msg.get("message_thread_id") and msg.get("is_topic_message"):
            return True, str(c["id"]), str(msg["message_thread_id"]), ""
    return False, "", "", ("Aucun message de sujet reçu : dans ton groupe, ouvre le sujet de cette appli, écris « bonjour » "
                           "(le bot doit être administrateur du groupe), puis réessaie.")


def valid_token(t):
    return bool(_TOKEN_RE.match(t or ""))


def valid_chat(c):
    return bool(_CHAT_RE.match(c or ""))


def _clean(err, token):
    return str(err).replace(token, "***")


def check_bot(token):
    """(ok, message) : Telegram reconnaît-il ce jeton ?"""
    repair_urllib3()
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    except requests.exceptions.RequestException as e:
        return False, "Telegram injoignable : " + type(e).__name__
    if r.status_code == 401:
        return False, "Telegram refuse ce jeton"
    if r.status_code != 200:
        return False, f"Telegram a répondu {r.status_code}"
    try:
        return True, "Bot reconnu : @" + r.json()["result"]["username"]
    except (ValueError, KeyError):
        return True, "Bot reconnu"


def send(text, token=None, chat=None, thread=None):
    """Envoie un message. -> (ok, message). Ne lève jamais d'exception ; le jeton n'apparaît jamais dans le retour.
    thread : None = sujet des réglages ; "" = aucun ; sinon numéro du sujet."""
    if not token:
        token, chat, _o = telegram_config()
        if thread is None:
            thread = telegram_thread()
    if not token or not chat:
        return False, "Telegram n'est pas réglé"
    repair_urllib3()
    corps = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
    if valid_thread(thread):
        if int(thread) != 1:                     # 1 = sujet « Général » : Telegram veut qu'on ne précise rien
            corps["message_thread_id"] = int(thread)
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=corps, timeout=15)
    except requests.exceptions.RequestException as e:
        return False, "Telegram injoignable : " + type(e).__name__
    if r.status_code == 200:
        return True, "Message envoyé"
    try:
        why = r.json().get("description", "")
    except ValueError:
        why = ""
    return False, f"Telegram a refusé le message ({r.status_code}) {_clean(why, token)}".strip()


# ---------------------------------------------------------------- compte rendu
def _plural(n, one, many):
    return f"{n} {one if n <= 1 else many}"


_REASONS = [                       # (mot-clé dans le message d'échec, libellé du groupe)
    ("⏳", "⏳ panne passagère (retenté au prochain lot)"),
    ("ThemerrDB", "📭 pas de thème validé par la communauté (ThemerrDB)"),
    ("aucun générique", "🔎 aucun générique trouvé (AnimeThemes)"),
    ("fiche propre", "🎞️ pas de générique propre à la saison"),
    ("même thème", "🎞️ pas de générique propre à la saison"),
    ("pour une saison", "🎞️ saison : à chercher à la main"),
]


def reason_group(message):
    for key, label in _REASONS:
        if key in (message or ""):
            return label
    return "❓ autre raison (voir le Journal)"


def format_report(by_cat, seconds, now=None):
    """by_cat : [{"kind": "movie|series|anime", "added": [titres], "failed": n, "failures": [(titre, raison)], "nas_error": "..."}]
    -> texte du message, ou None s'il n'y a vraiment rien à dire."""
    now = now or datetime.now()
    added = sum(len(c["added"]) for c in by_cat)
    failed = sum(c["failed"] for c in by_cat)
    nas = list(dict.fromkeys(p for c in by_cat if c.get("nas_error") for p in c["nas_error"].split(", ")))   # chaque dossier une fois
    if not added and not failed and not nas:
        return None
    mins = max(1, round(seconds / 60))
    lines = ["🌙 MouFlopening — compte rendu de la nuit",
             f"📅 {_JOURS[now.weekday()]} {now.day} {_MOIS[now.month - 1]} · ⏱️ {mins} min", ""]
    if nas:
        lines += ["⚠️ Partage réseau inaccessible : " + ", ".join(nas), "   Rien n'a été touché dans ces dossiers. Le NAS est-il bien monté ?", ""]
    for c in by_cat:
        if not c["added"]:
            continue
        lines.append(f"{_ICON.get(c['kind'], '🎵')} {_NAME.get(c['kind'], 'Médiathèque')} — {_plural(len(c['added']), 'thème ajouté', 'thèmes ajoutés')}")
        shown = c["added"][:20]
        lines += [f"  ✅ {t}" for t in shown]
        if len(c["added"]) > len(shown):
            lines.append(f"  … et {len(c['added']) - len(shown)} autres")
        lines.append("")
    if added:
        lines.append(f"🎶 {_plural(added, 'nouveau thème', 'nouveaux thèmes')} dans Emby" + (" 🎉" if added >= 5 else ""))
    if failed:
        lines.append(f"🔍 {_plural(failed, 'titre', 'titres')} sans thème validé : à chercher à la main")
        groups = {}
        for c in by_cat:
            for title, why in c.get("failures") or []:
                groups.setdefault(reason_group(why), []).append(title)
        for label, titles in sorted(groups.items(), key=lambda g: -len(g[1])):
            more = f" … (+{len(titles) - 4})" if len(titles) > 4 else ""
            lines.append(f"  {label} : {len(titles)}")
            lines.append("     " + ", ".join(titles[:4]) + more)
    text = "\n".join(lines)
    return text if len(text) <= 4000 else text[:3990] + "\n…"


# ---------------------------------------------------------------- planificateur
def loop(run_now, is_busy):
    """Vérifie chaque minute s'il est l'heure ; run_now() lance le lot de nuit (une seule fois par jour)."""
    time.sleep(90)
    while True:
        try:
            s = settings()
            today = datetime.now().strftime("%Y-%m-%d")
            if s["enabled"] and datetime.now().hour == s["hour"] and s["last_run"] != today and not is_busy():
                save(last_run=today)
                run_now()
        except Exception:
            logger.exception("Lot de nuit en erreur")
        time.sleep(60)


WEBHOOK = "Ce bot est déjà branché sur une autre application (par exemple Jeedom) : Telegram lui envoie directement les messages, l'appli ne peut donc pas les lire pour détecter quoi que ce soit. Utilise plutôt « Lien d'un message » (appui long sur un message du sujet → Copier le lien), ou crée un bot réservé à tes applis avec @BotFather."

_LIEN = re.compile(r"t\.me/c/(\d{5,})/(\d+)(?:/(\d+))?")


def lire_lien(lien):
    """Lien d'un message de groupe (appui long → « Copier le lien ») → (groupe, sujet) ou None.
    https://t.me/c/1234567890/45/678 : groupe -1001234567890, sujet 45 ; https://t.me/c/1234567890/678 : sujet « Général »."""
    m = _LIEN.search(lien or "")
    return ("-100" + m.group(1), m.group(2) if m.group(3) else "") if m else None
