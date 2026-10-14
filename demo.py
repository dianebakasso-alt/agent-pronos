"""Données fictives pour tester le site sans clé API."""
import random
from datetime import timedelta

MATCHS = [
    ("soccer_france_ligue_one", "Ligue 1", "Rennes", "Lens", (0.44, 0.28, 0.28)),
    ("soccer_france_ligue_one", "Ligue 1", "Marseille", "Nice", (0.52, 0.25, 0.23)),
    ("soccer_france_ligue_one", "Ligue 1", "Nantes", "Paris Saint Germain", (0.13, 0.19, 0.68)),
    ("soccer_epl", "EPL", "Brighton", "Aston Villa", (0.41, 0.26, 0.33)),
    ("soccer_epl", "EPL", "Everton", "Newcastle United", (0.30, 0.29, 0.41)),
    ("soccer_spain_la_liga", "La Liga - Spain", "Real Betis", "Villarreal", (0.40, 0.29, 0.31)),
    ("soccer_italy_serie_a", "Serie A - Italy", "Bologna", "Lazio", (0.39, 0.30, 0.31)),
    ("soccer_germany_bundesliga", "Bundesliga - Germany", "Freiburg", "Stuttgart", (0.35, 0.27, 0.38)),
    ("soccer_brazil_campeonato", "Brazil Série A", "Fortaleza", "Botafogo", (0.33, 0.30, 0.37)),
    ("soccer_japan_j_league", "J League", "Kashima Antlers", "Urawa Reds", (0.46, 0.27, 0.27)),
]
BKS = [("pinnacle", "Pinnacle", 0.025), ("betclic_fr", "Betclic", 0.07), ("winamax_fr", "Winamax", 0.065),
       ("unibet_fr", "Unibet", 0.07), ("pmu_fr", "PMU", 0.075), ("netbet_fr", "NetBet", 0.08),
       ("betfair_ex_eu", "Betfair", 0.02), ("onexbet", "1xBet", 0.04), ("marathonbet", "Marathon Bet", 0.045)]


def matchs_fictifs(maintenant):
    rnd = random.Random(7)
    out = []
    for n, (cle, titre, dom, ext, probas) in enumerate(MATCHS):
        debut = (maintenant + timedelta(hours=3 + n * 2.5)).replace(minute=0, second=0, microsecond=0)
        bks = []
        for bcle, btitre, marge in BKS:
            p = [x * rnd.uniform(0.95, 1.05) for x in probas]
            if bcle.endswith("_fr") and rnd.random() < 0.18:  # un bookmaker FR mal calé
                i = rnd.randrange(3)
                p[i] *= 0.84
            s = sum(p)
            p = [x / s * (1 + marge) for x in p]
            if bcle == "pinnacle":
                s = sum(probas)
                p = [x / s * (1 + marge) for x in probas]
            noms = [dom, "Draw", ext]
            bks.append({"key": bcle, "title": btitre, "markets": [{"key": "h2h", "outcomes": [
                {"name": nm, "price": round(1 / x, 2)} for nm, x in zip(noms, p)]}]})
        out.append({"id": f"demo{n}", "sport_key": cle, "sport_title": titre,
                    "commence_time": debut.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "home_team": dom, "away_team": ext, "bookmakers": bks})
    return out


def avis_fictif(m):
    return {
        "avis": "confirme" if m["value"]["edge"] > 0.05 else "prudence",
        "resume": "Exemple d'avis : en vrai, l'IA résume ici les compos, blessures et avis de pronostiqueurs trouvés sur le web.",
        "points": ["Compo probable annoncée par la presse locale", "Aucun blessé majeur signalé",
                   "Les tipsters suivis sont partagés"],
    }


