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
BAISSE_MAX = 0.06
AJUST = {}                      # rempli par l'agent : ce que l'expert a appris (autopsie.ajustements)
SPECIALITE = {}                 # rempli par l'agent : {championnat: bonus/malus} selon ses résultats réels
COTE_MIN_TICKET = 1.40          # les petites cotes perdent sur la durée : jamais dans un ticket
EXCLUS_TICKET = {"petite_cote", "fatigue", "champ_faible"}


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
        rebond = False
        if f is False:
            # mauvaise passe… mais le marché la donne encore nettement favorite : c'est un « rebond » possible
            if i["proba"] >= 0.58 and i["edge"] >= -0.03:
                rebond, f = True, None
            else:
                continue
        note = i["proba"] + 1.5 * i["edge"] + (0.05 if f else 0) + (0.03 if m.get("value") else 0) \
            + min(m.get("nb_bookmakers", 0), 10) * 0.003
        # ce que l'expert a appris de ses résultats passés (types de paris qui ratent plus que prévu)
        traits = (["exterieur"] if i["court"] == "2" else []) + (["petite_cote"] if i["cote"] < 1.40 else []) \
            + (["favori_net"] if i["proba"] >= 0.65 else []) + (["rebond"] if rebond else []) \
            + (["doute_ia"] if (m.get("avis") or {}).get("avis") == "prudence" else [])
        note += sum(AJUST.get(tr, {}).get("ajust", 0) for tr in traits)
        # spécialisation : les championnats où l'expert gagne (ou perd) vraiment
        sp = SPECIALITE.get(m.get("champ_nom"), 0)
        if sp:
            note += sp
            if sp < 0:
                traits.append("champ_faible")
        # fatigue (données gratuites ESPN) : match européen 3 jours avant ou après
        fat = m.get("fatigue") or {}
        adv = "2" if i["court"] == "1" else "1"
        if fat.get(i["court"]):
            note -= 0.05
            traits.append("fatigue")
        if fat.get(adv):
            note += 0.02
            traits.append("adversaire_fatigue")
        if not best or note > best["note"]:
            best = {"court": i["court"], "issue": i["issue"], "proba": i["proba"], "cote": i["cote"],
                    "bk": i["bookmaker"], "edge": i["edge"], "forme": f, "note": round(note, 4),
                    "rebond": rebond, "traits": traits}
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
            if c and not c.get("rebond") and not EXCLUS_TICKET & set(c["traits"]):
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
    # au plus UN match jugé « prudence » par l'IA : un doute, passe ; deux doutes, c'est trop
    jambes, doutes = [], 0
    for s in ok:
        if (s.get("avis") or {}).get("avis") == "prudence":
            if doutes:
                continue
            doutes += 1
        jambes.append(s)
    jambes = jambes[:3]          # 3 matchs maximum : chaque match en plus multiplie les chances de tout perdre
    prod = lambda xs: __import__("math").prod(xs)
    while len(jambes) > 2 and prod(s["proba"] for s in jambes) < 0.25:
        jambes.pop()
    if len(jambes) >= 2 and prod(s["proba"] for s in jambes) < 0.20:
        return None             # même à 2 matchs, trop peu de chances : pas de ticket
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


# ---------------------------------------------------------------- le jour : ticket du jour et avis par match
def ticket_du_jour(analyses, bookmakers, avis_connus=None):
    """2 à 3 matchs du jour, les plus solides, avec au moins 25 % de chances de passer."""
    sel = {"matchs": {}}
    cands = [(c["note"], m, c) for m in analyses
             if (c := candidat(m)) and not c.get("rebond") and not EXCLUS_TICKET & set(c["traits"])]
    for _, m, c in sorted(cands, key=lambda x: -x[0])[:5]:
        s = {"id": m["id"], "debut": m["debut"], "domicile": m["domicile"], "exterieur": m["exterieur"],
             "championnat": m["championnat"], "sport_key": m.get("sport_key"), "court": c["court"], "issue": c["issue"],
             "proba": c["proba"], "cote": c["cote"], "bk": c["bk"], "note": c["note"], "statut": "suivi"}
        a = (avis_connus or {}).get(m["id"])
        if a:
            s["avis"] = a
            if a.get("avis") == "eviter":
                continue
        sel["matchs"][m["id"]] = s
    import math
    ok = sorted(sel["matchs"].values(), key=lambda s: -s["note"])[:3]
    while len(ok) > 2 and math.prod(s["proba"] for s in ok) < 0.25:
        ok.pop()
    sel["matchs"] = {s["id"]: s for s in ok}
    return ticket(sel, analyses, bookmakers)


NIVEAUX = {"forte": "Confiance forte", "bonne": "Bonne confiance", "moyenne": "Confiance moyenne", "ouvert": "Match ouvert"}


def avis_match(m):
    """Le prono de l'expert pour un match. Le niveau dépend d'abord des vraies chances :
    forte ≥ 65 %, bonne ≥ 55 %, moyenne ≥ 45 %, sinon match ouvert ;
    on descend d'un cran si la forme contredit le pari ou si l'IA a un doute."""
    if not m.get("issues"):
        return None
    fav = max(m["issues"], key=lambda i: i["proba"])
    a = (m.get("avis") or {}).get("avis")
    v = m.get("value")
    if v and a != "eviter":
        court, issue, proba, cote = v["court"], v["issue"], v["proba"], v["cote"]
    else:
        c = candidat(m) or {}
        src = c if c else fav
        court, issue, proba, cote = src["court"], src["issue"], src["proba"], src["cote"]
    ordre = ["ouvert", "moyenne", "bonne", "forte"]
    k = 3 if proba >= 0.65 else 2 if proba >= 0.55 else 1 if proba >= 0.45 else 0
    if court != "N" and _forme_ok(m, court) is False:
        k -= 1
    if a == "prudence":
        k -= 1
    if a == "eviter":
        k = 0
    niveau = ordre[max(0, k)]
    if v and a != "eviter":
        niveau = ordre[max(1, k)]      # un value bet reste jouable, même s'il n'est pas sûr
    piege = fav["proba"] >= 0.5 and _forme_ok(m, fav["court"]) is False
    rb = bool((candidat(m) or {}).get("rebond")) and not (v and a != "eviter")
    return {"court": court, "issue": issue, "proba": proba, "cote": cote, "niveau": niveau, "piege": piege and not rb,
            "value": bool(v and a != "eviter"), "doute": a == "prudence", "rebond": rb}


# ---------------------------------------------------------------- contre la foule
def contre_la_foule(m):
    """L'outsider (ou le nul) que les bookmakers français paient plus que son vrai risque :
    le public se jette sur le favori, la cote d'en face devient trop belle."""
    if m.get("deja_commence") or m.get("ecart_refs", 0) > 0.03 or not m.get("issues"):
        return None
    fav = max(m["issues"], key=lambda i: i["proba"])
    best = None
    for i in m["issues"]:
        if i is fav or not (0.25 <= i["proba"] <= 0.48) or i["edge"] < 0.02 or i["cote"] > 4.5:
            continue
        if (m.get("fatigue") or {}).get(i["court"]):
            continue
        if not best or i["edge"] > best["edge"]:
            best = {"court": i["court"], "issue": i["issue"], "proba": i["proba"], "cote": i["cote"],
                    "bk": i["bookmaker"], "edge": i["edge"]}
    return best
