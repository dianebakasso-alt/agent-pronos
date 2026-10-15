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
import expert
import selection
import autopsie
import direct
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
Cherche surtout les SIGNAUX DE SURPRISE qui font tomber les favoris : fatigue (match européen ou de coupe
3 jours avant ou après), rotation annoncée, cadres absents, série sans victoire à domicile, adversaire qui
remonte (nouvel entraîneur, série positive), match sans enjeu pour le favori. Un favori n'est jamais « sûr ».

Réponds UNIQUEMENT avec ce JSON, en français :
{{"avis": "confirme" | "prudence" | "eviter",
  "resume": "2 phrases maximum",
  "points": ["3 à 5 faits courts et vérifiés"],
  "a_retenir": {{"{dom}": ["faits durables utiles pour les prochains matchs"], "{ext}": ["..."]}}}}
"a_retenir" = seulement des faits qui resteront vrais quelques semaines (blessure longue, suspension,
crise, changement d'entraîneur, série en cours). Liste vide si rien de durable.
"confirme" = rien ne contredit le pari. "prudence" = signal mitigé. "eviter" = info importante contre le pari
(ex. joueur clé absent que la cote n'a peut-être pas encore intégré)."""

PROFOND = """

ANALYSE APPROFONDIE : ce match fait partie de la sélection de la semaine, l'expert le suit jusqu'au jour J.
Creuse davantage que d'habitude : blessés ET leur importance réelle dans l'équipe, rotation probable
(match de coupe ou d'Europe avant/après), enjeu au classement pour chacun, série en cours,
déplacement, météo, arbitre, et ce qui a changé depuis hier. Sois exigeant : au moindre doute sérieux, « prudence » ;
une info qui retourne le match, « eviter »."""


LECONS_TXT = ""


def appel_ia(texte, cfg, cle_ia, max_uses=3):
    corps = {"model": cfg["modele_ia"], "max_tokens": 6000,
             "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
             "messages": [{"role": "user", "content": texte}]}
    data, _ = http_json("https://api.anthropic.com/v1/messages", data=json.dumps(corps).encode(),
                        headers={"x-api-key": cle_ia, "anthropic-version": "2023-06-01",
                                 "content-type": "application/json"}, timeout=timeout)
    txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])


CONSIGNE_JOUR = """Tu es un pronostiqueur football expert, exigeant et honnête. Voici les matchs du jour.
Pour CHAQUE match, cherche sur le web l'actu récente (blessés, suspendus, rotation, forme, enjeu, fatigue)
puis donne TON verdict : est-ce qu'il y a un bon pari 1-N-2 à jouer, oui ou non ?

{matchs}

{lecons}

Réponds UNIQUEMENT avec ce JSON, en français :
{{"verdicts": [{{"n": numéro du match, "verdict": "jouer" | "prudence" | "eviter",
  "pari": "1" | "N" | "2" | "aucun", "raison": "1 à 2 phrases concrètes, avec les faits trouvés"}}]}}
"jouer" = tu le jouerais vraiment, l'actu et la forme vont dans le sens du pari.
"prudence" = jouable mais avec un vrai doute. "eviter" = pas bon : piège, actu défavorable ou match trop ouvert (pari "aucun").
Sois sévère : les favoris à petite cote perdent souvent, ne dis « jouer » que si tu y crois vraiment."""


def _verdicts_paquet(matchs, cfg, cle_ia):
    lignes = []
    for k, m in enumerate(matchs, 1):
        cotes = " / ".join(f'{i["court"]} {i["cote"]:.2f}' for i in m["issues"])
        st = stats.resume_texte(m.get("stats"), m["domicile"], m["exterieur"])
        deja = (m.get("avis") or {}).get("resume")
        lignes.append(f"{k}. {m['domicile']} - {m['exterieur']} ({m['championnat']}, {m['debut'][:16]} UTC). "
                      f"Cotes 1/N/2 : {cotes}. {st}" + (f" Déjà noté : {deja}" if deja else ""))
    res = appel_ia(CONSIGNE_JOUR.format(matchs="\n".join(lignes), lecons=LECONS_TXT), cfg, cle_ia,
                   max_uses=len(matchs) + 1, max_tokens=4000, timeout=300)
    out = {}
    for v in res.get("verdicts", []):
        try:
            m = matchs[int(v["n"]) - 1]
        except Exception:
            continue
        if v.get("verdict") in ("jouer", "prudence", "eviter"):
            out[m["id"]] = {"verdict": v["verdict"], "pari": v.get("pari") if v.get("pari") in ("1", "N", "2") else None,
                            "raison": str(v.get("raison", ""))[:300]}
    return out


