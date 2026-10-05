#!/usr/bin/env python3
"""
MouFlopening - interface web (même conception que MouFloster et MouFlanimeXer).

- Liste de la médiathèque : séries avec ou sans thème
- Choix manuel : on écoute les génériques proposés par AnimeThemes puis on clique « Utiliser »
- Mode automatique : une série, ou toutes celles qui n'ont pas de thème (avec barre de progression)
- Le thème est enregistré sous theme.mp3 dans le dossier de la série, puis Emby actualise cette série seule
"""

import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from src.config import load_config, load_secrets_env

BASE_DIR = Path(__file__).resolve().parent
load_secrets_env()   # identifiants et clé Emby (data/secrets.env), avant l'initialisation de la connexion


def _tmdb_key_from_moufloster():
    """Pas de clé TheMovieDB ici : on reprend celle de MouFloster (même serveur, même compte) sans la copier ni l'afficher."""
    if os.getenv("TMDB_API_KEY", "").strip():
        return
    try:
        for line in Path("/opt/moufloster/data/secrets.env").read_text(encoding="utf-8").splitlines():
            if line.startswith("TMDB_API_KEY="):
                os.environ["TMDB_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                return
    except OSError:
        pass


_tmdb_key_from_moufloster()

from src import library
from src.emby_client import EmbyClient
from src.fsutil import safe_move
from src.library import THEME_DIR, THEME_EXTS, THEME_FILENAME, find_theme
from src.sources.animethemes import AnimeThemesSource
from src.sources.youtube import YouTubeSource
from src.sources.base_source import ThemeResult

BASE_VERSION = "0.2"


def _changelog_version():
    """Numéro de version = la dernière entrée du CHANGELOG.md (celle que je décris à chaque mise à jour)."""
    try:
        m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (BASE_DIR / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def get_version():
    num = _changelog_version()
    try:
        short = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        if num:
            return f"v{num} ({short})"
        count = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        return f"v{BASE_VERSION}.{count} ({short})"
    except Exception:
        return f"v{num or BASE_VERSION}"


APP_VERSION = get_version()
CONFIG = load_config()
IGNORED_FOLDERS = []
CATS = library.discover_categories(CONFIG, IGNORED_FOLDERS)   # onglets : Animes, Séries, Films (dossiers du même type regroupés)
ROOTS, ROOT_CAT = [], []                                      # dossiers racine à plat, et l'onglet de chacun
for _i, _c in enumerate(CATS):
    for _p in _c["paths"]:
        ROOTS.append(_p)
        ROOT_CAT.append(_i)
EMBY = EmbyClient(CONFIG.get("emby", {}))
TARGET_DB = float(CONFIG.get("audio", {}).get("target_db", 89))   # niveau de chaque thème (référence ReplayGain / MP3Gain)
SOURCE = AnimeThemesSource(CONFIG.get("sources", {}).get("animethemes", {"enabled": True}),
                           threshold=CONFIG.get("matching", {}).get("threshold", 70), target_db=TARGET_DB)

YOUTUBE = YouTubeSource(CONFIG.get("sources", {}).get("youtube", {}), target_db=TARGET_DB)


def source_for(kind):
    """AnimeThemes pour les animes, YouTube pour les séries et les films."""
    return SOURCE if kind == "anime" else YOUTUBE


def kind_of(item_id):
    """Type (anime / series / movie) de l'onglet auquel appartient un identifiant « n/Dossier »."""
    try:
        return CATS[ROOT_CAT[int(str(item_id).split("/")[0])]]["kind"]
    except (ValueError, IndexError):
        return "anime"


app = Flask(__name__)

from src import progress
from src import skipped
from src.netfix import repair_urllib3


@app.before_request
def _repair_http():
    repair_urllib3()          # yt-dlp abîme urllib3 : on le répare avant chaque requête (voir src/netfix.py)

import auth
import diag

diag.setup_logging()
logger = logging.getLogger("mouflopening")
auth.init_app(app, APP_VERSION)

_work_lock = threading.Lock()   # un seul téléchargement/conversion à la fois (ménage le NAS et le CPU)

# Anciens thèmes mis de côté : sur le NAS (dossier MouFlopening), repli sur data/ si le partage n'est pas accessible
OLD_BACKUP_DIR = BASE_DIR / "data" / "themes-backup"
_BACKUP_CFG = Path(CONFIG.get("themes", {}).get("backup_dir") or "/mnt/mouflosyno/MouFlopening/Anciens thèmes")


def _backup_dir():
    try:
        _BACKUP_CFG.mkdir(parents=True, exist_ok=True)
        if os.access(_BACKUP_CFG, os.W_OK):
            return _BACKUP_CFG
    except OSError:
        pass
    logger.warning("Dossier de sauvegarde %s inaccessible (partage monté ?) : repli sur %s", _BACKUP_CFG, OLD_BACKUP_DIR)
    return OLD_BACKUP_DIR


def _migrate_old_backups():
    """Une fois : les sauvegardes déjà faites dans data/themes-backup sont déplacées vers le NAS."""
    if not OLD_BACKUP_DIR.is_dir() or not any(OLD_BACKUP_DIR.iterdir()):
        return
    dest = _backup_dir()
    if dest == OLD_BACKUP_DIR:
        return
    for item in list(OLD_BACKUP_DIR.iterdir()):
        try:
            target = dest / item.name
            if not target.exists():
                safe_move(item, target)
                logger.info("Sauvegarde déplacée vers le NAS : %s", target)
        except OSError as e:
            logger.warning("Déplacement impossible (%s) : %s", item.name, e)
NORMALIZED_FILE = BASE_DIR / "data" / "normalized.json"
skipped.init(BASE_DIR / "data" / "skipped.json")


def _slug(text):
    return re.sub(r"[^\w.-]+", "_", text).strip("_")[:80] or "theme"


def _backup_existing(folder):
    """Avant de poser un nouveau thème, l'ancien (theme.mp3 ou theme.flac, ogg…) est mis de côté, jamais supprimé."""
    for ext in THEME_EXTS:
        old = folder / f"theme{ext}"
        if old.is_file():
            dest = _backup_dir()
            name = f"{datetime.now():%Y%m%d-%H%M%S}_{_slug(folder.parent.name)}_{_slug(folder.name)}{ext}"
            safe_move(old, dest / name)
            logger.info("Ancien thème mis de côté : %s", dest / name)


def _download_replace(source, url, folder):
    """Télécharge d'abord à côté ; l'ancien thème n'est mis de côté qu'une fois le nouveau bien reçu. -> (succès, raison)"""
    tmp = folder / "theme.nouveau.partiel"
    progress.say("Téléchargement du thème…")
    try:
        tmp.unlink()
    except OSError:
        pass
    if not source.download(url, tmp):
        try:
            tmp.unlink()
        except OSError:
            pass
        return False, getattr(source, "last_error", "") or "téléchargement ou conversion impossible (détails : bouton Journal)"
    progress.say("Mise en place du thème (l'ancien est mis de côté)…")
    _backup_existing(folder)
    safe_move(tmp, folder / THEME_FILENAME)
    return True, ""


def _read_registry():
    try:
        return json.loads(NORMALIZED_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _signature(path):
    st = path.stat()
    return [st.st_size, int(st.st_mtime)]


# ---------------------------------------------------------------------------
# Téléchargement automatique de toutes les séries sans thème (en arrière-plan)
# ---------------------------------------------------------------------------

BATCH = {"kind": "download", "running": False, "stop": False, "total": 0, "done": 0, "failed": 0, "current": "", "messages": []}
_batch_lock = threading.Lock()


def _batch_note(text):
    logger.info("[lot] %s", text)
    with _batch_lock:
        BATCH["messages"] = (BATCH["messages"] + [text])[-40:]


def _batch_state_text():
    with _batch_lock:
        b = dict(BATCH)
    if not b["running"] and not b["total"]:
        return "aucun lot lancé depuis le démarrage"
    norm = b.get("kind") == "normalize"
    return (f"{'Normalisation' if norm else 'Téléchargement'} · {'EN COURS' if b['running'] else 'terminé'} · {b['done'] + b['failed']}/{b['total']} "
            f"({'vérifiés' if norm else 'ajoutés'} {b['done']}, {'erreurs' if norm else 'introuvables'} {b['failed']}) · en cours : {b['current'] or '-'}")


def _run_batch(limit, with_seasons, cat=0):
    kind = CATS[cat]["kind"]
    roots = list(CATS[cat]["paths"])
    todo = [("film" if kind == "movie" else "série", title, folder, folder, None) for title, folder in library.missing_themes(roots)]
    if with_seasons and kind == "anime":          # films et séries : seul ThemerrDB est accepté, et il ne connaît pas les saisons
        todo += [(f"saison {n}", title, folder, series, n) for title, n, folder, series in library.missing_season_themes(roots)]
    sk = skipped.all_keys()
    n_all = len(todo)
    todo = [t for t in todo if str(t[2]) not in sk]          # les titres déjà recherchés sans résultat sont laissés de côté
    n_skip = n_all - len(todo)
    if limit:
        todo = todo[:limit]
    with _batch_lock:
        BATCH.update(kind="download", running=True, stop=False, total=len(todo), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(todo)} thème(s) à chercher" + (" (séries et saisons)" if with_seasons else " (séries)")
                + (f" · {n_skip} mis de côté (déjà cherchés sans résultat) ignoré(s)" if n_skip else ""))
    try:
        for _what, title, folder, series, number in todo:
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            label = title if number is None else f"{title} — saison {number}"
            with _batch_lock:
                BATCH["current"] = label
            ok, msg = _auto_one(folder, title, series, number, kind=kind)   # kind = type de l'onglet (anime / série / film)
            if ok:
                skipped.remove(folder)
            elif kind == "anime":              # films et séries : « pas dans ThemerrDB » ne veut pas dire « introuvable » (recherche à la main possible)
                skipped.add(folder)
            with _batch_lock:
                BATCH["done" if ok else "failed"] += 1
            _batch_note(("✅ " if ok else "❌ ") + f"{label} — {msg}")
    except Exception:
        logger.exception("Le lot s'est arrêté sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        with _batch_lock:
            BATCH.update(running=False, current="")


def year_of(name):
    """Année d'un dossier « Titre (2025) » (None si absente)."""
    m = re.search(r"\(\s*((?:19|20)\d{2})\s*\)", name or "")
    return int(m.group(1)) if m else None


def original_title_for(series, title, kind):
    """Titre original : d'abord Emby, sinon TheMovieDB (dossier vide créé par Radarr, pas encore scanné…). -> (titre, remarque)"""
    orig, why = EMBY.original_title(series.name, title, kind, series.parent.name)
    if orig:
        return orig, ""
    from src import title_lookup
    online, why2 = title_lookup.original_title(series.name, library.clean_title(series.name), kind, os.getenv("TMDB_API_KEY", "").strip())
    if online:
        return online, ""
    return "", f"{why} ; {why2}"


def themerr_for(series, kind):
    """Thème choisi par la base ThemerrDB (films et séries, via l'identifiant TheMovieDB). -> ({"title","video_id"} ou None, remarque)"""
    if kind == "anime":
        return None, ""
    from src import title_lookup
    from src.sources import themerrdb
    tid, why = title_lookup.tmdb_id(series.name, library.clean_title(series.name), kind, os.getenv("TMDB_API_KEY", "").strip())
    if not tid:
        return None, why
    return themerrdb.lookup(kind, tid)


def _auto_one(folder, title, series=None, number=None, query=None, kind="anime"):
    """Choisit automatiquement le générique (animes : AnimeThemes ; films et séries : uniquement ThemerrDB), l'enregistre (normalisé) et prévient Emby. -> (succès, message)"""
    series = series or folder
    query = query or (title if number is None else library.season_query(title, number))
    source = source_for(kind)
    with _work_lock:
        mtype = "anime" if kind == "anime" else ("movie" if kind == "movie" else "tv")
        result = None
        if kind != "anime":
            # Films et séries : on n'accepte QUE un thème validé par la communauté (ThemerrDB). Aucun choix automatique
            # sur YouTube (il valide n'importe quoi) : sinon on passe au suivant, la recherche se fait à la main.
            if number is not None:
                return False, "pas de thème validé par la communauté pour une saison : à chercher à la main"
            tr, why = themerr_for(series, kind)
            if not tr:
                return False, f"pas de thème validé par la communauté (ThemerrDB : {why or 'inconnu'}) : à chercher à la main"
            from src.sources.youtube import watch_url
            result = ThemeResult(title=(tr["title"] or title) + " (ThemerrDB)", source="YouTube", url=watch_url(tr["video_id"]))
        else:
            result = source.search(query, mtype)
            if not result and number is None:         # rien sous le titre du dossier : on tente le titre original
                alt, _ = original_title_for(series, title, kind)
                if alt and alt.casefold() != query.casefold():
                    result = source.search(alt, mtype)
            if not result:
                return False, f"aucun générique trouvé sur {source.name} pour « {query} »"
        ok, why = _download_replace(source, result.url, folder)
        if not ok:
            return False, why
    emby = EMBY.refresh_series(series.name, title, number, kind, series.parent.name)
    return True, f"{result.title} · {emby['message']}"

def _run_normalize():
    """Ramène à TARGET_DB tous les theme.mp3 déjà présents (originaux copiés dans le dossier des anciens thèmes)."""
    from src.audio import normalize_file
    files = []
    skipped_other = 0
    movie_roots = [Path(p) for c in CATS if c["kind"] == "movie" for p in c["paths"]]
    for series in library.iter_series_folders(ROOTS):
        is_movie = any(r in series.parents for r in movie_roots)
        extra = [] if is_movie else [(f"saison {n}", f) for n, f in library.season_folders(series)]
        for label, folder in [("film" if is_movie else "série", series)] + extra:
            theme = find_theme(folder)
            if theme is None:
                continue
            if theme.suffix.lower() == ".mp3" and theme.parent == folder:
                files.append((f"{library.clean_title(series.name)} — {label}", theme))
            else:
                skipped_other += 1
    registry = _read_registry()
    backup = _backup_dir() / "normalisation" / f"{datetime.now():%Y%m%d-%H%M%S}"
    with _batch_lock:
        BATCH.update(kind="normalize", running=True, stop=False, total=len(files), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(files)} thème(s) MP3 à vérifier (cible {TARGET_DB:g} dB)" + (f" · {skipped_other} autre(s) format(s) ignoré(s)" if skipped_other else ""))
    changed = already = 0

    def save_registry():
        try:
            NORMALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
            NORMALIZED_FILE.write_text(json.dumps(registry))
        except OSError:
            pass
    try:
        for n_seen, (label, path) in enumerate(files, 1):
            if n_seen % 20 == 0:
                save_registry()     # enregistré au fil de l'eau : un redémarrage (mise à jour) ne fait pas tout refaire
            for leftover in path.parent.glob("*.partiel"):    # reste d'une copie interrompue (redémarrage en plein travail)
                try:
                    leftover.unlink()
                except OSError:
                    pass
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            with _batch_lock:
                BATCH["current"] = label
            if registry.get(str(path)) == _signature(path):
                already += 1
                with _batch_lock:
                    BATCH["done"] += 1
                continue
            try:
                with _work_lock:
                    status, before, after = normalize_file(path, TARGET_DB, backup_dir=backup / _slug(label))
            except Exception as e:      # un fichier récalcitrant ne doit pas arrêter tout le lot
                logger.exception("Normalisation impossible : %s", path)
                status, before, after = "error", None, None
                _batch_note(f"❌ {label} — {type(e).__name__} : {e}")
                with _batch_lock:
                    BATCH["failed"] += 1
                continue
            if status == "error":
                with _batch_lock:
                    BATCH["failed"] += 1
                _batch_note(f"❌ {label} — mesure ou conversion impossible (voir le Journal)")
                continue
            if status == "done":
                changed += 1
                registry[str(path)] = _signature(path)
                _batch_note(f"🔊 {label} — {before:.1f} → {after:.1f} dB" if after is not None else f"🔊 {label} normalisé")
            else:
                already += 1
                registry[str(path)] = _signature(path)
            with _batch_lock:
                BATCH["done"] += 1
        save_registry()
        _batch_note(f"Terminé : {changed} normalisé(s), {already} déjà au bon niveau" + (f" · originaux dans {backup}" if changed else ""))
    except Exception:
        logger.exception("La normalisation s'est arrêtée sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        save_registry()
        with _batch_lock:
            BATCH.update(running=False, current="")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html", version=APP_VERSION, target_db=f"{TARGET_DB:g}")


@app.route("/api/library")
def api_library():
    items = library.list_library(ROOTS)
    sk = skipped.all_keys()
    for it in items:
        root = int(it["id"].split("/")[0])
        base = Path(ROOTS[root]) / it["name"]
        it["skipped"] = (not it["has_theme"]) and str(base) in sk
        for se in it["seasons"]:
            se["skipped"] = (not se["has_theme"]) and str(base / se["name"]) in sk
        it["cat"] = ROOT_CAT[root]
        it["origin"] = Path(ROOTS[root]).name      # dossier d'origine (utile quand un onglet regroupe Films HD et Films 4K)
    cats = [{"index": i, "name": c["name"], "kind": c["kind"], "ok": c["ok"], "multi": len(c["paths"]) > 1} for i, c in enumerate(CATS)]
    return jsonify({"items": items, "emby": EMBY.configured, "categories": cats})


def _search_work(body):
    title = body.get("title", "").strip()
    if not title:
        return {"error": "Titre vide"}, 400
    try:
        kind = CATS[int(body.get("cat", 0))]["kind"]
    except (ValueError, IndexError):
        kind = "anime"

    titles = [title]
    note = ""
    folder, series, _ = library.resolve_target(ROOTS, body.get("id", ""))
    series_name = series.name if series else ""
    results, seen = [], set()
    if series and kind != "anime":
        progress.say("Consultation de ThemerrDB (thème validé par la communauté)…")
        tr, _why = themerr_for(series, kind)
        progress.say("ThemerrDB : thème trouvé ★" if tr else "ThemerrDB : rien pour ce titre")
        if tr:
            from src.sources.youtube import watch_url
            seen.add(tr["video_id"])
            results.append({"name": "★ " + (tr["title"] or title), "year": "base ThemerrDB", "channel": "choix validé par la communauté",
                            "score": 100, "themes": [{"slug": "▶", "type": "yt", "youtube": tr["video_id"], "url": watch_url(tr["video_id"])}]})
            if not body.get("full"):         # thème validé par la communauté : inutile de chercher sur YouTube (sauf demande explicite)
                return {"results": results, "source": "ThemerrDB", "queries": [], "themerr_only": True,
                        "note": "", "skipped": False}, 200
    if body.get("original"):
        # titre original d'après Emby / TheMovieDB (le titre français ne donne pas toujours de résultat)
        if series:
            progress.say("Recherche du titre original (Emby, puis TheMovieDB)…")
            orig, why = original_title_for(series, title, kind)
            if orig and orig.casefold() not in (t.casefold() for t in titles):
                titles.insert(0, orig)                    # le titre original a plus de chances d'avoir des sources : on le cherche en premier
            elif orig:
                note = "Le titre original est identique au titre cherché"
            else:
                note = "Titre original non utilisé : " + why

    def run(t):
        if kind == "anime":
            return SOURCE.candidates(t)
        return YOUTUBE.candidates(t, "movie" if kind == "movie" else "series", year=year_of(series_name))

    for i, t in enumerate(titles, 1):
        progress.say(f"Recherche {'AnimeThemes' if kind == 'anime' else 'sur YouTube'} : « {t} »" + (f" ({i}/{len(titles)})" if len(titles) > 1 else "") + "…")
        try:
            found = run(t)
        except Exception:
            if len(titles) == 1:
                raise
            logger.exception("Recherche impossible pour « %s »", t)
            continue
        for r in found:
            key = (r.get("themes") or [{}])[0].get("youtube") if kind != "anime" else r.get("name")
            if key in seen:
                continue
            seen.add(key)
            results.append(r)
    progress.say("Classement des résultats…")
    if not results and folder:
        skipped.add(folder)             # rien trouvé : mis de côté, pour ne plus le voir dans la liste « sans thème »
    results.sort(key=lambda r: -int(r.get("score") or 0))     # la sélection ThemerrDB (score 100) reste en tête
    return {"results": results[:12], "source": "AnimeThemes" if kind == "anime" else "YouTube", "queries": titles, "note": note,
            "skipped": bool(not results and folder)}, 200


@app.route("/api/search", methods=["POST"])
def api_search():
    body = request.get_json(silent=True) or {}
    return jsonify({"job": progress.start(lambda: _search_work(body))})


@app.route("/api/job/<jid>")
def api_job(jid):
    st = progress.status(jid, int(request.args.get("since", 0) or 0))
    if st is None:
        return jsonify({"error": "Opération inconnue (l'appli a peut-être redémarré)"}), 404
    return jsonify(st)


def _save_work(data):
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    url = data.get("url", "")
    if not folder:
        return {"error": "Série ou saison introuvable"}, 404
    kind = kind_of(data.get("id", ""))
    source = source_for(kind)
    if not source.is_allowed_url(url):
        return {"error": "Adresse non autorisée (seuls animethemes.moe et youtube.com sont acceptés)"}, 400
    if _work_lock.locked():
        progress.say("En attente : un autre traitement est en cours…")
    with _work_lock:
        ok, why = _download_replace(source, url, folder)
        if not ok:
            return {"error": "Thème non enregistré : " + why + ". L'ancien thème (s'il y en avait un) est conservé."}, 502
        progress.say("Mise à jour d'Emby…")
        emby = EMBY.refresh_series(series.name, data.get("title", ""), number, kind, series.parent.name)
    logger.info("Thème enregistré : %s", folder / THEME_FILENAME)
    skipped.remove(folder)
    return {"ok": True, "message": f"Thème enregistré. {emby['message']}", "emby_ok": emby["ok"]}, 200


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    return jsonify({"job": progress.start(lambda: _save_work(data))})


@app.route("/api/skip", methods=["POST"])
def api_skip():
    data = request.get_json(silent=True) or {}
    folder, _series, _n = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    (skipped.add if data.get("skip", True) else skipped.remove)(folder)
    return jsonify({"ok": True})


@app.route("/api/theme/delete", methods=["POST"])
def api_theme_delete():
    """Supprime le thème d'un titre : double validation obligatoire. Le fichier n'est pas détruit, il est mis de côté dans le dossier des anciens thèmes."""
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != 2:
        return jsonify({"error": "Double validation manquante : rien n'a été supprimé."}), 400
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    if not find_theme(folder):
        return jsonify({"error": "Ce titre n'a pas de thème"}), 404
    with _work_lock:
        _backup_existing(folder)
    if find_theme(folder):
        return jsonify({"error": "Le thème n'a pas pu être supprimé (droits d'écriture ? détails : bouton Journal)"}), 500
    logger.info("Thème supprimé (mis de côté) : %s", folder)
    kind = kind_of(data.get("id", ""))
    emby = EMBY.refresh_series(series.name, library.clean_title(series.name), number, kind, series.parent.name)
    return jsonify({"ok": True, "message": f"Thème supprimé (l'ancien fichier est conservé dans le dossier des anciens thèmes). {emby['message']}"})


@app.route("/api/auto", methods=["POST"])
def api_auto():
    data = request.get_json(silent=True) or {}
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    title = library.clean_title(series.name)
    query = (data.get("title") or "").strip() or None      # titre éventuellement corrigé à la main dans la page
    ok, msg = _auto_one(folder, title, series, number, query, kind_of(data.get("id", "")))
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 404)


@app.route("/api/theme")
def api_theme():
    folder = library.resolve_folder(ROOTS, request.args.get("id", ""))
    path = find_theme(folder) if folder else None
    if not path:
        return jsonify({"error": "Pas de thème"}), 404
    return send_file(path, mimetype=mimetypes.guess_type(path.name)[0] or "audio/mpeg", conditional=True)


@app.route("/api/batch/start", methods=["POST"])
def api_batch_start():
    body = request.get_json(silent=True) or {}
    limit, with_seasons = body.get("limit"), bool(body.get("seasons"))
    try:
        cat = int(body.get("cat", 0))
        CATS[cat]
    except (ValueError, IndexError):
        return jsonify({"error": "Médiathèque inconnue"}), 400
    with _batch_lock:   # on marque « en cours » tout de suite : la page qui interroge juste après le voit
        if BATCH["running"]:
            return jsonify({"error": "Un lot est déjà en cours"}), 409
        BATCH.update(running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_batch, args=(int(limit) if limit else None, with_seasons, cat), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/normalize/start", methods=["POST"])
def api_normalize_start():
    with _batch_lock:
        if BATCH["running"]:
            return jsonify({"error": "Un traitement est déjà en cours"}), 409
        BATCH.update(kind="normalize", running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_normalize, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/batch/stop", methods=["POST"])
def api_batch_stop():
    BATCH["stop"] = True
    return jsonify({"ok": True})


@app.route("/api/batch/status")
def api_batch_status():
    with _batch_lock:
        return jsonify(dict(BATCH))


os.environ['_TARGET_DB'] = f'{TARGET_DB:g}'
import emby_settings


def _emby_key_changed(key):
    EMBY.api_key = key


for _i, _c in enumerate(CATS):
    logger.info("Onglet %s : %s", _c["name"], " + ".join(_c["paths"]))
if IGNORED_FOLDERS:
    logger.info("Dossiers ignorés (type non reconnu) : %s — à ajouter dans config.json (library.categories) si besoin", ", ".join(IGNORED_FOLDERS))
try:
    _migrate_old_backups()
except Exception:
    logger.exception("Migration des anciennes sauvegardes impossible")
emby_settings.init_app(app, BASE_DIR, lambda: EMBY.host, _emby_key_changed)
import tmdb_settings
tmdb_settings.init_app(app, BASE_DIR)
diag.init_app(app, APP_VERSION, lambda: ROOTS, EMBY.describe, _batch_state_text)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8001)
