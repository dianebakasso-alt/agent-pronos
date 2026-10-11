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
