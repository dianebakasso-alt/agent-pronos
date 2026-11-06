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
MAX_AUTOPSIES = 0   # autopsies IA coupées : l'autopsie gratuite ESPN les remplace, le budget IA va aux avis du jour

TRAITS = {
    "exterieur": "Favori à l'extérieur",
    "petite_cote": "Petite cote (moins de 1,40)",
    "doute_ia": "Joué malgré un doute de l'IA",
    "rebond": "Rebond (bonne équipe en mauvaise passe)",
    "favori_net": "Gros favori (plus de 65 %)",
    "buts_plus": "Paris « beaucoup de buts » (+2,5, les 2 marquent)",
    "buts_moins": "Paris « peu de buts » (−2,5, pas les 2)",
    "piege": "Favori avec une alerte « match piège »",
    "force_contre": "Favori contredit par la note de force",
    "force_pour": "Favori confirmé par la note de force",
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
    if j.get("marche"):
        return ["buts_" + ("plus" if j["marche"].startswith("plus") or j["marche"] == "btts" else "moins")]
    if j.get("court") == "2":
        t.append("exterieur")
    if j.get("cote") and j["cote"] < 1.40:
        t.append("petite_cote")
    if (j.get("proba") or 0) >= 0.65:
        t.append("favori_net")
    if m is not None:
        if (m.get("avis") or {}).get("avis") == "prudence":
            t.append("doute_ia")
        if (m.get("pieges") or {}).get(j.get("court")):
            t.append("piege")
        fo = m.get("force") or {}
        if fo.get("favori") == j.get("court"):
            if fo.get("suspect"):
                t.append("force_contre")
            elif fo.get("confirme"):
                t.append("force_pour")
    if j.get("rebond"):
        t.append("rebond")
    return t


def enrichir(carnet, analyses):
    """Ajoute les traits aux jambes encore sans traits (au moment où elles sont notées)."""
    par_id = {a["id"]: a for a in analyses}
    for p in carnet:
        for j in p["jambes"]:
            if "traits" not in j:
                j["traits"] = traits_jambe(j, par_id.get(j["id"]))


def ajustements(carnet):
    """Réussite réelle contre réussite attendue, par trait. Renvoie {trait: {...}}."""
    stats = {}
    vus = set()
    for p in carnet:
        for j in p["jambes"]:
            if j.get("ok") is None or not j.get("proba"):
                continue
            cle = (j["id"], j.get("court") or j.get("marche"))
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
            cle = (j["id"], j.get("court") or j.get("marche"))
            if j.get("ok") is False and "autopsie" not in j and j.get("score") \
                    and _dt(j["date"]) > maintenant - timedelta(days=30) and cle not in vus:
                vus.add(cle)
                jambes.append(j)
    return sorted(jambes, key=lambda j: -(j.get("proba") or 0))[:MAX_AUTOPSIES]


def a_autopsier_tout(carnet, maintenant, n=60, jours=30):
    """Toutes les jambes perdues récentes sans autopsie (pour l'autopsie gratuite ESPN)."""
    jambes, vus = [], set()
    for p in carnet:
        for j in p["jambes"]:
            cle = (j["id"], j.get("court") or j.get("marche"))
            if j.get("ok") is False and "autopsie" not in j and j.get("score") and j.get("espn") \
                    and _dt(j["date"]) > maintenant - timedelta(days=jours) and cle not in vus:
                vus.add(cle)
                jambes.append(j)
    return sorted(jambes, key=lambda j: -(j.get("proba") or 0))[:n]


def autopsies_gratuites(carnet, lecons, maintenant, n=60, jours=30):
    faites = erreurs = 0
    for j in a_autopsier_tout(carnet, maintenant, n, jours):
        try:
            res = autopsie_gratuite(j)
        except Exception:
            erreurs += 1
            if erreurs >= 5:
                break
            continue
        if res:
            noter_autopsie(carnet, lecons, j, res, maintenant)
            faites += 1
    return faites


def consigne(j):
    return CONSIGNE.format(dom=j["domicile"], ext=j["exterieur"], champ=j.get("championnat", ""),
                           date=j["date"][:10], score=j.get("score", "?"), pari=j["pari"],
                           cote=j.get("cote") or "?", proba=f"{(j.get('proba') or 0) * 100:.0f} %")


def noter_autopsie(carnet, lecons, j, res, maintenant):
    res = {k: res.get(k) for k in ("pourquoi", "previsible", "signal_rate", "tags", "lecon", "source") if res.get(k) is not None}
    for p in carnet:
        for x in p["jambes"]:
            if x["id"] == j["id"] and (x.get("court") or x.get("marche")) == (j.get("court") or j.get("marche")):
                x["autopsie"] = res
    lecons.append({"date": maintenant.strftime("%Y-%m-%d"), "match": f"{j['domicile']} - {j['exterieur']}",
                   "pari": j["pari"], "cote": j.get("cote"), "proba": j.get("proba"), "score": j.get("score"), **res})
    del lecons[:-400]


def texte_lecons(lecons, n=6):
    """Les leçons à rappeler à l'IA avant une nouvelle analyse."""
    vues, utiles = set(), []
    for l in reversed(lecons):   # les plus récentes, sans doublon
        if l.get("previsible") in ("oui", "en partie") and l.get("lecon") and l["lecon"] not in vues:
            vues.add(l["lecon"]); utiles.append(l)
        if len(utiles) >= n:
            break
    if not utiles:
        return ""
    return ("Leçons tirées de tes pronostics perdus récemment (applique-les) :\n"
            + "\n".join(f"- {l['lecon']}" for l in utiles))


def charger(chemin):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return []


# ---------------------------------------------------------------- autopsie gratuite (ESPN, sans IA)
def _stats_equipe(sm, tid):
    for t in (sm.get("boxscore") or {}).get("teams", []):
        if (t.get("team") or {}).get("id") == tid:
            out = {}
            for s in t.get("statistics", []):
                try:
                    out[s["name"]] = float(s.get("displayValue") or 0)
                except (TypeError, ValueError):
                    pass
            return out
    return {}


def _minute(k):
    try:
        return int(str((k.get("clock") or {}).get("displayValue", "0")).split("'")[0].split("+")[0])
    except ValueError:
        return 0


def autopsie_gratuite(j, get=None):
    """Explique un pari perdu avec les faits du match publiés par ESPN : cartons rouges, penalties,
    buts tardifs, tirs et tirs cadrés. Gratuit, sans IA. Renvoie le même format que l'autopsie IA, ou None."""
    esp = j.get("espn") or {}
    if not esp.get("id"):
        return None
    if get is None:
        import direct
        get = direct._get
        base = direct.BASE
    else:
        base = ""
    sm = get(f"{base}/{esp['ligue']}/summary?event={esp['id']}")
    comp = ((sm.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
    ids = {c.get("homeAway"): c.get("id") for c in comp}
    if not ids.get("home") or not ids.get("away"):
        return None
    sh, sa = _stats_equipe(sm, ids["home"]), _stats_equipe(sm, ids["away"])
    ke = sm.get("keyEvents") or []
    buts = [k for k in ke if (k.get("type") or {}).get("type") == "goal" or k.get("scoringPlay")]
    rouges = [k for k in ke if (k.get("type") or {}).get("type") == "red-card"]
    nom = {ids["home"]: j["domicile"], ids["away"]: j["exterieur"]}
    tirs = (f"tirs {sh.get('totalShots', 0):.0f}-{sa.get('totalShots', 0):.0f}, "
            f"cadrés {sh.get('shotsOnTarget', 0):.0f}-{sa.get('shotsOnTarget', 0):.0f}, "
            f"possession {sh.get('possessionPct', 0):.0f}-{sa.get('possessionPct', 0):.0f} %")
    tags, faits, previsible, lecon = [], [], "en partie", ""

    if j.get("court") in ("1", "2"):
        moi = ids["home"] if j["court"] == "1" else ids["away"]
        lui = ids["away"] if j["court"] == "1" else ids["home"]
        s_moi, s_lui = (sh, sa) if j["court"] == "1" else (sa, sh)
        r_moi = [k for k in rouges if (k.get("team") or {}).get("id") == moi and _minute(k) < 80]
        if r_moi:
            tags.append("carton_rouge"); previsible = "non"
            faits.append(f"{nom[moi]} a pris un carton rouge à la {_minute(r_moi[0])}e")
        pen = [k for k in buts if (k.get("team") or {}).get("id") == lui and "penalty" in (k.get("text") or "").lower()]
        if pen:
            tags.append("penalty")
            faits.append(f"{nom[lui]} a marqué sur penalty")
        try:
            ecart = abs(int(j["score"].split("-")[0]) - int(j["score"].split("-")[1]))
        except (KeyError, ValueError, IndexError, AttributeError):
            ecart = 9
        tard = [k for k in buts if (k.get("team") or {}).get("id") == lui and _minute(k) >= 85] if ecart <= 1 else []
        t_moi, t_lui = s_moi.get("totalShots", 0), s_lui.get("totalShots", 0)
        c_moi, c_lui = s_moi.get("shotsOnTarget", 0), s_lui.get("shotsOnTarget", 0)
        if t_moi and t_moi >= 1.5 * max(1, t_lui) and c_moi >= c_lui:
            tags += ["malchance", "attaque_inefficace"]
            previsible = "non" if not r_moi else previsible
            faits.append(f"{nom[moi]} a dominé sans marquer assez")
            lecon = "Un favori qui domine aux tirs finit par gagner sur la durée : ce genre de défaite n'est pas une raison de l'éviter."
        elif c_lui >= c_moi + 2:
            tags.append("favori_surcote"); previsible = "oui" if not r_moi else "en partie"
            faits.append(f"{nom[lui]} a été plus dangereux ({c_lui:.0f} tirs cadrés contre {c_moi:.0f})")
            lecon = "Quand l'outsider se crée plus d'occasions cadrées que le favori, la cote du favori était trop basse : regarde la forme offensive réelle de l'adversaire."
        else:
            tags.append("favori_surcote")
            lecon = lecon or "Match équilibré dans le jeu : le favori n'avait pas l'avantage net que la cote laissait croire."
        if tard:   # but décisif dans les 5 dernières minutes
            tags.append("malchance"); previsible = "non" if previsible != "oui" else "en partie"
            faits.append(f"but décisif de {nom[lui]} à la {_minute(tard[-1])}e")
        if r_moi:
            lecon = "Un carton rouge change tout : rien à corriger dans l'analyse d'avant-match."
    elif j.get("marche"):
        cad = sh.get("shotsOnTarget", 0) + sa.get("shotsOnTarget", 0)
        if j["marche"] in ("plus25", "btts", "plus15"):
            if cad >= 10:
                tags += ["malchance", "attaque_inefficace"]; previsible = "non"
                faits.append(f"{cad:.0f} tirs cadrés au total, mais peu de buts")
                lecon = "Beaucoup d'occasions sans buts : variance normale, le pari « buts » restait bon."
            else:
                tags.append("attaque_inefficace")
                faits.append(f"match fermé : seulement {cad:.0f} tirs cadrés au total")
                lecon = "Les matchs à enjeu ou entre équipes prudentes ont moins de buts que leurs moyennes : méfie-toi du « plus de 2,5 » quand l'une des deux joue la sécurité."
        else:
            tags.append("defense_fragile")
            faits.append(f"plus de buts que prévu ({cad:.0f} tirs cadrés au total)")
            lecon = "Le « peu de buts » est risqué : un seul but rapide ouvre le match. À jouer seulement entre deux défenses vraiment solides."
    else:
        return None
    pourquoi = (f"Score {j.get('score', '?')} ({tirs}). " + ("; ".join(faits) + "." if faits else "")).strip()
    return {"pourquoi": pourquoi, "previsible": previsible, "signal_rate": "", "tags": sorted(set(tags)),
            "lecon": lecon, "source": "espn"}
