"""Alerte « match piège » : les situations où les favoris tombent plus souvent.

Tout est gratuit (forme football-data, fatigue ESPN, compos ESPN).
Un favori avec une alerte n'entre plus dans les combinés. Chaque alerte est notée dans le
carnet (trait « piege ») : l'expert vérifie ensuite si ces favoris ratent vraiment plus que prévu.
"""
from stats import _norm

# grands derbys et rivalités (les deux équipes, en minuscules sans accents, un mot suffit)
DERBYS = [
    ("arsenal", "tottenham"), ("liverpool", "everton"), ("manchester city", "manchester united"),
    ("chelsea", "tottenham"), ("chelsea", "arsenal"), ("newcastle", "sunderland"), ("aston villa", "birmingham"),
    ("real madrid", "atletico"), ("real madrid", "barcelona"), ("sevilla", "betis"), ("athletic", "real sociedad"),
    ("valencia", "levante"), ("espanyol", "barcelona"),
    ("inter", "milan"), ("roma", "lazio"), ("juventus", "torino"), ("genoa", "sampdoria"), ("napoli", "roma"),
    ("juventus", "inter"),
    ("dortmund", "schalke"), ("bayern", "dortmund"), ("hamburger", "st. pauli"), ("koln", "monchengladbach"),
    ("paris", "marseille"), ("lyon", "saint-etienne"), ("nice", "monaco"), ("lens", "lille"), ("nantes", "rennes"),
    ("ajax", "feyenoord"), ("ajax", "psv"), ("psv", "feyenoord"),
    ("benfica", "sporting"), ("porto", "benfica"), ("porto", "sporting"),
    ("celtic", "rangers"), ("galatasaray", "fenerbahce"), ("galatasaray", "besiktas"), ("fenerbahce", "besiktas"),
    ("olympiacos", "panathinaikos"), ("club brugge", "anderlecht"), ("boca", "river"),
    ("flamengo", "fluminense"), ("corinthians", "palmeiras"), ("al hilal", "al nassr"), ("al ittihad", "al ahli"),
]


def _derby(dom, ext):
    a, b = _norm(dom), _norm(ext)
    return any((x in a and y in b) or (y in a and x in b) for x, y in DERBYS)


def _defaites(forme):
    return sum(1 for r in forme if r == "D")


def analyser(m):
    """{court: [raisons]} pour les deux équipes (on regarde surtout celle du favori)."""
    out = {"1": [], "2": []}
    fat = m.get("fatigue") or {}
    st = m.get("stats")
    derby = _derby(m["domicile"], m["exterieur"])
    for court in ("1", "2"):
        nom = m["domicile"] if court == "1" else m["exterieur"]
        lui = m["exterieur"] if court == "1" else m["domicile"]
        r = out[court]
        if fat.get(court):
            r.append("fatigue : match européen à 3 jours")
        if derby:
            r.append("derby : la hiérarchie compte moins")
        if st:
            s_moi = st["domicile"] if court == "1" else st["exterieur"]
            s_lui = st["exterieur"] if court == "1" else st["domicile"]
            if len(s_moi["forme"]) >= 4 and _defaites(s_moi["forme"]) >= 3:
                r.append(f"série noire : {nom} a perdu {_defaites(s_moi['forme'])} de ses 5 derniers matchs")
            if len(s_lui["forme"]) >= 4 and _defaites(s_lui["forme"]) == 0 and s_lui["forme"].count("V") >= 2:
                r.append(f"{lui} est invaincu sur ses {len(s_lui['forme'])} derniers matchs")
            f = st.get("face") or {}
            gagne = f.get("v_dom" if court == "1" else "v_ext", 0)
            if f.get("n", 0) >= 3 and gagne == 0:
                r.append(f"bête noire : {nom} n'a battu {lui} dans aucun des {f['n']} derniers face-à-face")
            if court == "2" and len(s_moi["forme_lieu"]) >= 4 and s_moi["forme_lieu"].count("V") <= 1:
                r.append(f"{nom} gagne rarement à l'extérieur ({s_moi['forme_lieu'].count('V')} victoire sur {len(s_moi['forme_lieu'])})")
        cp = (m.get("compos") or {}).get(court)
        if cp and cp.get("rotation"):
            r.append(f"rotation : {cp['changements']} titulaires changés par rapport au dernier match")
    return {k: v for k, v in out.items() if v}


def marquer(analyses):
    n = 0
    for m in analyses:
        m["pieges"] = analyser(m)
        fav = max(m["issues"], key=lambda i: i["proba"])["court"] if m.get("issues") else None
        n += bool(fav and m["pieges"].get(fav))
    return n
