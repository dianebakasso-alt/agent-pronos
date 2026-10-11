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

import memoire
import moteur
import stats
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
NB_JOURS = 7


def fin_fenetre(maintenant):
    """Jusqu'à la fin du 7e jour (heure de Paris) : toute la semaine qui vient."""
    local = maintenant.astimezone(site_web.PARIS)
    fin = (local + timedelta(days=NB_JOURS)).replace(hour=0, minute=0, second=0, microsecond=0)
    return fin.astimezone(timezone.utc)


def jour_de(m):
    return datetime.fromisoformat(m["debut"].replace("Z", "+00:00")).astimezone(site_web.PARIS).strftime("%Y-%m-%d")


def choisir_championnats(api, cfg, maintenant):
    """Liste les championnats de foot qui ont des matchs bientôt (gratuit)."""
    sports = api.get("/sports")
    foot = [s["key"] for s in sports
            if s.get("group") == "Soccer" and s.get("active") and not s.get("has_outrights")]
    prio = cfg["championnats_prioritaires"]
    foot.sort(key=lambda k: (prio.index(k) if k in prio else len(prio), k))

    fin = fin_fenetre(maintenant)
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
    fin = fin_fenetre(maintenant)
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
{stats}
{memoire}

Cherche sur le web les infos les plus récentes : compositions probables, blessés et suspendus,
déclarations des coachs, forme récente, contexte (enjeu, calendrier chargé, ambiance),
et ce que disent les pronostiqueurs et la presse locale.

Réponds UNIQUEMENT avec ce JSON, en français :
{{"avis": "confirme" | "prudence" | "eviter",
  "resume": "2 phrases maximum",
  "points": ["3 à 5 faits courts et vérifiés"],
  "a_retenir": {{"{dom}": ["faits durables utiles pour les prochains matchs"], "{ext}": ["..."]}}}}
