"""Forme et stats chiffrées, à partir des résultats gratuits de football-data.co.uk.

Pour chaque match : 5 derniers résultats de chaque équipe, buts marqués/encaissés,
forme à domicile / à l'extérieur, et les 5 derniers face-à-face.
"""
import csv
import io
import re
import unicodedata
import urllib.request
from datetime import datetime
from difflib import SequenceMatcher

BASE = "https://www.football-data.co.uk"

# sport_key (The Odds API) -> fichier football-data
PRINCIPAUX = {
    "soccer_epl": "E0", "soccer_efl_champ": "E1", "soccer_england_league1": "E2", "soccer_england_league2": "E3",
    "soccer_spl": "SC0", "soccer_germany_bundesliga": "D1", "soccer_germany_bundesliga2": "D2",
    "soccer_italy_serie_a": "I1", "soccer_italy_serie_b": "I2", "soccer_spain_la_liga": "SP1",
    "soccer_spain_segunda_division": "SP2", "soccer_france_ligue_one": "F1", "soccer_france_ligue_two": "F2",
    "soccer_netherlands_eredivisie": "N1", "soccer_belgium_first_div": "B1", "soccer_portugal_primeira_liga": "P1",
    "soccer_turkey_super_league": "T1", "soccer_greece_super_league": "G1",
}
EXTRA = {
    "soccer_brazil_campeonato": "BRA", "soccer_argentina_primera_division": "ARG", "soccer_usa_mls": "USA",
    "soccer_japan_j_league": "JPN", "soccer_mexico_ligamx": "MEX", "soccer_austria_bundesliga": "AUT",
    "soccer_denmark_superliga": "DNK", "soccer_norway_eliteserien": "NOR", "soccer_sweden_allsvenskan": "SWE",
    "soccer_switzerland_superleague": "SWZ", "soccer_poland_ekstraklasa": "POL", "soccer_league_of_ireland": "IRL",
    "soccer_finland_veikkausliiga": "FIN", "soccer_china_superleague": "CHN",
}

# noms The Odds API -> noms football-data (quand la ressemblance ne suffit pas)
ALIAS = {
    "manchester city": "man city", "manchester united": "man united", "nottingham forest": "nott'm forest",
    "wolverhampton wanderers": "wolves", "brighton and hove albion": "brighton", "tottenham hotspur": "tottenham",
    "west ham united": "west ham", "newcastle united": "newcastle", "leeds united": "leeds",
    "sheffield united": "sheffield united", "sheffield wednesday": "sheffield weds", "queens park rangers": "qpr",
    "west bromwich albion": "west brom", "paris saint germain": "paris sg", "saint etienne": "st etienne",
    "atletico madrid": "ath madrid", "athletic bilbao": "ath bilbao", "real sociedad": "sociedad", "real betis": "betis",
    "celta vigo": "celta", "rayo vallecano": "vallecano", "alaves": "alaves", "espanyol": "espanol",
    "elche cf": "elche", "real oviedo": "oviedo", "inter milan": "inter", "ac milan": "milan", "as roma": "roma",
    "atalanta bc": "atalanta", "hellas verona": "verona", "bayern munich": "bayern munich",
    "borussia dortmund": "dortmund", "borussia monchengladbach": "m'gladbach", "bayer leverkusen": "leverkusen",
    "eintracht frankfurt": "ein frankfurt", "vfb stuttgart": "stuttgart", "sc freiburg": "freiburg",
    "vfl wolfsburg": "wolfsburg", "werder bremen": "werder bremen", "tsg hoffenheim": "hoffenheim",
    "1. fsv mainz 05": "mainz", "fc augsburg": "augsburg", "union berlin": "union berlin", "1. fc koln": "fc koln",
    "1. fc heidenheim": "heidenheim", "hamburger sv": "hamburg", "fc st. pauli": "st pauli", "rb leipzig": "rb leipzig",
    "sporting lisbon": "sp lisbon", "fc porto": "porto", "sc braga": "sp braga", "psv eindhoven": "psv eindhoven",
    "az alkmaar": "az alkmaar", "standard liege": "standard", "club brugge": "club brugge",
    "union saint-gilloise": "st. gilloise", "royal antwerp": "antwerp", "sint-truiden": "st truiden",
}

MOTS_VIDES = {"fc", "cf", "sc", "ac", "afc", "cd", "ud", "sd", "ca", "club", "de", "1.", "and", "the", "calcio", "sv", "vfl", "vfb", "tsg", "fsv"}


def _norm(nom):
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def _mots(nom):
    return {m for m in re.split(r"[\s\-'.]+", _norm(nom)) if m and m not in MOTS_VIDES}


def _ressemblance(a, b):
    na, nb = _norm(a), _norm(b)
    ma, mb = _mots(a), _mots(b)
    commun = len(ma & mb) / max(1, min(len(ma), len(mb)))
    prefixe = 1.0 if na[:5] == nb[:5] else 0.0
    return max(SequenceMatcher(None, na, nb).ratio(), commun * 0.95, prefixe * 0.8)


def trouver_equipe(nom, equipes):
    n = _norm(nom)
    cible = ALIAS.get(n, n)
    for e in equipes:
        if _norm(e) == cible:
            return e
    meilleur, score = None, 0.0
    for e in equipes:
        s = _ressemblance(cible, e)
        if s > score:
            meilleur, score = e, s
    return meilleur if score >= 0.72 else None


