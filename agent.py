"""Agent Pronos — lance l'analyse du jour et fabrique le site.

Utilisation :
  python agent.py           -> vraie analyse (clé ODDS_API_KEY nécessaire)
  python agent.py --demo    -> données fictives, pour voir le site sans clé
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import moteur
import site_web

ICI = Path(__file__).parent
DATA = ICI / "data"
HISTORIQUE = DATA / "historique.json"
API = "https://api.the-odds-api.com/v4"


# ---------------------------------------------------------------- outils
def charger_config():
    return json.loads((ICI / "config.json").read_text(encoding="utf-8"))


def http_json(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8")), dict(r.headers)


class OddsAPI:
    def __init__(self, cle):
        self.cle = cle
        self.credits_restants = None
        self.credits_utilises = 0

    def get(self, chemin, **params):
        params["apiKey"] = self.cle
        url = f"{API}{chemin}?{urllib.parse.urlencode(params)}"
        data, h = http_json(url)
        h = {k.lower(): v for k, v in h.items()}
        if "x-requests-remaining" in h:
            self.credits_restants = int(float(h["x-requests-remaining"]))
        self.credits_utilises += int(float(h.get("x-requests-last", 0) or 0))
        return data


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- collecte
def choisir_championnats(api, cfg, maintenant):
    """Liste les championnats de foot qui ont des matchs bientôt (gratuit)."""
    sports = api.get("/sports")
    foot = [s["key"] for s in sports
            if s.get("group") == "Soccer" and s.get("active") and not s.get("has_outrights")]
    prio = cfg["championnats_prioritaires"]
    foot.sort(key=lambda k: (prio.index(k) if k in prio else len(prio), k))

    fin = maintenant + timedelta(hours=cfg["heures_a_venir"])
    retenus = []
    for cle in foot:
        if len(retenus) >= cfg["credits_max_par_jour"]:
            break
        try:
            evts = api.get(f"/sports/{cle}/events",
                           commenceTimeFrom=iso(maintenant), commenceTimeTo=iso(fin))
        except Exception as e:
            print(f"  ! {cle}: {e}")
            continue
        if evts:
            retenus.append(cle)
    return retenus


def recuperer_matchs(api, cfg, championnats, maintenant):
    fin = maintenant + timedelta(hours=cfg["heures_a_venir"])
    matchs = []
    for cle in championnats:
        try:
            matchs += api.get(f"/sports/{cle}/odds",
                              bookmakers=",".join(cfg["bookmakers_interroges"][:10]),
                              markets="h2h", oddsFormat="decimal",
                              commenceTimeFrom=iso(maintenant), commenceTimeTo=iso(fin))
        except Exception as e:
            print(f"  ! cotes {cle}: {e}")
    return matchs


# ---------------------------------------------------------------- avis des experts (IA)
CONSIGNE_IA = """Tu es un pronostiqueur football expérimenté et prudent.
Match : {dom} - {ext} ({champ}), coup d'envoi {debut} UTC.
Pari envisagé : {issue} à la cote {cote:.2f} (probabilité du marché {proba:.0%}).

Cherche sur le web les infos les plus récentes : compositions probables, blessés et suspendus,
déclarations des coachs, forme récente, contexte (enjeu, calendrier chargé, ambiance),
et ce que disent les pronostiqueurs et la presse locale.

Réponds UNIQUEMENT avec ce JSON, en français :
{{"avis": "confirme" | "prudence" | "eviter",
  "resume": "2 phrases maximum",
  "points": ["3 à 5 faits courts et vérifiés"]}}
