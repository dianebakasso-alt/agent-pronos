"""Écussons originaux (couleurs du club + initiales) et drapeaux des championnats.

Ce ne sont PAS les logos officiels : juste une pastille aux couleurs de l'équipe.
"""
import hashlib
import re
import unicodedata

# ---------------------------------------------------------------- couleurs des clubs
# nom (minuscules, sans accents) : (couleur principale, couleur secondaire)
COULEURS = {
    # Ligue 1 / Ligue 2
    "paris saint germain": ("#004170", "#da291c"), "marseille": ("#2faee0", "#ffffff"),
    "lyon": ("#ffffff", "#1c3f94"), "monaco": ("#e51b22", "#ffffff"), "lille": ("#e01e13", "#20325f"),
    "rennes": ("#e13327", "#1a1a1a"), "lens": ("#ffd400", "#e30613"), "nice": ("#d50000", "#1a1a1a"),
    "nantes": ("#fcd405", "#00843d"), "strasbourg": ("#009fe3", "#ffffff"), "toulouse": ("#5b2d8e", "#ffffff"),
    "montpellier": ("#ee7623", "#0b2a5b"), "reims": ("#e2001a", "#ffffff"), "brest": ("#e30613", "#ffffff"),
    "auxerre": ("#ffffff", "#0b4ea2"), "angers": ("#1a1a1a", "#ffffff"), "le havre": ("#7cb4e3", "#0f2a4a"),
    "saint etienne": ("#00a650", "#ffffff"), "lorient": ("#f58220", "#1a1a1a"), "metz": ("#7d1132", "#ffffff"),
    "paris fc": ("#0a1f44", "#7fb3e6"), "troyes": ("#0055a4", "#ffffff"), "bordeaux": ("#0a1f44", "#ffffff"),
    "caen": ("#0a3a8c", "#e30613"), "guingamp": ("#e30613", "#1a1a1a"),
    # Premier League / Championship
    "arsenal": ("#ef0107", "#ffffff"), "aston villa": ("#670e36", "#95bfe5"), "bournemouth": ("#da291c", "#1a1a1a"),
    "brentford": ("#e30613", "#ffffff"), "brighton and hove albion": ("#0057b8", "#ffffff"),
    "chelsea": ("#034694", "#ffffff"), "crystal palace": ("#1b458f", "#c4122e"), "everton": ("#003399", "#ffffff"),
    "fulham": ("#ffffff", "#1a1a1a"), "liverpool": ("#c8102e", "#ffffff"), "manchester city": ("#6cabdd", "#ffffff"),
    "manchester united": ("#da291c", "#1a1a1a"), "newcastle united": ("#1a1a1a", "#ffffff"),
    "nottingham forest": ("#dd0000", "#ffffff"), "tottenham hotspur": ("#ffffff", "#132257"),
    "west ham united": ("#7a263a", "#1bb1e7"), "wolverhampton wanderers": ("#fdb913", "#231f20"),
    "leeds united": ("#ffffff", "#1d428a"), "burnley": ("#6c1d45", "#99d6ea"), "sunderland": ("#eb172b", "#ffffff"),
    "leicester city": ("#003090", "#fdbe11"), "southampton": ("#d71920", "#ffffff"), "ipswich town": ("#0044a9", "#ffffff"),
    "sheffield united": ("#ee2737", "#ffffff"), "norwich city": ("#fff200", "#00a650"), "west bromwich albion": ("#122f67", "#ffffff"),
    # Liga
    "real madrid": ("#ffffff", "#febe10"), "barcelona": ("#a50044", "#004d98"), "atletico madrid": ("#cb3524", "#ffffff"),
    "athletic bilbao": ("#ee2523", "#ffffff"), "real sociedad": ("#0067b1", "#ffffff"), "sevilla": ("#ffffff", "#d81920"),
    "real betis": ("#00954c", "#ffffff"), "villarreal": ("#ffe667", "#005187"), "valencia": ("#ffffff", "#ee3524"),
    "celta vigo": ("#8ac3ee", "#e5254e"), "osasuna": ("#d91a21", "#0a346f"), "getafe": ("#005999", "#ffffff"),
    "girona": ("#cd2534", "#ffffff"), "mallorca": ("#e20613", "#1a1a1a"), "rayo vallecano": ("#ffffff", "#e53027"),
    "espanyol": ("#007fc8", "#ffffff"), "alaves": ("#0761af", "#ffffff"), "elche cf": ("#ffffff", "#05642c"),
    "levante": ("#004d98", "#a50044"), "real oviedo": ("#0047ab", "#ffffff"),
    # Serie A
    "inter milan": ("#0068a8", "#1a1a1a"), "ac milan": ("#fb090b", "#1a1a1a"), "juventus": ("#ffffff", "#1a1a1a"),
    "napoli": ("#12a0d7", "#ffffff"), "as roma": ("#8e1f2f", "#f0bc42"), "lazio": ("#87d8f7", "#ffffff"),
    "atalanta bc": ("#1e71b8", "#1a1a1a"), "fiorentina": ("#482e92", "#ffffff"), "bologna": ("#1a2f48", "#a21c26"),
    "torino": ("#8a1e03", "#ffffff"), "genoa": ("#a51d2d", "#002a5c"), "udinese": ("#ffffff", "#1a1a1a"),
    "sassuolo": ("#00a752", "#1a1a1a"), "cagliari": ("#a00f2e", "#002350"), "lecce": ("#ffed00", "#d71920"),
    "parma": ("#ffd200", "#1b4fa0"), "como": ("#003da5", "#ffffff"), "hellas verona": ("#ffe000", "#1d3b8b"),
    "cremonese": ("#c8102e", "#7a8b99"), "pisa": ("#1a1a1a", "#00539f"),
    # Bundesliga
    "bayern munich": ("#dc052d", "#ffffff"), "borussia dortmund": ("#fde100", "#1a1a1a"),
    "bayer leverkusen": ("#e32221", "#1a1a1a"), "rb leipzig": ("#ffffff", "#dd0741"),
    "eintracht frankfurt": ("#e1000f", "#1a1a1a"), "vfb stuttgart": ("#ffffff", "#e32219"),
    "sc freiburg": ("#1a1a1a", "#e2001a"), "vfl wolfsburg": ("#65b32e", "#ffffff"),
    "borussia monchengladbach": ("#ffffff", "#1a1a1a"), "werder bremen": ("#1d9053", "#ffffff"),
    "tsg hoffenheim": ("#1c63b7", "#ffffff"), "1. fsv mainz 05": ("#c3141e", "#ffffff"), "fc augsburg": ("#ba3733", "#46714d"),
    "union berlin": ("#eb1923", "#ffffff"), "1. fc koln": ("#ffffff", "#ed1c24"), "1. fc heidenheim": ("#e2001a", "#003b79"),
    "hamburger sv": ("#ffffff", "#0a3f86"), "fc st. pauli": ("#5b3a29", "#ffffff"),
    # Portugal, Pays-Bas, Belgique, Turquie
    "benfica": ("#e83030", "#ffffff"), "fc porto": ("#003f8a", "#ffffff"), "sporting lisbon": ("#008057", "#ffffff"),
    "sc braga": ("#d6001c", "#ffffff"), "ajax": ("#ffffff", "#d2122e"), "psv eindhoven": ("#ed1c24", "#ffffff"),
    "feyenoord": ("#e30613", "#ffffff"), "az alkmaar": ("#da1f26", "#ffffff"), "fc twente": ("#e30613", "#ffffff"),
    "club brugge": ("#0067b1", "#1a1a1a"), "anderlecht": ("#5a2d82", "#ffffff"), "standard liege": ("#d7001e", "#ffffff"),
    "charleroi": ("#1a1a1a", "#ffffff"), "genk": ("#004b93", "#ffffff"), "gent": ("#00539f", "#ffffff"),
    "galatasaray": ("#a90432", "#fdb912"), "fenerbahce": ("#002d72", "#fcdc00"), "besiktas": ("#1a1a1a", "#ffffff"),
    "trabzonspor": ("#7a1931", "#4fb6e6"),
    # Amériques
    "flamengo": ("#c3281e", "#1a1a1a"), "palmeiras": ("#006437", "#ffffff"), "corinthians": ("#ffffff", "#1a1a1a"),
    "sao paulo": ("#ffffff", "#e30613"), "santos": ("#ffffff", "#1a1a1a"), "atletico mineiro": ("#1a1a1a", "#ffffff"),
    "fluminense": ("#870a28", "#00613c"), "botafogo": ("#1a1a1a", "#ffffff"), "gremio": ("#0d80bf", "#1a1a1a"),
    "internacional": ("#e30613", "#ffffff"), "boca juniors": ("#103f79", "#f3b229"), "river plate": ("#ffffff", "#e30613"),
}

