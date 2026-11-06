"""Le carnet de l'expert : chaque prono qu'il donne est noté, puis réglé tout seul.

But : savoir, chiffres à l'appui, si l'expert gagne de l'argent sur la durée.
- Chaque prono = mise fictive de 10 € (même mise partout, pour comparer honnêtement).
- On note : le prono de chaque match du jour, les value bets et tous les tickets d'experts.
- Les scores viennent du tableau public d'ESPN : aucun crédit consommé.
"""
import json
from datetime import datetime, timedelta

import direct
import site_web

MISE = 10.0
CATEGORIES = {
    "match": ("🎯", "Prono de chaque match"),
    "value": ("💎", "Value bets"),
    "prudent": ("🛡️", "Combiné Prudent"),
    "equilibre": ("⚖️", "Combiné Équilibré"),
    "gros": ("🚀", "Combiné Gros gain"),
    "buts": ("⚽", "Combiné Buts"),
    "mixte": ("🔀", "Combiné Mixte"),
    "mixte_gros": ("💥", "Mixte gros gain"),
    "jour": ("📌", "Ticket du jour"),
    "semaine": ("🔭", "Ticket de la semaine"),
    "rebond": ("🔄", "Rebond"),
    "foule": ("🎯", "Contre la foule"),
}
SEUIL_JUGER = 50  # en dessous, c'est trop tôt pour conclure


