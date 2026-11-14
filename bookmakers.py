"""L'expert apprend des bookmakers.

1. Consensus pondéré : la probabilité d'un match est la moyenne des bookmakers (marge retirée),
   mais tous ne comptent pas pareil. Au départ, les « pointus » (Pinnacle, Betfair Exchange)
   comptent plus. Ensuite, chaque bookmaker gagne ou perd du poids selon sa justesse réelle.
2. Le désaccord comme signal : si les bookmakers sont d'accord, le match est lisible.
   S'ils divergent beaucoup, le match est flou : l'expert s'en méfie (note prudence baissée,
   pas dans les combinés). Si un seul bookmaker paie nettement plus que les autres, c'est
   peut-être un bon prix : c'est signalé.
3. Mémoire par bookmaker : le carnet garde, pour chaque match, la probabilité de chaque bookmaker.
   Une fois le match joué, on mesure qui s'est le moins trompé (score de Brier : plus petit = meilleur).
   Plus il y a de matchs, plus ces mesures pèsent dans le consensus.
"""
import json
import math

# poids de départ (avant d'avoir assez de matchs pour juger)
POIDS_DEPART = {"pinnacle": 3.0, "betfair_ex_eu": 2.0}
N_CONFIANCE = 100       # matchs à partir desquels la mesure pèse autant que le poids de départ
ECHELLE = 0.004         # un Brier plus petit de 0,004 que la moyenne = poids multiplié par e (≈ 2,7)
DESACCORD_FORT = 0.07   # écart de probabilité entre bookmakers (sur une même issue) jugé « flou »
PRIX_HORS_NORME = 1.05  # un bookmaker jouable qui paie 5 % de plus que la médiane des autres

FIABILITE = {}          # {bookmaker: {"n", "brier", "poids", ...}} chargé à chaque passage


def probas_sans_marge(cotes):
    brutes = {k: 1.0 / c for k, c in cotes.items() if c and c > 1.0}
    t = sum(brutes.values())
    return {k: v / t for k, v in brutes.items()} if t > 0 else {}


def poids(bk):
    """Poids d'un bookmaker : poids de départ, puis de plus en plus sa justesse mesurée."""
    depart = POIDS_DEPART.get(bk, 1.0)
    f = FIABILITE.get(bk)
    if not f or not f.get("n"):
        return depart
    a = f["n"] / (f["n"] + N_CONFIANCE)
    return (1 - a) * depart + a * f["poids_mesure"]


def consensus(par_bk):
    """{issue: proba} pondérée + texte de la source + désaccord (écart max entre bookmakers)."""
    probas = {k: probas_sans_marge(v["cotes"]) for k, v in par_bk.items()}
    probas = {k: p for k, p in probas.items() if len(p) == 3}
    if not probas:
        return {}, None, 0.0
    issues = next(iter(probas.values())).keys()
    tot_w = sum(poids(k) for k in probas)
    mix = {i: sum(p.get(i, 0) * poids(k) for k, p in probas.items()) / tot_w for i in issues}
    s = sum(mix.values())
    mix = {i: v / s for i, v in mix.items()}
    ecart = max((max(p[i] for p in probas.values()) - min(p[i] for p in probas.values())) for i in issues) \
        if len(probas) >= 2 else 0.0
    top = sorted(probas, key=poids, reverse=True)[:2]
    src = f"consensus pondéré de {len(probas)} bookmakers (" + ", ".join(
        f"{par_bk[k]['titre']} ×{poids(k):.1f}" for k in top) + "…)"
    return mix, src, ecart


def probas_par_bk(par_bk, code):
    """Pour le carnet : {bookmaker: {"1": p, "N": p, "2": p}} (marge retirée), arrondi."""
    out = {}
    for k, v in par_bk.items():
        p = probas_sans_marge(v["cotes"])
        if len(p) == 3:
            out[k] = {code[i]: round(x, 4) for i, x in p.items() if i in code}
    return out


def prix_hors_norme(par_bk, jouables, code):
    """Les issues où un bookmaker jouable paie nettement plus que la médiane des autres."""
    out = {}
    for issue, court in code.items():
        cotes = sorted((v["cotes"][issue], k) for k, v in par_bk.items() if issue in v["cotes"])
        if len(cotes) < 4:
            continue
        for c, k in reversed(cotes):
            if k not in jouables:
                continue
            autres = [x for x, kk in cotes if kk != k]
            med = autres[len(autres) // 2]
            if c >= med * PRIX_HORS_NORME:
                out[court] = {"bookmaker": par_bk[k]["titre"], "cote": c, "mediane": med}
            break
    return out


def mesurer(carnet):
    """Justesse de chaque bookmaker sur les matchs joués (score de Brier, plus petit = meilleur)."""
    g = {}
    vus = set()
    for p in carnet:
        if p.get("cat") != "match":
            continue
        j = p["jambes"][0]
        if not j.get("bk_p") or not j.get("score") or j["id"] in vus or j.get("score") == "annulé":
            continue
        vus.add(j["id"])
        try:
            h, a = map(int, j["score"].split("-"))
        except ValueError:
            continue
        res = "1" if h > a else "2" if a > h else "N"
        for bk, pr in j["bk_p"].items():
            b = sum((pr.get(k, 0) - (k == res)) ** 2 for k in ("1", "N", "2"))
            s = g.setdefault(bk, [0, 0.0, 0])
            s[0] += 1
            s[1] += b
            s[2] += max(pr, key=pr.get) == res
    if not g:
        return {}
    briers = {bk: s[1] / s[0] for bk, s in g.items()}
    # moyenne pondérée par le nombre de matchs : la référence commune
    moy = sum(briers[bk] * g[bk][0] for bk in g) / sum(s[0] for s in g.values())
    out = {}
    for bk, s in g.items():
        pm = math.exp((moy - briers[bk]) / ECHELLE)
        out[bk] = {"n": s[0], "brier": round(briers[bk], 4), "favori_ok": round(s[2] / s[0], 3),
                   "poids_mesure": round(min(5.0, max(0.2, pm)), 3)}
    return out


def charger(chemin):
    global FIABILITE
    try:
        FIABILITE = json.loads(chemin.read_text(encoding="utf-8")).get("bookmakers", {})
    except Exception:
        FIABILITE = {}
    return FIABILITE
