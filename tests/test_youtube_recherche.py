"""🔎 Recherche YouTube : plus de mots-clés (main theme, opening…), notes qui séparent le bon thème des reprises et des compilations, raison affichée."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.sources.youtube import YouTubeSource, est_exclue  # noqa: E402


def source():
    return YouTubeSource({"timeout": 5})


class MotsClesTest(unittest.TestCase):
    def test_films_et_series_cherchent_main_theme_et_opening(self):
        for genre in ("movie", "series"):
            k = YouTubeSource._keywords(genre)
            for mot in ("theme", "main theme", "opening", "soundtrack"):
                self.assertIn(mot, k, (genre, mot))
        self.assertIn("theme song", YouTubeSource._keywords("movie"))
        self.assertIn("opening theme", YouTubeSource._keywords("series"))
        self.assertTrue(any("générique" in x for x in YouTubeSource._keywords("series")))
        self.assertIn("thème principal", YouTubeSource._keywords("movie"))


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.s = source()
        self.bon = {"title": "Die Hard - Main Theme (Michael Kamen)", "duration": 130, "uploader": "Michael Kamen - Topic"}

    def test_le_bon_thème_passe_devant_les_reprises_et_les_compilations(self):
        note = lambda e: self.s._score("Die Hard", e)
        reprise = {"title": "Die Hard Main Theme - piano cover", "duration": 140}
        compil = {"title": "Best Christmas movie themes compilation (Die Hard, Home Alone)", "duration": 1500}
        autre = {"title": "Opening theme of Another Show", "duration": 90}
        reaction = {"title": "Die Hard theme reaction", "duration": 200}
        for mauvais in (reprise, compil, autre, reaction):
            self.assertGreater(note(self.bon), note(mauvais), mauvais["title"])

    def test_titre_absent_est_ecarte_meme_avec_les_bons_mots(self):
        points, raisons = self.s._noter("Die Hard", {"title": "Opening theme main title soundtrack", "duration": 100})
        self.assertLess(points, 40)
        self.assertIn("titre absent", raisons)

    def test_raisons_affichees(self):
        points, raisons = self.s._noter("Die Hard", self.bon)
        self.assertTrue(any("main theme" in r for r in raisons), raisons)
        self.assertIn("le titre exact", raisons)
        self.assertIn("chaîne officielle ou musicale", raisons)

    def test_les_accents_ne_comptent_pas(self):
        p, _ = self.s._noter("Amélie", {"title": "AMELIE - Générique", "duration": 100})
        q, _ = self.s._noter("Amelie", {"title": "Amélie - Generique", "duration": 100})
        self.assertAlmostEqual(p, q, delta=10)
        self.assertGreater(p, 80)

    def test_un_titre_bourre_de_mots_cles_n_en_gagne_pas_plus(self):
        a, _ = self.s._noter("Lost", {"title": "Lost main theme theme song opening title sequence soundtrack ost score intro", "duration": 100})
        b, _ = self.s._noter("Lost", {"title": "Lost main theme theme song opening title sequence", "duration": 100})
        self.assertLessEqual(abs(a - b), 15)

    def test_titre_plus_long_que_la_video_et_annee_ignoree(self):
        p, raisons = self.s._noter("Die Hard (1988)", self.bon)                  # l'année de la fiche n'est pas dans le titre de la vidéo
        self.assertNotIn("titre absent", raisons)

    def test_le_titre_tout_seul_passe_apres_une_video_qui_dit_theme(self):
        seul, raisons = self.s._noter("Menteur", {"title": "Menteur", "duration": 150})
        theme, _ = self.s._noter("Menteur", {"title": "Menteur - Main Theme", "duration": 150})
        self.assertGreater(theme, seul)
        self.assertTrue(any("titre seul" in r for r in raisons))

    def test_video_trop_longue_ecartee(self):
        p, _ = self.s._noter("Die Hard", {"title": "Die Hard main theme 10 hours", "duration": 36000})
        self.assertLess(p, 0)


class ExclusionsTest(unittest.TestCase):
    """Les vidéos où l'on parle ne sont JAMAIS proposées (demande du 27/10) : bande-annonce en tête."""

    def test_titres_exclus(self):
        for titre in ("Les Tuche 4 - Bande-annonce officielle", "LES TUCHE 4 BANDE ANNONCE", "Les Tuche 4 | Bande-Annonce", "Die Hard Trailer #2",
                      "Die Hard (Official Teaser)", "Die Hard - extrait exclusif", "Die Hard - Scène culte", "Interview du réalisateur de Die Hard",
                      "Die Hard : making of", "Die Hard behind the scenes", "Die Hard critique", "Die Hard review", "Die Hard film complet",
                      "Die Hard full movie", "Les Tuche 4 BA officielle", "Die Hard - TV spot", "Die Hard épisode 1"):
            self.assertTrue(est_exclue(titre), titre)

    def test_vrais_themes_gardes(self):
        for titre in ("Die Hard - Main Theme", "Les Tuche 4 - Générique fin", "Ouverture - \"Les Tuche 4\"", "Menteur", "Joyeux Noël - Les Tuche 4",
                      "Die Hard (Original Motion Picture Soundtrack) - Opening", "Effraction - \"Les Tuche 4\"", "Bastille - Pompeii"):
            self.assertFalse(est_exclue(titre), titre)

    def test_mot_entier_seulement(self):
        self.assertFalse(est_exclue("Respite - Main Theme"))                      # « spite » ≠ « spot »
        self.assertFalse(est_exclue("Scenery - Main Theme"))                      # « scenery » ≠ « scene »
        self.assertFalse(est_exclue("Trailerpark Boys Theme"))                    # un mot qui contient « trailer » n'est pas « trailer »

    def test_un_mot_du_titre_cherche_n_est_pas_exclu(self):
        self.assertFalse(est_exclue("The Interview - Main Theme", "The Interview"))          # le film s'appelle « The Interview »
        self.assertTrue(est_exclue("The Interview - Bande-annonce", "The Interview"))
        self.assertFalse(est_exclue("Trailer Park Boys - Theme", "Trailer Park Boys"))
        self.assertTrue(est_exclue("Trailer Park Boys - Interview", "Trailer Park Boys"))

    def test_une_note_jamais_bonne_pour_un_titre_exclu(self):
        points, raisons = source()._noter("Die Hard", {"title": "Die Hard - Main Theme (Trailer version)", "duration": 100})
        self.assertLess(points, 0)

    def test_les_candidats_ne_contiennent_aucune_video_exclue(self):
        s = source()
        faux = [{"id": "A" * 11, "title": "Les Tuche 4 - Bande-annonce officielle", "duration": 100},
                {"id": "B" * 11, "title": "Les Tuche 4 - Générique fin", "duration": 90, "uploader": "OST - Topic"},
                {"id": "C" * 11, "title": "Les Tuche 4 | Extrait exclusif", "duration": 60},
                {"id": "D" * 11, "title": "Les Tuche 4 trailer", "duration": 130}]
        with mock.patch.object(s, "_raw_search", return_value=faux):
            res = s.candidates("Les Tuche 4", "movie", limit=10)
        self.assertEqual([r["name"] for r in res], ["Les Tuche 4 - Générique fin"])
        with mock.patch.object(s, "_raw_search", return_value=faux[:1] + faux[2:]):
            self.assertEqual(s.candidates("Les Tuche 4", "movie", limit=10), [])         # rien : plutôt aucun choix qu'une bande-annonce