"a_retenir" = seulement des faits qui resteront vrais quelques semaines (blessure longue, suspension,
crise, changement d'entraîneur, série en cours). Liste vide si rien de durable.
"confirme" = rien ne contredit le pari. "prudence" = signal mitigé. "eviter" = info importante contre le pari
(ex. joueur clé absent que la cote n'a peut-être pas encore intégré)."""


def avis_expert(m, v, cfg, cle_ia):
    corps = {
        "model": cfg["modele_ia"],
        "max_tokens": 3000,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
        "messages": [{"role": "user", "content": CONSIGNE_IA.format(
            dom=m["domicile"], ext=m["exterieur"], champ=m["championnat"], debut=m["debut"],
            issue=v["issue"], cote=v["cote"], proba=v["proba"],
            stats=stats.resume_texte(m.get("stats"), m["domicile"], m["exterieur"]),
            memoire=m.get("_memoire", ""))}],
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
        avis = (m.get("avis") or {}).get("avis")
        historique.append({
            "championnat": site_web.championnat(m["sport_key"], m["championnat"])[1], "proba": round(v["proba"], 4), "edge": round(v["edge"], 4),
            "avis": avis, "joue": avis != "eviter",
            "id": m["id"], "sport_key": m["sport_key"], "date": m["debut"],
            "match": f'{m["domicile"]} - {m["exterieur"]}',
            "domicile": m["domicile"], "exterieur": m["exterieur"],
            "pari": v["issue"], "court": v["court"], "cote": v["cote"],
            "mise": v["mise"], "bookmaker": v["bookmaker"], "statut": "en attente", "gain": 0,
        })


COMBINES = DATA / "combines.json"


def _termine(date_iso, maintenant):
    return datetime.fromisoformat(date_iso.replace("Z", "+00:00")) < maintenant - timedelta(hours=3)


def _resultat(s, dom, ext):
    if not s or not s.get("completed") or not s.get("scores"):
        return None, None
    buts = {x["name"]: int(x["score"]) for x in s["scores"]}
    d, e = buts.get(dom), buts.get(ext)
    if d is None or e is None:
        return None, None
    return ("1" if d > e else "2" if e > d else "N"), f"{d}-{e}"


def regler_paris(api, historique, combines, maintenant):
    """Va chercher les scores des paris et combinés terminés (2 crédits par championnat)."""
    simples = [h for h in historique if h["statut"] == "en attente" and _termine(h["date"], maintenant)]
    jambes = [j for c in combines if c["statut"] == "en attente" for j in c["jambes"]
              if not j.get("res") and _termine(j["date"], maintenant)]
    cles = {h["sport_key"] for h in simples} | {j["sport_key"] for j in jambes}
    scores = {}
    for cle in cles:
        try:
            scores.update({s["id"]: s for s in api.get(f"/sports/{cle}/scores", daysFrom=3)})
        except Exception as e:
            print(f"  ! scores {cle}: {e}")
    for h in simples:
        res, score = _resultat(scores.get(h["id"]), h["domicile"], h["exterieur"])
        if not res:
            continue
        h["score"], h["res"] = score, res
        if res == h["court"]:
            h["statut"], h["gain"] = "gagné", round(h["mise"] * (h["cote"] - 1), 2)
        else:
            h["statut"], h["gain"] = "perdu", -h["mise"]
    for j in jambes:
        res, score = _resultat(scores.get(j["id"]), j["domicile"], j["exterieur"])
        if res:
            j["res"], j["score"], j["ok"] = res, score, res == j["court"]
    for c in combines:
        if c["statut"] != "en attente":
            continue
        if any(j.get("ok") is False for j in c["jambes"]):
            c["statut"], c["gain"] = "perdu", -c["mise"]
        elif all(j.get("ok") for j in c["jambes"]):
            c["statut"], c["gain"] = "gagné", round(c["mise"] * (c["cote"] - 1), 2)


def enregistrer_combine(combines, combine, maintenant):
    """Garde le combiné du jour (un par jour, celui du matin), mise fictive de 10 €."""
    if not combine:
        return
    jour = maintenant.astimezone(site_web.PARIS).strftime("%Y-%m-%d")
    du_jour = [c for c in combines if c["jour"] == jour]
    if du_jour:
        c = du_jour[0]
        commence = any(datetime.fromisoformat(j["date"].replace("Z", "+00:00")) <= maintenant for j in c["jambes"])
        if commence or c["statut"] != "en attente":
            return
        combines.remove(c)
    combines.append({
        "jour": jour, "bookmaker": combine["bookmaker"], "cote": round(combine["cote"], 2),
        "proba": round(combine["proba"], 4), "conseille": combine["conseille"], "mise": 10,
        "statut": "en attente", "gain": 0,
        "jambes": [{"id": j["match"]["id"], "sport_key": j["match"]["sport_key"], "date": j["match"]["debut"],
                    "domicile": j["match"]["domicile"], "exterieur": j["match"]["exterieur"],
                    "pari": j["issue"], "court": j["court"], "cote": j["cote"]} for j in combine["jambes"]],
    })


def bilan_combines(combines):
    def calc(cs):
        r = [c for c in cs if c["statut"] in ("gagné", "perdu")]
        mises = sum(c["mise"] for c in r)
        gains = sum(c["gain"] for c in r)
        return {"nb": len(r), "gagnes": sum(c["statut"] == "gagné" for c in r),
                "benefice": round(gains, 2), "roi": gains / mises if mises else None}
    return {"tous": calc(combines), "conseilles": calc([c for c in combines if c["conseille"]]),
            "en_attente": sum(c["statut"] == "en attente" for c in combines)}


def bilan(historique):
    historique = [h for h in historique if h.get("joue", True)]
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
def d_stats(a):
    import demo as d
    return d.stats_fictives(a)


def main():
    demo = "--demo" in sys.argv
    cfg = charger_config()
    maintenant = datetime.now(timezone.utc)
    DATA.mkdir(exist_ok=True)

    if demo:
        import demo as d
        matchs = d.matchs_fictifs(maintenant)
        historique = d.historique_fictif(maintenant)
        combines = d.combines_fictifs(maintenant)
        appris = memoire.apprendre(historique, combines)
        api = None
    else:
        cle = os.environ.get("ODDS_API_KEY")
        if not cle:
            sys.exit("Il manque la clé ODDS_API_KEY (voir le guide).")
        api = OddsAPI(cle)
        historique = charger_historique()
        combines = json.loads(COMBINES.read_text(encoding="utf-8")) if COMBINES.exists() else []
        print("1/4 Règlement des paris passés…")
        regler_paris(api, historique, combines, maintenant)
        appris = memoire.apprendre(historique, combines)
        cfg["ajustements"] = appris["ajustements"]
        (DATA / "memoire.json").write_text(json.dumps(appris, ensure_ascii=False, indent=1), encoding="utf-8")
        print("    " + " | ".join(appris["lecons"]))
        print("2/4 Recherche des championnats avec des matchs…")
        champs = choisir_championnats(api, cfg, maintenant)
        print(f"    {len(champs)} championnats retenus")
        print("3/4 Récupération des cotes…")
        matchs = recuperer_matchs(api, cfg, champs, maintenant)

    analyses = [a for a in (moteur.analyser_match(m, cfg) for m in matchs) if a]
    analyses.sort(key=lambda a: a["debut"])
    values = sorted([a for a in analyses if a["value"]], key=lambda a: -a["value"]["edge"])
    print(f"    {len(analyses)} matchs analysés, {len(values)} value bets")

    print("    Forme et stats des équipes…")
    st = stats.Stats(maintenant)
    for a in analyses:
        if demo:
            a["stats"] = d_stats(a)
        else:
            try:
                a["stats"] = st.pour_match(a)
            except Exception as e:
                print(f"  ! stats {a['domicile']}: {e}")
    if not demo:
        (DATA / "stats_journal.json").write_text(json.dumps(st.journal, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"    stats : {st.journal['equipes_trouvees']} équipes trouvées, {len(st.journal['equipes_manquees'])} manquées")

    for a in analyses:
        a["buts"] = moteur.analyser_buts(a)

    # aujourd'hui et demain : chacun ses paris et ses combinés
    local = maintenant.astimezone(site_web.PARIS)
    auj = local.strftime("%Y-%m-%d")
    jours = []
    for k in range(NB_JOURS):
        cle = (local + timedelta(days=k)).strftime("%Y-%m-%d")
        quand = "aujourd'hui" if k == 0 else "demain" if k == 1 else site_web.nom_jour(cle)
        an_j = [a for a in analyses if jour_de(a) == cle]
        jours.append({"cle": cle, "quand": quand, "analyses": an_j,
                      "values": [a for a in values if jour_de(a) == cle],
                      "combos": moteur.combines_experts(an_j, cfg) + moteur.combines_buts(an_j),
                      "buts": moteur.pronos_buts(an_j)})
    if not demo:
        (DATA / "semaine.json").write_text(json.dumps([{"jour": j["cle"], "matchs": len(j["analyses"]),
            "value_bets": len(j["values"]), "combines": [(c["style"], c["conseille"], round(c["cote"], 2), round(c["proba"], 3)) for c in j["combos"]]}
            for j in jours], ensure_ascii=False, indent=1), encoding="utf-8")
    an_auj = jours[0]["analyses"]
    combine = moteur.combine_du_jour(an_auj, cfg)        # le combiné suivi dans le bilan (aujourd'hui)
    combos = [c for j in jours for c in j["combos"]]

    # l'IA vérifie l'actu des paris simples, puis des matchs des combinés (équilibré d'abord)
    # priorité à aujourd'hui, puis demain
    ordre = sorted([c for c in combos if not c.get("estime")],
                   key=lambda c: (jour_de(c["jambes"][0]["match"]) != auj,
                                  {"equilibre": 0, "prudent": 1, "gros": 2}.get(c["style"], 3)))
    taches, vus = [], set()
    for m in sorted(values, key=lambda m: jour_de(m) != auj):
        taches.append((m, m["value"], m)); vus.add((m["id"], m["value"]["court"]))
    for c in ordre:
        for j in c["jambes"]:
            if (j["match"]["id"], j["court"]) not in vus:
                taches.append((j["match"], j, j)); vus.add((j["match"]["id"], j["court"]))
    taches = taches[: cfg["analyse_ia_max_matchs"]]

    actu = memoire.charger(DATA / "memoire_actu.json", {})
    for m, v, cible in taches:
        m["_memoire"] = memoire.texte_memoire(actu, m["domicile"], m["exterieur"], maintenant)
    cle_ia = os.environ.get("ANTHROPIC_API_KEY")
    ia = {"etat": "eteinte", "ok": 0, "erreur": None, "souvenirs": sum(1 for m, _, _ in taches if m["_memoire"])}
    if cfg.get("analyse_ia") and taches:
        if demo:
            import demo as d
            for m, v, cible in taches:
                cible["avis"] = d.avis_fictif({"value": {"edge": v.get("edge", 0)}})
            ia["etat"], ia["ok"] = "active", len(taches)
        elif cle_ia:
            print("4/4 Vérification des infos et avis d'experts par l'IA…")
            for m, v, cible in taches:
                try:
                    cible["avis"] = avis_expert(m, v, cfg, cle_ia)
                    memoire.retenir(actu, cible["avis"].get("a_retenir"), maintenant)
                    ia["ok"] += 1
                except Exception as e:
                    detail = e.read().decode()[:200] if hasattr(e, "read") else str(e)[:200]
                    print(f"  ! IA {m['domicile']}: {e} {detail}")
                    ia["erreur"] = f"{getattr(e, 'code', '')} {detail}".strip()
            ia["etat"] = "active" if ia["ok"] else "erreur"
            (DATA / "memoire_actu.json").write_text(json.dumps(actu, ensure_ascii=False, indent=1), encoding="utf-8")
    elif cfg.get("analyse_ia") and cle_ia:
        ia["etat"] = "rien"
    # un même pari analysé une fois : on recopie l'avis partout où il apparaît
    avis_par_pari = {}
    for m, v, cible in taches:
        if cible.get("avis"):
            avis_par_pari[(m["id"], v["court"])] = cible["avis"]
    for c in combos + ([combine] if combine else []):
        for j in c["jambes"]:
            j.setdefault("avis", avis_par_pari.get((j["match"]["id"], j.get("court"))))

    if not demo:
        enregistrer_paris(historique, [v for v in values if jour_de(v) == auj])
        enregistrer_combine(combines, combine, maintenant)
        HISTORIQUE.write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
        COMBINES.write_text(json.dumps(combines, ensure_ascii=False, indent=1), encoding="utf-8")

    infos = {
        "genere": maintenant,
        "demo": demo,
        "credits_restants": api.credits_restants if api else None,
        "credits_utilises": api.credits_utilises if api else None,
        "bankroll": cfg["bankroll_euros"],
        "ia": ia,
        "combines": combines,
        "bilan_combines": bilan_combines(combines),
        "appris": appris,
        "jours": jours,
        "memoire_equipes": len(actu),
        "resultats": {**{h["id"]: {"res": h["res"], "score": h.get("score", "")} for h in historique if h.get("res")},
                      **{j["id"]: {"res": j["res"], "score": j.get("score", "")}
                         for c in combines for j in c["jambes"] if j.get("res") and j.get("id")}},
    }
    site_web.generer(ICI / "site" / "index.html", analyses, values, historique, bilan(historique), infos, combos)
    print("Site généré : site/index.html")


if __name__ == "__main__":
    main()
