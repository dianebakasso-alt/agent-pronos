"""La mémoire de l'agent.

1. Apprentissage : il compte ses résultats (par championnat, type de pari, tranche de cote,
   avis de l'IA) et durcit ses critères là où il perd — seulement quand il y a assez de matchs
   pour que ce ne soit pas du hasard.
2. Actu : ce que l'IA a appris sur chaque équipe, gardé 21 jours.
"""
import json
from datetime import datetime, timedelta, timezone

# règles prudentes : en dessous de ces volumes, on observe sans rien changer
MIN_DURCIR = 30      # paris réglés dans un championnat avant de durcir
ROI_DURCIR = -0.15   # rendement sous lequel on exige +2 points d'avantage
MIN_PAUSE = 50
ROI_PAUSE = -0.25    # rendement sous lequel on met le championnat en pause
JOURS_ACTU = 21


def _unite(h):
    """Gain pour 1 € misé (mise identique partout, pour comparer honnêtement)."""
    return (h["cote"] - 1) if h["statut"] == "gagné" else -1.0


def _segment(paris):
    n = len(paris)
    g = sum(1 for h in paris if h["statut"] == "gagné")
    roi = sum(_unite(h) for h in paris) / n if n else None
    attendu = sum(h.get("proba", 1 / h["cote"]) for h in paris)
    return {"n": n, "gagnes": g, "roi": roi, "gagnes_attendus": round(attendu, 1)}


def _tranche(cote):
    return "cote < 2" if cote < 2 else "cote 2 à 3" if cote < 3 else "cote 3 à 4" if cote < 4 else "cote 4 et +"


def apprendre(historique, combines):
    regles = [h for h in historique if h["statut"] in ("gagné", "perdu")]
    joues = [h for h in regles if h.get("joue", True)]

    def grouper(cle, paris):
        g = {}
        for h in paris:
            g.setdefault(cle(h), []).append(h)
        return {k: _segment(v) for k, v in sorted(g.items(), key=lambda kv: -len(kv[1]))}

    par_champ = grouper(lambda h: h.get("championnat") or h["sport_key"], joues)
    par_cle = {}
    for h in joues:
        par_cle.setdefault(h["sport_key"], []).append(h)

    ajustements, lecons = {}, []
    for cle, ps in par_cle.items():
        s = _segment(ps)
        nom = ps[0].get("championnat") or cle
        if s["n"] >= MIN_PAUSE and s["roi"] < ROI_PAUSE:
            ajustements[cle] = {"pause": True}
            lecons.append(f"⛔ {nom} mis en pause : {s['n']} paris, rendement {s['roi']:+.0%}.")
        elif s["n"] >= MIN_DURCIR and s["roi"] < ROI_DURCIR:
            ajustements[cle] = {"edge_bonus": 2}
            lecons.append(f"⚠️ {nom} : critères durcis (+2 pts d'avantage exigés), rendement {s['roi']:+.0%} sur {s['n']} paris.")
        elif s["n"] >= MIN_DURCIR and s["roi"] > 0.05:
            lecons.append(f"✅ {nom} réussit bien : {s['roi']:+.0%} sur {s['n']} paris.")

    # l'avis de l'IA est-il utile ? on compare les paris qu'elle a déconseillés et les autres
    par_avis = grouper(lambda h: h.get("avis") or "sans avis", regles)
    ev, ok = par_avis.get("eviter"), par_avis.get("confirme")
    if ev and ok and ev["n"] >= 15 and ok["n"] >= 15:
        if ev["roi"] < ok["roi"]:
            lecons.append(f"🤖 Les avis « À éviter » de l'IA sont utiles : {ev['roi']:+.0%} contre {ok['roi']:+.0%} quand elle confirme.")
        else:
            lecons.append(f"🤖 Les avis « À éviter » ne font pas mieux pour l'instant ({ev['roi']:+.0%} contre {ok['roi']:+.0%}).")

    cb = [c for c in combines if c["statut"] in ("gagné", "perdu")]
    if len(cb) >= 20:
        r = sum((c["cote"] - 1) if c["statut"] == "gagné" else -1 for c in cb) / len(cb)
        lecons.append(f"🎟️ Combinés : {r:+.0%} de rendement sur {len(cb)} tickets.")

    if not lecons:
        lecons.append(f"📒 {len(regles)} paris réglés pour l'instant. L'agent observe : il ne change ses "
                      f"critères qu'après {MIN_DURCIR} paris dans un même championnat.")

    return {
        "maj": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": _segment(joues),
        "par_championnat": par_champ,
        "par_issue": grouper(lambda h: {"1": "Victoire domicile", "N": "Match nul", "2": "Victoire extérieur"}[h["court"]], joues),
        "par_cote": grouper(lambda h: _tranche(h["cote"]), joues),
        "par_avis": par_avis,
        "ajustements": ajustements,
        "lecons": lecons,
    }


# ---------------------------------------------------------------- mémoire de l'actu
def _cle_equipe(nom):
    return nom.strip().lower()


def actu_connue(memo, equipe, maintenant):
    limite = maintenant - timedelta(days=JOURS_ACTU)
    faits = memo.get(_cle_equipe(equipe), {}).get("faits", [])
    return [f for f in faits if datetime.fromisoformat(f["date"]) >= limite.replace(tzinfo=None)]


def texte_memoire(memo, dom, ext, maintenant):
    lignes = []
    for eq in (dom, ext):
        for f in actu_connue(memo, eq, maintenant)[-6:]:
            lignes.append(f"- {eq} ({f['date'][:10]}) : {f['texte']}")
    if not lignes:
        return ""
    return ("Ce que tu avais déjà appris les jours précédents (vérifie si c'est toujours vrai) :\n"
            + "\n".join(lignes))


def retenir(memo, a_retenir, maintenant):
    """Ajoute les faits durables renvoyés par l'IA et oublie ce qui a plus de 21 jours."""
    jour = maintenant.strftime("%Y-%m-%dT%H:%M:%S")
    for equipe, faits in (a_retenir or {}).items():
        if not isinstance(faits, list):
            continue
        e = memo.setdefault(_cle_equipe(equipe), {"nom": equipe, "faits": []})
        connus = {f["texte"].lower() for f in e["faits"]}
        for t in faits[:4]:
            t = str(t).strip()[:200]
            if t and t.lower() not in connus:
                e["faits"].append({"date": jour, "texte": t})
    limite = (maintenant - timedelta(days=JOURS_ACTU)).replace(tzinfo=None)
    for k in list(memo):
        memo[k]["faits"] = [f for f in memo[k]["faits"] if datetime.fromisoformat(f["date"]) >= limite][-12:]
        if not memo[k]["faits"]:
            del memo[k]
    return memo


def charger(chemin, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return defaut