TAILLE_PAQUET = 6
MAX_VERDICTS = 36


def verdicts_du_jour(matchs, cfg, cle_ia):
    """L'IA donne son verdict sur chaque match du jour, par paquets de 6 (réponse complète, pas tronquée)."""
    out = {}
    for k in range(0, min(len(matchs), MAX_VERDICTS), TAILLE_PAQUET):
        paquet = matchs[k:k + TAILLE_PAQUET]
        try:
            out.update(_verdicts_paquet(paquet, cfg, cle_ia))
        except Exception as e:
            print(f"  ! IA verdicts (paquet {k // TAILLE_PAQUET + 1}) : {e}")
    return out


def avis_expert(m, v, cfg, cle_ia, profond=False):
    corps = {
        "model": cfg["modele_ia"],
        "max_tokens": 3000,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 7 if profond else 4}],
        "messages": [{"role": "user", "content": CONSIGNE_IA.format(
            dom=m["domicile"], ext=m["exterieur"], champ=m["championnat"], debut=m["debut"],
            issue=v["issue"], cote=v["cote"], proba=v["proba"],
            stats=stats.resume_texte(m.get("stats"), m["domicile"], m["exterieur"]),
            memoire=m.get("_memoire", "") + ("\n" + LECONS_TXT if LECONS_TXT else "")) + (PROFOND if profond else "")}],
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
        try:
            jd = direct.relier(analyses, maintenant)
            (DATA / "espn_journal.json").write_text(json.dumps(jd, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"    direct : {jd['relies']} matchs reliés aux scores en direct")
        except Exception as e:
            print(f"  ! direct : {e}")
        (DATA / "stats_journal.json").write_text(json.dumps(st.journal, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"    stats : {st.journal['equipes_trouvees']} équipes trouvées, {len(st.journal['equipes_manquees'])} manquées")

    for a in analyses:
        a["buts"] = moteur.analyser_buts(a)

    # matchs du jour déjà commencés : la source des cotes ne les donne plus après le coup d'envoi,
    # on les reprend du passage précédent pour les afficher et les suivre en direct (jamais conseillés)
    if not demo:
        fichier_jour = DATA / "aujourdhui.json"
        jour_local = maintenant.astimezone(site_web.PARIS).strftime("%Y-%m-%d")
        avant = memoire.charger(fichier_jour, {})
        presents = {a["id"] for a in analyses}
        if avant.get("jour") == jour_local:
            for a in avant.get("matchs", []):
                if a["id"] not in presents and datetime.fromisoformat(a["debut"].replace("Z", "+00:00")) <= maintenant:
                    a.update({"value": None, "deja_commence": True})
                    analyses.append(a)
            analyses.sort(key=lambda a: a["debut"])
        garder = [{k: v for k, v in a.items() if k not in ("avis", "_memoire", "favori")}
                  for a in analyses if jour_de(a) == jour_local]
        fichier_jour.write_text(json.dumps({"jour": jour_local, "matchs": garder}, ensure_ascii=False, default=str), encoding="utf-8")

    # aujourd'hui et demain : chacun ses paris et ses combinés
    local = maintenant.astimezone(site_web.PARIS)
    auj = local.strftime("%Y-%m-%d")
    jours = []
    for k in range(NB_JOURS):
        cle = (local + timedelta(days=k)).strftime("%Y-%m-%d")
        quand = "aujourd'hui" if k == 0 else "demain" if k == 1 else site_web.nom_jour(cle)
        an_j = [a for a in analyses if jour_de(a) == cle]
        jouables = [a for a in an_j if not a.get("deja_commence")]
        jours.append({"cle": cle, "quand": quand, "analyses": an_j,
                      "values": [a for a in values if jour_de(a) == cle],
                      "combos": moteur.combines_experts(jouables, cfg) + moteur.combines_buts(jouables),
                      "buts": moteur.pronos_buts(jouables)})
    if not demo:
        (DATA / "semaine.json").write_text(json.dumps([{"jour": j["cle"], "matchs": len(j["analyses"]),
            "value_bets": len(j["values"]), "combines": [(c["style"], c["conseille"], round(c["cote"], 2), round(c["proba"], 3)) for c in j["combos"]]}
            for j in jours], ensure_ascii=False, indent=1), encoding="utf-8")
    an_auj = jours[0]["analyses"]
    combine = moteur.combine_du_jour(an_auj, cfg)        # le combiné suivi dans le bilan (aujourd'hui)
    combos = [c for j in jours for c in j["combos"]]

    # le carnet de l'expert (réglé tôt) : ce qu'il a appris de ses résultats oriente la sélection
    global LECONS_TXT
    if demo:
        import demo as d
        carnet = d.carnet_fictif(maintenant)
        lecons = d.lecons_fictives(maintenant)
    else:
        carnet = expert.charger(DATA / "carnet.json")
        try:
            expert.regler(carnet, maintenant)
        except Exception as e:
            print(f"  ! carnet réglement : {e}")
        lecons = autopsie.charger(DATA / "lecons.json")
    selection.AJUST = autopsie.ajustements(carnet)
    LECONS_TXT = autopsie.texte_lecons(lecons)

    # la sélection de la semaine : les matchs où l'expert a le plus confiance, suivis jusqu'au jour J
    sel = {"matchs": {}} if demo else selection.charger(DATA / "selection.json")
    focus = selection.mettre_a_jour(sel, [a for a in analyses if not a.get("deja_commence")], maintenant)
    jouables_auj = [a for a in jours[0]["analyses"] if not a.get("deja_commence")]
    avis_jour, verdicts = {}, {}

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
    # puis l'affiche du jour (le match le plus suivi) si elle n'est pas déjà vérifiée
    an_jour = [a for a in jours[0]["analyses"] if not a.get("deja_commence")]
    if an_jour:
        choc = max(an_jour, key=lambda m: (m["nb_bookmakers"], -abs(m["issues"][0]["proba"] - m["issues"][-1]["proba"])))
        fav = max(choc["issues"], key=lambda i: i["proba"])
        if (choc["id"], fav["court"]) not in vus and not choc.get("value"):
            taches.insert(min(len(taches), 3), (choc, fav, choc))
    taches = taches[: cfg["analyse_ia_max_matchs"]]

    actu = memoire.charger(DATA / "memoire_actu.json", {})
    for m, v, cible in taches:
        m["_memoire"] = memoire.texte_memoire(actu, m["domicile"], m["exterieur"], maintenant)
    cle_ia = os.environ.get("ANTHROPIC_API_KEY")
    ia = {"etat": "eteinte", "ok": 0, "erreur": None, "souvenirs": sum(1 for m, _, _ in taches if m["_memoire"])}
    if cfg.get("analyse_ia") and (taches or focus or autopsie.a_autopsier(carnet, maintenant)):
        if demo:
            import demo as d
            for m, v, cible in taches:
                cible["avis"] = d.avis_fictif({"value": {"edge": v.get("edge", 0)}})
            for m in focus:
                selection.noter_avis(sel, m["id"], d.avis_fictif({"value": {"edge": 0.05}}), maintenant)
            verdicts = d.verdicts_fictifs(jouables_auj)
            ia["etat"], ia["ok"] = "active", len(taches)
        elif cle_ia:
            print("4/4 Vérification des infos et avis d'experts par l'IA…")
            for j in autopsie.a_autopsier(carnet, maintenant):
                try:
                    autopsie.noter_autopsie(carnet, lecons, j, appel_ia(autopsie.consigne(j), cfg, cle_ia), maintenant)
                    ia["ok"] += 1
                except Exception as e:
                    print(f"  ! autopsie {j['domicile']}: {e}")
            LECONS_TXT = autopsie.texte_lecons(lecons)
            for m in focus[: cfg.get("analyse_profonde_max", 6)]:
                s = sel["matchs"][m["id"]]
                v = {"issue": s["issue"], "cote": s["cote"], "proba": s["proba"], "court": s["court"]}
                m["_memoire"] = memoire.texte_memoire(actu, m["domicile"], m["exterieur"], maintenant)
                try:
                    a = avis_expert(m, v, cfg, cle_ia, profond=True)
                    selection.noter_avis(sel, m["id"], a, maintenant)
                    memoire.retenir(actu, a.get("a_retenir"), maintenant)
                    ia["ok"] += 1
                except Exception as e:
                    print(f"  ! IA sélection {m['domicile']}: {e}")
            # le ticket du jour : ses matchs sont aussi analysés en profondeur
            deja = {x["id"] for x in focus}
            tk0 = selection.ticket_du_jour(jouables_auj, cfg["bookmakers_jouables"])
            for s in (tk0 or {}).get("jambes", [])[:3]:
                if s["id"] in deja:
                    continue
                m = next(a for a in analyses if a["id"] == s["id"])
                m["_memoire"] = memoire.texte_memoire(actu, m["domicile"], m["exterieur"], maintenant)
                try:
                    a = avis_expert(m, s, cfg, cle_ia, profond=True)
                    avis_jour[m["id"]] = a
                    memoire.retenir(actu, a.get("a_retenir"), maintenant)
                    ia["ok"] += 1
                except Exception as e:
                    print(f"  ! IA ticket du jour {m['domicile']}: {e}")
            # le verdict de l'IA sur chaque match du jour (un seul appel)
            try:
                for a in jouables_auj:
                    if a["id"] in avis_jour and not a.get("avis"):
                        a["avis"] = avis_jour[a["id"]]
                verdicts = verdicts_du_jour(sorted(jouables_auj, key=lambda a: a["debut"]), cfg, cle_ia) if jouables_auj else {}
                ia["ok"] += 1 if verdicts else 0
            except Exception as e:
                print(f"  ! IA verdicts du jour : {e}")
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

    ticket_semaine = selection.ticket(sel, analyses, cfg["bookmakers_jouables"])
    # chaque jour : un ticket du jour et l'avis de l'expert sur chaque match
    avis_connus = {k: s["avis"] for k, s in sel["matchs"].items() if s.get("avis")}
    avis_connus.update(avis_jour)
    for a in analyses:
        v = verdicts.get(a["id"])
        if v:
            a["verdict_ia"] = v
            avis_connus.setdefault(a["id"], {"avis": {"jouer": "confirme", "prudence": "prudence", "eviter": "eviter"}[v["verdict"]],
                                             "resume": v["raison"]})
    for a in analyses:
        if a["id"] in avis_connus and not a.get("avis"):
            a["avis"] = avis_connus[a["id"]]
    for j in jours:
        jj = [a for a in j["analyses"] if not a.get("deja_commence")]
        j["ticket"] = selection.ticket_du_jour(jj, cfg["bookmakers_jouables"], avis_connus)
        j["pronos"] = {a["id"]: selection.avis_match(a) for a in j["analyses"]}
    if not demo:
        (DATA / "selection.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")

    # le carnet de l'expert : chaque prono noté puis réglé tout seul (scores ESPN, sans crédit)
    if not demo:
        expert.noter(carnet, auj, jours[0]["analyses"], jours[0]["values"], jours[0]["combos"], maintenant,
                     semaine=ticket_semaine, analyses_semaine=analyses)
        expert.noter_ticket(carnet, f"jour:{auj}", "jour", auj, jours[0].get("ticket"), analyses, maintenant)
        # les « rebonds » du jour : suivis à part pour savoir si la méthode rapporte
        for a in jours[0]["analyses"]:
            c = selection.candidat(a)
            if c and c.get("rebond"):
                expert.noter_ticket(carnet, f"rebond:{a['id']}", "rebond", auj,
                                    {"jambes": [{"id": a["id"], "debut": a["debut"], "domicile": a["domicile"], "exterieur": a["exterieur"],
                                                 "court": c["court"], "issue": c["issue"], "proba": c["proba"], "cote_t": c["cote"], "rebond": True}],
                                     "cote": c["cote"], "proba": c["proba"]}, analyses, maintenant)
        autopsie.enrichir(carnet, analyses)
        (DATA / "lecons.json").write_text(json.dumps(lecons, ensure_ascii=False, indent=1), encoding="utf-8")
        (DATA / "carnet.json").write_text(json.dumps(carnet, ensure_ascii=False, indent=1), encoding="utf-8")
    # l'expert apprend de ses résultats : un type de ticket qui perd sur la durée n'est plus conseillé
    en_pause = expert.pauses(carnet)
    for j in jours:
        for c in j["combos"]:
            s = en_pause.get(c.get("style"))
            if s:
                c["conseille"] = False if c.get("conseille") is not None else None
                c["desc"] = f"⛔ En pause : ce type de ticket perd sur la durée ({s['roi'] * 100:+.0f} % sur {s['n']} tickets). " + c["desc"]
        if "jour" in en_pause:
            j["ticket"] = None
    res_carnet = {}
    for p in carnet:
        for j in p["jambes"]:
            if j.get("score") and "-" in j["score"]:
                dd, xx = map(int, j["score"].split("-"))
                res_carnet[j["id"]] = {"res": "1" if dd > xx else "2" if xx > dd else "N", "score": j["score"]}

    infos = {
        "expert": expert.tableau(carnet),
        "lecons": lecons[-8:], "ajust": selection.AJUST,
        "semaine": {"ticket": ticket_semaine, "suivis": sorted(sel["matchs"].values(), key=lambda s: s["debut"])},
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
        "resultats": {**res_carnet, **{h["id"]: {"res": h["res"], "score": h.get("score", "")} for h in historique if h.get("res")},
                      **{j["id"]: {"res": j["res"], "score": j.get("score", "")}
                         for c in combines for j in c["jambes"] if j.get("res") and j.get("id")}},
    }
    site_web.generer(ICI / "site" / "index.html", analyses, values, historique, bilan(historique), infos, combos)
    print("Site généré : site/index.html")


if __name__ == "__main__":
    main()
