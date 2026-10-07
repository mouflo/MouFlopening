"""
🎵 Génériques pour les comptes « copain » (page /copain) : jamais de recherche libre sur YouTube.
  1) un titre que l'admin a déjà : son générique (lecture seule, rien n'est modifié chez elle) ;
  2) sinon, seulement un générique VALIDÉ par la communauté : ThemerrDB (films et séries, par identifiant TheMovieDB)
     ou AnimeThemes (animes). Le serveur télécharge et convertit, le copain reçoit le fichier.
Les liens de téléchargement sont des jetons créés par le serveur : un copain ne peut pas faire télécharger une autre vidéo.
"""
import logging
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from flask import after_this_request, jsonify, render_template, request, send_file

logger = logging.getLogger(__name__)
_jetons = {}             # jeton → (source, adresse, titre, date)
_verrou = threading.Lock()


def _jeton(source, adresse, titre):
    j = secrets.token_urlsafe(12)
    with _verrou:
        for k in [k for k, v in _jetons.items() if time.time() - v[3] > 3600]:
            _jetons.pop(k, None)
        _jetons[j] = (source, adresse, titre, time.time())
    return j


def init_app(app, roots, library, find_theme, animethemes, youtube, version):
    from src import title_lookup
    from src.sources import themerrdb

    @app.route("/copain")
    def copain_page():
        return render_template("copain.html", version=version())

    @app.route("/api/copain/chercher")
    def copain_chercher():
        q = (request.args.get("q") or "").strip()
        if len(q) < 2:
            return jsonify({"chez_admin": [], "tmdb": []})
        import unicodedata
        plie = lambda t: "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()
        cle = plie(q)
        chez = []
        for it in library.list_library(roots):
            nom = it.get("title") or it.get("name") or ""
            if cle in plie(nom) and it.get("has_theme"):
                chez.append({"id": it["id"], "titre": nom})
        res = []
        key = os.getenv("TMDB_API_KEY", "").strip()
        if key:
            try:
                r = title_lookup._get("/search/multi", key, {"query": q, "language": "fr-FR"})
                for x in (r.json().get("results") or [])[:10]:
                    if x.get("media_type") not in ("movie", "tv"):
                        continue
                    date = x.get("release_date") or x.get("first_air_date") or ""
                    res.append({"tmdb": x["id"], "type": x["media_type"], "titre": x.get("title") or x.get("name") or "?",
                                "original": x.get("original_title") or x.get("original_name") or "", "annee": date[:4],
                                "anime": x.get("original_language") == "ja" and 16 in (x.get("genre_ids") or [])})
            except Exception as e:
                logger.warning("Recherche TheMovieDB (copain) impossible : %s", e)
        return jsonify({"chez_admin": chez[:20], "tmdb": res})

    @app.route("/api/copain/theme")
    def copain_theme():
        """Générique d'un titre de l'admin, en lecture seule."""
        folder = library.resolve_folder(roots, request.args.get("id", ""))
        f = find_theme(folder) if folder else None
        if not f:
            return jsonify({"error": "Pas de générique"}), 404
        return send_file(f, as_attachment=request.args.get("dl") == "1", download_name=f"{folder.name} - theme{f.suffix}", conditional=True)

    @app.route("/api/copain/communaute", methods=["POST"])
    def copain_communaute():
        """Générique validé par la communauté pour un titre TheMovieDB : ThemerrDB, sinon AnimeThemes pour un anime."""
        b = request.get_json(silent=True) or {}
        try:
            tid = int(b.get("tmdb"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Titre inconnu"}), 400
        genre = "movie" if b.get("type") == "movie" else "tv"
        tr, why = themerrdb.lookup(genre, tid)
        if tr and tr.get("video_id"):
            return jsonify({"ok": True, "source": "ThemerrDB", "titre": tr.get("title") or b.get("titre"),
                            "jeton": _jeton("youtube", "https://www.youtube.com/watch?v=" + tr["video_id"], b.get("titre", ""))})
        if b.get("anime") or genre == "tv":
            for t in [x for x in (b.get("original"), b.get("titre")) if x]:
                r = animethemes.search(t, "series")
                if r:
                    return jsonify({"ok": True, "source": "AnimeThemes", "titre": r.title,
                                    "jeton": _jeton("animethemes", r.url, b.get("titre", ""))})
        return jsonify({"ok": False, "error": "Pas de générique validé par la communauté pour ce titre."})

    @app.route("/api/copain/fichier/<jeton>")
    def copain_fichier(jeton):
        with _verrou:
            v = _jetons.get(jeton)
        if not v:
            return jsonify({"error": "Lien expiré : relance la recherche."}), 404
        source, adresse, titre, _ = v
        tmp = Path(tempfile.mkdtemp(prefix="copain-")) / "theme.mp3"
        ok = youtube.download(adresse, tmp, trusted=True) if source == "youtube" else animethemes.download(adresse, tmp)
        if not ok or not tmp.exists():
            return jsonify({"error": "Téléchargement impossible pour le moment."}), 502
        data = tmp.read_bytes()
        try:
            tmp.unlink()
            tmp.parent.rmdir()
        except OSError:
            pass
        from io import BytesIO
        nom = "".join(c for c in (titre or "theme") if c.isalnum() or c in " -_").strip() or "theme"
        return send_file(BytesIO(data), mimetype="audio/mpeg", as_attachment=True, download_name=f"{nom} - theme.mp3")
