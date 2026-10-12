"""La sélection de la semaine : les matchs où l'expert a le plus confiance, suivis de près jusqu'au jour J.

Chaque matin :
1. on note tous les matchs des 7 prochains jours (marché, accord des références, forme, valeur) ;
2. on garde les meilleurs (6 max) — un match déjà suivi reste suivi tant que rien ne se dégrade ;
3. l'IA refait une analyse approfondie de chacun, chaque jour, jusqu'au coup d'envoi ;
4. un mauvais signal (avis « à éviter », chances en forte baisse) retire le match ;
5. avec les plus solides, on compose le ticket de la semaine.
"""
import json
from datetime import datetime

NB_SUIVIS = 6
P_MIN, P_MAX = 0.45, 0.82       # ni loterie, ni cote ridicule
EDGE_MIN = -0.06                # la cote ne doit pas être trop rabotée par le bookmaker
BAISSE_MAX = 0.06               # si les chances baissent de plus de 6 points : retiré


def _dt(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _forme_ok(m, court):
    """True / False / None : la forme récente va-t-elle dans le sens du pari ?"""
    st = m.get("stats")
    if not st or court == "N":
        return None
    moi, lui = (st["domicile"], st["exterieur"]) if court == "1" else (st["exterieur"], st["domicile"])
    if not moi["forme"] or not lui["forme"]:
        return None
    if moi["points"] >= lui["points"] + 2:
        return True
    if moi["points"] + 3 <= lui["points"] or moi["forme"].count("V") == 0:
        return False
    return None


def candidat(m):
    """Le meilleur pari de confiance d'un match, avec sa note — ou None."""
    if m.get("deja_commence") or m.get("ecart_refs", 0) > 0.04:
        return None
    best = None
    for i in m["issues"]:
        if i["court"] == "N" or not (P_MIN <= i["proba"] <= P_MAX) or i["edge"] < EDGE_MIN:
            continue
        f = _forme_ok(m, i["court"])
        if f is False:
            continue
        note = i["proba"] + 1.5 * i["edge"] + (0.05 if f else 0) + (0.03 if m.get("value") else 0) \
            + min(m.get("nb_bookmakers", 0), 10) * 0.003
        if not best or note > best["note"]:
            best = {"court": i["court"], "issue": i["issue"], "proba": i["proba"], "cote": i["cote"],
                    "bk": i["bookmaker"], "edge": i["edge"], "forme": f, "note": round(note, 4)}
    return best


def mettre_a_jour(sel, analyses, maintenant):
    """sel = {"matchs": {id: suivi}} — renvoie la liste des matchs à analyser en profondeur."""
    suivis = sel.setdefault("matchs", {})
    par_id = {m["id"]: m for m in analyses}
    # 1) les matchs passés quittent la sélection
    for mid in [k for k, s in suivis.items() if _dt(s["debut"]) <= maintenant]:
        del suivis[mid]
    # 2) on revérifie ceux qui sont suivis
    for mid, s in suivis.items():
        if s["statut"] != "suivi":
            continue
        m = par_id.get(mid)
        if not m:
            continue
        i = next((x for x in m["issues"] if x["court"] == s["court"]), None)
        if i:
            s["proba"], s["cote"], s["bk"] = i["proba"], i["cote"], i["bookmaker"]
            if s["proba_depart"] - i["proba"] > BAISSE_MAX:
                s["statut"], s["raison"] = "retiré", f"Ses chances ont chuté de {(s['proba_depart'] - i['proba']) * 100:.0f} points depuis sa sélection."
            elif m.get("ecart_refs", 0) > 0.04:
                s["statut"], s["raison"] = "retiré", "Les bookmakers de référence ne sont plus d'accord sur ce match."
    # 3) on complète avec les meilleurs nouveaux candidats
    actifs = [s for s in suivis.values() if s["statut"] == "suivi"]
    places = NB_SUIVIS - len(actifs)
    if places > 0:
        cands = []
        for m in analyses:
            if m["id"] in suivis:
                continue
            c = candidat(m)
            if c:
                cands.append((c["note"], m, c))
        for _, m, c in sorted(cands, key=lambda x: -x[0])[:places]:
            suivis[m["id"]] = {
                "id": m["id"], "debut": m["debut"], "domicile": m["domicile"], "exterieur": m["exterieur"],
                "championnat": m["championnat"], "sport_key": m.get("sport_key"),
                "court": c["court"], "issue": c["issue"], "proba": c["proba"], "proba_depart": c["proba"],
                "cote": c["cote"], "bk": c["bk"], "note": c["note"], "forme": c["forme"],
                "ajoute": maintenant.strftime("%Y-%m-%d"), "statut": "suivi", "analyses": [],
            }
    return [par_id[k] for k, s in suivis.items() if s["statut"] == "suivi" and k in par_id]


def noter_avis(sel, mid, avis, maintenant):
    s = sel["matchs"].get(mid)
    if not s or not avis:
        return
    s["analyses"] = (s.get("analyses") or [])[-4:] + [{"jour": maintenant.strftime("%Y-%m-%d"),
                                                      "avis": avis.get("avis"), "resume": avis.get("resume", "")}]
    s["avis"] = avis
    if avis.get("avis") == "eviter":
        s["statut"], s["raison"] = "retiré", "L'analyse approfondie l'a écarté : " + (avis.get("resume") or "info défavorable.")


def ticket(sel, analyses, bookmakers):
    """Le ticket de la semaine : 2 à 4 matchs suivis, les plus solides, chez un seul bookmaker si possible."""
    par_id = {m["id"]: m for m in analyses}
    ok = [s for s in sel.get("matchs", {}).values() if s["statut"] == "suivi" and s["id"] in par_id
          and (s.get("avis") or {}).get("avis") != "eviter"]
    # confirmés par l'IA d'abord, puis par note
    ok.sort(key=lambda s: (-((s.get("avis") or {}).get("avis") == "confirme"), -s["note"]))
    jambes = ok[:4]
    prod = lambda xs: __import__("math").prod(xs)
    while len(jambes) > 2 and prod(s["proba"] for s in jambes) < 0.15:
        jambes.pop()
    if len(jambes) < 2:
        return None
    meilleur = None
    for bk in bookmakers:
        cotes = [par_id[s["id"]].get("cotes_bk", {}).get(bk, {}).get(s["court"]) for s in jambes]
        if all(cotes):
            c = prod(cotes)
            if not meilleur or c > meilleur[1]:
                meilleur = (par_id[jambes[0]["id"]]["cotes_bk"][bk]["titre"], c, cotes)
    if meilleur:
        bk, cote, cotes = meilleur
    else:
        bk, cotes = "plusieurs bookmakers", [s["cote"] for s in jambes]
        cote = prod(cotes)
    proba = prod(s["proba"] for s in jambes)
    return {"jambes": [dict(s, cote_t=c) for s, c in zip(jambes, cotes)], "cote": cote, "proba": proba,
            "bookmaker": bk, "edge": proba * cote - 1}


def charger(chemin):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return {"matchs": {}}
