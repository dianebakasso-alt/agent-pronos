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

    # mémoire : championnats où l'agent a perdu sur la durée → critères durcis ou pause
    ajust = cfg.get("ajustements", {}).get(match.get("sport_key"), {})
    seuil = (cfg["edge_minimum_pourcent"] + ajust.get("edge_bonus", 0)) / 100
    value = None
    candidats = [i for i in issues
                 if i["edge"] >= seuil and i["cote"] <= cfg["cote_max"]]
    if ajust.get("pause"):
        candidats = []
    if candidats:
        top = max(candidats, key=lambda i: i["edge"])
        ref_ok = cfg["bookmaker_reference"] in par_bk
        value = dict(top,
                     mise=mise_conseillee(top["proba"], top["cote"], cfg),
                     confiance=niveau_confiance(top["edge"], len(par_bk), ref_ok))

    # cotes de chaque bookmaker jouable (utile pour les combinés, qui se jouent chez un seul bookmaker)
    jouables = set(cfg["bookmakers_jouables"])
    code = {dom: "1", NUL: "N", ext: "2"}
    cotes_bk = {cle: {"titre": v["titre"], **{code[k]: c for k, c in v["cotes"].items() if k in code}}
                for cle, v in par_bk.items() if cle in jouables}

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
        "cotes_bk": cotes_bk,
    }


def _meilleur_combine(analyses, cfg, n_max, p_min, edge_min, chance_min=0.0,
                      tri=None, critere=None, n_min=2):
    """Meilleur ticket chez un seul bookmaker.
    tri     : ordre de préférence des matchs (par défaut : valeur x chance)
    critere : ce qu'on maximise entre bookmakers (par défaut : l'avantage)"""
    tri = tri or (lambda o: -o["edge"] * o["proba"])
    critere = critere or (lambda c: c["edge"])
    meilleur = None
    for bk in cfg["bookmakers_jouables"]:
        jambes = []
        for m in analyses:
            cotes = m.get("cotes_bk", {}).get(bk)
            if not cotes:
                continue
            options = []
            for i in m["issues"]:
                c = cotes.get(i["court"])
                if not c or c > cfg["cote_max"] or i["proba"] < p_min:
                    continue
                edge = i["proba"] * c - 1
                if edge > edge_min:
                    options.append({"match": m, "issue": i["issue"], "court": i["court"],
                                    "cote": c, "proba": i["proba"], "edge": edge})
            if options:
                jambes.append(max(options, key=lambda o: o["edge"]))
        # les plus sûres d'abord parmi celles qui ont de la valeur, puis on retire
        # des matchs tant que le ticket a trop peu de chances de passer
        jambes.sort(key=tri)
        jambes = jambes[:n_max]
        while len(jambes) > n_min and _prod(j["proba"] for j in jambes) < chance_min:
            jambes.remove(min(jambes, key=lambda o: o["proba"]))
        if len(jambes) < n_min or _prod(j["proba"] for j in jambes) < chance_min:
            continue
        cote, proba = 1.0, 1.0
        for j in jambes:
            cote *= j["cote"]
            proba *= j["proba"]
        edge = proba * cote - 1
        titre = jambes[0]["match"]["cotes_bk"][bk]["titre"]
        c = {"bookmaker": titre, "jambes": jambes, "cote": cote, "proba": proba, "edge": edge}
        if meilleur is None or critere(c) > critere(meilleur):
            meilleur = c
    return meilleur


def _prod(xs):
    r = 1.0
    for x in xs:
        r *= x
    return r


def combine_du_jour(analyses, cfg):
    """Ticket combiné chez UN seul bookmaker jouable.

    1) Combiné conseillé : chaque match a un avantage chez ce bookmaker, donc le ticket aussi.
    2) Sinon, le combiné le moins coûteux (2 matchs, favoris raisonnables), marqué « non conseillé ».
    """
    c = _meilleur_combine(analyses, cfg, cfg.get("combine_max_matchs", 3), cfg.get("combine_proba_min", 0.40), 0,
                          cfg.get("combine_chance_min", 0.15))
    if c:
        c["conseille"] = True
        return c
    c = _meilleur_combine(analyses, cfg, 2, 0.45, -1)
    if c:
        c["conseille"] = False
    return c


STYLES = {
    "prudent": {"nom": "Prudent", "emoji": "🛡️", "desc": "2 matchs, des favoris : la meilleure chance de passer."},
    "equilibre": {"nom": "Équilibré", "emoji": "⚖️", "desc": "Le meilleur rapport valeur / chance du jour."},
    "gros": {"nom": "Gros gain", "emoji": "🚀", "desc": "3 à 4 matchs : grosse cote, plus risqué."},
}


def combines_experts(analyses, cfg):
    """Trois tickets au choix : prudent, équilibré, gros gain.
    Chacun : un seul bookmaker, chaque match avec un avantage positif ; sinon repli « non conseillé »."""
    def prudent(edge_min):
        return _meilleur_combine(analyses, cfg, 2, 0.48, edge_min, 0.28,
                                 tri=lambda o: -o["proba"], critere=lambda c: (c["proba"], c["edge"]))

    def gros(edge_min):
        return _meilleur_combine(analyses, cfg, 4, 0.30, edge_min, 0.04, n_min=3,
                                 critere=lambda c: (c["edge"] > 0, len(c["jambes"]), c["cote"] * (1 + c["edge"])))

    out = {}
    for style, fn in (("prudent", prudent), ("gros", gros)):
        c = fn(0)
        if c:
            c["conseille"] = True
        else:
            c = fn(-1)
            if c:
                c["conseille"] = False
        out[style] = c
    out["equilibre"] = combine_du_jour(analyses, cfg)

    # pas deux fois le même ticket
    vus, resultat = set(), []
    for style in ("prudent", "equilibre", "gros"):
        c = out[style]
        if not c:
            continue
        cle = (c["bookmaker"], tuple(sorted((j["match"]["id"], j["court"]) for j in c["jambes"])))
        if cle in vus:
            continue
        vus.add(cle)
        c["style"] = style
        c.update({k: v for k, v in STYLES[style].items()})
        resultat.append(c)
    return resultat


