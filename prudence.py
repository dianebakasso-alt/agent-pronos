"""IA prudence : le pari « double chance » (match nul ou une équipe) noté sur 10.

Principe :
  1. Pour chaque match, on additionne la vraie probabilité (marge retirée) de la victoire
     d'une équipe et du nul : « Nul ou Rennes », « Nul ou Lille »… On garde le côté le plus sûr.
  2. La note sur 10 = cette probabilité (75 % → 7,5/10), retouchée par ce que l'agent sait déjà :
       - l'IA a lu l'actu et dit d'éviter le match       → -1,5
       - l'IA voit l'autre équipe gagner                 → -1
       - alerte « match piège » sur l'équipe choisie      → -0,5
       - l'équipe choisie joue en Europe à 3 jours        → -0,3
       - l'IA confirme l'équipe choisie                   → +0,3
  3. Sous la note limite (`prudence_note_min`, 7 par défaut), le match est marqué « trop risqué ».
     Si l'IA dit d'éviter le match, il est aussi marqué « trop risqué », quelle que soit sa note.
  4. La cote : la plupart des bookmakers proposent la double chance. L'agent n'a que les cotes 1N2,
     il donne donc la cote juste et la cote « maison » obtenue en partageant la mise entre
     les deux issues chez le même bookmaker (même résultat qu'une double chance).
"""

NOTE_MIN = 7.0


def _cote_maison(cotes_bk, a, b):
    """Meilleure cote double chance « faite maison » (mise partagée entre a et b) chez un seul bookmaker."""
    best = None
    for v in (cotes_bk or {}).values():
        ca, cb = v.get(a), v.get(b)
        if not ca or not cb or ca <= 1 or cb <= 1:
            continue
        c = 1 / (1 / ca + 1 / cb)
        if not best or c > best["cote"]:
            best = {"cote": c, "bookmaker": v["titre"],
                    "part_a": (1 / ca) / (1 / ca + 1 / cb)}   # part de la mise sur l'issue a
    return best


def analyser(m, note_min=NOTE_MIN):
    """Le pari prudent d'un match, ou None si les probabilités manquent."""
    p = {i["court"]: i["proba"] for i in m.get("issues", [])}
    if not all(k in p for k in ("1", "N", "2")):
        return None
    cote_f = (m.get("cotes_bk") or {})
    options = []
    for equipe, nom in (("1", m["domicile"]), ("2", m["exterieur"])):
        options.append({"court": "1N" if equipe == "1" else "N2", "equipe": equipe, "nom": nom,
                        "proba": p[equipe] + p["N"]})
    choix = max(options, key=lambda o: o["proba"])
    autre = min(options, key=lambda o: o["proba"])

    note = choix["proba"] * 10
    raisons = []
    v = m.get("verdict_ia") or {}
    if v.get("verdict") == "eviter":
        note -= 1.5
        raisons.append("l'IA a lu l'actu et dit d'éviter ce match")
    elif v.get("pari") in ("1", "2") and v["pari"] != choix["equipe"]:
        note -= 1.0
        raisons.append("l'IA voit plutôt l'autre équipe gagner")
    elif v.get("pari") == choix["equipe"] and v.get("verdict") == "jouer":
        note += 0.3
        raisons.append("l'IA confirme")
    if (m.get("pieges") or {}).get(choix["equipe"]):
        note -= 0.5
        raisons.append("alerte match piège : " + "; ".join(m["pieges"][choix["equipe"]])[:120])
    if (m.get("fatigue") or {}).get(choix["equipe"]):
        note -= 0.3
        raisons.append(m["fatigue"][choix["equipe"]])
    if choix["proba"] - autre["proba"] < 0.04:
        raisons.append("les deux côtés se valent : match très ouvert")
    note = max(0.0, min(10.0, round(note, 1)))

    maison = _cote_maison(cote_f, choix["equipe"], "N")
    return {
        "id": m["id"], "debut": m["debut"], "domicile": m["domicile"], "exterieur": m["exterieur"],
        "sport_key": m.get("sport_key"), "championnat": m.get("championnat"),
        "court": choix["court"], "equipe": choix["equipe"],
        "issue": f"Nul ou {choix['nom']}",
        "proba": choix["proba"], "proba_autre": autre["proba"], "issue_autre": f"Nul ou {autre['nom']}",
        "note": note, "jouable": note >= note_min and v.get("verdict") != "eviter",
        "cote_juste": 1 / choix["proba"],
        "cote": maison["cote"] if maison else None,
        "bookmaker": maison["bookmaker"] if maison else None,
        "part_equipe": maison["part_a"] if maison else None,
        "raisons": raisons,
    }


def du_jour(analyses, cfg):
    """Tous les matchs encore à jouer, du plus sûr au moins sûr."""
    note_min = float(cfg.get("prudence_note_min", NOTE_MIN))
    res = [r for r in (analyser(m, note_min) for m in analyses if not m.get("deja_commence")) if r]
    return sorted(res, key=lambda r: (-r["note"], r["debut"]))
