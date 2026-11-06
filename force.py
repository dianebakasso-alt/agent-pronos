"""La note de force maison : un classement Elo des équipes, calculé par l'expert lui-même.

Il part des résultats gratuits de football-data (2 saisons par championnat) :
chaque victoire contre une équipe forte fait gagner beaucoup de points, une défaite contre
une équipe faible en fait perdre beaucoup. Avantage du terrain compris.

À quoi ça sert : un avis indépendant des bookmakers, montré sur chaque match et donné à l'IA.
Testé sur 2 saisons de 8 championnats (sonde) : il est moins précis que les cotes du marché,
et le mélanger aux cotes ne les améliore pas. Il n'écarte donc aucun match tout seul :
l'expert note s'il confirme ou contredit le favori, et ajuste automatiquement si le carnet
montre que ce signal compte vraiment.
"""
K = 20            # vitesse d'apprentissage
AVANTAGE = 60     # points d'Elo pour l'équipe qui joue à domicile
DEPART = 1500
DIVERGENCE = 0.10  # écart de proba avec le marché à partir duquel le favori est « suspect »


def _attendu(diff):
    return 1 / (1 + 10 ** (-diff / 400))


def classement(lignes):
    """lignes = [(date, dom, ext, buts_dom, buts_ext)] triées par date -> ({équipe: elo}, taux de nuls)."""
    elo, nuls = {}, 0
    for _, h, a, hg, ag in lignes:
        eh, ea = elo.get(h, DEPART), elo.get(a, DEPART)
        att = _attendu(eh + AVANTAGE - ea)
        res = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        nuls += hg == ag
        ecart = abs(hg - ag)
        mult = 1 if ecart <= 1 else 1.5 if ecart == 2 else (11 + ecart) / 8   # une large victoire compte plus
        d = K * mult * (res - att)
        elo[h], elo[a] = eh + d, ea - d
    return elo, (nuls / len(lignes) if lignes else 0.26)


def probas(elo_dom, elo_ext, taux_nuls=0.26):
    """Probabilités 1-N-2 à partir des deux notes."""
    e = _attendu(elo_dom + AVANTAGE - elo_ext)
    p_nul = max(0.10, (taux_nuls + 0.02) - 0.45 * abs(e - 0.5))
    p1 = max(0.03, e - p_nul / 2)
    p2 = max(0.03, 1 - e - p_nul / 2)
    s = p1 + p_nul + p2
    return {"1": p1 / s, "N": p_nul / s, "2": p2 / s}


class Force:
    def __init__(self):
        self.cache = {}

    def pour_match(self, lignes, sport_key, dom, ext, issues):
        """dom / ext : noms déjà retrouvés dans football-data. issues : celles du marché."""
        if not lignes or not dom or not ext:
            return None
        if sport_key not in self.cache:
            self.cache[sport_key] = classement(lignes)
        elo, tn = self.cache[sport_key]
        if dom not in elo or ext not in elo:
            return None
        p = probas(elo[dom], elo[ext], tn)
        marche = {i["court"]: i["proba"] for i in issues}
        fav = max(marche, key=marche.get)
        rang = sorted(elo.values(), reverse=True)
        return {"elo_dom": round(elo[dom]), "elo_ext": round(elo[ext]),
                "rang_dom": rang.index(elo[dom]) + 1, "rang_ext": rang.index(elo[ext]) + 1, "nb": len(rang),
                "p": {k: round(v, 3) for k, v in p.items()},
                "favori": fav, "ecart_favori": round(p[fav] - marche[fav], 3),
                "suspect": p[fav] < marche[fav] - DIVERGENCE,
                "confirme": p[fav] >= marche[fav] - 0.03}


def texte(f, dom, ext):
    """Résumé pour l'IA et pour la carte du match."""
    if not f:
        return ""
    return (f"Note de force maison (Elo) : {dom} {f['elo_dom']} ({f['rang_dom']}e/{f['nb']}), "
            f"{ext} {f['elo_ext']} ({f['rang_ext']}e/{f['nb']}) → {f['p']['1'] * 100:.0f} % / "
            f"{f['p']['N'] * 100:.0f} % / {f['p']['2'] * 100:.0f} %.")


def evaluer(lignes, cotes=None):
    """Test sur le passé : on rejoue la saison match par match (sans tricher, l'Elo n'a vu que le passé).
    Renvoie le score de Brier de l'Elo, du marché (si cotes connues) et d'un mélange 80 % marché / 20 % Elo."""
    elo, nuls, n = {}, 0, 0
    b_elo = b_mar = b_mix = 0.0
    nm = 0
    for idx, (_, h, a, hg, ag) in enumerate(lignes):
        eh, ea = elo.get(h, DEPART), elo.get(a, DEPART)
        res = "1" if hg > ag else "N" if hg == ag else "2"
        if idx >= 150:   # on laisse l'Elo apprendre sur les premiers matchs
            p = probas(eh, ea, nuls / max(1, idx))
            b_elo += sum((p[k] - (k == res)) ** 2 for k in "1N2")
            n += 1
            c = cotes[idx] if cotes else None
            if c:
                inv = {k: 1 / c[k] for k in "1N2"}
                s = sum(inv.values())
                pm = {k: v / s for k, v in inv.items()}
                b_mar += sum((pm[k] - (k == res)) ** 2 for k in "1N2")
                px = {k: 0.8 * pm[k] + 0.2 * p[k] for k in "1N2"}
                b_mix += sum((px[k] - (k == res)) ** 2 for k in "1N2")
                nm += 1
        att = _attendu(eh + AVANTAGE - ea)
        r = 1.0 if res == "1" else 0.5 if res == "N" else 0.0
        ecart = abs(hg - ag)
        mult = 1 if ecart <= 1 else 1.5 if ecart == 2 else (11 + ecart) / 8
        d = K * mult * (r - att)
        elo[h], elo[a] = eh + d, ea - d
        nuls += res == "N"
    return {"n": n, "brier_elo": round(b_elo / n, 4) if n else None,
            "n_cotes": nm, "brier_marche": round(b_mar / nm, 4) if nm else None,
            "brier_melange": round(b_mix / nm, 4) if nm else None}