# ---------------------------------------------------------------- les buts (sans crédit en plus)
# On retrouve combien de buts le marché attend de chaque équipe (loi de Poisson) à partir
# des probabilités 1-N-2 du marché, puis on en déduit Plus/Moins de buts, Les deux marquent, etc.
from math import exp, factorial


def _poisson(k, lam):
    return exp(-lam) * lam ** k / factorial(k)


def _grille(lh, la, n=10):
    ph = [_poisson(i, lh) for i in range(n)]
    pa = [_poisson(j, la) for j in range(n)]
    g = [[ph[i] * pa[j] for j in range(n)] for i in range(n)]
    # petit correctif de Dixon-Coles : les scores serrés (0-0, 1-1) sont un peu plus fréquents
    rho = -0.06
    g[0][0] *= 1 - lh * la * rho
    g[0][1] *= 1 + lh * rho
    g[1][0] *= 1 + la * rho
    g[1][1] *= 1 - rho
    s = sum(map(sum, g))
    return [[x / s for x in ligne] for ligne in g]


def _probas_1n2(g):
    n = len(g)
    p1 = sum(g[i][j] for i in range(n) for j in range(n) if i > j)
    pn = sum(g[i][i] for i in range(n))
    return p1, pn, 1 - p1 - pn


def buts_attendus(p1, p2):
    """Trouve (buts domicile, buts extérieur) qui reproduisent le mieux les probas du marché."""
    best, err = (1.3, 1.1), 9.0
    pas = 0.4
    for _ in range(6):  # recherche de plus en plus fine
        cx, cy = best
        for i in range(-5, 6):
            for j in range(-5, 6):
                lh, la = cx + i * pas, cy + j * pas
                if not (0.15 <= lh <= 4.5 and 0.15 <= la <= 4.5):
                    continue
                q1, _, q2 = _probas_1n2(_grille(lh, la))
                e = (q1 - p1) ** 2 + (q2 - p2) ** 2
                if e < err:
                    best, err = (lh, la), e
        pas /= 3
    return best


def _cote(p):
    return round(1 / p, 2) if p > 0.01 else None


def analyser_buts(m):
    """Marchés de buts calculés pour un match analysé."""
    pr = {i["court"]: i["proba"] for i in m["issues"]}
    if not {"1", "N", "2"} <= set(pr):
        return None
    lh, la = buts_attendus(pr["1"], pr["2"])
    g = _grille(lh, la)
    n = len(g)
    tot = lambda cond: sum(g[i][j] for i in range(n) for j in range(n) if cond(i, j))
    marches = {
        "plus15": tot(lambda i, j: i + j >= 2), "plus25": tot(lambda i, j: i + j >= 3),
        "plus35": tot(lambda i, j: i + j >= 4), "btts": tot(lambda i, j: i >= 1 and j >= 1),
        "dom_marque": tot(lambda i, j: i >= 1), "ext_marque": tot(lambda i, j: j >= 1),
    }
    scores = sorted(((g[i][j], f"{i}-{j}") for i in range(6) for j in range(6)), reverse=True)[:3]
    return {"lh": lh, "la": la, "total": lh + la, **marches,
            "scores": [(s, p) for p, s in scores]}


LIBELLES_BUTS = {
    "plus15": "Plus de 1,5 but", "moins15": "Moins de 1,5 but",
    "plus25": "Plus de 2,5 buts", "moins25": "Moins de 2,5 buts",
    "plus35": "Plus de 3,5 buts", "moins35": "Moins de 3,5 buts",
    "btts": "Les 2 équipes marquent", "pas_btts": "Les 2 ne marquent pas",
}


def pronos_buts(analyses, n=4):
    """Les pronos de buts les plus nets du jour (proba élevée), avec la cote juste à chercher."""
    choix = []
    for m in analyses:
        b = m.get("buts")
        if not b:
            continue
        options = [("plus25", b["plus25"]), ("moins25", 1 - b["plus25"]), ("btts", b["btts"]),
                   ("pas_btts", 1 - b["btts"]), ("plus15", b["plus15"]), ("moins35", 1 - b["plus35"])]
        # on évite les paris « trop sûrs » à cote ridicule : entre 55 % et 80 %
        options = [(k, p) for k, p in options if 0.55 <= p <= 0.80]
        if not options:
            continue
        # préférence aux marchés les plus parlants (2,5 buts et BTTS) quand ils sont nets
        k, p = max(options, key=lambda o: o[1] + (0.25 if o[0] in ("plus25", "moins25", "btts", "pas_btts") else 0))
        choix.append({"match": m, "marche": k, "libelle": LIBELLES_BUTS[k], "proba": p,
                      "cote_juste": _cote(p), "cote_cible": round(1.05 / p, 2)})
    choix.sort(key=lambda c: -c["proba"])
    vus, res = set(), []
    for c in choix:
        if c["match"]["id"] not in vus:
            vus.add(c["match"]["id"]); res.append(c)
    return res[:n]