def _dt(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _jambe(m, court=None, marche=None, pari="", cote=None, proba=None):
    j = {"id": m["id"], "date": m["debut"], "domicile": m["domicile"], "exterieur": m["exterieur"],
         "championnat": site_web.championnat(m.get("sport_key", ""), m.get("championnat", ""))[1],
         "pari": pari, "cote": round(cote, 2) if cote else None, "proba": round(proba, 4) if proba else None}
    if court:
        j["court"] = court
    if marche:
        j["marche"] = marche
    if m.get("espn"):
        j["espn"] = m["espn"]
    return j


def _prono(cle, jour, cat, jambes, cote, proba, estime=False, conseille=None):
    return {"cle": cle, "jour": jour, "cat": cat, "jambes": jambes, "cote": round(cote, 2), "proba": round(proba, 4),
            "estime": estime, "conseille": conseille, "mise": MISE, "statut": "en attente", "gain": 0.0}


def noter(carnet, jour, analyses, values, combos, maintenant, semaine=None, analyses_semaine=None):
    """Ajoute (ou remplace tant que rien n'a commencé) les pronos du jour."""
    nouveaux = []
    for m in analyses:
        if m.get("deja_commence") or not m.get("issues"):
            continue
        i = max(m["issues"], key=lambda x: x["proba"])
        jb = _jambe(m, court=i["court"], pari=i["issue"], cote=i["cote"], proba=i["proba"])
        if m.get("force"):   # pour le duel : la note de force maison contre les bookmakers
            jb["force_p"] = m["force"]["p"]
            jb["marche_p"] = {x["court"]: round(x["proba"], 4) for x in m["issues"]}
        nouveaux.append(_prono(f"match:{m['id']}", jour, "match", [jb], i["cote"], i["proba"]))
    for m in values:
        v = m["value"]
        if m.get("deja_commence"):
            continue
        nouveaux.append(_prono(f"value:{m['id']}", jour, "value",
                               [_jambe(m, court=v["court"], pari=v["issue"], cote=v["cote"], proba=v["proba"])],
                               v["cote"], v["proba"], conseille=(m.get("avis") or {}).get("avis") != "eviter"))
    for c in combos:
        jb = []
        for j in c["jambes"]:
            if j.get("type") == "buts":
                jb.append(_jambe(j["match"], marche=j["marche"], pari=j["issue"], proba=j["proba"]))
            else:
                jb.append(_jambe(j["match"], court=j["court"], pari=j["issue"], cote=j.get("cote"), proba=j["proba"]))
        cote = c["cote_cible"] if c.get("estime") else c["cote"]
        num = f":{c['num']}" if c.get("num", 1) > 1 else ""
        nouveaux.append(_prono(f"{c['style']}:{jour}{num}", jour, c["style"], jb, cote, c["proba"],
                               estime=bool(c.get("estime")), conseille=c.get("conseille")))

    if semaine:
        sem = maintenant.isocalendar()
        jb = []
        for s in semaine["jambes"]:
            m = {"id": s["id"], "debut": s["debut"], "domicile": s["domicile"], "exterieur": s["exterieur"],
                 "sport_key": s.get("sport_key"), "championnat": s.get("championnat", "")}
            esp = next((a.get("espn") for a in analyses_semaine if a["id"] == s["id"]), None) if analyses_semaine else None
            if esp:
                m["espn"] = esp
            jb.append(_jambe(m, court=s["court"], pari=s["issue"], cote=s["cote_t"], proba=s["proba"]))
        nouveaux.append(_prono(f"semaine:{sem[0]}-{sem[1]}", jour, "semaine", jb, semaine["cote"], semaine["proba"],
                               conseille=True))

    par_cle = {p["cle"]: p for p in carnet}
    for n in nouveaux:
        ancien = par_cle.get(n["cle"])
        if ancien:
            fige = ancien["statut"] != "en attente" or any(_dt(j["date"]) <= maintenant for j in ancien["jambes"])
            if fige:
                continue
            carnet.remove(ancien)
        carnet.append(n)
        par_cle[n["cle"]] = n
    # un ticket d'expert qui a disparu avant de commencer (plus proposé) n'est plus suivi
    cles_jour = {n["cle"] for n in nouveaux}
    for p in [p for p in carnet if p["jour"] == jour and p["cle"] not in cles_jour and p["statut"] == "en attente" and p["cat"] != "semaine"]:
        if all(_dt(j["date"]) > maintenant for j in p["jambes"]):
            carnet.remove(p)
    return carnet


# ---------------------------------------------------------------- règlement (ESPN, gratuit)
def _score_espn(ev):
    comp = (ev.get("competitions") or [{}])[0]
    st = (comp.get("status") or ev.get("status") or {}).get("type", {})
    if not st.get("completed"):
        return None
    sc = {}
    for c in comp.get("competitors", []):
        try:
            sc[c.get("homeAway")] = int(float(c.get("score", 0) if not isinstance(c.get("score"), dict) else c["score"].get("value", 0)))
        except (TypeError, ValueError):
            return None
    if "home" not in sc or "away" not in sc:
        return None
    if "postponed" in (st.get("name") or "").lower() or "cancel" in (st.get("name") or "").lower():
        return "annule"
    return sc["home"], sc["away"]


def _gagne(j, d, x):
    if "court" in j:
        res = "1" if d > x else "2" if x > d else "N"
        return res == j["court"]
    t = d + x
    return {
        "plus15": t >= 2, "moins15": t <= 1, "plus25": t >= 3, "moins25": t <= 2,
        "plus35": t >= 4, "moins35": t <= 3, "btts": d >= 1 and x >= 1, "pas_btts": not (d >= 1 and x >= 1),
    }.get(j.get("marche"))


def regler(carnet, maintenant):
    a_regler = [j for p in carnet if p["statut"] == "en attente" for j in p["jambes"]
                if "ok" not in j and _dt(j["date"]) < maintenant - timedelta(hours=2, minutes=15)]
    besoins = {}
    for j in a_regler:
        if j.get("espn"):
            jour = _dt(j["date"]).strftime("%Y%m%d")
            besoins.setdefault((j["espn"]["ligue"], jour), []).append(j)
    for (ligue, jour), jambes in besoins.items():
        evs = {}
        for d in {jour, (datetime.strptime(jour, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")}:
            try:
                for ev in direct._get(f"{direct.BASE}/{ligue}/scoreboard?dates={d}").get("events", []):
                    evs[str(ev["id"])] = ev
            except Exception as e:
                print(f"  ! carnet {ligue} {d}: {e}")
        for j in jambes:
            ev = evs.get(str(j["espn"]["id"]))
            sc = _score_espn(ev) if ev else None
            if sc == "annule":
                j["ok"], j["score"] = None, "annulé"
            elif sc:
                j["score"] = f"{sc[0]}-{sc[1]}"
                j["ok"] = _gagne(j, *sc)
    for p in carnet:
        if p["statut"] != "en attente":
            continue
        jb = p["jambes"]
        if any(j.get("ok") is False for j in jb):
            p["statut"], p["gain"] = "perdu", -p["mise"]
        elif all("ok" in j for j in jb):
            valides = [j for j in jb if j["ok"]]
            if not valides:
                p["statut"], p["gain"] = "annulé", 0.0
            else:
                p["statut"], p["gain"] = "gagné", round(p["mise"] * (p["cote"] - 1), 2)
        elif all(_dt(j["date"]) < maintenant - timedelta(days=4) for j in jb if "ok" not in j):
            p["statut"], p["gain"] = "annulé", 0.0   # score introuvable : on ne le compte pas
    return carnet


# ---------------------------------------------------------------- tableau de bord
def _seg(ps):
    r = [p for p in ps if p["statut"] in ("gagné", "perdu")]
    mises = sum(p["mise"] for p in r)
    gains = sum(p["gain"] for p in r)
    return {"n": len(r), "gagnes": sum(p["statut"] == "gagné" for p in r),
            "attendus": round(sum(p["proba"] for p in r), 1),
            "benefice": round(gains, 2), "mises": mises, "roi": gains / mises if mises else None}


def duel(carnet):
    """Note de force maison contre bookmakers, sur les matchs réellement joués."""
    d = {"n": 0, "brier_force": 0.0, "brier_bk": 0.0, "desaccords": 0, "force_raison": 0, "bk_raison": 0, "aucun": 0, "exemples": []}
    vus = set()
    for p in carnet:
        if p["cat"] != "match" or p["statut"] not in ("gagné", "perdu"):
            continue
        j = p["jambes"][0]
        if not j.get("force_p") or not j.get("marche_p") or not j.get("score") or j["id"] in vus:
            continue
        vus.add(j["id"])
        h, a = map(int, j["score"].split("-"))
        res = "1" if h > a else "2" if a > h else "N"
        fp, mp = j["force_p"], j["marche_p"]
        d["n"] += 1
        d["brier_force"] += sum((fp.get(k, 0) - (k == res)) ** 2 for k in "1N2")
        d["brier_bk"] += sum((mp.get(k, 0) - (k == res)) ** 2 for k in "1N2")
        ff, fb = max(fp, key=fp.get), max(mp, key=mp.get)
        if ff != fb:
            d["desaccords"] += 1
            qui = "force_raison" if res == ff else "bk_raison" if res == fb else "aucun"
            d[qui] += 1
            d["exemples"].append({"match": f"{j['domicile']} – {j['exterieur']}", "score": j["score"], "jour": p["jour"],
                                  "force": ff, "bk": fb, "gagnant": qui})
    if d["n"]:
        d["brier_force"] = round(d["brier_force"] / d["n"], 4)
        d["brier_bk"] = round(d["brier_bk"] / d["n"], 4)
    d["exemples"] = sorted(d["exemples"], key=lambda x: x["jour"])[-6:][::-1]
    return d


def tableau(carnet):
    regles = sorted([p for p in carnet if p["statut"] in ("gagné", "perdu")],
                    key=lambda p: max(j["date"] for j in p["jambes"]))
    courbe, cumul = [], 0.0
    for p in regles:
        cumul += p["gain"]
        courbe.append(round(cumul, 2))
    par_cat = {k: _seg([p for p in carnet if p["cat"] == k]) for k in CATEGORIES}
    sur7 = [p for p in regles if p["jour"] >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")]
    return {
        "total": _seg(carnet), "sept_jours": _seg(sur7), "par_cat": par_cat, "courbe": courbe[-200:],
        "en_attente": sum(p["statut"] == "en attente" for p in carnet),
        "duel": duel(carnet),
        "derniers": [p for p in reversed(regles)][:12],
    }


def charger(chemin):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return []


def noter_ticket(carnet, cle, cat, jour, tk, analyses, maintenant):
    """Note un ticket (du jour) dans le carnet ; remplacé tant qu'aucun match n'a commencé."""
    if not tk:
        return
    par_id = {a["id"]: a for a in analyses}
    jb = []
    for s in tk["jambes"]:
        m = dict(par_id.get(s["id"]) or {"id": s["id"], "debut": s["debut"], "domicile": s["domicile"],
                                          "exterieur": s["exterieur"], "sport_key": s.get("sport_key"), "championnat": s.get("championnat", "")})
        jb.append(_jambe(m, court=s["court"], pari=s["issue"], cote=s["cote_t"], proba=s["proba"]))
        if s.get("rebond"):
            jb[-1]["rebond"] = True
    nouveau = _prono(cle, jour, cat, jb, tk["cote"], tk["proba"], conseille=True)
    ancien = next((p for p in carnet if p["cle"] == cle), None)
    if ancien:
        if ancien["statut"] != "en attente" or any(_dt(j["date"]) <= maintenant for j in ancien["jambes"]):
            return
        carnet.remove(ancien)
    carnet.append(nouveau)


MIN_PAUSE, ROI_PAUSE = 15, 0.0


def pauses(carnet):
    """Les types de pronos qui perdent : l'expert arrête de les conseiller.
    Règle : à partir de 15 tickets réglés, tout type dont le rendement est négatif est mis en pause
    (dès 3 tickets s'il n'en a gagné aucun). Ils restent notés en fictif : un type qui repasse
    en positif est de nouveau conseillé tout seul."""
    out = {}
    for k in CATEGORIES:
        s = _seg([p for p in carnet if p["cat"] == k])
        if s["roi"] is None:
            continue
        if (s["n"] >= MIN_PAUSE and s["roi"] < ROI_PAUSE) or (s["n"] >= 3 and s["gagnes"] == 0):
            out[k] = s
    return out


def zones_faibles(carnet, n_min=25, marge=0.03):
    """Tranches de probabilité (par 5 %) où les favoris gagnent nettement moins que prévu.
    Ex. les favoris « 55-60 % » passent 51 % du temps : l'expert les évite dans ses combinés."""
    g = {}
    for p in carnet:
        if p["cat"] != "match" or p["statut"] not in ("gagné", "perdu"):
            continue
        z = int(p["proba"] * 20) / 20
        s = g.setdefault(z, [0, 0, 0.0])
        s[0] += 1
        s[1] += p["statut"] == "gagné"
        s[2] += p["proba"]
    return {round(z, 2) for z, (n, ok, sp) in g.items() if n >= n_min and ok / n < sp / n - marge}


def calib_buts(carnet, prior=5.0):
    """Paris de buts : réussite réelle / réussite annoncée, par marché (lissé vers 1).
    Ex. « moins de 2,5 buts » annoncé à 66 % mais passé 45 % du temps → ses probabilités sont baissées."""
    vus = {}
    for p in carnet:
        for j in p["jambes"]:
            if j.get("marche") and j.get("ok") is not None and j.get("proba"):
                vus[(j["id"], j["marche"])] = j
    g = {}
    for (_, k), j in vus.items():
        s = g.setdefault(k, [0, 0.0])
        s[0] += 1 if j["ok"] else 0
        s[1] += j["proba"]
    return {k: round(min(1.05, (ok + prior) / (sp + prior)), 3) for k, (ok, sp) in g.items()}


def specialites(carnet, n_min=15):
    """Bonus/malus par championnat selon les pronos de match réellement réglés."""
    g = {}
    for p in carnet:
        if p["cat"] != "match" or p["statut"] not in ("gagné", "perdu"):
            continue
        g.setdefault(p["jambes"][0].get("championnat"), []).append(p)
    out, detail = {}, {}
    for ch, ps in g.items():
        s = _seg(ps)
        detail[ch] = s
        if s["n"] >= n_min and s["roi"] is not None:
            if s["roi"] < -0.08:
                out[ch] = -0.06
            elif s["roi"] > 0.05:
                out[ch] = 0.02
    return out, detail