# codes courts pour les noms où les initiales tombent mal
CODES = {
    "paris saint germain": "PSG", "manchester city": "MCI", "manchester united": "MUN", "real madrid": "RMA",
    "atletico madrid": "ATM", "bayern munich": "FCB", "borussia dortmund": "BVB", "borussia monchengladbach": "BMG",
    "inter milan": "INT", "ac milan": "MIL", "as roma": "ROM", "rb leipzig": "RBL", "tottenham hotspur": "TOT",
    "west ham united": "WHU", "newcastle united": "NEW", "nottingham forest": "NFO", "aston villa": "AVL",
    "crystal palace": "CRY", "brighton and hove albion": "BHA", "wolverhampton wanderers": "WOL", "leeds united": "LEE",
    "1. fc koln": "KOE", "1. fsv mainz 05": "M05", "vfb stuttgart": "VFB", "vfl wolfsburg": "WOB", "sc freiburg": "SCF",
    "eintracht frankfurt": "SGE", "bayer leverkusen": "B04", "werder bremen": "SVW", "union berlin": "FCU",
    "hamburger sv": "HSV", "fc st. pauli": "STP", "tsg hoffenheim": "TSG", "fc augsburg": "FCA",
    "saint etienne": "ASSE", "le havre": "HAC", "paris fc": "PFC", "real sociedad": "RSO", "real betis": "BET",
    "athletic bilbao": "ATH", "celta vigo": "CEL", "rayo vallecano": "RAY", "elche cf": "ELC", "real oviedo": "OVI",
    "hellas verona": "VER", "atalanta bc": "ATA", "psv eindhoven": "PSV", "az alkmaar": "AZ", "fc porto": "FCP",
    "sporting lisbon": "SCP", "sc braga": "SCB", "club brugge": "CLB", "standard liege": "STL",
    "boca juniors": "BOC", "river plate": "RIV", "sao paulo": "SAO", "atletico mineiro": "CAM",
}