class CandidatsTest(unittest.TestCase):
    def test_plus_de_requetes_notes_distinctes_et_raison(self):
        s = source()
        vus = []

        def recherche(q, n):
            vus.append(q)
            return [{"id": "A" * 11, "title": "Die Hard - Main Theme", "duration": 130, "uploader": "OST - Topic"},
                    {"id": "B" * 11, "title": "Die Hard theme (piano cover)", "duration": 150},
                    {"id": ("C" + str(len(vus))).ljust(11, "x")[:11], "title": "Best movie themes of the 80s compilation", "duration": 1800}]
        with mock.patch.object(s, "_raw_search", side_effect=recherche):
            res = s.candidates("Die Hard", "movie", limit=5)
        self.assertGreaterEqual(len(vus), 12)                                       # douze formulations au moins
        self.assertTrue(any("main theme" in q for q in vus))
        self.assertTrue(any("opening" in q for q in vus))
        self.assertEqual(res[0]["name"], "Die Hard - Main Theme")
        self.assertIn("main theme", res[0]["why"])
        self.assertTrue(all(0 <= r["score"] <= 99 for r in res))
        self.assertGreater(res[0]["score"], res[1]["score"])
        self.assertEqual(len({r["themes"][0]["youtube"] for r in res}), len(res))   # sans doublon

    def test_le_mode_automatique_ne_retient_que_ce_qui_convainc(self):
        s = source()
        with mock.patch.object(s, "_raw_search", return_value=[{"id": "D" * 11, "title": "Rien à voir", "duration": 100}]):
            self.assertIsNone(s.search("Die Hard", "movie"))
        with mock.patch.object(s, "_raw_search", return_value=[{"id": "E" * 11, "title": "Die Hard - Main Theme", "duration": 120, "uploader": "OST - Topic"}]):
            self.assertIsNotNone(s.search("Die Hard", "movie"))


if __name__ == "__main__":
    unittest.main()