# ---------------------------------------------------------------- téléchargement
def _telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 agent-pronos"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def _date(s):
    for f in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), f)
        except ValueError:
            pass
    return None


def _saisons(maintenant):
    a = maintenant.year % 100
    if maintenant.month >= 7:
        return [f"{a:02d}{a + 1:02d}", f"{a - 1:02d}{a:02d}"]
    return [f"{a - 1:02d}{a:02d}", f"{a - 2:02d}{a - 1:02d}"]


class Stats:
    def __init__(self, maintenant):
        self.maintenant = maintenant
        self.cache = {}
        self.journal = {"ligues_ok": [], "ligues_ko": [], "equipes_trouvees": 0, "equipes_manquees": []}

    def resultats(self, sport_key):
        if sport_key in self.cache:
            return self.cache[sport_key]
        lignes = []
        try:
            if sport_key in PRINCIPAUX:
                code = PRINCIPAUX[sport_key]
                for saison in _saisons(self.maintenant):
                    try:
                        texte = _telecharger(f"{BASE}/mmz4281/{saison}/{code}.csv")
                    except Exception:
                        continue
                    for r in csv.DictReader(io.StringIO(texte)):
                        if r.get("HomeTeam") and r.get("FTHG") not in (None, ""):
                            lignes.append((_date(r.get("Date", "")), r["HomeTeam"].strip(), r["AwayTeam"].strip(),
                                           int(float(r["FTHG"])), int(float(r["FTAG"]))))
            elif sport_key in EXTRA:
                texte = _telecharger(f"{BASE}/new/{EXTRA[sport_key]}.csv")
                for r in csv.DictReader(io.StringIO(texte)):
                    if r.get("Home") and r.get("HG") not in (None, ""):
                        lignes.append((_date(r.get("Date", "")), r["Home"].strip(), r["Away"].strip(),
                                       int(float(r["HG"])), int(float(r["AG"]))))
        except Exception as e:
            print(f"  ! stats {sport_key}: {e}")
        lignes = [l for l in lignes if l[0] and l[0] < self.maintenant.replace(tzinfo=None)]
        lignes.sort(key=lambda l: l[0])
        (self.journal["ligues_ok"] if lignes else self.journal["ligues_ko"]).append(sport_key)
        self.cache[sport_key] = lignes
        return lignes

    def pour_match(self, m):
        lignes = self.resultats(m.get("sport_key", ""))
        if not lignes:
            return None
        equipes = {l[1] for l in lignes} | {l[2] for l in lignes}
        dom = trouver_equipe(m["domicile"], equipes)
        ext = trouver_equipe(m["exterieur"], equipes)
        for nom, trouve in ((m["domicile"], dom), (m["exterieur"], ext)):
            if trouve:
                self.journal["equipes_trouvees"] += 1
            else:
                self.journal["equipes_manquees"].append(f"{m.get('sport_key')}: {nom}")
        if not dom or not ext:
            return None
        return {
            "domicile": _forme(lignes, dom, lieu="dom"),
            "exterieur": _forme(lignes, ext, lieu="ext"),
            "face": _face_a_face(lignes, dom, ext),
        }


def _res(l, equipe):
    _, h, a, hg, ag = l
    pour, contre = (hg, ag) if h == equipe else (ag, hg)
    return ("V" if pour > contre else "N" if pour == contre else "D"), pour, contre


def _forme(lignes, equipe, lieu):
    tous = [l for l in lignes if equipe in (l[1], l[2])][-5:]
    lieu_l = [l for l in lignes if (l[1] if lieu == "dom" else l[2]) == equipe][-5:]
    res = [_res(l, equipe) for l in tous]
    res_lieu = [_res(l, equipe) for l in lieu_l]
    n = len(res) or 1
    return {
        "forme": [r[0] for r in res],
        "points": sum(3 if r[0] == "V" else 1 if r[0] == "N" else 0 for r in res),
        "buts_pour": sum(r[1] for r in res) / n,
        "buts_contre": sum(r[2] for r in res) / n,
        "forme_lieu": [r[0] for r in res_lieu],
        "derniers": [f"{l[1]} {l[3]}-{l[4]} {l[2]}" for l in tous],
    }


def _face_a_face(lignes, dom, ext):
    ff = [l for l in lignes if {l[1], l[2]} == {dom, ext}][-5:]
    v_dom = sum(1 for l in ff if _res(l, dom)[0] == "V")
    v_ext = sum(1 for l in ff if _res(l, ext)[0] == "V")
    return {"n": len(ff), "v_dom": v_dom, "nuls": len(ff) - v_dom - v_ext, "v_ext": v_ext,
            "scores": [f"{l[1]} {l[3]}-{l[4]} {l[2]}" for l in ff]}


def resume_texte(s, dom, ext):
    """Résumé chiffré pour la consigne de l'IA."""
    if not s:
        return ""
    d, x, f = s["domicile"], s["exterieur"], s["face"]
    return (f"Stats (football-data.co.uk) : {dom} forme {''.join(d['forme'])} "
            f"({d['buts_pour']:.1f} buts marqués / {d['buts_contre']:.1f} encaissés par match), "
            f"à domicile {''.join(d['forme_lieu'])}. {ext} forme {''.join(x['forme'])} "
            f"({x['buts_pour']:.1f} / {x['buts_contre']:.1f}), à l'extérieur {''.join(x['forme_lieu'])}. "
            f"Face-à-face ({f['n']} derniers) : {f['v_dom']} V {dom}, {f['nuls']} N, {f['v_ext']} V {ext}.")