MOTS_VIDES = {"fc", "cf", "sc", "ac", "as", "afc", "cd", "ud", "sd", "ca", "club", "de", "del", "la", "le", "1.", "and", "the", "us"}

PALETTE = ["#d7263d", "#1b998b", "#2e86ab", "#f46036", "#5b2a86", "#e9c46a", "#264653", "#c1121f",
           "#3a86ff", "#06d6a0", "#8338ec", "#ff8800", "#0b6e4f", "#9d0208", "#1d3557", "#bc6c25"]


def normaliser(nom):
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def couleurs(nom):
    n = normaliser(nom)
    if n in COULEURS:
        return COULEURS[n]
    h = int(hashlib.md5(n.encode()).hexdigest(), 16)
    p = PALETTE[h % len(PALETTE)]
    return p, "#ffffff" if (h >> 8) % 3 else "#1a1a1a"


def code(nom):
    n = normaliser(nom)
    if n in CODES:
        return CODES[n]
    mots = [m for m in re.split(r"[\s\-]+", n) if m and m not in MOTS_VIDES and not m.isdigit()]
    if not mots:
        return nom[:3].upper()
    if len(mots) == 1:
        return mots[0][:3].upper()
    return "".join(m[0] for m in mots[:3]).upper()


def _lum(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


_COMPTEUR = 0


def ecusson(nom, taille=44):
    """Petit écusson SVG original aux couleurs du club."""
    c1, c2 = couleurs(nom)
    n = normaliser(nom)
    motif = MOTIFS.get(n) or ["moitie", "bande", "echarpe", "uni"][int(hashlib.md5(("m" + n).encode()).hexdigest(), 16) % 4]
    global _COMPTEUR
    _COMPTEUR += 1
    uid = f"{hashlib.md5(n.encode()).hexdigest()[:6]}{_COMPTEUR}"  # unique dans la page
    forme = "M24 2 L44 8 V24 C44 36 35 43 24 47 C13 43 4 36 4 24 V8 Z"
    deco = _deco(motif, c1, c2)
    txt = code(nom)
    fs = {1: 14, 2: 14, 3: 13, 4: 11}.get(len(txt), 9.5)
    return f"""<svg class="ecu" width="{taille}" height="{taille}" viewBox="0 0 48 50" aria-hidden="true">
<defs><clipPath id="c{uid}"><path d="{forme}"/></clipPath></defs>
<g clip-path="url(#c{uid})"><rect width="48" height="50" fill="{c1}"/>{deco}</g>
<path d="{forme}" fill="none" stroke="rgba(0,0,0,.25)" stroke-width="1.5"/>
<rect x="8" y="17.5" width="32" height="13" rx="6.5" fill="rgba(10,14,12,.72)"/>
<text x="24" y="27.6" text-anchor="middle" font-family="Barlow Condensed, Arial Narrow, sans-serif" font-weight="700" font-size="{fs}" fill="#fff">{txt}</text>
</svg>"""




# ---------------------------------------------------------------- style des maillots (inspiré des tenues, pas des logos)
# motifs : uni, rayures, cerceaux, moitie, bande (horizontale), bandev (verticale centrale),
#          echarpe, diagonale, croix, epaules
MOTIFS = {
    # France
    "paris saint germain": "bandev", "marseille": "uni", "lyon": "epaules", "monaco": "diagonale", "lille": "uni",
    "rennes": "bande", "lens": "bande", "nice": "rayures", "nantes": "uni", "strasbourg": "uni", "toulouse": "uni",
    "montpellier": "uni", "reims": "epaules", "brest": "uni", "auxerre": "uni", "angers": "rayures", "le havre": "moitie",
    "saint etienne": "uni", "lorient": "uni", "metz": "uni", "paris fc": "uni", "troyes": "uni", "bordeaux": "bande",
    # Angleterre
    "arsenal": "epaules", "aston villa": "epaules", "bournemouth": "rayures", "brentford": "rayures",
    "brighton and hove albion": "rayures", "chelsea": "uni", "crystal palace": "rayures", "everton": "uni", "fulham": "uni",
    "liverpool": "uni", "manchester city": "uni", "manchester united": "uni", "newcastle united": "rayures",
    "nottingham forest": "uni", "tottenham hotspur": "uni", "west ham united": "epaules", "wolverhampton wanderers": "uni",
    "leeds united": "uni", "burnley": "epaules", "sunderland": "rayures", "leicester city": "uni", "southampton": "rayures",
    "ipswich town": "uni", "sheffield united": "rayures", "norwich city": "uni", "west bromwich albion": "rayures",
    "stoke city": "rayures", "queens park rangers": "cerceaux", "hull city": "rayures", "blackburn rovers": "moitie",
    "celtic": "cerceaux", "rangers": "uni",
    # Espagne
    "real madrid": "uni", "barcelona": "rayures", "atletico madrid": "rayures", "athletic bilbao": "rayures",
    "real sociedad": "rayures", "sevilla": "uni", "real betis": "rayures", "villarreal": "uni", "valencia": "uni",
    "celta vigo": "uni", "osasuna": "uni", "getafe": "uni", "girona": "rayures", "mallorca": "uni",
    "rayo vallecano": "echarpe", "espanyol": "rayures", "alaves": "rayures", "elche cf": "bande", "levante": "rayures",
    "real oviedo": "uni",
    # Italie
    "inter milan": "rayures", "ac milan": "rayures", "juventus": "rayures", "napoli": "uni", "as roma": "uni",
    "lazio": "uni", "atalanta bc": "rayures", "fiorentina": "uni", "bologna": "rayures", "torino": "uni",
    "genoa": "moitie", "udinese": "rayures", "sassuolo": "rayures", "cagliari": "moitie", "lecce": "rayures",
    "parma": "croix", "como": "uni", "hellas verona": "uni", "cremonese": "rayures", "pisa": "rayures",
    # Allemagne
    "bayern munich": "uni", "borussia dortmund": "uni", "bayer leverkusen": "uni", "rb leipzig": "uni",
    "eintracht frankfurt": "uni", "vfb stuttgart": "bande", "sc freiburg": "uni", "vfl wolfsburg": "uni",
    "borussia monchengladbach": "uni", "werder bremen": "uni", "tsg hoffenheim": "uni", "1. fsv mainz 05": "uni",
    "fc augsburg": "uni", "union berlin": "uni", "1. fc koln": "uni", "1. fc heidenheim": "uni", "hamburger sv": "uni",
    "fc st. pauli": "uni",
    # Portugal, Pays-Bas, Belgique, Turquie
    "benfica": "uni", "fc porto": "rayures", "sporting lisbon": "cerceaux", "sc braga": "epaules", "ajax": "bandev",
    "psv eindhoven": "rayures", "feyenoord": "moitie", "az alkmaar": "uni", "fc twente": "uni", "club brugge": "rayures",
    "anderlecht": "uni", "standard liege": "uni", "charleroi": "rayures", "genk": "uni", "gent": "uni",
    "royal antwerp": "uni", "westerlo": "uni", "union saint-gilloise": "uni", "galatasaray": "moitie",
    "fenerbahce": "rayures", "besiktas": "rayures", "trabzonspor": "rayures",
    # Amériques
    "flamengo": "cerceaux", "palmeiras": "uni", "corinthians": "uni", "sao paulo": "bande", "santos": "uni",
    "atletico mineiro": "rayures", "fluminense": "rayures", "botafogo": "rayures", "gremio": "rayures",
    "internacional": "uni", "boca juniors": "bande", "river plate": "echarpe",
}

COULEURS.update({
    "stoke city": ("#e03a3e", "#ffffff"), "queens park rangers": ("#1d5ba4", "#ffffff"), "hull city": ("#f5a12d", "#1a1a1a"),
    "blackburn rovers": ("#009ee0", "#ffffff"), "celtic": ("#018749", "#ffffff"), "rangers": ("#1b458f", "#ffffff"),
    "royal antwerp": ("#e30613", "#ffffff"), "westerlo": ("#fdd700", "#004c99"), "union saint-gilloise": ("#fcd116", "#00337f"),
    "bordeaux": ("#0a1f44", "#ffffff"), "le havre": ("#7cb4e3", "#0f2a4a"), "lyon": ("#ffffff", "#e2001a"),
    "arsenal": ("#ef0107", "#ffffff"), "aston villa": ("#670e36", "#95bfe5"), "west ham united": ("#7a263a", "#1bb1e7"),
    "burnley": ("#6c1d45", "#99d6ea"), "reims": ("#e2001a", "#ffffff"), "sc braga": ("#d6001c", "#ffffff"),
    "barcelona": ("#a50044", "#004d98"), "levante": ("#004d98", "#a50044"), "bologna": ("#a21c26", "#1a2f48"),
    "genoa": ("#a51d2d", "#002a5c"), "cagliari": ("#a00f2e", "#002350"), "parma": ("#ffffff", "#1a1a1a"),
    "galatasaray": ("#a90432", "#fdb912"), "feyenoord": ("#e30613", "#ffffff"), "ajax": ("#ffffff", "#d2122e"),
    "paris saint germain": ("#004170", "#da291c"), "vfb stuttgart": ("#ffffff", "#e32219"), "rennes": ("#e13327", "#1a1a1a"),
    "boca juniors": ("#103f79", "#f3b229"), "sao paulo": ("#ffffff", "#e30613"), "elche cf": ("#ffffff", "#05642c"),
    "monaco": ("#e51b22", "#ffffff"), "rayo vallecano": ("#ffffff", "#e53027"), "river plate": ("#ffffff", "#e30613"),
    "fluminense": ("#870a28", "#00613c"), "gremio": ("#0d80bf", "#1a1a1a"), "fenerbahce": ("#fcdc00", "#002d72"),
    "besiktas": ("#1a1a1a", "#ffffff"), "trabzonspor": ("#7a1931", "#4fb6e6"), "flamengo": ("#c3281e", "#1a1a1a"),
    "fc porto": ("#ffffff", "#003f8a"), "sporting lisbon": ("#008057", "#ffffff"), "club brugge": ("#0067b1", "#1a1a1a"),
    "charleroi": ("#1a1a1a", "#ffffff"), "crystal palace": ("#c4122e", "#1b458f"), "brighton and hove albion": ("#0057b8", "#ffffff"),
    "bournemouth": ("#da291c", "#1a1a1a"), "brentford": ("#e30613", "#ffffff"), "southampton": ("#d71920", "#ffffff"),
    "sunderland": ("#eb172b", "#ffffff"), "sheffield united": ("#ee2737", "#ffffff"), "west bromwich albion": ("#122f67", "#ffffff"),
    "girona": ("#cd2534", "#ffffff"), "espanyol": ("#007fc8", "#ffffff"), "alaves": ("#0761af", "#ffffff"),
    "real sociedad": ("#0067b1", "#ffffff"), "real betis": ("#00954c", "#ffffff"), "lecce": ("#ffed00", "#d71920"),
    "udinese": ("#ffffff", "#1a1a1a"), "sassuolo": ("#00a752", "#1a1a1a"), "atalanta bc": ("#1e71b8", "#1a1a1a"),
    "cremonese": ("#c8102e", "#7a8b99"), "pisa": ("#1a1a1a", "#00539f"), "atletico mineiro": ("#1a1a1a", "#ffffff"),
    "botafogo": ("#1a1a1a", "#ffffff"), "psv eindhoven": ("#ed1c24", "#ffffff"), "angers": ("#1a1a1a", "#ffffff"),
    "juventus": ("#ffffff", "#1a1a1a"), "newcastle united": ("#1a1a1a", "#ffffff"), "nice": ("#d50000", "#1a1a1a"),
    "lens": ("#ffd400", "#e30613"),
})

# abréviations courantes (celles qu'on lit dans la presse et chez les bookmakers)
CODES.update({
    "marseille": "OM", "lyon": "OL", "lille": "LOSC", "monaco": "ASM", "rennes": "SRFC", "lens": "RCL", "nice": "OGCN",
    "nantes": "FCN", "strasbourg": "RCSA", "toulouse": "TFC", "montpellier": "MHSC", "reims": "SDR", "brest": "SB29",
    "auxerre": "AJA", "angers": "SCO", "lorient": "FCL", "metz": "FCM", "troyes": "ESTAC", "bordeaux": "FCGB",
    "arsenal": "ARS", "liverpool": "LIV", "chelsea": "CHE", "everton": "EVE", "fulham": "FUL", "brentford": "BRE",
    "bournemouth": "BOU", "burnley": "BUR", "sunderland": "SUN", "leicester city": "LEI", "southampton": "SOU",
    "ipswich town": "IPS", "hull city": "HUL", "stoke city": "STK", "queens park rangers": "QPR", "west bromwich albion": "WBA",
    "celtic": "CEL", "rangers": "RAN", "barcelona": "BAR", "sevilla": "SEV", "villarreal": "VIL", "valencia": "VAL",
    "girona": "GIR", "mallorca": "MLL", "osasuna": "OSA", "getafe": "GET", "espanyol": "ESP", "alaves": "ALA",
    "levante": "LEV", "juventus": "JUV", "napoli": "NAP", "lazio": "LAZ", "fiorentina": "FIO", "bologna": "BFC",
    "torino": "TOR", "genoa": "GEN", "udinese": "UDI", "lecce": "LEC", "parma": "PAR", "como": "COM", "cagliari": "CAG",
    "sassuolo": "SAS", "cremonese": "CRE", "pisa": "PIS", "benfica": "SLB", "ajax": "AJA", "feyenoord": "FEY",
    "galatasaray": "GS", "fenerbahce": "FB", "besiktas": "BJK", "trabzonspor": "TS", "flamengo": "FLA",
    "palmeiras": "PAL", "corinthians": "COR", "santos": "SAN", "fluminense": "FLU", "botafogo": "BOT",
    "gremio": "GRE", "internacional": "INT", "royal antwerp": "RAFC", "union saint-gilloise": "USG", "anderlecht": "RSCA",
    "genk": "KRC", "gent": "KAAG", "westerlo": "KVCW", "manchester city": "MCI", "manchester united": "MUN",
})


def _deco(motif, c1, c2):
    if motif == "uni":
        return f'<path d="M4 8 L24 2 L44 8" fill="none" stroke="{c2}" stroke-width="3"/>'
    if motif == "rayures":
        return "".join(f'<rect x="{x}" y="0" width="5.5" height="50" fill="{c2}"/>' for x in (3, 14, 25, 36))
    if motif == "cerceaux":
        return "".join(f'<rect x="0" y="{y}" width="48" height="5.5" fill="{c2}"/>' for y in (6, 17, 28, 39))
    if motif == "moitie":
        return f'<rect x="24" y="0" width="24" height="50" fill="{c2}"/>'
    if motif == "bande":
        return f'<rect x="0" y="9" width="48" height="8" fill="{c2}"/>'
    if motif == "bandev":
        return (f'<rect x="17" y="0" width="14" height="50" fill="{c2}"/>'
                f'<rect x="15" y="0" width="2" height="50" fill="#fff" opacity=".9"/><rect x="31" y="0" width="2" height="50" fill="#fff" opacity=".9"/>')
    if motif == "echarpe":
        return f'<path d="M-4 6 L6 -4 L52 42 L42 52 Z" fill="{c2}"/>'
    if motif == "diagonale":
        return f'<path d="M48 0 L48 50 L0 50 Z" fill="{c2}"/>'
    if motif == "croix":
        return f'<rect x="20" y="0" width="8" height="50" fill="{c2}"/><rect x="0" y="12" width="48" height="8" fill="{c2}"/>'
    if motif == "epaules":
        return f'<path d="M0 0 L14 0 L4 22 L0 22 Z M48 0 L34 0 L44 22 L48 22 Z" fill="{c2}"/>'
    return ""


# ---------------------------------------------------------------- championnats
CHAMPIONNATS = {
    "soccer_france_ligue_one": ("🇫🇷", "Ligue 1"), "soccer_france_ligue_two": ("🇫🇷", "Ligue 2"),
    "soccer_epl": ("🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Premier League"), "soccer_efl_champ": ("🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Championship"),
    "soccer_spain_la_liga": ("🇪🇸", "Liga"), "soccer_spain_segunda_division": ("🇪🇸", "Liga 2"),
    "soccer_italy_serie_a": ("🇮🇹", "Serie A"), "soccer_italy_serie_b": ("🇮🇹", "Serie B"),
    "soccer_germany_bundesliga": ("🇩🇪", "Bundesliga"), "soccer_germany_bundesliga2": ("🇩🇪", "2. Bundesliga"),
    "soccer_uefa_champs_league": ("⭐", "Ligue des champions"), "soccer_uefa_europa_league": ("🟠", "Europa League"),
    "soccer_uefa_europa_conference_league": ("🟢", "Conference League"),
    "soccer_netherlands_eredivisie": ("🇳🇱", "Eredivisie"), "soccer_portugal_primeira_liga": ("🇵🇹", "Liga Portugal"),
    "soccer_belgium_first_div": ("🇧🇪", "Pro League"), "soccer_turkey_super_league": ("🇹🇷", "Süper Lig"),
    "soccer_brazil_campeonato": ("🇧🇷", "Brasileirão"), "soccer_argentina_primera_division": ("🇦🇷", "Liga Argentina"),
    "soccer_usa_mls": ("🇺🇸", "MLS"), "soccer_japan_j_league": ("🇯🇵", "J1 League"),
    "soccer_spl": ("🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Premiership"), "soccer_mexico_ligamx": ("🇲🇽", "Liga MX"),
    "soccer_switzerland_superleague": ("🇨🇭", "Super League"), "soccer_austria_bundesliga": ("🇦🇹", "Bundesliga AUT"),
    "soccer_denmark_superliga": ("🇩🇰", "Superliga"), "soccer_norway_eliteserien": ("🇳🇴", "Eliteserien"),
    "soccer_sweden_allsvenskan": ("🇸🇪", "Allsvenskan"), "soccer_greece_super_league": ("🇬🇷", "Super League GRE"),
    "soccer_poland_ekstraklasa": ("🇵🇱", "Ekstraklasa"), "soccer_korea_kleague1": ("🇰🇷", "K League 1"),
    "soccer_australia_aleague": ("🇦🇺", "A-League"), "soccer_saudi_arabia_pro_league": ("🇸🇦", "Saudi Pro League"),
    "soccer_fifa_world_cup_qualifiers_europe": ("🌍", "Qualifs Mondial (Europe)"),
    "soccer_uefa_nations_league": ("🇪🇺", "Ligue des nations"),
}


def championnat(sport_key, titre):
    if sport_key in CHAMPIONNATS:
        return CHAMPIONNATS[sport_key]
    return "⚽", titre


# couleur d'accent par championnat (pour le liseré des cartes)
COULEURS_LIGUES = {
    "soccer_france_ligue_one": "#3b82f6", "soccer_france_ligue_two": "#60a5fa", "soccer_epl": "#a855f7",
    "soccer_efl_champ": "#c084fc", "soccer_spain_la_liga": "#f43f5e", "soccer_italy_serie_a": "#06b6d4",
    "soccer_germany_bundesliga": "#ef4444", "soccer_uefa_champs_league": "#6366f1",
    "soccer_uefa_europa_league": "#f97316", "soccer_uefa_europa_conference_league": "#22c55e",
    "soccer_netherlands_eredivisie": "#fb923c", "soccer_portugal_primeira_liga": "#10b981",
    "soccer_belgium_first_div": "#facc15", "soccer_turkey_super_league": "#e11d48",
    "soccer_brazil_campeonato": "#22c55e", "soccer_argentina_primera_division": "#38bdf8",
    "soccer_usa_mls": "#2563eb", "soccer_japan_j_league": "#ec4899",
}


def couleur_ligue(sport_key):
    return COULEURS_LIGUES.get(sport_key, "#c6ff3d")