def historique_fictif(maintenant):
    rnd = random.Random(3)
    h = []
    for i in range(14):
        cote = round(rnd.uniform(1.8, 3.6), 2)
        gagne = rnd.random() < 1 / cote * 1.06
        mise = rnd.choice([2, 2.5, 3, 3.5, 4])
        h.append({"id": f"h{i}", "sport_key": "x",
                  "date": (maintenant - timedelta(days=i + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "match": f"Équipe A{i} - Équipe B{i}", "domicile": "", "exterieur": "",
                  "pari": "Victoire Équipe A" if i % 2 else "Match nul", "court": "1",
                  "cote": cote, "mise": mise, "bookmaker": "Winamax",
                  "statut": "gagné" if gagne else "perdu",
                  "gain": round(mise * (cote - 1), 2) if gagne else -mise,
                  "score": "2-1" if gagne else "0-1"})
    return h


def stats_fictives(m):
    rnd = random.Random(m["domicile"])
    f = lambda: [rnd.choice("VVVNND") for _ in range(5)]
    def eq():
        fo = f()
        return {"forme": fo, "points": sum(3 if x == "V" else 1 if x == "N" else 0 for x in fo),
                "buts_pour": rnd.uniform(0.8, 2.2), "buts_contre": rnd.uniform(0.6, 1.8), "forme_lieu": f(), "derniers": []}
    v1, v2 = rnd.randint(0, 3), rnd.randint(0, 2)
    return {"domicile": eq(), "exterieur": eq(),
            "face": {"n": 5, "v_dom": v1, "v_ext": v2, "nuls": 5 - v1 - v2, "scores": []}}


def combines_fictifs(maintenant):
    rnd = random.Random(5)
    out = []
    for i in range(6):
        cote = round(rnd.uniform(3.2, 7.5), 2)
        ok = rnd.random() < 1 / cote * 1.1
        jour = (maintenant - timedelta(days=i + 1)).strftime("%Y-%m-%d")
        out.append({"jour": jour, "bookmaker": "Winamax", "cote": cote, "proba": 1 / cote, "conseille": i % 3 != 2,
                    "mise": 10, "statut": "gagné" if ok else "perdu", "gain": round(10 * (cote - 1), 2) if ok else -10,
                    "jambes": [{"domicile": "Équipe A", "exterieur": "Équipe B", "pari": "Victoire Équipe A", "court": "1",
                                "cote": 2.1, "ok": ok or j, "score": "2-0"} for j in range(2)]})
    return out


def carnet_fictif(maintenant):
    """60 pronos réglés + quelques-uns en attente, pour la démo du tableau de bord."""
    import random
    rnd = random.Random(7)
    cats = ["match"] * 6 + ["value"] * 2 + ["prudent", "equilibre", "gros", "buts", "mixte"]
    equipes = [("Rennes", "Lens"), ("Marseille", "Nice"), ("Lyon", "Lille"), ("Arsenal", "Chelsea"), ("Inter", "Roma")]
    out = []
    for k in range(66):
        cat = rnd.choice(cats)
        cote = {"match": rnd.uniform(1.4, 2.6), "value": rnd.uniform(2, 4), "prudent": rnd.uniform(2, 3),
                "equilibre": rnd.uniform(3, 5), "gros": rnd.uniform(8, 20), "buts": rnd.uniform(2.5, 4), "mixte": rnd.uniform(3, 5)}[cat]
        proba = min(0.9, 1 / cote * rnd.uniform(0.95, 1.12))
        jour = (maintenant - timedelta(days=12 - k // 6)).strftime("%Y-%m-%d")
        regle = k < 60
        ok = rnd.random() < proba
        d, x = equipes[k % 5]
        out.append({"cle": f"{cat}:{k}", "jour": jour, "cat": cat, "cote": round(cote, 2), "proba": round(proba, 4),
                    "estime": cat in ("buts", "mixte"), "conseille": True, "mise": 10.0,
                    "statut": ("gagné" if ok else "perdu") if regle else "en attente",
                    "gain": (round(10 * (cote - 1), 2) if ok else -10.0) if regle else 0.0,
                    "jambes": [{"id": f"x{k}", "date": f"{jour}T18:00:00Z", "domicile": d, "exterieur": x,
                                "pari": f"Victoire {d}", "court": "1", "cote": round(cote, 2),
                                **({"ok": ok, "score": "2-1" if ok else "0-1"} if regle else {})}]})
    return out


def lecons_fictives(maintenant):
    j = (maintenant - timedelta(days=1)).strftime("%Y-%m-%d")
    return [
        {"date": j, "match": "PAOK - Kalamata", "pari": "Victoire PAOK", "cote": 1.17, "proba": 0.76, "score": "1-3",
         "pourquoi": "Exemple : PAOK a fait tourner après son match européen et a encaissé deux buts sur coups de pied arrêtés.",
         "previsible": "en partie", "signal_rate": "Match européen trois jours avant, rotation annoncée en conférence.",
         "tags": ["rotation", "fatigue"], "lecon": "Un favori qui sort d'un match européen en semaine perd beaucoup de sa marge."},
        {"date": j, "match": "Jaguares - Tolima", "pari": "Victoire Tolima", "cote": 1.54, "proba": 0.59, "score": "3-2",
         "pourquoi": "Exemple : Tolima a dominé mais a encaissé à la 93e minute.", "previsible": "non", "signal_rate": "",
         "tags": ["malchance"], "lecon": "Un but à la dernière minute reste de la malchance : ne pas changer de méthode pour ça."},
    ]
