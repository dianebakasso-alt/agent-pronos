"""L'expert apprend de ses erreurs.

1. Autopsie : chaque prono perdu (surtout les grosses surprises) est analysé par l'IA :
   pourquoi il a perdu, était-ce prévisible, quel signal a été raté, quelle leçon générale.
2. Leçons : les leçons « prévisibles » sont rappelées à l'IA avant chaque nouvelle analyse.
3. Ajustements chiffrés : on compare, par type de pari (favori à l'extérieur, petite cote,
   doute de l'IA, rebond…), les réussites aux réussites attendues. Un type qui rate
   nettement plus que prévu est pénalisé dans la sélection ; un type qui réussit mieux est favorisé.
"""
import json
from datetime import datetime, timedelta

MIN_N = 25          # pronos réglés avant d'ajuster un type de pari
ECART = 0.08        # 8 points de réussite en dessous (ou au-dessus) de l'attendu
MAX_AUTOPSIES = 4   # par passage (coût IA)

TRAITS = {
    "exterieur": "Favori à l'extérieur",
    "petite_cote": "Petite cote (moins de 1,40)",
    "doute_ia": "Joué malgré un doute de l'IA",
    "rebond": "Rebond (bonne équipe en mauvaise passe)",
    "favori_net": "Gros favori (plus de 65 %)",
}

CONSIGNE = """Tu es un analyste football. Un pronostic a perdu, explique pourquoi.
Match : {dom} - {ext} ({champ}), joué le {date}. Score final : {score}.
Pari perdu : {pari} (cote {cote}, {proba} de chances selon le marché).

Cherche sur le web le compte rendu du match : buts, cartons rouges, penalties, blessures pendant le match,
composition (rotation ?), contexte (fatigue, enjeu, météo), statistiques (tirs, occasions, xG si disponibles).

Réponds UNIQUEMENT avec ce JSON, en français :
{{"pourquoi": "2 phrases : ce qui s'est vraiment passé",
  "previsible": "oui" | "en partie" | "non",
  "signal_rate": "le signal qu'on aurait pu voir avant le match, ou chaîne vide si rien",
  "tags": ["parmi : rotation, fatigue, blessure, carton_rouge, penalty, malchance, favori_surcote, derby, motivation, meteo, defense_fragile, attaque_inefficace"],
  "lecon": "1 phrase générale, réutilisable pour d'autres matchs (pas spécifique à ces équipes)"}}
"non" = malchance pure (domination sans réussite, erreur d'arbitrage, but à la dernière minute)."""


def _dt(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def traits_jambe(j, m=None):
    t = []
    if j.get("court") == "2":
        t.append("exterieur")
    if j.get("cote") and j["cote"] < 1.40:
        t.append("petite_cote")
    if (j.get("proba") or 0) >= 0.65:
        t.append("favori_net")
    if m is not None:
        if (m.get("avis") or {}).get("avis") == "prudence":
            t.append("doute_ia")
    if j.get("rebond"):
        t.append("rebond")
    return t


def enrichir(carnet, analyses):
    """Ajoute les traits aux jambes encore sans traits (au moment où elles sont notées)."""
    par_id = {a["id"]: a for a in analyses}
    for p in carnet:
        for j in p["jambes"]:
            if "traits" not in j and "court" in j:
                j["traits"] = traits_jambe(j, par_id.get(j["id"]))


def ajustements(carnet):
    """Réussite réelle contre réussite attendue, par trait. Renvoie {trait: {...}}."""
    stats = {}
    vus = set()
    for p in carnet:
        for j in p["jambes"]:
            if j.get("ok") is None or "court" not in j or not j.get("proba"):
                continue
            cle = (j["id"], j["court"])
            if cle in vus:
                continue
            vus.add(cle)
            for t in j.get("traits", []):
                s = stats.setdefault(t, {"n": 0, "ok": 0, "attendu": 0.0})
                s["n"] += 1
                s["ok"] += 1 if j["ok"] else 0
                s["attendu"] += j["proba"]
    out = {}
    for t, s in stats.items():
        ecart = (s["ok"] - s["attendu"]) / s["n"]
        ajust = 0.0
        if s["n"] >= MIN_N:
            ajust = -0.04 if ecart < -ECART else 0.02 if ecart > ECART else 0.0
        out[t] = {"n": s["n"], "reussite": s["ok"] / s["n"], "attendu": s["attendu"] / s["n"],
                  "ecart": ecart, "ajust": ajust}
    return out


def a_autopsier(carnet, maintenant):
    """Les jambes perdues récentes, la plus grosse surprise d'abord."""
    jambes, vus = [], set()
    for p in carnet:
        for j in p["jambes"]:
            if j.get("ok") is False and "autopsie" not in j and j.get("score") and "court" in j \
                    and _dt(j["date"]) > maintenant - timedelta(days=4) and j["id"] not in vus:
                vus.add(j["id"])
                jambes.append(j)
    return sorted(jambes, key=lambda j: -(j.get("proba") or 0))[:MAX_AUTOPSIES]


def consigne(j):
    return CONSIGNE.format(dom=j["domicile"], ext=j["exterieur"], champ=j.get("championnat", ""),
                           date=j["date"][:10], score=j.get("score", "?"), pari=j["pari"],
                           cote=j.get("cote") or "?", proba=f"{(j.get('proba') or 0) * 100:.0f} %")


def noter_autopsie(carnet, lecons, j, res, maintenant):
    res = {k: res.get(k) for k in ("pourquoi", "previsible", "signal_rate", "tags", "lecon")}
    for p in carnet:
        for x in p["jambes"]:
            if x["id"] == j["id"]:
                x["autopsie"] = res
    lecons.append({"date": maintenant.strftime("%Y-%m-%d"), "match": f"{j['domicile']} - {j['exterieur']}",
                   "pari": j["pari"], "cote": j.get("cote"), "proba": j.get("proba"), "score": j.get("score"), **res})
    del lecons[:-60]


def texte_lecons(lecons, n=6):
    """Les leçons à rappeler à l'IA avant une nouvelle analyse."""
    utiles = [l for l in lecons if l.get("previsible") in ("oui", "en partie") and l.get("lecon")][-n:]
    if not utiles:
        return ""
    return ("Leçons tirées de tes pronostics perdus récemment (applique-les) :\n"
            + "\n".join(f"- {l['lecon']}" for l in utiles))


def charger(chemin):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return []
