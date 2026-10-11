"""Le cerveau : probabilités du marché, meilleures cotes, value bets et mises.

Principe :
  1. On enlève la marge du bookmaker de référence (Pinnacle, le plus « juste »)
     pour obtenir la vraie probabilité estimée par le marché.
     S'il n'est pas là, on fait la moyenne de tous les bookmakers.
  2. On cherche la meilleure cote chez les bookmakers où tu peux jouer.
  3. Si (meilleure cote x vraie probabilité) > 1, le pari a de la valeur.
"""

NUL = "Nul"


def probas_sans_marge(cotes):
    """{issue: cote} -> {issue: probabilité}, marge du bookmaker retirée."""
    brutes = {k: 1.0 / c for k, c in cotes.items() if c and c > 1.0}
    total = sum(brutes.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in brutes.items()}


def cotes_1n2(match):
    """Extrait {bookmaker: {issue: cote}} pour le marché 1N2 d'un match."""
    resultat = {}
    for bk in match.get("bookmakers", []):
        for marche in bk.get("markets", []):
            if marche.get("key") != "h2h":
                continue
            cotes = {}
            for o in marche.get("outcomes", []):
                nom = NUL if o["name"] == "Draw" else o["name"]
                cotes[nom] = float(o["price"])
            if len(cotes) == 3:  # 1, N et 2 obligatoires
                resultat[bk["key"]] = {"titre": bk.get("title", bk["key"]), "cotes": cotes}
    return resultat


def probas_marche(par_bk, reference):
    """Vraie probabilité selon le marché + source utilisée."""
    if reference in par_bk:
        return probas_sans_marge(par_bk[reference]["cotes"]), par_bk[reference]["titre"]
    toutes = [probas_sans_marge(v["cotes"]) for v in par_bk.values()]
    toutes = [p for p in toutes if p]
    if not toutes:
        return {}, None
    issues = toutes[0].keys()
    moyenne = {i: sum(p.get(i, 0) for p in toutes) / len(toutes) for i in issues}
    total = sum(moyenne.values())
    return {i: v / total for i, v in moyenne.items()}, f"consensus de {len(toutes)} bookmakers"


def meilleures_cotes(par_bk, jouables):
    """Pour chaque issue : meilleure cote chez un bookmaker jouable."""
    meilleures = {}
    for cle, v in par_bk.items():
        if jouables and cle not in jouables:
            continue
        for issue, cote in v["cotes"].items():
            if issue not in meilleures or cote > meilleures[issue]["cote"]:
                meilleures[issue] = {"cote": cote, "bookmaker": v["titre"], "cle": cle}
    return meilleures


def mise_conseillee(proba, cote, cfg):
    """Critère de Kelly fractionné, plafonné à X % de la bankroll."""
    edge = proba * cote - 1
    if edge <= 0:
        return 0.0
    kelly = edge / (cote - 1)
    pourcent = min(kelly * cfg["fraction_kelly"], cfg["mise_max_pourcent"] / 100)
    mise = cfg["bankroll_euros"] * pourcent
    return max(0.5, round(mise * 2) / 2)  # arrondi à 0,50 €


def niveau_confiance(edge, nb_bk, source_ref):
    score = 0
    score += 2 if edge >= 0.06 else 1 if edge >= 0.04 else 0
    score += 1 if nb_bk >= 8 else 0
    score += 1 if source_ref else 0
    return ["Faible", "Moyenne", "Bonne", "Bonne", "Forte"][score]


def analyser_match(match, cfg):
    """Analyse complète d'un match. Renvoie None si pas assez de données."""
    par_bk = cotes_1n2(match)
    if len(par_bk) < cfg["bookmakers_minimum"]:
        return None

    probas, source = probas_marche(par_bk, cfg["bookmaker_reference"])
    if not probas:
        return None
    best = meilleures_cotes(par_bk, set(cfg["bookmakers_jouables"]))
    if not best:
        return None

    dom, ext = match["home_team"], match["away_team"]
    libelles = {dom: f"Victoire {dom}", NUL: "Match nul", ext: f"Victoire {ext}"}

    issues = []
    for cle in (dom, NUL, ext):
        if cle not in probas or cle not in best:
            continue
        p, c = probas[cle], best[cle]["cote"]
        edge = p * c - 1
        issues.append({
            "issue": libelles[cle],
            "court": "1" if cle == dom else "N" if cle == NUL else "2",
            "proba": p,
            "cote": c,
            "cote_juste": 1 / p,
            "bookmaker": best[cle]["bookmaker"],
            "edge": edge,
        })

    value = None
    candidats = [i for i in issues
                 if i["edge"] >= cfg["edge_minimum_pourcent"] / 100 and i["cote"] <= cfg["cote_max"]]
    if candidats:
        top = max(candidats, key=lambda i: i["edge"])
        ref_ok = cfg["bookmaker_reference"] in par_bk
        value = dict(top,
                     mise=mise_conseillee(top["proba"], top["cote"], cfg),
                     confiance=niveau_confiance(top["edge"], len(par_bk), ref_ok))

    favori = max(issues, key=lambda i: i["proba"]) if issues else None
    return {
        "id": match["id"],
        "championnat": match.get("sport_title", match.get("sport_key")),
        "sport_key": match.get("sport_key"),
        "debut": match["commence_time"],
        "domicile": dom,
        "exterieur": ext,
        "nb_bookmakers": len(par_bk),
        "source_proba": source,
        "issues": issues,
        "favori": favori,
        "value": value,
    }