"confirme" = rien ne contredit le pari. "prudence" = signal mitigé. "eviter" = info importante contre le pari
(ex. joueur clé absent que la cote n'a peut-être pas encore intégré)."""


def avis_expert(m, cfg, cle_ia):
    v = m["value"]
    corps = {
        "model": cfg["modele_ia"],
        "max_tokens": 1500,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
        "messages": [{"role": "user", "content": CONSIGNE_IA.format(
            dom=m["domicile"], ext=m["exterieur"], champ=m["championnat"], debut=m["debut"],
            issue=v["issue"], cote=v["cote"], proba=v["proba"])}],
    }
    data, _ = http_json("https://api.anthropic.com/v1/messages",
                        data=json.dumps(corps).encode(),
                        headers={"x-api-key": cle_ia, "anthropic-version": "2023-06-01",
                                 "content-type": "application/json"}, timeout=180)
    texte = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    debut, fin = texte.find("{"), texte.rfind("}")
    avis = json.loads(texte[debut:fin + 1])
    if avis.get("avis") not in ("confirme", "prudence", "eviter"):
        avis["avis"] = "prudence"
    return avis


# ---------------------------------------------------------------- historique / bilan
def charger_historique():
    if HISTORIQUE.exists():
        return json.loads(HISTORIQUE.read_text(encoding="utf-8"))
    return []


def enregistrer_paris(historique, analyses):
    deja = {h["id"] for h in historique}
    for m in analyses:
        v = m["value"]
        if not v or m["id"] in deja:
            continue
        if m.get("avis", {}).get("avis") == "eviter":
            continue
        historique.append({
            "id": m["id"], "sport_key": m["sport_key"], "date": m["debut"],
            "match": f'{m["domicile"]} - {m["exterieur"]}',
            "domicile": m["domicile"], "exterieur": m["exterieur"],
            "pari": v["issue"], "court": v["court"], "cote": v["cote"],
            "mise": v["mise"], "bookmaker": v["bookmaker"], "statut": "en attente", "gain": 0,
        })


def regler_paris(api, historique, maintenant):
    """Va chercher les scores des paris terminés (2 crédits par championnat)."""
    a_regler = [h for h in historique if h["statut"] == "en attente"
                and datetime.fromisoformat(h["date"].replace("Z", "+00:00")) < maintenant - timedelta(hours=3)]
    for cle in {h["sport_key"] for h in a_regler}:
        try:
            scores = {s["id"]: s for s in api.get(f"/sports/{cle}/scores", daysFrom=3)}
        except Exception as e:
            print(f"  ! scores {cle}: {e}")
            continue
        for h in a_regler:
            s = scores.get(h["id"])
            if h["sport_key"] != cle or not s or not s.get("completed") or not s.get("scores"):
                continue
            buts = {x["name"]: int(x["score"]) for x in s["scores"]}
            d, e = buts.get(h["domicile"]), buts.get(h["exterieur"])
            if d is None or e is None:
                continue
            res = "1" if d > e else "2" if e > d else "N"
            h["score"] = f"{d}-{e}"
            if res == h["court"]:
                h["statut"], h["gain"] = "gagné", round(h["mise"] * (h["cote"] - 1), 2)
            else:
                h["statut"], h["gain"] = "perdu", -h["mise"]


def bilan(historique):
    regles = [h for h in historique if h["statut"] in ("gagné", "perdu")]
    mises = sum(h["mise"] for h in regles)
    gains = sum(h["gain"] for h in regles)
    return {
        "nb": len(regles),
        "gagnes": sum(h["statut"] == "gagné" for h in regles),
        "en_attente": sum(h["statut"] == "en attente" for h in historique),
        "mises": round(mises, 2),
        "benefice": round(gains, 2),
        "roi": (gains / mises) if mises else None,
    }


# ---------------------------------------------------------------- programme principal
def main():
    demo = "--demo" in sys.argv
    cfg = charger_config()
    maintenant = datetime.now(timezone.utc)
    DATA.mkdir(exist_ok=True)

    if demo:
        import demo as d
        matchs = d.matchs_fictifs(maintenant)
        historique = d.historique_fictif(maintenant)
        api = None
    else:
        cle = os.environ.get("ODDS_API_KEY")
        if not cle:
            sys.exit("Il manque la clé ODDS_API_KEY (voir le guide).")
        api = OddsAPI(cle)
        historique = charger_historique()
        print("1/4 Règlement des paris passés…")
        regler_paris(api, historique, maintenant)
        print("2/4 Recherche des championnats avec des matchs…")
        champs = choisir_championnats(api, cfg, maintenant)
        print(f"    {len(champs)} championnats retenus")
        print("3/4 Récupération des cotes…")
        matchs = recuperer_matchs(api, cfg, champs, maintenant)

    analyses = [a for a in (moteur.analyser_match(m, cfg) for m in matchs) if a]
    analyses.sort(key=lambda a: a["debut"])
    values = sorted([a for a in analyses if a["value"]], key=lambda a: -a["value"]["edge"])
    print(f"    {len(analyses)} matchs analysés, {len(values)} value bets")

    cle_ia = os.environ.get("ANTHROPIC_API_KEY")
    if cfg.get("analyse_ia") and values:
        if demo:
            import demo as d
            for m in values[: cfg["analyse_ia_max_matchs"]]:
                m["avis"] = d.avis_fictif(m)
        elif cle_ia:
            print("4/4 Vérification des infos et avis d'experts par l'IA…")
            for m in values[: cfg["analyse_ia_max_matchs"]]:
                try:
                    m["avis"] = avis_expert(m, cfg, cle_ia)
                except Exception as e:
                    print(f"  ! IA {m['domicile']}: {e}")

    if not demo:
        enregistrer_paris(historique, values)
        HISTORIQUE.write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")

    infos = {
        "genere": maintenant,
        "demo": demo,
        "credits_restants": api.credits_restants if api else None,
        "credits_utilises": api.credits_utilises if api else None,
        "bankroll": cfg["bankroll_euros"],
    }
    combine = moteur.combine_du_jour(analyses, cfg)
    site_web.generer(ICI / "site" / "index.html", analyses, values, historique, bilan(historique), infos, combine)
    print("Site généré : site/index.html")


if __name__ == "__main__":
    main()
