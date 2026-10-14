"""Fabrique la page web (une seule page, pensée pour le téléphone)."""
import json
import shutil
from collections import OrderedDict
from pathlib import Path
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from moteur import LIBELLES_BUTS
from ecussons import championnat, couleur_ligue, ecusson

PARIS = ZoneInfo("Europe/Paris")
JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


NOMS_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def nom_jour(cle):
    d = datetime.strptime(cle, "%Y-%m-%d")
    return f"{NOMS_JOURS[d.weekday()]} {d.day}"


def e(x):
    return escape(str(x))


def heure(iso_str):
    d = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(PARIS)
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} · {d:%H:%M}"


def euros(x, signe=False):
    s = f"{x:+.2f}" if signe else f"{x:.2f}"
    return s.replace(".", ",").replace(",00", "") + " €"


def pct(x, signe=False):
    return (f"{x * 100:+.1f}" if signe else f"{x * 100:.0f}").replace(".", ",") + " %"


BOUTON_JOUE = """<div class="joue"><button class="btn-joue" onclick="ouvrirJoue(this)">✍️ J'ai joué ce pari</button>
      <div class="joue-f" hidden><label>Mise <input type="number" inputmode="decimal" step="0.5" min="0" class="j-mise"> €</label>
        <label>Cote <input type="number" inputmode="decimal" step="0.01" min="1" class="jj-cote"></label>
        <button onclick="enregistrerJoue(this)">Enregistrer</button></div></div>"""

AVIS = {
    "confirme": ("ok", "L'actu confirme"),
    "prudence": ("warn", "Prudence"),
    "eviter": ("bad", "À éviter"),
}


def barre_probas(m, surligne=None):
    segs = ""
    for i in m["issues"]:
        cls = {"1": "s1", "N": "sn", "2": "s2"}[i["court"]]
        on = " on" if i["court"] == surligne else ""
        lab = f'<em>{i["court"]} · {pct(i["proba"])}</em>' if i["proba"] >= 0.13 else ""
        segs += f'<span class="{cls}{on}" style="flex:{i["proba"]:.3f}">{lab}</span>'
    return f'<div class="barre-p">{segs}</div>'


def favori(m):
    """'1' ou '2' si une équipe est nettement favorite, sinon None."""
    p = {i["court"]: i["proba"] for i in m["issues"]}
    if not p:
        return None
    k = max(p, key=p.get)
    return k if k in ("1", "2") and p[k] >= 0.40 else None


def affiche(m, grand=False):
    t = 56 if grand else 42
    d = datetime.fromisoformat(m["debut"].replace("Z", "+00:00")).astimezone(PARIS)
    jour = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"
    esp = m.get("espn") or {}
    data = (f' data-espn="{e(esp["ligue"])}|{e(esp["id"])}"' if esp else "") + f' data-mid="{e(m["id"])}" data-dom="{e(m["domicile"])}" data-ext="{e(m["exterieur"])}" data-ko="{e(m["debut"])}"'
    fav = favori(m)
    pr = {i["court"]: i["proba"] for i in m["issues"]}

    def cote_eq(nom, k):
        f = fav == k
        pill = f'<em class="pill">⭐ Favori {pct(pr[k])}</em>' if f else f'<em class="pill pill-o">{pct(pr.get(k, 0))}</em>'
        return f"""<div class="eq eq{k}{' fav' if f else ''}"><div class="ecu-w">{ecusson(nom, t)}</div><span>{e(nom)}</span>{pill}</div>"""

    return f"""<div class="affiche{' grande' if grand else ''}"{data}>
        {cote_eq(m["domicile"], "1")}
        <div class="ko"><i class="vs">VS</i><b class="ko-h">{d:%H:%M}</b><small class="ko-j">{jour}</small><em class="cd" data-ko="{e(m["debut"])}"></em></div>
        {cote_eq(m["exterieur"], "2")}
      </div>"""


def tag_champ(m):
    drap, nom = championnat(m.get("sport_key", ""), m["championnat"])
    return f'<span class="champ"><i>{drap}</i>{e(nom)}</span>'


def _nb(v):
    return f"{v:.1f}".replace(".", ",")


def _forme_txt(nom, f):
    v = f["forme"].count("V")
    n = len(f["forme"])
    if not n:
        return ""
    if v >= 4 or f["points"] >= 11:
        return f"{nom} est en forme ({v} victoires sur {n})"
    if v == 0 and f["forme"].count("N") <= 1:
        return f"{nom} est en crise (aucune victoire sur {n})"
    if v <= 1:
        return f"{nom} gagne peu ({v} victoire sur {n})"
    return ""


def pourquoi_1n2(m, court, cote=None, bk=None, valeur=True):
    """Une à deux phrases simples qui expliquent un pari 1-N-2."""
    i = next((x for x in m["issues"] if x["court"] == court), None)
    if not i:
        return ""
    p = i["proba"]
    morceaux = []
    if valeur and cote:
        morceaux.append(f"La cote {cote:.2f}{' chez ' + bk if bk else ''} paie plus que le vrai risque : "
                        f"{pct(p)} de chances, soit une cote juste de {1 / p:.2f}")
    else:
        morceaux.append(f"{pct(p)} de chances selon le marché")
    st, b = m.get("stats"), m.get("buts")
    if st:
        d, x, f = st["domicile"], st["exterieur"], st["face"]
        if court in ("1", "2"):
            (moi, fm), (lui, fl) = ((m["domicile"], d), (m["exterieur"], x)) if court == "1" else ((m["exterieur"], x), (m["domicile"], d))
            t_moi, t_lui = _forme_txt(moi, fm), _forme_txt(lui, fl)
            morceaux += [z for z in (t_moi if "est en forme" in t_moi else "", t_lui if "crise" in t_lui or "gagne peu" in t_lui else "") if z]
        else:
            if f["n"] >= 3 and f["nuls"] >= 2:
                morceaux.append(f"face-à-face serrés : {f['nuls']} nuls sur les {f['n']} derniers")
            if abs(d["points"] - x["points"]) <= 3 and d["forme"] and x["forme"]:
                morceaux.append("deux équipes de niveau proche en ce moment")
    if court == "N" and b and b["total"] < 2.45:
        morceaux.append(f"peu de buts attendus ({_nb(b['total'])})")
    a = (m.get("avis") or {}).get("avis")
    if a == "confirme":
        morceaux.append("l'actu va dans le même sens")
    elif a == "eviter":
        morceaux.append("mais l'actu le déconseille")
    texte = " ; ".join(morceaux[:3])
    return texte[0].upper() + texte[1:] + "." if texte else ""


def pourquoi_buts(m, marche):
    b, st = m.get("buts"), m.get("stats")
    if not b:
        return ""
    if marche in ("plus25", "btts", "plus15"):
        t = f"{_nb(b['total'])} buts attendus ({_nb(b['lh'])} pour {m['domicile']}, {_nb(b['la'])} pour {m['exterieur']})"
        if st and min(st["domicile"]["buts_pour"], st["exterieur"]["buts_pour"]) >= 1.3:
            t += " ; les deux attaques marquent régulièrement"
    else:
        t = f"seulement {_nb(b['total'])} buts attendus : match plutôt fermé"
        if st and max(st["domicile"]["buts_contre"], st["exterieur"]["buts_contre"]) <= 1.0:
            t += " ; deux défenses solides"
    return t[0].upper() + t[1:] + "."


def carte_value(m):
    v = m["value"]
    avis_html = ""
    a = m.get("avis")
    if a:
        cls, titre = AVIS.get(a.get("avis"), AVIS["prudence"])
        points = "".join(f"<li>{e(p)}</li>" for p in a.get("points", [])[:5])
        avis_html = f"""
      <div class="avis {cls}">
        <div class="avis-t">{titre}</div>
        <p>{e(a.get("resume", ""))}</p>
        {f'<ul>{points}</ul>' if points else ''}
      </div>"""
    return f"""
    <article style="--lig:{couleur_ligue(m.get('sport_key', ''))}" class="carte value{' barre' if a and a.get('avis') == 'eviter' else ''}" data-poids="{0 if a and a.get('avis') == 'eviter' else v['mise']}" data-cote="{v['cote']:.2f}" data-pari="{e(json.dumps({"type": "simple", "id": m["id"], "date": m["debut"], "match": m["domicile"] + " – " + m["exterieur"], "pari": v["issue"], "court": v["court"], "cote": v["cote"], "bk": v["bookmaker"]}, ensure_ascii=False))}">
      <div class="meta">{tag_champ(m)}<span class="badge c-{e(v["confiance"]).lower()}">Confiance {e(v["confiance"]).lower()}</span></div>
      {affiche(m, grand=True)}
      {barre_probas(m, v["court"])}
      {bloc_stats(m)}
      {bloc_buts(m)}
      <div class="pari">
        <div><div class="lbl">Le pari</div><div class="choix">{e(v["issue"])}</div></div>
        <div class="cote"><div class="lbl">Cote</div><div class="num">{v["cote"]:.2f}</div>
          <div class="bk">chez {e(v["bookmaker"])}</div></div>
      </div>
      <div class="calc" hidden></div>
      <div class="grille">
        <div><span>Proba marché</span><b>{pct(v["proba"])}</b></div>
        <div><span>Cote juste</span><b>{v["cote_juste"]:.2f}</b></div>
        <div><span>Avantage</span><b class="vert">{pct(v["edge"], True)}</b></div>
      </div>
      <p class="pq">💡 {e(pourquoi_1n2(m, v["court"], v["cote"], v["bookmaker"]))}</p>
      <div class="src">Réf. : {e(m["source_proba"])} · {m["nb_bookmakers"]} bookmakers comparés</div>{avis_html}
      {BOUTON_JOUE}
    </article>"""


def ligne_match(m):
    vcourt = m["value"]["court"] if m["value"] else None
    cases = ""
    for i in m["issues"]:
        cls = "case val" if i["court"] == vcourt else "case"
        if i["court"] == favori(m):
            cls += " fav"
        cases += f"""<button class="{cls}" data-ajout="{e(m["id"])}|{i["court"]}"><span class="k">{i["court"]}</span>
          <b>{i["cote"]:.2f}</b><span class="p">{pct(i["proba"])}</span></button>"""
    buts = ""
    if m.get("buts"):
        buts = '<div class="ajout-buts">' + "".join(
            f'<button data-ajout="{e(m["id"])}|{k}">{lbl}</button>'
            for k, lbl in (("plus25", "+2,5 buts"), ("moins25", "−2,5 buts"), ("btts", "Les 2 marquent"), ("pas_btts", "Pas les 2"))) + "</div>"
    jm = datetime.fromisoformat(m["debut"].replace("Z", "+00:00")).astimezone(PARIS).strftime("%Y-%m-%d")
    return f"""
      <div class="match" data-jour="{jm}">
        {affiche(m)}
        {barre_probas(m, vcourt)}
        {bloc_stats(m, compact=True)}
        {bloc_buts(m, compact=True)}
        <div class="cases">{cases}</div>
        {buts}
      </div>"""


def avis_jambe(j):
    a = j.get("avis")
    if not a:
        return ""
    cls, titre = AVIS.get(a.get("avis"), AVIS["prudence"])
    return f"""<li class="avis-j {cls}"><b>{titre} :</b> {e(a.get("resume", ""))}</li>"""


def carte_combine_estime(c, jour):
    style = c["style"]
    jambes = ""
    for j in c["jambes"]:
        m = j["match"]
        etiquette = "⚽" if j["type"] == "buts" else "🎯"
        jambes += f"""<li>{ecusson(m["domicile"], 26)}{ecusson(m["exterieur"], 26)}
          <div class="j-txt"><b>{etiquette} {e(j["issue"])}</b><small>{e(m["domicile"])} – {e(m["exterieur"])} · {heure(m["debut"])}</small>
          <small class="pq-j">💡 {e(pourquoi_buts(m, j["marche"]) if j["type"] == "buts" else pourquoi_1n2(m, j["court"], valeur=False))}</small></div>
          <span class="j-cote">{pct(j["proba"])}</span></li>"""
    legs = [{"id": j["match"]["id"], **({"marche": j["marche"]} if j["type"] == "buts" else {"court": j["court"]}),
             "pari": j["issue"]} for j in c["jambes"]]
    pari = {"type": "combine", "id": f"combo-{style}-{c['jambes'][0]['match']['id']}", "date": c["jambes"][0]["match"]["debut"],
            "match": " + ".join(j["match"]["domicile"] + " – " + j["match"]["exterieur"] for j in c["jambes"]),
            "pari": f"Combiné {c['nom']} · {len(c['jambes'])} matchs", "cote": round(c["cote_cible"], 2), "bk": "ton bookmaker", "jambes": legs}
    return f"""
    <article class="carte combo st-{style} estime" id="combo-{jour}-{style}" data-style="{style}" data-nom="{e(c['nom'])}" data-cote="{c['cote_cible']:.4f}" data-pari="{e(json.dumps(pari, ensure_ascii=False))}">
      <div class="combo-t"><span class="ct"><i class="ct-e">{c["emoji"]}</i> <span class="ct-n">{e(c["nom"])}</span></span><span class="badge c-moyenne">À vérifier</span></div>
      <p class="combo-desc">{e(c["desc"])}</p>
      <div class="chance"><div class="chance-b"><span style="width:{max(3, round(c["proba"] * 100))}%"></span></div>
        <b>{pct(c["proba"])}</b><small>de chances que ça passe</small></div>
      <ul class="jambes">{jambes}</ul>
      <div class="pari">
        <div><div class="lbl">Cote juste du ticket</div><div class="choix">{c["cote_juste"]:.2f}</div></div>
        <div class="cote"><div class="lbl">Prends-le à</div><div class="num">{c["cote_cible"]:.2f}+</div></div>
      </div>
      <div class="calc" hidden></div>
      <p class="src combo-note">L'agent n'a pas les cotes des bookmakers pour les paris de buts. Compose ce ticket chez ton bookmaker :
        <b>s'il te propose {c["cote_cible"]:.2f} ou plus</b>, le ticket vaut le coup ; en dessous, passe. Le gain affiché est calculé à {c["cote_cible"]:.2f}.</p>
      {BOUTON_JOUE}
    </article>"""


def carte_combine(c, jour=""):
    if not c:
        return """<article class="carte combo vide-c"><div class="combo-t">🎟️ Pas de combiné aujourd'hui</div>
      <p class="src">Pas assez de matchs avec des cotes correctes chez un même bookmaker.</p></article>"""
    if c.get("estime"):
        return carte_combine_estime(c, jour)
    jambes = ""
    for j in c["jambes"]:
        m = j["match"]
        jambes += f"""<li>{ecusson(m["domicile"], 26)}{ecusson(m["exterieur"], 26)}
          <div class="j-txt"><b>{e(j["issue"])}</b><small>{e(m["domicile"])} – {e(m["exterieur"])} · {heure(m["debut"])}</small>
          <small class="pq-j">💡 {e(pourquoi_1n2(m, j["court"], j["cote"], None, valeur=j.get("edge", 0) > 0))}</small></div>
          <span class="j-cote">{j["cote"]:.2f}</span></li>{avis_jambe(j)}"""
    style = c.get("style", "equilibre")
    if c.get("estime"):
        return carte_combine_estime(c, jour)
    badge = '<span class="badge c-bonne">Conseillé</span>' if c["conseille"] else '<span class="badge c-risque">Non conseillé</span>'
    entete = f"""<div class="combo-t"><span class="ct"><i class="ct-e">{c.get("emoji", "🎟️")}</i> <span class="ct-n">{e(c.get("nom", "Combiné"))}</span></span>{badge}</div>
      <p class="combo-desc">{e(c.get("desc", ""))}</p>
      <div class="chance"><div class="chance-b"><span style="width:{max(3, round(c["proba"] * 100))}%"></span></div>
        <b>{pct(c["proba"])}</b><small>de chances que ça passe</small></div>"""
    if c["conseille"]:
        note = f'Chaque match a un avantage chez {e(c["bookmaker"])} : le ticket garde un avantage de <b class="vert">{pct(c["edge"], True)}</b>.'
    else:
        perte = -c["edge"] * 10
        note = (f'Pas de ticket rentable dans ce style aujourd\'hui. Celui-ci est le moins coûteux, mais sur la durée '
                f'il fait perdre environ <b class="rouge">{euros(perte)} pour 10 € joués</b>. À toi de voir.')
    return f"""
    <article class="carte combo st-{style}{'' if c['conseille'] else ' risque'}" id="combo-{jour}-{style}" data-style="{style}" data-nom="{e(c.get('nom', 'Combiné'))}" data-cote="{c['cote']:.4f}" data-pari="{e(json.dumps({"type": "combine", "id": "combo-" + style + "-" + c["jambes"][0]["match"]["id"], "date": c["jambes"][0]["match"]["debut"], "match": " + ".join(j["match"]["domicile"] + " – " + j["match"]["exterieur"] for j in c["jambes"]), "pari": "Combiné " + c.get("nom", "") + " · " + str(len(c["jambes"])) + " matchs", "cote": round(c["cote"], 2), "bk": c["bookmaker"], "jambes": [{"id": j["match"]["id"], "court": j["court"], "pari": j["issue"]} for j in c["jambes"]]}, ensure_ascii=False))}">
      {entete}
      <ul class="jambes">{jambes}</ul>
      <div class="pari">
        <div><div class="lbl">Cote du ticket</div><div class="choix">{len(c["jambes"])} matchs chez {e(c["bookmaker"])}</div></div>
        <div class="cote"><div class="lbl">Cote</div><div class="num">{c["cote"]:.2f}</div></div>
      </div>
      <div class="calc" hidden></div>
      <div class="grille">
        <div><span>Chance que ça passe</span><b>{pct(c["proba"])}</b></div>
        <div><span>Soit environ</span><b>1 fois sur {max(1, round(1 / c["proba"]))}</b></div>
        <div><span>Avantage</span><b class="{'vert' if c['edge'] > 0 else 'rouge'}">{pct(c["edge"], True)}</b></div>
      </div>
      <p class="src combo-note">{note}</p>
      {BOUTON_JOUE}
    </article>"""


def bloc_buts(m, compact=False):
    b = m.get("buts")
    if not b:
        return ""
    nb = lambda v: f"{v:.1f}".replace(".", ",")
    if compact:
        return f"""<div class="buts compact">⚽ <b>{nb(b["total"])}</b> buts attendus · +2,5&nbsp;: <b>{pct(b["plus25"])}</b> · Les 2 marquent&nbsp;: <b>{pct(b["btts"])}</b></div>"""
    score = " · ".join(f"{e(sc)} <small>{pct(p)}</small>" for sc, p in b["scores"])
    return f"""<div class="buts">
        <div class="buts-t">⚽ Les buts <small>{nb(b["lh"])} – {nb(b["la"])} attendus</small></div>
        <div class="buts-g">
          <div><span>+1,5</span><b>{pct(b["plus15"])}</b></div>
          <div><span>+2,5</span><b>{pct(b["plus25"])}</b></div>
          <div><span>+3,5</span><b>{pct(b["plus35"])}</b></div>
          <div><span>Les 2 marquent</span><b>{pct(b["btts"])}</b></div>
        </div>
        <div class="buts-s">Scores les plus probables : {score}</div>
      </div>"""


def carte_buts(c, jour):
    m = c["match"]
    pari = {"type": "buts", "id": m["id"], "date": m["debut"], "match": m["domicile"] + " – " + m["exterieur"],
            "pari": c["libelle"], "marche": c["marche"], "cote": c["cote_cible"], "bk": "ton bookmaker"}
    return f"""
    <article class="carte prono-buts" style="--lig:{couleur_ligue(m.get('sport_key', ''))}" data-pari="{e(json.dumps(pari, ensure_ascii=False))}">
      <div class="meta">{tag_champ(m)}<span class="badge c-bonne">{pct(c["proba"])} de chances</span></div>
      {affiche(m)}
      <p class="pq">💡 {e(pourquoi_buts(m, c["marche"]))}</p>
      <div class="pb-pari"><b>{e(c["libelle"])}</b>
        <span>Cote juste <b>{c["cote_juste"]:.2f}</b> · joue-le seulement si ton bookmaker propose <b class="vert">{c["cote_cible"]:.2f} ou plus</b></span></div>
      {bloc_buts(m, compact=True)}
      {BOUTON_JOUE}
    </article>"""


def pastilles(forme):
    return "".join(f'<i class="f-{x}">{x}</i>' for x in forme) or '<small>—</small>'


def bloc_stats(m, compact=False):
    st = m.get("stats")
    if not st:
        return ""
    d, x, f = st["domicile"], st["exterieur"], st["face"]
    ligne_forme = f"""<div class="st-l"><div class="pas">{pastilles(d["forme"])}</div><span>Forme</span>
        <div class="pas r">{pastilles(x["forme"])}</div></div>"""
    if compact:
        return f'<div class="stats compact">{ligne_forme}</div>'
    def nb(v):
        return f"{v:.1f}".replace(".", ",")
    face = ""
    if f["n"]:
        face = f"""<div class="st-l"><b>{f["v_dom"]}</b><span>Face-à-face ({f["n"]} derniers) · {f["nuls"]} nul{'s' if f["nuls"] > 1 else ''}</span><b>{f["v_ext"]}</b></div>"""
    return f"""<div class="stats">
        {ligne_forme}
        <div class="st-l"><div class="pas">{pastilles(d["forme_lieu"])}</div><span>À dom. / à l'ext.</span>
          <div class="pas r">{pastilles(x["forme_lieu"])}</div></div>
        <div class="st-l"><b>{nb(d["buts_pour"])}</b><span>Buts marqués / match</span><b>{nb(x["buts_pour"])}</b></div>
        <div class="st-l"><b>{nb(d["buts_contre"])}</b><span>Buts encaissés / match</span><b>{nb(x["buts_contre"])}</b></div>
        {face}
      </div>"""


def section_appris(a):
    if not a:
        return ""
    lecons = "".join(f"<li>{e(l)}</li>" for l in a["lecons"])
    lignes = ""
    for nom, sg in list(a["par_championnat"].items())[:8]:
        roi = pct(sg["roi"], True) if sg["roi"] is not None else "—"
        cls = "vert" if (sg["roi"] or 0) >= 0 else "rouge"
        nom = championnat(nom, nom)[1] if nom.startswith("soccer_") else nom
        lignes += f"""<tr><td>{e(nom)}<small>{sg["gagnes"]} gagnés sur {sg["n"]} · {sg["gagnes_attendus"]} attendus</small></td>
          <td class="r"><b class="{cls}">{roi}</b></td></tr>"""
    tableau = f'<table class="hist">{lignes}</table>' if lignes else ""
    return f"""<ul class="lecons">{lecons}</ul>{tableau}"""


def section_combines(cs, bc):
    if not cs:
        return '<p class="vide">Le suivi des combinés commence demain matin.</p>'
    def roi(x):
        return pct(x["roi"], True) if x["roi"] is not None else "—"
    t, k = bc["tous"], bc["conseilles"]
    cls = "vert" if t["benefice"] >= 0 else "rouge"
    lignes = ""
    for c in sorted(cs, key=lambda c: c["jour"], reverse=True)[:15]:
        st = {"gagné": "ok", "perdu": "bad"}.get(c["statut"], "att")
        j_txt = " + ".join(f'{"✅" if j.get("ok") else "❌" if j.get("ok") is False else "⏳"} {e(j["pari"])}' for j in c["jambes"])
        tag = "" if c["conseille"] else ' <span class="c-risque">· non conseillé</span>'
        lignes += f"""<tr><td>{e(c["jour"][8:10])}/{e(c["jour"][5:7])} · cote {c["cote"]:.2f}{tag}<small>{j_txt}</small></td>
          <td class="r"><span class="st {st}">{e(c["statut"])}</span><small>{euros(c["gain"], True) if c["statut"] != "en attente" else ""}</small></td></tr>"""
    return f"""
    <p class="note">Comme si tu avais misé <b>10 € chaque jour</b> sur le combiné de l'agent.</p>
    <div class="bilan">
      <div><span>Tickets réglés</span><b>{t["nb"]}</b></div>
      <div><span>Passés</span><b>{t["gagnes"]}</b></div>
      <div><span>Bénéfice</span><b class="{cls}">{euros(t["benefice"], True)}</b></div>
      <div><span>Rendement</span><b class="{cls}">{roi(t)}</b></div>
    </div>
    <p class="note">Seulement les combinés <b>conseillés</b> : {k["nb"]} ticket{'s' if k["nb"] > 1 else ''}, {k["gagnes"]} passé{'s' if k["gagnes"] > 1 else ''}, bénéfice <b class="{'vert' if k['benefice'] >= 0 else 'rouge'}">{euros(k["benefice"], True)}</b> ({roi(k)}).</p>
    <table class="hist">{lignes}</table>"""


def _courbe_svg(pts, w=340, h=90):
    if len(pts) < 2:
        return ""
    vals = [0.0] + pts
    lo, hi = min(vals + [0]), max(vals + [0])
    rng = (hi - lo) or 1
    xs = lambda i: round(i * w / (len(vals) - 1), 1)
    ys = lambda v: round(h - 6 - (v - lo) * (h - 12) / rng, 1)
    ligne = " ".join(f"{xs(i)},{ys(v)}" for i, v in enumerate(vals))
    zero = ys(0)
    coul = "var(--ok)" if vals[-1] >= 0 else "var(--bad)"
    return f"""<svg class="courbe" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-label="Évolution du bénéfice">
      <defs><linearGradient id="cb-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{coul}" stop-opacity=".35"/><stop offset="1" stop-color="{coul}" stop-opacity="0"/></linearGradient></defs>
      <line x1="0" y1="{zero}" x2="{w}" y2="{zero}" stroke="var(--line)" stroke-dasharray="4 4"/>
      <polygon points="0,{zero} {ligne} {w},{zero}" fill="url(#cb-g)"/>
      <polyline points="{ligne}" fill="none" stroke="{coul}" stroke-width="2.5" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    </svg>"""


def section_expert(t):
    from expert import CATEGORIES, SEUIL_JUGER
    if not t:
        return ""
    tot = t["total"]
    n = tot["n"]
    roi = tot["roi"]
    if n == 0:
        verdict, vcls, vtxt = "⏳ Le compteur démarre", "att", (
            f"L'expert note chacun de ses pronos dès aujourd'hui ({t['en_attente']} en attente). "
            "Les premiers résultats tombent après les matchs.")
    elif n < SEUIL_JUGER:
        verdict, vcls = "🔍 Trop tôt pour juger", "att"
        vtxt = f"{n} pronos réglés sur {SEUIL_JUGER} minimum. Sur si peu, la chance pèse plus que le talent."
    elif roi >= 0:
        verdict, vcls, vtxt = "🏆 Dans le vert : c'est un expert", "ok", f"Sur {n} pronos, il gagne de l'argent."
    else:
        verdict, vcls, vtxt = "📉 Dans le rouge pour l'instant", "bad", f"Sur {n} pronos, il perd de l'argent : il s'ajuste."
    cls = "vert" if tot["benefice"] >= 0 else "rouge"
    reussite = f"{tot['gagnes'] / n * 100:.0f} %" if n else "—"
    attendu = f"{tot['attendus'] / n * 100:.0f} %" if n else "—"
    mieux = ""
    if n >= 10:
        d = tot["gagnes"] - tot["attendus"]
        mieux = (f'<p class="note">Il a trouvé <b class="vert">{d:+.0f} bons pronos de plus</b> que ce que les cotes prévoyaient.</p>' if d > 0.5
                 else f'<p class="note">Il a trouvé <b class="rouge">{d:+.0f} bons pronos</b> par rapport à ce que les cotes prévoyaient.</p>' if d < -0.5
                 else '<p class="note">Il trouve autant de bons pronos que ce que les cotes prévoyaient.</p>')
    lignes = ""
    for k, (emo, nom) in CATEGORIES.items():
        s = t["par_cat"].get(k) or {}
        if not s.get("n"):
            continue
        c = "vert" if s["benefice"] >= 0 else "rouge"
        lignes += f"""<tr><td>{emo} {e(nom)}<small>{s["gagnes"]} réussis sur {s["n"]}</small></td>
          <td class="r"><b class="{c}">{euros(s["benefice"], True)}</b><small>{pct(s["roi"], True) if s["roi"] is not None else "—"}</small></td></tr>"""
    derniers = ""
    for p in t["derniers"][:8]:
        emo = CATEGORIES.get(p["cat"], ("•", ""))[0]
        jb = " + ".join(f'{"✅" if j.get("ok") else "❌" if j.get("ok") is False else "➖"} {e(j["pari"])}'
                        + (f' <i>({e(j["score"])})</i>' if j.get("score") else "") for j in p["jambes"])
        st = "ok" if p["statut"] == "gagné" else "bad"
        derniers += f"""<tr><td>{emo} {e(p["jour"][8:10])}/{e(p["jour"][5:7])} · cote {p["cote"]:.2f}<small>{jb}</small></td>
          <td class="r"><span class="st {st}">{euros(p["gain"], True)}</span></td></tr>"""
    s7 = t["sept_jours"]
    return f"""
    <div class="ex-carte ex-{vcls}">
      <div class="ex-t">L'expert est-il vraiment un expert ?</div>
      <div class="ex-v">{verdict}</div>
      <p class="ex-p">{vtxt}</p>
      <div class="ex-gros"><b class="{cls}">{euros(tot["benefice"], True)}</b><span>de bénéfice si tu avais misé <b>10 € sur chaque prono</b></span></div>
      {_courbe_svg(t["courbe"])}
      <div class="bilan">
        <div><span>Pronos réglés</span><b>{n}</b></div>
        <div><span>Réussite</span><b>{reussite}</b></div>
        <div><span>Prévue par les cotes</span><b>{attendu}</b></div>
        <div><span>Rendement</span><b class="{cls}">{pct(roi, True) if roi is not None else "—"}</b></div>
      </div>
      {mieux}
      <p class="note">7 derniers jours : <b>{s7["n"]}</b> pronos, <b class="{'vert' if s7['benefice'] >= 0 else 'rouge'}">{euros(s7["benefice"], True)}</b> · {t["en_attente"]} en attente de résultat.</p>
    </div>
    <div id="toi-bilan"></div>
    {f'<h3 class="sous">Par type de prono</h3><table class="hist">{lignes}</table>' if lignes else ''}
    {f'<h3 class="sous">Derniers résultats</h3><table class="hist">{derniers}</table>' if derniers else ''}
    <p class="note">Le rendement, c'est le bénéfice pour 100 € misés. Un vrai expert se juge sur des centaines de pronos : un bon ou un mauvais soir ne veut rien dire.</p>"""


def _quand(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS)
    return f"{JOURS[d.weekday()]} {d.day} · {d:%H:%M}"


def carte_ticket(tk, style, emoji, nom, desc, badge):
    jambes = ""
    for j in tk["jambes"]:
        a = j.get("avis") or {}
        cls, titre = AVIS.get(a.get("avis"), ("att", "Analyse IA à venir"))
        jambes += f"""<li>{ecusson(j["domicile"], 26)}{ecusson(j["exterieur"], 26)}
          <div class="j-txt"><b>{e(j["issue"])}</b><small>{e(j["domicile"])} – {e(j["exterieur"])} · {_quand(j["debut"])}</small>
          <small class="pq-j">🤖 <b class="sm-{cls}">{titre}</b>{' : ' + e(a.get("resume", "")) if a.get("resume") else ''}</small></div>
          <span class="j-cote">{j["cote_t"]:.2f}</span></li>"""
    pari = {"type": "combine", "id": f"{style}-" + "-".join(j["id"][:6] for j in tk["jambes"]), "date": tk["jambes"][0]["debut"],
            "match": " + ".join(j["domicile"] + " – " + j["exterieur"] for j in tk["jambes"]),
            "pari": f"{nom} · {len(tk['jambes'])} matchs", "cote": round(tk["cote"], 2), "bk": tk["bookmaker"],
            "jambes": [{"id": j["id"], "court": j["court"], "pari": j["issue"]} for j in tk["jambes"]]}
    return f"""
    <article class="carte combo st-{style}" data-style="{style}" data-cote="{tk['cote']:.4f}" data-pari="{e(json.dumps(pari, ensure_ascii=False))}">
      <div class="combo-t"><span class="ct"><i class="ct-e">{emoji}</i> <span class="ct-n">{e(nom)}</span></span><span class="badge c-forte">{e(badge)}</span></div>
      <p class="combo-desc">{e(desc)}</p>
      <div class="chance"><div class="chance-b"><span style="width:{max(3, round(tk["proba"] * 100))}%"></span></div>
        <b>{pct(tk["proba"])}</b><small>de chances que ça passe</small></div>
      <ul class="jambes">{jambes}</ul>
      <div class="pari">
        <div><div class="lbl">Cote du ticket</div><div class="choix">{len(tk["jambes"])} matchs chez {e(tk["bookmaker"])}</div></div>
        <div class="cote"><div class="lbl">Cote</div><div class="num">{tk["cote"]:.2f}</div></div>
      </div>
      <div class="calc" hidden></div>
      {BOUTON_JOUE}
    </article>"""


NIV_CLS = {"forte": "ok", "bonne": "ok", "moyenne": "warn", "ouvert": "att"}


def resume_jour(j, bankroll):
    tk = j.get("ticket")
    jv = [m for m in j["values"] if (m.get("avis") or {}).get("avis") != "eviter"]
    pr = j.get("pronos") or {}
    par_id = {m["id"]: m for m in j["analyses"]}
    eviter = [m for m in j["analyses"] if (m.get("avis") or {}).get("avis") == "eviter"]
    pieges = [par_id[k] for k, a in pr.items() if a and a.get("piege") and k in par_id]
    lignes = []
    mise = max(1, round(bankroll * 0.02))
    if tk:
        lignes.append(f"📌 <b>Le ticket du jour</b> à <b>{tk['cote']:.2f}</b> ({pct(tk['proba'])} de chances) : mise <b>{mise} €</b> pour {bankroll} € de budget.")
    for m in jv[:2]:
        v = m["value"]
        lignes.append(f"💎 <b>{e(v['issue'])}</b> à {v['cote']:.2f} chez {e(v['bookmaker'])} : mise <b>{euros(v['mise'])}</b>.")
    if not tk:
        # pas de ticket : on nomme quand même les paris simples où l'expert a confiance
        surs = sorted([(a, par_id[k]) for k, a in pr.items() if a and k in par_id and a["niveau"] in ("forte", "bonne")
                       and not a.get("value") and not par_id[k].get("deja_commence")], key=lambda x: -x[0]["proba"])[:3]
        for a, m in surs:
            doute = " (l'IA a un doute)" if a.get("doute") else ""
            lignes.append(f"{'💪' if a['niveau'] == 'forte' else '👍'} <b>{e(a['issue'])}</b> à {a['cote']:.2f} "
                          f"({pct(a['proba'])} de chances){doute} : en simple, mise <b>{max(1, round(bankroll * 0.01))} €</b>.")
    if not lignes:
        lignes.append(f"🧘 <b>Rien de solide</b> : je ne jouerais pas {e(j['quand'])}. Garder son argent, c'est aussi gagner.")
    a_eviter = [f"{e(m['domicile'])} – {e(m['exterieur'])}" for m in (eviter + pieges)[:3]]
    ev = f'<p class="rj-ev">🚫 <b>À éviter :</b> {", ".join(a_eviter)} (favori en mauvaise forme ou mauvaise nouvelle).</p>' if a_eviter else ""
    nb_forte = sum(1 for a in pr.values() if a and a["niveau"] in ("forte", "bonne"))
    return f"""
<section class="rj">
  <div class="ex-t">🧠 Ce que je jouerais {e(j["quand"])}</div>
  <ul>{"".join(f"<li>{l}</li>" for l in lignes)}</ul>
  {ev}
  <p class="rj-n">{len(j["analyses"])} matchs étudiés · {nb_forte} où l'expert a confiance.</p>
</section>"""


def liste_avis(j):
    pr = j.get("pronos") or {}
    if not pr:
        return ""
    lignes = ""
    ordre = {"forte": 0, "bonne": 1, "moyenne": 2, "ouvert": 3}
    for m in sorted(j["analyses"], key=lambda m: (ordre.get((pr.get(m["id"]) or {}).get("niveau"), 4), m["debut"])):
        a = pr.get(m["id"])
        if not a:
            continue
        cls = NIV_CLS[a["niveau"]]
        if a["niveau"] == "ouvert":
            txt = "Trop incertain pour un pari 1-N-2."
            b = m.get("buts")
            if b and max(b["plus25"], 1 - b["plus25"]) >= 0.58:
                txt += " Piste buts : " + ("plus de 2,5 buts" if b["plus25"] >= 0.5 else "moins de 2,5 buts") + f" ({pct(max(b['plus25'], 1 - b['plus25']))})."
            pari = "Pas de pari conseillé"
        else:
            txt = pourquoi_1n2(m, a["court"], valeur=False)
            pari = f"{a['issue']} · {a['cote']:.2f}"
        ia = (m.get("avis") or {})
        ia_txt = f'<small class="av-ia">🤖 {e(ia.get("resume", ""))}</small>' if ia.get("resume") else ""
        piege = ' <span class="av-p">⚠️ piège</span>' if a.get("piege") else ""
        lignes += f"""<li class="av-l av-{cls}"><div class="av-h"><span>{ecusson(m["domicile"], 22)}{ecusson(m["exterieur"], 22)}</span>
          <div><b>{e(m["domicile"])} – {e(m["exterieur"])}</b><small>{heure(m["debut"])} · {e(championnat(m.get("sport_key", ""), m["championnat"])[1])}</small></div>
          <em class="av-n">{NIVEAUX_TXT[a["niveau"]]}</em></div>
          <div class="av-p1"><b>{e(pari)}</b>{piege}</div><small class="av-t">💡 {e(txt)}</small>{ia_txt}</li>"""
    return f"""<h2>🗂️ L'avis de l'expert <small>match par match</small></h2><ul class="av">{lignes}</ul>"""


NIVEAUX_TXT = {"forte": "💪 Forte", "bonne": "👍 Bonne", "moyenne": "🤔 Moyenne", "ouvert": "🎲 Ouvert"}


def section_semaine(s):
    if not s:
        return ""
    suivis = s.get("suivis") or []
    tk = s.get("ticket")
    if not suivis:
        return ""
    def quand(iso):
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS)
        return f"{JOURS[d.weekday()]} {d.day} · {d:%H:%M}"
    ticket_html = ""
    if tk:
        jambes = ""
        for j in tk["jambes"]:
            a = j.get("avis") or {}
            cls, titre = AVIS.get(a.get("avis"), ("att", "Analyse en cours"))
            jambes += f"""<li>{ecusson(j["domicile"], 26)}{ecusson(j["exterieur"], 26)}
          <div class="j-txt"><b>{e(j["issue"])}</b><small>{e(j["domicile"])} – {e(j["exterieur"])} · {quand(j["debut"])}</small>
          <small class="pq-j">🤖 <b class="sm-{cls}">{titre}</b>{' : ' + e(a.get("resume", "")) if a.get("resume") else ''}</small></div>
          <span class="j-cote">{j["cote_t"]:.2f}</span></li>"""
        pari = {"type": "combine", "id": "semaine-" + "-".join(j["id"][:6] for j in tk["jambes"]), "date": tk["jambes"][0]["debut"],
                "match": " + ".join(j["domicile"] + " – " + j["exterieur"] for j in tk["jambes"]),
                "pari": f"Ticket de la semaine · {len(tk['jambes'])} matchs", "cote": round(tk["cote"], 2), "bk": tk["bookmaker"],
                "jambes": [{"id": j["id"], "court": j["court"], "pari": j["issue"]} for j in tk["jambes"]]}
        ticket_html = f"""
    <article class="carte combo st-semaine" data-style="semaine" data-cote="{tk['cote']:.4f}" data-pari="{e(json.dumps(pari, ensure_ascii=False))}">
      <div class="combo-t"><span class="ct"><i class="ct-e">🔭</i> <span class="ct-n">Ticket de la semaine</span></span><span class="badge c-forte">Suivi de près</span></div>
      <p class="combo-desc">Les matchs où l'expert a le plus confiance, analysés en profondeur chaque jour jusqu'au coup d'envoi.</p>
      <div class="chance"><div class="chance-b"><span style="width:{max(3, round(tk["proba"] * 100))}%"></span></div>
        <b>{pct(tk["proba"])}</b><small>de chances que ça passe</small></div>
      <ul class="jambes">{jambes}</ul>
      <div class="pari">
        <div><div class="lbl">Cote du ticket</div><div class="choix">{len(tk["jambes"])} matchs chez {e(tk["bookmaker"])}</div></div>
        <div class="cote"><div class="lbl">Cote</div><div class="num">{tk["cote"]:.2f}</div></div>
      </div>
      <div class="calc" hidden></div>
      {BOUTON_JOUE}
    </article>"""
    lignes = ""
    for x in suivis:
        a = x.get("avis") or {}
        if x["statut"] == "suivi":
            etat = {"confirme": "✅ confirmé", "prudence": "⚠️ prudence"}.get(a.get("avis"), "🔎 en analyse")
            det = e(a.get("resume", "")) if a.get("resume") else f"{pct(x['proba'])} de chances · cote {x['cote']:.2f}"
        else:
            etat, det = "❌ retiré", e(x.get("raison", ""))
        n = len(x.get("analyses") or [])
        lignes += f"""<li class="sm-l {'out' if x['statut'] != 'suivi' else ''}"><div><b>{e(x["issue"])}</b>
          <small>{e(x["domicile"])} – {e(x["exterieur"])} · {quand(x["debut"])}</small><small class="sm-d">{det}</small></div>
          <span class="sm-e">{etat}<small>{n} analyse{'s' if n > 1 else ''}</small></span></li>"""
    return f"""
<section class="sem">
  <h2>🔭 La sélection de la semaine <small>suivie jusqu'au jour J</small></h2>
  {ticket_html or '<p class="note">Pas encore assez de matchs solides pour un ticket : l\'expert continue de chercher.</p>'}
  <details class="sm-det"><summary>Les {len(suivis)} matchs suivis par l'expert <span class="cpt">▾</span></summary><ul class="sm-liste">{lignes}</ul></details>
</section>"""


def section_historique(historique, b):
    if not historique:
        return '<p class="vide">Le suivi commencera après les premiers paris.</p>'
    roi = pct(b["roi"], True) if b["roi"] is not None else "—"
    cls = "vert" if b["benefice"] >= 0 else "rouge"
    lignes = ""
    for h in sorted(historique, key=lambda h: h["date"], reverse=True)[:20]:
        st = {"gagné": "ok", "perdu": "bad"}.get(h["statut"], "att")
        lignes += f"""<tr><td>{e(h["match"])}<small>{e(h["pari"])} · {h["cote"]:.2f}{' · ' + e(h["score"]) if h.get("score") else ''}</small></td>
          <td class="r">{euros(h["mise"])}</td><td class="r"><span class="st {st}">{e(h["statut"])}</span></td></tr>"""
    return f"""
    <div class="bilan">
      <div><span>Paris réglés</span><b>{b["nb"]}</b></div>
      <div><span>Gagnés</span><b>{b["gagnes"]}</b></div>
      <div><span>Bénéfice</span><b class="{cls}">{euros(b["benefice"], True)}</b></div>
      <div><span>Rendement</span><b class="{cls}">{roi}</b></div>
    </div>
    <p class="note">Le rendement compte plus que le nombre de paris gagnés. Juge l'agent sur 200 paris minimum, pas sur une semaine.</p>
    <table class="hist">{lignes}</table>"""


def mot_agent(analyses, values, combos, quand="aujourd'hui", k=0):
    jouables = [m for m in values if (m.get("avis") or {}).get("avis") != "eviter"]
    conseilles = [c for c in combos if c.get("conseille")]
    if jouables or conseilles:
        icone, titre = "🎯", f"Il y a de quoi jouer {quand}"
        lignes = []
        if jouables:
            m = jouables[0]; v = m["value"]
            lignes.append(f"<b>{len(jouables)} bon{'s' if len(jouables) > 1 else ''} pari{'s' if len(jouables) > 1 else ''}</b>. "
                          f"Le meilleur : <b>{e(v['issue'])}</b> ({e(m['domicile'])} – {e(m['exterieur'])}) à <b>{v['cote']:.2f}</b> chez {e(v['bookmaker'])}.")
        if conseilles:
            noms = ", ".join(f"{c['emoji']} {e(c['nom'])}" for c in conseilles)
            lignes.append(f"Combiné{'s' if len(conseilles) > 1 else ''} conseillé{'s' if len(conseilles) > 1 else ''} : <b>{noms}</b>.")
        eviter = sum(1 for m in values if (m.get("avis") or {}).get("avis") == "eviter")
        if eviter:
            lignes.append(f"⚠️ L'IA a écarté {eviter} pari{'s' if eviter > 1 else ''} après lecture de l'actu.")
        ton = "go"
    else:
        icone, titre = "🧘", f"{quand[0].upper() + quand[1:]}, le plus malin c'est d'attendre"
        lignes = ["Aucune cote ne paie plus que le vrai risque : les bookmakers sont trop gourmands sur ces matchs. "
                  "Garder ton argent, c'est gagner contre eux."]
        if combos:
            c = max(combos, key=lambda c: c["edge"])
            lignes.append(f"Si tu veux quand même jouer, le ticket le moins cher est le {c['emoji']} <b>{e(c['nom'])}</b> "
                          f"({round(c['proba'] * 100)} % de chances).")
        ton = "calme"
    if not analyses:
        icone, titre, ton = "📭", f"Pas de match suivi {quand}", "calme"
        lignes = ["Les bookmakers n'ont pas encore publié de cotes pour ce jour dans les championnats suivis."]
    if k >= 1 and analyses:
        lignes.append("🕒 <i>Verdict provisoire : les cotes et les compos bougent. L'agent refait le point chaque matin à 6 h 45.</i>")
    return f"""<section class="mot {ton}"><div class="mot-i">{icone}</div><div><div class="mot-t">Le mot de l'agent</div>
      <h3>{titre}</h3>{''.join(f'<p>{l}</p>' for l in lignes)}</div></section>"""


def statut_ia(ia):
    if not ia:
        return ""
    if ia["etat"] == "active":
        souv = f" 🧠 {ia['souvenirs']} avec des souvenirs des jours précédents." if ia.get("souvenirs") else ""
        return f"🤖 IA active : {ia['ok']} match{'s' if ia['ok'] > 1 else ''} vérifié{'s' if ia['ok'] > 1 else ''} (actu, compos, avis d'experts).{souv}"
    if ia["etat"] == "rien":
        return "🤖 IA prête : aucun match à vérifier aujourd'hui."
    if ia["etat"] == "erreur":
        return f"🤖 IA en erreur : {e(ia.get('erreur') or '')}"
    return "🤖 IA éteinte (clé ANTHROPIC_API_KEY absente)."


def generer(chemin, analyses, values, historique, b, infos, combos=None):
    if isinstance(combos, dict):
        combos = [combos]
    combos = [c for c in (combos or []) if c]
    d = infos["genere"].astimezone(PARIS)
    date_txt = f"{['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche'][d.weekday()]} {d.day} {MOIS[d.month-1]}"

    a_jouer = [m for m in values if not (m.get("avis") and m["avis"].get("avis") == "eviter")]
    total_mises = sum(m["value"]["mise"] for m in a_jouer)

    if values:
        cartes = "".join(carte_value(m) for m in values)
    else:
        cartes = """<div class="rien"><div class="sifflet">🧘</div><b>Aucun pari simple aujourd'hui.</b>
        <p>Aucune cote ne paie plus que le vrai risque. Ne pas parier, c'est aussi une décision gagnante.</p></div>"""
    if analyses:
        choc = max(analyses, key=lambda m: (m["nb_bookmakers"], -abs(m["issues"][0]["proba"] - m["issues"][-1]["proba"])))
        cartes += f"""
    <h2>🔥 L'affiche du jour <small>le match le plus suivi</small></h2>
    <article class="carte choc" style="--lig:{couleur_ligue(choc.get('sport_key', ''))}">
      <div class="meta">{tag_champ(choc)}<span class="src">{choc["nb_bookmakers"]} bookmakers</span></div>
      {affiche(choc, grand=True)}
      {barre_probas(choc)}
      {bloc_stats(choc)}
      {bloc_buts(choc)}
      <div class="leg">{''.join(f'<span><i class="{ {"1":"s1","N":"sn","2":"s2"}[i["court"]] }"></i>{e(i["issue"])} <b>{pct(i["proba"])}</b> · {i["cote"]:.2f}</span>' for i in choc["issues"])}</div>
      {f'<div class="avis {AVIS.get(choc["avis"].get("avis"), AVIS["prudence"])[0]}"><div class="avis-t">🤖 L&#39;actu du match</div><p>{e(choc["avis"].get("resume", ""))}</p></div>' if choc.get("avis") else ""}
    </article>"""

    par_champ = OrderedDict()
    for m in sorted(analyses, key=lambda m: (-sum(1 for x in analyses if x["sport_key"] == m["sport_key"] and x["value"]),
                                             championnat(m.get("sport_key", ""), m["championnat"])[1], m["debut"])):
        par_champ.setdefault(championnat(m.get("sport_key", ""), m["championnat"]), []).append(m)
    groupes = ""
    for champ, ms in par_champ.items():
        nv = sum(1 for m in ms if m["value"])
        tag = f'<span class="nv">{nv} value</span>' if nv else ""
        groupes += f"""
    <details data-l="{e(champ[1])}" style="--lig:{couleur_ligue(ms[0].get('sport_key', ''))}"{' open' if nv else ''}><summary><span class="champ g"><i>{champ[0]}</i>{e(champ[1])}</span><span class="cpt">{tag}<span class="cpt-n">{len(ms)} match{'s' if len(ms) > 1 else ''}</span></span></summary>
      {''.join(ligne_match(m) for m in ms)}
    </details>"""

    jours = infos.get("jours") or [{"cle": d.strftime("%Y-%m-%d"), "quand": "aujourd'hui",
                                     "analyses": analyses, "values": values, "combos": combos}]
    selecteur, mots, corps = "", "", ""
    for k, j in enumerate(jours):
        jv = [m for m in j["values"] if (m.get("avis") or {}).get("avis") != "eviter"]
        jc = [c for c in j["combos"] if c.get("conseille")]
        if not j["analyses"]:
            etat, sous = "vide", "—"
        elif jv or jc:
            n = len(jv) + len(jc)
            etat, sous = "go", f"{n} à jouer"
        else:
            etat, sous = "calme", "attendre"
        dt = datetime.strptime(j["cle"], "%Y-%m-%d")
        titre_j = "Auj." if k == 0 else "Demain" if k == 1 else NOMS_JOURS[dt.weekday()][:3] + "."
        selecteur += f"""<button data-j="{j["cle"]}" class="j-{etat}"><span>{titre_j}</span><b>{dt.day}</b><small>{sous}</small></button>"""
        mots += f"""<div class="jour-mot" data-jour="{j["cle"]}"{'' if k == 0 else ' hidden'}>{mot_agent(j["analyses"], j["values"], j["combos"], j["quand"], k)}{resume_jour(j, infos.get("bankroll") or 100)}</div>"""
        if j["values"]:
            cartes_j = "".join(carte_value(m) for m in j["values"])
        else:
            cartes_j = f"""<div class="rien"><div class="sifflet">🧘</div><b>Aucun pari simple {e(j["quand"])}.</b>
        <p>Aucune cote ne paie plus que le vrai risque. Ne pas parier, c'est aussi une décision gagnante.</p></div>"""
        if j["analyses"]:
            choc = max(j["analyses"], key=lambda m: (m["nb_bookmakers"], -abs(m["issues"][0]["proba"] - m["issues"][-1]["proba"])))
            cartes_j += f"""
    <h2>🔥 L'affiche {'du jour' if k == 0 else 'de ' + e(j["quand"])} <small>le match le plus suivi</small></h2>
    <article class="carte choc" style="--lig:{couleur_ligue(choc.get('sport_key', ''))}">
      <div class="meta">{tag_champ(choc)}<span class="src">{choc["nb_bookmakers"]} bookmakers</span></div>
      {affiche(choc, grand=True)}
      {barre_probas(choc)}
      {bloc_stats(choc)}
      {bloc_buts(choc)}
      <div class="leg">{''.join(f'<span><i class="{ {"1":"s1","N":"sn","2":"s2"}[i["court"]] }"></i>{e(i["issue"])} <b>{pct(i["proba"])}</b> · {i["cote"]:.2f}</span>' for i in choc["issues"])}</div>
      {f'<div class="avis {AVIS.get(choc["avis"].get("avis"), AVIS["prudence"])[0]}"><div class="avis-t">🤖 L&#39;actu du match</div><p>{e(choc["avis"].get("resume", ""))}</p></div>' if choc.get("avis") else ""}
    </article>"""
        combos_j = "".join(carte_combine(c, j["cle"]) for c in j["combos"]) or carte_combine(None)
        tkj = carte_ticket(j["ticket"], "jour", "📌", "Ticket du jour", "Les 2 à 3 matchs les plus solides du jour, vérifiés en profondeur par l'IA.", "Le plus solide") if j.get("ticket") else ""
        corps += f"""<div class="jour-corps" data-jour="{j["cle"]}"{'' if k == 0 else ' hidden'}>
{tkj}
{liste_avis(j)}
<h2>🎟️ Combinés d'experts <small>résultats, buts ou mixte · un seul bookmaker par ticket</small></h2>
{combos_j}
<h2>🎯 Paris simples <small>selon l'avantage de chaque pari</small></h2>
{cartes_j}
<h2>⚽ Pronos buts <small>calculés à partir des cotes du marché</small></h2>
<p class="note">L'agent n'a pas les cotes des bookmakers sur ces paris : il te donne la <b>cote juste</b>.
Si ton bookmaker propose <b>au moins la cote indiquée</b>, le pari vaut le coup ; sinon, passe.</p>
{"".join(carte_buts(c, j["cle"]) for c in j.get("buts", [])) or '<p class="vide">Pas de prono buts assez net ce jour-là.</p>'}
</div>"""

    donnees = {}
    for m in analyses:
        donnees[m["id"]] = {
            "dom": m["domicile"], "ext": m["exterieur"], "ko": m["debut"],
            "champ": championnat(m.get("sport_key", ""), m["championnat"])[1],
            "issues": {i["court"]: {"p": round(i["proba"], 4), "c": i["cote"], "bk": i["bookmaker"], "lib": i["issue"]} for i in m["issues"]},
            "bks": {v["titre"]: {k: v.get(k) for k in ("1", "N", "2")} for v in (m.get("cotes_bk") or {}).values()},
            "buts": {k: round(m["buts"][k], 4) for k in ("plus15", "plus25", "plus35", "btts")} if m.get("buts") else None,
            "avis": (m.get("avis") or {}).get("resume"),
        }
    donnees_json = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")

    # vue « par heure » : tous les matchs de la semaine dans l'ordre chronologique
    chrono, jour_prec, heure_prec = "", None, None
    for m in sorted(analyses, key=lambda m: m["debut"]):
        dl = datetime.fromisoformat(m["debut"].replace("Z", "+00:00")).astimezone(PARIS)
        cle_j = dl.strftime("%Y-%m-%d")
        if cle_j != jour_prec:
            if jour_prec is not None:
                chrono += "</div></div>"
            chrono += (f'<div class="ch-jour" data-jour="{cle_j}"><div class="ch-jt">'
                       f'{["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][dl.weekday()]} {dl.day} {MOIS[dl.month-1]}</div><div>')
            jour_prec, heure_prec = cle_j, None
        h = dl.strftime("%H:%M")
        if h != heure_prec:
            chrono += f'<div class="ch-h" data-jour="{cle_j}">🕒 {h}</div>'
            heure_prec = h
        drap, nom = championnat(m.get("sport_key", ""), m["championnat"])
        chrono += (f'<div class="ch-m" data-l="{e(nom)}" style="--lig:{couleur_ligue(m.get("sport_key", ""))}">'
                   f'<div class="ch-l">{drap} {e(nom)}</div>{ligne_match(m)}</div>')
    if jour_prec is not None:
        chrono += "</div></div>"

    # rangée de jours de l'onglet Matchs (avec le nombre de matchs par jour)
    selecteur_m = '<button data-jm="" class="j-tous"><span>Semaine</span><b>7 j</b><small>' + str(len(analyses)) + ' matchs</small></button>'
    for k, j in enumerate(jours):
        dt = datetime.strptime(j["cle"], "%Y-%m-%d")
        titre_j = "Auj." if k == 0 else "Demain" if k == 1 else NOMS_JOURS[dt.weekday()][:3] + "."
        n = len(j["analyses"])
        selecteur_m += f'<button data-jm="{j["cle"]}" class="{"" if n else "j-vide"}"><span>{titre_j}</span><b>{dt.day}</b><small>{n} match{"s" if n > 1 else ""}</small></button>'

    bandeau_demo = '<div class="demo">Mode démo : données fictives</div>' if infos.get("demo") else ""
    credits = ""
    if infos.get("credits_restants") is not None:
        credits = f" · {infos['credits_restants']} crédits API restants"

    html = f"""<!doctype html>
<html lang="fr" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#060b09">
<meta name="color-scheme" content="dark">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Prono Malin">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" href="logo.svg" type="image/svg+xml">
<link rel="alternate icon" href="icon-192.png">
<title>Prono Malin</title>
<script>
try {{
  const pin = localStorage.getItem("pin"), jusqu = +localStorage.getItem("pin-ok-jusqu") || 0;
  if (pin && !sessionStorage.getItem("pin-ok") && Date.now() > jusqu) document.documentElement.classList.add("verrouille");
}} catch (e) {{}}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#0e1411; --surface:#161e1a; --surface2:#1d2722; --line:#2a3630;
  --text:#ecf2ee; --muted:#93a39a; --accent:#c8f169; --accent-ink:#13200a;
  --ok:#5fd38d; --warn:#f2c14e; --bad:#ff6b6b;
  --p1:#c8f169; --pn:#7d8a83; --p2:#5aa9e6; --pitch:rgba(200,241,105,.10); --glow:rgba(200,241,105,.07);
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
    --bg:#f3f5f1; --surface:#ffffff; --surface2:#eef2ec; --line:#dbe2d9;
    --text:#14201a; --muted:#5d6b63; --accent:#2f7d32; --accent-ink:#ffffff;
    --ok:#1f8a4c; --warn:#a86b00; --bad:#c62828;
    --p1:#3c9a3f; --pn:#a3ada7; --p2:#2f78c4; --pitch:rgba(47,125,50,.14); --glow:rgba(47,125,50,.08);
  }}
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--text); font:15px/1.45 Inter, system-ui, sans-serif;
  padding:0 16px calc(32px + env(safe-area-inset-bottom)); max-width:640px; margin:0 auto; }}
h1,h2,h3,.num,.choix,.bilan b,.grille b {{ font-family:"Barlow Condensed", Inter, sans-serif; letter-spacing:.01em; }}
header {{ position:relative; padding:calc(20px + env(safe-area-inset-top)) 0 18px; }}
header::before {{ content:""; position:absolute; z-index:-1; inset:0 -16px; pointer-events:none;
  background:
    radial-gradient(circle at 50% 100%, transparent 58px, var(--pitch) 59px, var(--pitch) 60px, transparent 61px),
    linear-gradient(180deg, var(--glow), transparent 75%);
  border-bottom:1px solid var(--pitch); }}
.haut {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.maj {{ background:var(--surface); color:var(--text); border:1px solid var(--line); border-radius:99px;
  font:600 13px Inter, sans-serif; padding:6px 12px; cursor:pointer; }}
.installer {{ display:none; background:var(--surface); border:1px solid var(--accent); border-radius:12px;
  padding:12px 14px; margin-top:14px; font-size:14px; }}
.installer b {{ color:var(--accent); }}
.installer button {{ float:right; background:none; border:0; color:var(--muted); font-size:18px; line-height:1; cursor:pointer; }}
.date {{ color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.08em; }}
h1 {{ font-size:40px; line-height:1; margin-top:4px; }}
h1 em {{ font-style:normal; color:var(--accent); }}
.ballon {{ font-size:28px; vertical-align:6px; }}
.resume {{ display:flex; gap:8px; margin-top:16px; }}
.resume div {{ flex:1; background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:10px 12px; }}
.resume span {{ display:block; color:var(--muted); font-size:12px; }}
.resume b {{ font-size:22px; font-family:"Barlow Condensed",sans-serif; }}
h2 {{ font-size:24px; margin:28px 0 12px; display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:4px 12px; }}
h2 small {{ font-family:Inter,sans-serif; font-size:12px; color:var(--muted); font-weight:500; }}
.demo {{ background:var(--warn); color:#1d1500; font-weight:600; text-align:center; font-size:13px;
  padding:6px; border-radius:0 0 10px 10px; }}
.carte {{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:16px; margin-bottom:12px; }}
.carte.barre {{ opacity:.6; }}
.meta {{ display:flex; justify-content:space-between; align-items:center; color:var(--muted); font-size:12px; gap:8px; }}
.champ {{ display:inline-flex; align-items:center; gap:6px; font-weight:600; color:var(--text); }}
.champ i {{ font-style:normal; font-size:15px; line-height:1; }}
.champ.g i {{ font-size:18px; }}
.affiche {{ display:grid; grid-template-columns:1fr auto 1fr; align-items:start; gap:6px; text-align:center; margin:4px 0 10px; }}
.affiche.grande {{ margin:14px 0 14px; }}
.eq {{ display:flex; flex-direction:column; align-items:center; gap:6px; min-width:0; }}
.eq span {{ font-weight:600; font-size:13px; line-height:1.2; overflow-wrap:anywhere; }}
.affiche.grande .eq span {{ font-family:"Barlow Condensed",sans-serif; font-size:19px; font-weight:700; }}
.ecu {{ display:block; filter:drop-shadow(0 2px 3px rgba(0,0,0,.25)); }}
.ko {{ display:flex; flex-direction:column; align-items:center; padding-top:8px; min-width:62px; }}
.ko b {{ font-family:"Barlow Condensed",sans-serif; font-size:22px; line-height:1; }}
.affiche.grande .ko b {{ font-size:28px; padding-top:4px; }}
.ko small {{ color:var(--muted); font-size:11px; margin-top:3px; white-space:nowrap; }}
.barre-p {{ display:flex; gap:3px; height:6px; margin:0 0 12px; }}
.barre-p span {{ border-radius:3px; opacity:.55; }}
.barre-p span.on {{ opacity:1; box-shadow:0 0 0 2px var(--surface), 0 0 0 3px currentColor; }}
.s1 {{ background:var(--p1); color:var(--p1); }} .sn {{ background:var(--pn); color:var(--pn); }} .s2 {{ background:var(--p2); color:var(--p2); }}
.leg {{ display:flex; flex-direction:column; gap:4px; font-size:13px; color:var(--muted); }}
.leg i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:7px; vertical-align:-1px; }}
.leg b {{ color:var(--text); }}
.choc {{ background:linear-gradient(160deg, var(--glow), transparent 60%), var(--surface); }}
.sifflet {{ font-size:30px; margin-bottom:6px; }}
.budget {{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:14px; margin-top:22px; }}
.budget label {{ font-family:"Barlow Condensed",sans-serif; font-weight:700; font-size:20px; display:block; }}
.saisie {{ display:flex; align-items:center; gap:8px; margin-top:8px; background:var(--surface2); border:2px solid var(--line);
  border-radius:12px; padding:4px 14px; }}
.saisie:focus-within {{ border-color:var(--accent); }}
.saisie input {{ flex:1; min-width:0; background:none; border:0; outline:0; color:var(--text);
  font:700 30px "Barlow Condensed",sans-serif; padding:6px 0; }}
.saisie span {{ font:700 24px "Barlow Condensed",sans-serif; color:var(--muted); }}
.puces {{ display:flex; gap:6px; margin-top:8px; }}
.puces button {{ flex:1; background:var(--surface2); color:var(--text); border:1px solid var(--line); border-radius:99px;
  font:600 14px Inter,sans-serif; padding:8px 0; cursor:pointer; }}
.puces button.on {{ background:var(--accent); color:var(--accent-ink); border-color:var(--accent); }}
.budget-res {{ margin-top:10px; font-size:14px; color:var(--muted); }}
.budget-res b {{ color:var(--text); }}
.budget-res .gros {{ color:var(--ok); }}
.calc {{ margin-top:10px; border:2px dashed var(--accent); border-radius:12px; padding:10px 12px;
  display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.calc[hidden] {{ display:none; }}
.mode {{ display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-top:10px; background:var(--surface2); border-radius:12px; padding:4px; }}
.mode button {{ background:none; border:0; border-radius:9px; padding:9px 0; font:600 14px Inter,sans-serif; color:var(--muted); cursor:pointer; }}
.mode button.on {{ background:var(--surface); color:var(--text); box-shadow:0 1px 3px rgba(0,0,0,.2); }}
.combo {{ border:1.5px solid var(--accent); background:linear-gradient(160deg, var(--glow), transparent 55%), var(--surface); }}
.combo.risque {{ border-color:var(--warn); }}
.combo.risque .pari {{ background:var(--surface2); color:var(--text); }}
.combo-t {{ font:700 21px "Barlow Condensed",sans-serif; display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap; }}
.c-risque {{ color:var(--warn); }}
.jambes {{ list-style:none; margin:12px 0; display:flex; flex-direction:column; gap:8px; }}
.jambes li {{ display:flex; align-items:center; gap:4px; background:var(--surface2); border-radius:12px; padding:8px 10px; }}
.jambes .ecu {{ flex:none; }}
.j-txt {{ flex:1; min-width:0; margin-left:6px; }}
.j-txt b {{ display:block; font-size:14px; }}
.j-txt small {{ display:block; color:var(--muted); font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.j-cote {{ font:700 20px "Barlow Condensed",sans-serif; }}
.jambes li.avis-j {{ display:block; background:none; padding:0 4px 4px 12px; margin-top:-4px; font-size:13px; color:var(--muted);
  border-left:3px solid var(--warn); border-radius:0; }}
.avis-j.ok {{ border-color:var(--ok); }} .avis-j.bad {{ border-color:var(--bad); }}
.avis-j.ok b {{ color:var(--ok); }} .avis-j.warn b {{ color:var(--warn); }} .avis-j.bad b {{ color:var(--bad); }}
.stats {{ background:var(--surface2); border-radius:12px; padding:8px 10px; margin:-2px 0 12px; display:flex; flex-direction:column; gap:6px; }}
.stats.compact {{ background:none; padding:0; margin:0 0 8px; }}
.st-l {{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:8px; font-size:12px; }}
.st-l > span {{ color:var(--muted); text-align:center; white-space:nowrap; }}
.st-l > b {{ font:700 17px "Barlow Condensed",sans-serif; }}
.st-l > b:last-child {{ text-align:right; }}
.pas {{ display:flex; gap:3px; }}
.pas.r {{ justify-content:flex-end; }}
.pas i {{ font-style:normal; font:700 10px Inter,sans-serif; width:17px; height:17px; border-radius:5px; display:grid; place-items:center; color:#fff; }}
.f-V {{ background:#2f9e55; }} .f-N {{ background:#8a958f; }} .f-D {{ background:#d64545; }}
.sous {{ font-size:19px; margin:18px 0 8px; }}
.hist td small + small {{ margin-top:0; }}
.joue {{ margin-top:12px; }}
.btn-joue {{ width:100%; background:var(--surface2); color:var(--text); border:1px dashed var(--line); border-radius:12px;
  padding:10px; font:600 14px Inter,sans-serif; cursor:pointer; }}
.btn-joue.fait {{ border-style:solid; border-color:var(--ok); color:var(--ok); }}
.joue-f {{ display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap; font-size:13px; color:var(--muted); }}
.joue-f[hidden] {{ display:none; }}
.joue-f input {{ width:70px; background:var(--surface2); color:var(--text); border:1px solid var(--line); border-radius:8px;
  padding:7px; font:600 15px Inter,sans-serif; }}
.joue-f button {{ margin-left:auto; background:var(--accent); color:var(--accent-ink); border:0; border-radius:10px;
  padding:9px 14px; font:700 14px Inter,sans-serif; cursor:pointer; }}
.mp-act {{ display:flex; gap:6px; justify-content:flex-end; margin-top:4px; }}
.mp-act button {{ background:var(--surface2); border:1px solid var(--line); color:var(--muted); border-radius:8px; font-size:12px; padding:3px 7px; cursor:pointer; }}
.lecons {{ margin:0 0 10px 18px; font-size:14px; display:flex; flex-direction:column; gap:6px; }}
.combo-note {{ margin-top:10px; font-size:13px; line-height:1.45; }}
.vide-c p {{ margin-top:6px; }}
.calc span {{ display:block; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }}
.calc b {{ font:700 24px "Barlow Condensed",sans-serif; }}
.calc .r b {{ color:var(--ok); }}
.calc .r {{ text-align:right; }}
.carte h3 {{ font-size:23px; margin:6px 0 12px; line-height:1.1; }}
.vs {{ color:var(--muted); }}
.pari {{ display:flex; justify-content:space-between; align-items:flex-end; background:var(--accent); color:var(--accent-ink);
  border-radius:12px; padding:12px 14px; }}
.lbl {{ font-size:11px; text-transform:uppercase; letter-spacing:.08em; opacity:.75; }}
.choix {{ font-size:22px; font-weight:700; line-height:1.1; }}
.cote {{ text-align:right; }}
.num {{ font-size:34px; font-weight:700; line-height:1; }}
.bk {{ font-size:12px; font-weight:600; }}
.grille {{ display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin-top:10px; }}
.grille div {{ background:var(--surface2); border-radius:10px; padding:8px 4px; text-align:center; }}
.grille span {{ display:block; font-size:11px; color:var(--muted); }}
.grille b {{ font-size:18px; white-space:nowrap; }}
.vert {{ color:var(--ok); }} .rouge {{ color:var(--bad); }}
.pied-carte {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:10px; flex-wrap:wrap; }}
.badge {{ font-size:12px; font-weight:600; padding:3px 9px; border-radius:99px; background:var(--surface2); }}
.c-forte,.c-bonne {{ color:var(--ok); }} .c-moyenne {{ color:var(--warn); }} .c-faible {{ color:var(--muted); }}
.src {{ font-size:11px; color:var(--muted); }}
.carte > .src {{ margin-top:10px; }}
.avis {{ margin-top:12px; border-left:3px solid var(--warn); padding:4px 0 2px 12px; font-size:14px; }}
.avis.ok {{ border-color:var(--ok); }} .avis.bad {{ border-color:var(--bad); }}
.avis-t {{ font-weight:600; font-size:13px; }}
.avis.ok .avis-t {{ color:var(--ok); }} .avis.warn .avis-t {{ color:var(--warn); }} .avis.bad .avis-t {{ color:var(--bad); }}
.avis ul {{ margin:6px 0 0 16px; color:var(--muted); font-size:13px; }}
.rien {{ background:var(--surface); border:1px dashed var(--line); border-radius:16px; padding:20px; text-align:center; }}
.rien p {{ color:var(--muted); margin-top:6px; font-size:14px; }}
details {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; margin-bottom:8px; overflow:hidden; }}
summary {{ list-style:none; cursor:pointer; padding:13px 14px; display:flex; justify-content:space-between; gap:8px; font-weight:600; }}
summary::-webkit-details-marker {{ display:none; }}
.cpt {{ color:var(--muted); font-weight:500; font-size:13px; white-space:nowrap; }}
.nv {{ color:var(--accent); margin-right:8px; }}
.match {{ border-top:1px solid var(--line); padding:12px 14px 14px; }}
.match .barre-p {{ height:4px; margin-bottom:8px; }}
.mh {{ display:flex; justify-content:space-between; gap:8px; font-size:14px; }}
.mh .h {{ color:var(--muted); font-size:12px; white-space:nowrap; }}
.cases {{ display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin-top:8px; }}
.case {{ background:var(--surface2); border-radius:8px; padding:6px 8px; display:flex; align-items:baseline; gap:6px; }}
.case .k {{ color:var(--muted); font-size:12px; font-weight:600; }}
.case .p {{ margin-left:auto; color:var(--muted); font-size:12px; }}
.case.val {{ outline:2px solid var(--accent); }}
.carte {{ animation:monte .45s ease both; }}
@keyframes monte {{ from {{ opacity:0; transform:translateY(8px); }} }}
@media (prefers-reduced-motion: reduce) {{ .carte {{ animation:none; }} }}
.bilan {{ display:grid; grid-template-columns:repeat(4,1fr); gap:6px; }}
.bilan div {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:8px; text-align:center; }}
.bilan span {{ display:block; font-size:11px; color:var(--muted); }}
.bilan b {{ font-size:20px; white-space:nowrap; }}
.note {{ color:var(--muted); font-size:13px; margin:10px 0; }}
.hist {{ width:100%; border-collapse:collapse; font-size:14px; }}
.hist td {{ border-top:1px solid var(--line); padding:9px 0; vertical-align:top; }}
.hist small {{ display:block; color:var(--muted); font-size:12px; }}
.r {{ text-align:right; white-space:nowrap; padding-left:8px !important; }}
.st {{ font-size:12px; font-weight:600; }}
.st.ok {{ color:var(--ok); }} .st.bad {{ color:var(--bad); }} .st.att {{ color:var(--muted); }}
.vide {{ color:var(--muted); }}
footer {{ margin-top:32px; color:var(--muted); font-size:13px; border-top:1px solid var(--line); padding-top:16px; }}
footer p + p {{ margin-top:8px; }}
footer b {{ color:var(--text); }}

/* ===================== thème vif ===================== */
:root {{
  --bg:#060b09; --surface:#0f1814; --surface2:#16231d; --line:#22352c;
  --text:#f2fbf5; --muted:#9db3a6; --accent:#c6ff3d; --accent-ink:#0b1500;
  --ok:#34d399; --warn:#fbbf24; --bad:#fb7185;
  --p1:#c6ff3d; --pn:#fbbf24; --p2:#38bdf8;
  --grad:linear-gradient(120deg,#c6ff3d 0%,#34d399 55%,#22d3ee 100%);
  --grad-ticket:linear-gradient(135deg,#a855f7 0%,#ec4899 50%,#f97316 100%);
  --pitch:rgba(198,255,61,.12); --glow:rgba(198,255,61,.10);
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
    --bg:#f2f7f1; --surface:#ffffff; --surface2:#eef5ec; --line:#d9e6d6;
    --text:#0d1a12; --muted:#56685d; --accent:#16a34a; --accent-ink:#ffffff;
    --ok:#059669; --warn:#d97706; --bad:#e11d48;
    --p1:#22c55e; --pn:#f59e0b; --p2:#0ea5e9;
    --grad:linear-gradient(120deg,#16a34a 0%,#059669 55%,#0891b2 100%);
    --pitch:rgba(22,163,74,.14); --glow:rgba(22,163,74,.10);
  }}
}}
body {{
  background:
    radial-gradient(600px 380px at 0% -5%, rgba(198,255,61,.16), transparent 70%),
    radial-gradient(520px 360px at 100% 0%, rgba(34,211,238,.14), transparent 70%),
    radial-gradient(700px 500px at 50% 110%, rgba(168,85,247,.10), transparent 70%),
    var(--bg);
  background-attachment:fixed;
}}
h1 {{ font-size:clamp(32px, 10.5vw, 46px); white-space:nowrap; }}
h1 em {{ background:var(--grad); -webkit-background-clip:text; background-clip:text; color:transparent; }}
.marque {{ display:flex; align-items:center; gap:12px; margin-top:6px; }}
.logo {{ width:58px; height:58px; flex:none; filter:drop-shadow(0 6px 16px rgba(52,211,153,.45)); animation:rebond 3.2s ease-in-out infinite; }}
@keyframes rebond {{ 0%,100% {{ transform:translateY(0) rotate(0); }} 50% {{ transform:translateY(-4px) rotate(-6deg); }} }}
.marque h1 {{ margin-top:0; }}
.slogan {{ color:var(--muted); font-size:13px; font-weight:500; margin-top:2px; }}
header.reduit .logo {{ width:40px; height:40px; }}
header.reduit .slogan {{ display:none; }}
@keyframes roule {{ to {{ transform:rotate(360deg); }} }}
.resume div {{ position:relative; overflow:hidden; border:0; background:var(--surface);
  box-shadow:inset 0 0 0 1px var(--line); }}
.resume div::before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px; }}
.resume div:nth-child(1)::before {{ background:#38bdf8; }}
.resume div:nth-child(2)::before {{ background:var(--accent); }}
.resume div:nth-child(3)::before {{ background:#a855f7; }}
.resume div:nth-child(2) b {{ color:var(--accent); }}
h2 {{ font-size:26px; }}
.carte {{ position:relative; overflow:hidden; box-shadow:0 10px 30px -18px rgba(0,0,0,.6); }}
.carte.value::before, .carte.choc::before {{ content:""; position:absolute; inset:0 0 auto 0; height:4px; background:var(--lig, var(--accent)); }}
.carte.value {{ background:radial-gradient(400px 160px at 100% 0%, color-mix(in srgb, var(--lig) 16%, transparent), transparent 70%), var(--surface); }}
.choc {{ background:radial-gradient(420px 200px at 50% 0%, color-mix(in srgb, var(--lig) 22%, transparent), transparent 70%), var(--surface); }}
.pari {{ background:var(--grad); color:var(--accent-ink); position:relative; overflow:hidden; box-shadow:0 8px 24px -10px rgba(52,211,153,.55); }}
.pari::after {{ content:""; position:absolute; top:0; bottom:0; width:40%; left:-60%;
  background:linear-gradient(100deg, transparent, rgba(255,255,255,.45), transparent); animation:brille 3.8s ease-in-out infinite; }}
@keyframes brille {{ 0%,55% {{ left:-60%; }} 100% {{ left:130%; }} }}
@media (prefers-color-scheme: light) {{ :root:not([data-theme="dark"]) .pari {{ color:#fff; }} }}
.grille div {{ border:1px solid var(--line); }}
.vert {{ color:var(--ok); }}
.badge {{ border:1px solid currentColor; background:transparent; }}
.barre-p {{ height:8px; }}
.barre-p span {{ opacity:.85; }}
/* combiné façon ticket */
.combo {{ border:0; padding:2px; background:var(--grad-ticket); box-shadow:0 14px 34px -16px rgba(236,72,153,.6); }}
.combo > * {{ position:relative; }}
.combo::after {{ content:""; position:absolute; inset:2px; border-radius:14px; background:
  radial-gradient(420px 180px at 100% 0%, rgba(236,72,153,.14), transparent 70%), var(--surface); z-index:0; }}
.combo > * {{ z-index:1; margin-left:14px; margin-right:14px; }}
.combo > .combo-t {{ margin-top:14px; }}
.combo > .joue {{ margin-bottom:14px; }}
.combo .pari {{ background:var(--grad-ticket); color:#fff; box-shadow:0 8px 24px -10px rgba(236,72,153,.6); }}
.combo.risque {{ background:linear-gradient(135deg,#f59e0b,#ef4444); }}
.combo.risque .pari {{ background:var(--surface2); color:var(--text); box-shadow:none; }}
.combo-t {{ font-size:23px; }}
.combo:not(.risque) .combo-t .ct-n {{ background:var(--grad-ticket); -webkit-background-clip:text; background-clip:text; color:transparent; }}
.ct-e {{ font-style:normal; }}
.combo .combo-t .badge {{ -webkit-text-fill-color:initial; }}
.jambes li {{ border-left:3px solid #ec4899; }}
.combo.risque .jambes li {{ border-left-color:var(--warn); }}
.jambes li.avis-j {{ border-left-width:3px; }}
/* saisie de la mise */
.budget {{ border:0; background:linear-gradient(var(--surface),var(--surface)) padding-box, var(--grad) border-box; border:2px solid transparent; }}
.puces button.on, .mode button.on {{ background:var(--grad); color:var(--accent-ink); border-color:transparent; }}
.saisie input {{ color:var(--accent); }}
.calc {{ border-color:var(--ok); background:color-mix(in srgb, var(--ok) 8%, transparent); }}
/* liste des matchs */
details {{ border-left:4px solid var(--lig, var(--line)); }}
.case.val {{ outline:2px solid var(--accent); background:color-mix(in srgb, var(--accent) 14%, var(--surface2)); }}
.f-V {{ background:#10b981; }} .f-N {{ background:#64748b; }} .f-D {{ background:#f43f5e; }}
.btn-joue {{ border:1px solid transparent; background:linear-gradient(var(--surface2),var(--surface2)) padding-box, var(--grad) border-box; }}
.maj {{ background:var(--grad); color:var(--accent-ink); border:0; }}
.installer {{ border:0; background:linear-gradient(var(--surface),var(--surface)) padding-box, var(--grad) border-box; border:2px solid transparent; }}
.styles {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
.styles button {{ flex:1 1 30%; }}
.styles[hidden] {{ display:none; }}
.styles button {{ background:var(--surface2); color:var(--text); border:1px solid var(--line); border-radius:10px;
  padding:8px 4px; font:600 13px Inter,sans-serif; cursor:pointer; white-space:nowrap; }}
.styles button.on {{ background:var(--grad-ticket); color:#fff; border-color:transparent; }}
.styles button::before {{ content:"☐ "; opacity:.6; }}
.styles button.on::before {{ content:"☑ "; opacity:1; }}
.combo {{ margin-bottom:14px; cursor:pointer; transition:transform .2s, box-shadow .2s; }}
.combo.choisi {{ transform:scale(1.01); box-shadow:0 0 0 3px color-mix(in srgb, #ec4899 45%, transparent), 0 16px 36px -14px rgba(236,72,153,.7); }}
.combo.st-prudent {{ --grad-ticket:linear-gradient(135deg,#22d3ee 0%,#3b82f6 60%,#6366f1 100%); }}
.combo.st-buts {{ --grad-ticket:linear-gradient(135deg,#fbbf24 0%,#f59e0b 50%,#ea580c 100%); }}
.combo.st-mixte {{ --grad-ticket:linear-gradient(135deg,#22c55e 0%,#14b8a6 50%,#f59e0b 100%); }}
.combo.st-buts .jambes li {{ border-left-color:#f59e0b; }}
.combo.st-mixte .jambes li {{ border-left-color:#14b8a6; }}
.combo.estime .pari .choix {{ font-size:30px; }}
.combo.st-gros {{ --grad-ticket:linear-gradient(135deg,#f97316 0%,#ef4444 50%,#db2777 100%); }}
.combo.st-prudent .jambes li {{ border-left-color:#3b82f6; }}
.combo.st-gros .jambes li {{ border-left-color:#f97316; }}
.combo-desc {{ color:var(--muted); font-size:13px; margin-top:2px; }}
.chance {{ display:grid; grid-template-columns:1fr auto; grid-template-rows:auto auto; column-gap:10px; align-items:center; margin-top:10px; }}
.chance-b {{ height:10px; border-radius:99px; background:var(--surface2); overflow:hidden; }}
.chance-b span {{ display:block; height:100%; border-radius:99px; background:var(--grad-ticket); }}
.chance b {{ font:700 26px "Barlow Condensed",sans-serif; grid-row:span 2; }}
.chance small {{ color:var(--muted); font-size:12px; }}
body {{ padding-bottom:calc(92px + env(safe-area-inset-bottom)); }}
.onglet[hidden], .match[hidden], details[hidden], .ch-m[hidden], .ch-h[hidden], .ch-jour[hidden], #vue-heure[hidden], #vue-champ[hidden], .toast[hidden], #aucun[hidden] {{ display:none !important; }}
header.reduit .resume, header.reduit .mot, header.reduit .installer {{ display:none !important; }}
header.reduit {{ padding-bottom:4px; }}
header.reduit h1 {{ font-size:30px; }}
.barre-nav {{ position:fixed; z-index:50; left:50%; transform:translateX(-50%); bottom:calc(10px + env(safe-area-inset-bottom));
  width:min(608px, calc(100% - 24px)); display:grid; grid-template-columns:repeat(5,1fr); gap:2px; padding:6px;
  background:color-mix(in srgb, var(--surface) 82%, transparent); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  border:1px solid var(--line); border-radius:22px; box-shadow:0 12px 30px -10px rgba(0,0,0,.6); }}
.barre-nav button {{ position:relative; background:none; border:0; border-radius:16px; padding:7px 2px 6px; color:var(--muted);
  font:600 11px Inter,sans-serif; display:flex; flex-direction:column; align-items:center; gap:2px; cursor:pointer; }}
.barre-nav button i {{ font-style:normal; font-size:20px; line-height:1; filter:grayscale(.7); transition:transform .2s; }}
.barre-nav button.on {{ color:var(--text); background:color-mix(in srgb, var(--accent) 16%, transparent); }}
.barre-nav button.on i {{ filter:none; transform:translateY(-2px) scale(1.12); }}
.pastille {{ position:absolute; top:3px; right:calc(50% - 22px); min-width:17px; height:17px; padding:0 4px; border-radius:99px;
  background:#ec4899; color:#fff; font:700 10px/17px Inter,sans-serif; }}
.pastille[hidden] {{ display:none; }}
.mot {{ display:flex; gap:12px; margin-top:14px; padding:14px; border-radius:16px; position:relative;
  background:linear-gradient(var(--surface),var(--surface)) padding-box, var(--grad) border-box; border:2px solid transparent; }}
.mot.calme {{ background:linear-gradient(var(--surface),var(--surface)) padding-box, linear-gradient(120deg,#38bdf8,#a855f7) border-box; }}
.mot-i {{ font-size:30px; line-height:1; }}
.mot-t {{ font-size:11px; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); font-weight:600; }}
.mot h3 {{ font:700 20px "Barlow Condensed",sans-serif; margin:2px 0 4px; }}
.mot p {{ font-size:14px; color:var(--muted); }}
.mot p + p {{ margin-top:4px; }}
.mot b {{ color:var(--text); }}
.cd {{ display:block; font-style:normal; font-size:11px; font-weight:600; color:var(--accent); margin-top:2px; white-space:nowrap; }}
.cd.bientot {{ color:var(--warn); }}
.cd.live {{ color:#fb7185; animation:clignote 1.4s ease-in-out infinite; }}
.cd.fini {{ color:var(--muted); }}
@keyframes clignote {{ 50% {{ opacity:.35; }} }}
.filtres {{ position:relative; z-index:5; padding:8px 0 10px; margin:0 -16px 6px; padding-left:16px; padding-right:16px;
  background:linear-gradient(var(--bg) 75%, transparent); }}
#cherche {{ width:100%; background:var(--surface); border:1px solid var(--line); border-radius:12px; color:var(--text);
  font:500 15px Inter,sans-serif; padding:10px 12px; outline:0; }}
#cherche:focus {{ border-color:var(--accent); }}
.chips {{ display:flex; gap:6px; overflow-x:auto; margin-top:8px; padding-bottom:2px; scrollbar-width:none; }}
.chips::-webkit-scrollbar {{ display:none; }}
.chips button {{ flex:none; background:var(--surface); color:var(--text); border:1px solid var(--line); border-radius:99px;
  padding:6px 11px; font:600 13px Inter,sans-serif; cursor:pointer; }}
.chips button.on {{ background:var(--grad); color:var(--accent-ink); border-color:transparent; }}
.semaine {{ display:flex; gap:6px; overflow-x:auto; margin:4px -16px 12px; padding:2px 16px 4px; scrollbar-width:none; }}
.semaine::-webkit-scrollbar {{ display:none; }}
.semaine button {{ flex:none; width:64px; display:flex; flex-direction:column; align-items:center; gap:1px; padding:8px 0 7px;
  border-radius:14px; border:1px solid var(--line); background:var(--surface); color:var(--text); cursor:pointer; position:relative; }}
.semaine button span {{ font:600 11px Inter,sans-serif; color:var(--muted); text-transform:capitalize; }}
.semaine button b {{ font:700 22px "Barlow Condensed",sans-serif; line-height:1.05; }}
.semaine button small {{ font:600 10px Inter,sans-serif; white-space:nowrap; }}
.semaine .j-go small {{ color:var(--ok); }}
.semaine .j-calme small {{ color:var(--muted); }}
.semaine .j-vide {{ opacity:.5; }}
.semaine .j-go::after {{ content:""; position:absolute; top:6px; right:7px; width:7px; height:7px; border-radius:50%; background:var(--ok);
  box-shadow:0 0 0 3px color-mix(in srgb, var(--ok) 25%, transparent); }}
.semaine button.on {{ border:0; background:var(--grad); color:var(--accent-ink); }}
.semaine button.on span, .semaine button.on small {{ color:var(--accent-ink); }}
.jour-mot[hidden], .jour-corps[hidden], #styles button[hidden] {{ display:none !important; }}
.jour-mot .mot {{ margin-top:0; }}
.buts {{ background:var(--surface2); border-radius:12px; padding:9px 10px; margin:-2px 0 12px; }}
.buts-t {{ font:700 15px "Barlow Condensed",sans-serif; display:flex; justify-content:space-between; align-items:baseline; }}
.buts-t small {{ font:500 12px Inter,sans-serif; color:var(--muted); }}
.buts-g {{ display:grid; grid-template-columns:repeat(4,1fr); gap:5px; margin-top:6px; }}
.buts-g div {{ background:var(--surface); border-radius:8px; padding:5px 2px; text-align:center; }}
.buts-g span {{ display:block; font-size:10px; color:var(--muted); white-space:nowrap; }}
.buts-g b {{ font:700 17px "Barlow Condensed",sans-serif; color:#fbbf24; }}
.buts-s {{ font-size:12px; color:var(--muted); margin-top:6px; }}
.buts-s small {{ opacity:.75; }}
.buts.compact {{ background:none; padding:0; margin:0 0 8px; font-size:12px; color:var(--muted); }}
.buts.compact b {{ color:var(--text); white-space:nowrap; }}
.prono-buts::before {{ content:""; position:absolute; inset:0 0 auto 0; height:4px; background:linear-gradient(90deg,#fbbf24,#f97316); }}
.pb-pari {{ background:linear-gradient(120deg, rgba(251,191,36,.16), rgba(249,115,22,.10)); border:1px solid rgba(251,191,36,.45);
  border-radius:12px; padding:10px 12px; margin-bottom:10px; }}
.pb-pari > b {{ display:block; font:700 22px "Barlow Condensed",sans-serif; }}
.pb-pari span {{ font-size:13px; color:var(--muted); }}
.direct {{ margin:4px 0 14px; padding:12px; border-radius:16px; background:var(--surface);
  border:1.5px solid #fb7185; box-shadow:0 0 0 4px rgba(251,113,133,.10); }}
.direct[hidden] {{ display:none; }}
.direct-t {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }}
.direct-t b {{ font:700 20px "Barlow Condensed",sans-serif; color:#fb7185; }}
.direct-t button {{ background:var(--surface2); color:var(--text); border:1px solid var(--line); border-radius:99px; padding:6px 10px; font:600 12px Inter,sans-serif; cursor:pointer; }}
.dl {{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:8px; padding:8px 0; border-top:1px solid var(--line); font-size:14px; }}
.dl:first-child {{ border-top:0; }}
.dl b {{ font:700 22px "Barlow Condensed",sans-serif; min-width:58px; text-align:center; background:var(--surface2); border-radius:8px; padding:0 6px; }}
.dl .dl-e {{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.dl .dl-e.r {{ text-align:right; }}
.dl small {{ grid-column:1 / -1; text-align:center; color:#fb7185; font-size:11px; font-weight:600; margin-top:-2px; }}
.dl.moi b {{ background:var(--grad); color:var(--accent-ink); }}
.affiche.en-direct .ko-h {{ color:#fb7185; }}
.affiche.termine .ko-h {{ color:var(--text); }}
.mp-live {{ display:block; font-size:12px; font-weight:600; margin-top:2px; }}
.mp-live.ok {{ color:var(--ok); }} .mp-live.bad {{ color:var(--bad); }}
button.case {{ border:0; color:inherit; font:inherit; cursor:pointer; text-align:left; }}
button.case.pris, .ajout-buts button.pris {{ outline:2px solid #ec4899 !important; background:color-mix(in srgb, #ec4899 18%, var(--surface2)); }}
.ajout-buts {{ display:grid; grid-template-columns:repeat(4,1fr); gap:5px; margin-top:6px; }}
.ajout-buts button {{ background:var(--surface2); color:var(--text); border:1px dashed var(--line); border-radius:8px; padding:6px 2px;
  font:600 11px Inter,sans-serif; cursor:pointer; }}
.btn-plein {{ background:var(--grad); color:var(--accent-ink); border:0; border-radius:12px; padding:11px 14px; font:700 14px Inter,sans-serif; cursor:pointer; margin-top:10px; }}
.mt-res {{ background:var(--surface); border-radius:16px; padding:14px; margin-bottom:12px; border:2px solid var(--line); }}
.mt-res.ok {{ border-color:var(--ok); }} .mt-res.moy {{ border-color:var(--warn); }} .mt-res.bad {{ border-color:var(--bad); }}
.mt-t {{ font:700 26px "Barlow Condensed",sans-serif; }}
.mt-res > p {{ color:var(--muted); font-size:14px; margin:2px 0 6px; }}
.mt-res .grille {{ grid-template-columns:repeat(3,1fr); }}
.mt-al {{ margin:10px 0 0 18px; font-size:13px; color:var(--warn); display:flex; flex-direction:column; gap:4px; }}
.mt-l {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid #ec4899; border-radius:12px; padding:10px 12px; margin-bottom:8px; }}
.mt-h {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.mt-h b {{ font-size:15px; }}
.mt-h button {{ background:var(--surface2); border:0; color:var(--muted); border-radius:8px; width:28px; height:28px; cursor:pointer; }}
.mt-l small {{ display:block; color:var(--muted); font-size:12px; margin-top:2px; }}
.mt-g {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:8px; font-size:13px; color:var(--muted); }}
.mt-g b {{ color:var(--text); font:700 18px "Barlow Condensed",sans-serif; }}
.mt-g input {{ width:78px; margin-left:6px; background:var(--surface2); color:var(--text); border:1px solid var(--line); border-radius:8px; padding:6px; font:600 15px Inter,sans-serif; }}
.mt-v {{ margin-top:8px; font-size:13px; font-weight:600; padding:6px 8px; border-radius:8px; background:var(--surface2); }}
.mt-v.ok {{ color:var(--ok); }} .mt-v.moy {{ color:var(--warn); }} .mt-v.bad {{ color:var(--bad); }} .mt-v.att {{ color:var(--muted); }}
.mt-ia {{ font-style:italic; }}
.mt-exp {{ margin-top:8px; font-size:13px; padding:8px 10px; border-radius:10px; background:var(--surface2); border-left:3px solid var(--warn); }}
.mt-exp.ok {{ border-color:var(--ok); }} .mt-exp.eviter {{ border-color:var(--bad); }}
.mt-expg {{ background:var(--surface); border-radius:16px; padding:14px; margin-bottom:12px; border:2px solid var(--warn);
  background:linear-gradient(var(--surface),var(--surface)) padding-box, linear-gradient(120deg,#a855f7,#ec4899) border-box; border-color:transparent; }}
.mt-expg p {{ font-size:14px; margin-top:6px; }}
.mt-expg small {{ display:block; color:var(--muted); font-size:11px; margin-top:6px; }}
.mt-expg .mt-t {{ font-size:22px; }}
.mt-cle {{ background:var(--surface); border:2px dashed #a855f7; border-radius:16px; padding:14px; margin:6px 0 10px; }}
.mt-cle[hidden] {{ display:none; }}
.mt-cle p {{ font-size:13px; color:var(--muted); margin:6px 0 10px; }}
.mt-cle code {{ color:var(--text); }}
.mt-cle input {{ width:100%; background:var(--surface2); color:var(--text); border:1px solid var(--line); border-radius:10px; padding:10px; font:500 15px Inter,sans-serif; }}
.btn-plein[disabled] {{ opacity:.7; }}
.note a {{ color:var(--accent); }}
.mt-act {{ display:flex; flex-direction:column; gap:8px; margin-top:6px; }}
.mt-act button:not(.btn-plein) {{ background:var(--surface); color:var(--text); border:1px solid var(--line); border-radius:12px; padding:10px; font:600 14px Inter,sans-serif; cursor:pointer; }}
.barre-nav button {{ font-size:10px; }}
.semaine-m {{ margin:0 -16px 8px; }}
.semaine-m button {{ width:62px; padding:6px 0 5px; }}
.semaine-m button b {{ font-size:19px; }}
.semaine-m button.on {{ border:0; background:var(--grad); color:var(--accent-ink); }}
.semaine-m button.on span, .semaine-m button.on small {{ color:var(--accent-ink); }}
.vues {{ display:grid; grid-template-columns:1fr 1fr; gap:4px; background:var(--surface2); border-radius:12px; padding:4px; margin:0 0 12px; }}
.vues button {{ background:none; border:0; border-radius:9px; padding:8px 0; font:600 13px Inter,sans-serif; color:var(--muted); cursor:pointer; }}
.vues button.on {{ background:var(--surface); color:var(--text); box-shadow:0 1px 3px rgba(0,0,0,.25); }}
.ch-jt {{ font:700 22px "Barlow Condensed",sans-serif; margin:14px 0 6px; padding-bottom:4px; border-bottom:2px solid var(--line); }}
.ch-h {{ position:sticky; top:calc(8px + env(safe-area-inset-top)); z-index:3; display:inline-block; margin:10px 0 6px; padding:4px 12px; border-radius:99px;
  background:var(--grad); color:var(--accent-ink); font:700 14px Inter,sans-serif; }}
.ch-m {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--lig, var(--line)); border-radius:12px; margin-bottom:8px; overflow:hidden; }}
.ch-l {{ font-size:12px; font-weight:600; color:var(--muted); padding:8px 14px 0; }}
.ch-m .match {{ border-top:0; padding-top:4px; }}
html.verrouille body > *:not(#verrou) {{ visibility:hidden; }}
#verrou {{ position:fixed; inset:0; z-index:100; display:grid; place-items:center; padding:24px;
  background:radial-gradient(600px 400px at 20% 0%, rgba(198,255,61,.18), transparent 70%),
             radial-gradient(500px 400px at 100% 100%, rgba(34,211,238,.16), transparent 70%), var(--bg); }}
#verrou[hidden] {{ display:none; }}
.vr-box {{ width:min(320px, 100%); text-align:center; }}
.vr-logo {{ width:72px; height:72px; border-radius:18px; }}
.vr-t {{ font:700 28px "Barlow Condensed",sans-serif; margin-top:10px; }}
.vr-s {{ color:var(--muted); font-size:14px; min-height:20px; margin-top:2px; }}
.vr-s.err {{ color:var(--bad); }}
.vr-pts {{ display:flex; justify-content:center; gap:16px; margin:22px 0; }}
.vr-pts i {{ width:16px; height:16px; border-radius:50%; border:2px solid var(--muted); }}
.vr-pts i.on {{ background:var(--accent); border-color:var(--accent); }}
.vr-pts.secoue {{ animation:secoue .35s; }}
@keyframes secoue {{ 25% {{ transform:translateX(-10px); }} 75% {{ transform:translateX(10px); }} }}
.vr-pad {{ display:grid; grid-template-columns:repeat(3, 76px); justify-content:center; gap:14px; }}
.vr-pad button {{ width:76px; height:76px; border-radius:50%; border:1px solid var(--line); background:var(--surface);
  color:var(--text); font:600 28px Inter,sans-serif; cursor:pointer; }}
.vr-pad button:active {{ background:var(--surface2); }}
.vr-pad .vr-x {{ border:0; background:none; font-size:14px; color:var(--muted); }}
.vr-pad .vr-x[data-k="del"] {{ font-size:24px; }}
.vr-reste {{ display:block; margin-top:20px; font-size:13px; color:var(--muted); }}
.vr-oubli {{ margin-top:10px; background:none; border:0; color:var(--muted); text-decoration:underline; font-size:13px; cursor:pointer; }}
.pq {{ font-size:13px; line-height:1.45; margin:10px 0 0; padding:8px 10px; border-radius:10px;
  background:color-mix(in srgb, #fbbf24 10%, var(--surface2)); border-left:3px solid #fbbf24; }}
.pq-j {{ color:var(--text) !important; opacity:.85; white-space:normal !important; margin-top:3px; font-size:12px; line-height:1.35; }}
.toast {{ position:fixed; z-index:60; left:50%; transform:translateX(-50%); bottom:calc(96px + env(safe-area-inset-bottom));
  background:var(--text); color:var(--bg); font:600 14px Inter,sans-serif; padding:10px 16px; border-radius:99px;
  box-shadow:0 8px 24px rgba(0,0,0,.35); animation:monte .25s ease both; }}
.onglet {{ animation:fondu .25s ease both; }}
@keyframes fondu {{ from {{ opacity:0; transform:translateY(6px); }} }}
@media (prefers-reduced-motion: reduce) {{ .logo, .pari::after {{ animation:none; }} }}
@media (max-width:380px) {{ .bilan {{ grid-template-columns:repeat(2,1fr); }} }}

/* ===================== look appli de sport (sombre, énergique) ===================== */
.affiche {{ align-items:center; gap:4px; padding:12px 6px; margin:6px 0 10px; border-radius:16px;
  background:
    radial-gradient(120px 90px at 12% 50%, color-mix(in srgb, var(--p1) 14%, transparent), transparent 70%),
    radial-gradient(120px 90px at 88% 50%, color-mix(in srgb, var(--p2) 14%, transparent), transparent 70%),
    linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,0)), var(--surface2);
  box-shadow:inset 0 0 0 1px var(--line); position:relative; overflow:hidden; }}
.affiche::before {{ content:""; position:absolute; left:50%; top:0; bottom:0; width:1px; background:linear-gradient(transparent, var(--line), transparent); }}
.affiche > * {{ position:relative; }}
.ecu-w {{ display:grid; place-items:center; padding:6px; border-radius:50%;
  background:radial-gradient(circle, rgba(255,255,255,.10), rgba(255,255,255,.02) 70%); box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); transition:transform .3s; }}
.eq.fav .ecu-w {{ box-shadow:0 0 0 2px var(--fc), 0 0 22px -2px var(--fc); transform:scale(1.06); }}
.eq1 {{ --fc:var(--p1); }} .eq2 {{ --fc:var(--p2); }}
.eq span {{ font-weight:700; }}
.pill {{ font-style:normal; font:700 11px Inter,sans-serif; padding:3px 8px; border-radius:99px; white-space:nowrap;
  background:var(--fc); color:#06110b; letter-spacing:.01em; }}
.pill-o {{ background:transparent; color:var(--muted); box-shadow:inset 0 0 0 1px var(--line); }}
.ko {{ padding-top:0; min-width:64px; }}
.vs {{ font-style:normal; font:800 italic 15px "Barlow Condensed",sans-serif; letter-spacing:.06em; color:#06110b;
  background:var(--grad); padding:2px 9px; border-radius:7px; margin-bottom:6px; transform:skewX(-8deg);
  box-shadow:0 4px 14px -4px rgba(52,211,153,.6); }}
.affiche.grande .ko b {{ padding-top:0; }}
.affiche.en-direct {{ box-shadow:inset 0 0 0 1.5px #fb7185, 0 0 24px -8px #fb7185; }}
.affiche.en-direct .vs {{ background:#fb7185; animation:clignote 1.4s ease-in-out infinite; }}
.barre-p {{ height:20px; gap:3px; margin:0 0 12px; }}
.barre-p span {{ opacity:.9; border-radius:6px; display:flex; align-items:center; justify-content:center; overflow:hidden; min-width:6px; }}
.barre-p em {{ font-style:normal; font:700 11px Inter,sans-serif; color:#06110b; white-space:nowrap; }}
.barre-p span.on {{ opacity:1; box-shadow:0 0 0 2px var(--surface), 0 0 0 4px currentColor, 0 0 16px -2px currentColor; }}
.match .barre-p {{ height:18px; margin-bottom:8px; }}
.case {{ border-radius:10px; padding:8px; position:relative; box-shadow:inset 0 0 0 1px var(--line); transition:transform .15s; }}
.case:active {{ transform:scale(.96); }}
.case b {{ font:700 18px "Barlow Condensed",sans-serif; }}
.case.fav {{ box-shadow:inset 0 0 0 1.5px color-mix(in srgb, var(--accent) 60%, transparent); }}
.case.val {{ outline:0; box-shadow:0 0 0 2px var(--accent), 0 0 18px -4px var(--accent); }}
.case.val::after {{ content:"VALUE"; position:absolute; top:-8px; right:6px; font:800 9px Inter,sans-serif; letter-spacing:.06em;
  background:var(--accent); color:var(--accent-ink); padding:1px 5px; border-radius:5px; }}
.ch-m, details {{ background:linear-gradient(135deg, color-mix(in srgb, var(--lig, var(--accent)) 10%, transparent), transparent 45%), var(--surface);
  box-shadow:0 10px 26px -18px rgba(0,0,0,.8); }}
.ch-h {{ box-shadow:0 6px 16px -6px rgba(52,211,153,.6); }}
.carte {{ border-color:color-mix(in srgb, var(--line) 70%, transparent);
  box-shadow:0 18px 40px -24px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.04); }}
h2 {{ font-size:28px; text-transform:uppercase; letter-spacing:.02em; font-style:italic; }}
.carte h3, .combo-t {{ letter-spacing:.01em; }}
.ex-carte {{ position:relative; overflow:hidden; border-radius:18px; padding:16px; margin-bottom:12px;
  background:linear-gradient(var(--surface),var(--surface)) padding-box, var(--grad) border-box; border:2px solid transparent; }}
.ex-carte.ex-bad {{ background:linear-gradient(var(--surface),var(--surface)) padding-box, linear-gradient(120deg,#fb7185,#f97316) border-box; }}
.ex-carte.ex-att {{ background:linear-gradient(var(--surface),var(--surface)) padding-box, linear-gradient(120deg,#38bdf8,#a855f7) border-box; }}
.ex-t {{ font-size:11px; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); font-weight:700; }}
.ex-v {{ font:800 italic 26px "Barlow Condensed",sans-serif; margin-top:2px; line-height:1.1; }}
.ex-p {{ color:var(--muted); font-size:14px; margin-top:4px; }}
.ex-gros {{ display:flex; align-items:baseline; gap:10px; margin:14px 0 6px; flex-wrap:wrap; }}
.ex-gros b {{ font:800 46px/1 "Barlow Condensed",sans-serif; }}
.ex-gros span {{ color:var(--muted); font-size:13px; flex:1; min-width:150px; }}
.ex-gros span b {{ font:600 13px Inter,sans-serif; color:var(--text); }}
.courbe {{ display:block; width:100%; height:90px; margin:4px 0 12px; }}
.toi {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid #ec4899; border-radius:14px; padding:12px 14px; margin-bottom:12px; }}
.toi b.g {{ font:800 28px "Barlow Condensed",sans-serif; }}
.hist td i {{ font-style:normal; color:var(--muted); }}
.combo.st-semaine {{ --grad-ticket:linear-gradient(135deg,#c6ff3d 0%,#22d3ee 50%,#a855f7 100%); }}
.combo.st-semaine .jambes li {{ border-left-color:#22d3ee; }}
.sem h2 {{ margin-top:22px; }}
.sm-ok {{ color:var(--ok); }} .sm-warn {{ color:var(--warn); }} .sm-bad {{ color:var(--bad); }} .sm-att {{ color:var(--muted); }}
.sm-det {{ border-left:4px solid #22d3ee; }}
.j-txt .pq-j b {{ display:inline; font-size:12px; }}
.sm-liste {{ list-style:none; padding:0 14px 10px; display:flex; flex-direction:column; gap:8px; }}
.sm-l {{ display:flex; justify-content:space-between; gap:10px; padding-top:8px; border-top:1px solid var(--line); }}
.sm-l small {{ display:block; color:var(--muted); font-size:12px; }}
.sm-l .sm-d {{ color:var(--text); opacity:.8; margin-top:2px; }}
.sm-l.out {{ opacity:.55; }}
.sm-e {{ text-align:right; font-size:12px; font-weight:600; white-space:nowrap; }}
.combo.st-jour {{ --grad-ticket:linear-gradient(135deg,#34d399 0%,#22d3ee 55%,#3b82f6 100%); }}
.combo.st-jour .jambes li {{ border-left-color:#34d399; }}
.rj {{ margin:14px 0 12px; padding:14px; border-radius:16px; background:linear-gradient(135deg, color-mix(in srgb, var(--accent) 12%, transparent), transparent 60%), var(--surface);
  border:1px solid color-mix(in srgb, var(--accent) 40%, var(--line)); }}
.rj ul {{ list-style:none; margin:8px 0 0; display:flex; flex-direction:column; gap:8px; font-size:15px; }}
.rj-ev {{ margin-top:10px; font-size:13px; color:var(--warn); }}
.rj-n {{ margin-top:8px; font-size:12px; color:var(--muted); }}
.av {{ list-style:none; display:flex; flex-direction:column; gap:8px; }}
.av-l {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--muted); border-radius:12px; padding:10px 12px; }}
.av-l.av-ok {{ border-left-color:var(--ok); }} .av-l.av-warn {{ border-left-color:var(--warn); }} .av-l.av-att {{ opacity:.8; }}
.av-h {{ display:flex; align-items:center; gap:8px; }}
.av-h > span {{ display:flex; gap:2px; flex:none; }}
.av-h > div {{ flex:1; min-width:0; }}
.av-h b {{ display:block; font-size:14px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.av-h small {{ display:block; color:var(--muted); font-size:12px; }}
.av-n {{ font-style:normal; font-size:12px; font-weight:700; white-space:nowrap; }}
.av-ok .av-n {{ color:var(--ok); }} .av-warn .av-n {{ color:var(--warn); }} .av-att .av-n {{ color:var(--muted); }}
.av-p1 {{ margin-top:6px; font:700 18px "Barlow Condensed",sans-serif; }}
.av-p {{ font:700 12px Inter,sans-serif; color:var(--warn); margin-left:6px; }}
.av-t, .av-ia {{ display:block; font-size:12px; color:var(--muted); margin-top:3px; line-height:1.4; }}
.av-ia {{ color:var(--text); opacity:.85; }}
</style>
</head>
<body>
<div id="verrou" hidden>
  <div class="vr-box">
    <img src="logo.svg" alt="" class="vr-logo">
    <div class="vr-t" id="vr-t">Entre ton code</div>
    <div class="vr-s" id="vr-s">Prono Malin est verrouillé</div>
    <div class="vr-pts" id="vr-pts"><i></i><i></i><i></i><i></i></div>
    <div class="vr-pad">{''.join(f'<button data-k="{k}">{k}</button>' for k in "123456789")}<button data-k="plus" class="vr-x" id="vr-plus">Plus tard</button><button data-k="0">0</button><button data-k="del" class="vr-x">⌫</button></div>
    <label class="vr-reste" id="vr-reste"><input type="checkbox" id="vr-rc"> Rester déverrouillé 30 jours sur ce téléphone</label>
    <button class="vr-oubli" id="vr-oubli">Code oublié ?</button>
  </div>
</div>
{bandeau_demo}
<header>
  <div class="haut"><div class="date">{date_txt} · mis à jour {d:%H:%M}</div>
    <button class="maj" onclick="location.reload()">Actualiser</button></div>
  <div class="marque"><svg class="logo" viewBox="40 40 432 432" aria-hidden="true">
  <defs>
    <linearGradient id="lgg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c6ff3d"/><stop offset=".55" stop-color="#34d399"/><stop offset="1" stop-color="#22d3ee"/></linearGradient>
    <radialGradient id="lgglowA"><stop offset="0" stop-color="#c6ff3d" stop-opacity=".28"/><stop offset="1" stop-color="#c6ff3d" stop-opacity="0"/></radialGradient>
    <radialGradient id="lgglowB"><stop offset="0" stop-color="#22d3ee" stop-opacity=".22"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient>
    <clipPath id="lgballon"><circle cx="292" cy="222" r="118"/></clipPath>
  </defs>
  
  <g transform="translate(-12 0)">
    <rect x="128" y="104" width="78" height="318" rx="39" fill="url(#lgg)"/>
    <circle cx="292" cy="222" r="118" fill="url(#lgg)"/>
    <g clip-path="url(#lgballon)" fill="#060b09" stroke="#060b09" stroke-width="9" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="292.0,180.0 331.9,209.0 316.7,256.0 267.3,256.0 252.1,209.0"/><line x1="292.0" y1="180.0" x2="292.0" y2="130.0"/><line x1="331.9" y1="209.0" x2="379.5" y2="193.6"/><line x1="316.7" y1="256.0" x2="346.1" y2="296.5"/><line x1="267.3" y1="256.0" x2="237.9" y2="296.5"/><line x1="252.1" y1="209.0" x2="204.5" y2="193.6"/><polygon points="309.6,82.1 320.5,115.6 292.0,136.4 263.5,115.6 274.4,82.1"/><polygon points="430.5,195.5 402.0,216.3 373.4,195.5 384.3,162.0 419.6,162.0"/><polygon points="360.0,345.6 331.4,324.8 342.3,291.3 377.6,291.3 388.5,324.8"/><polygon points="195.5,324.8 206.4,291.3 241.7,291.3 252.6,324.8 224.0,345.6"/><polygon points="164.4,162.0 199.7,162.0 210.6,195.5 182.0,216.3 153.5,195.5"/>
    </g>
    <circle cx="292" cy="222" r="118" fill="none" stroke="#060b09" stroke-width="10"/>
  </g>
</svg><div><h1>Prono <em>Malin</em></h1><div class="slogan">Parier moins, parier mieux.</div></div></div>
  <div class="resume">
    <div><span>Matchs sur 7 jours</span><b>{len(analyses)}</b></div>
    <div><span>Value bets</span><b>{len(values)}</b></div>
    <div><span>Championnats</span><b>{len({m["sport_key"] for m in analyses})}</b></div>
  </div>
  <div class="installer" id="installer"><button onclick="fermer()" aria-label="Fermer">×</button>
    <b>Installe Prono Malin :</b> touche <b>Partager</b> en bas de Safari, puis <b>Sur l'écran d'accueil</b>.</div>
</header>

<main>
<div class="onglet" id="t-jour">
<section class="direct" id="direct" hidden>
  <div class="direct-t"><b>⚡ En direct</b><button id="btn-alertes" onclick="activerAlertes()">🔔 Alertes buts</button></div>
  <div id="direct-l"></div>
</section>
<div class="semaine" id="semaine">{selecteur}</div>
{mots}
{section_semaine(infos.get("semaine"))}
<section class="budget">
  <label for="somme">Ma mise du jour</label>
  <div class="saisie"><input id="somme" type="number" inputmode="decimal" min="0" step="0.5" placeholder="Ex. 6"><span>€</span></div>
  <div class="puces">{''.join(f'<button data-v="{x}">{x} €</button>' for x in (5, 10, 20, 50))}</div>
  <div class="mode"><button data-m="combine" class="on">🎟️ En combiné</button><button data-m="simples">Paris séparés</button></div>
  <div class="styles" id="styles"><button data-s="prudent">🛡️ Prudent</button><button data-s="equilibre">⚖️ Équilibré</button><button data-s="gros">🚀 Gros gain</button><button data-s="buts">⚽ Buts</button><button data-s="mixte">🔀 Mixte</button></div>
  <p class="budget-res" id="budget-res">Tape la somme que tu sors aujourd'hui.</p>
</section>

{corps}
</div>

<div class="onglet" id="t-matchs" hidden>
<h2>📅 Tous les matchs <small>meilleure cote · proba marché</small></h2>
<div class="filtres">
  <div class="semaine semaine-m" id="jours-m">{selecteur_m}</div>
  <input id="cherche" type="search" placeholder="🔍 Chercher une équipe…" autocomplete="off">
  <div class="chips" id="chips"><button class="on" data-l="">Tous</button>{''.join(f'<button data-l="{e(ch[1])}">{ch[0]} {e(ch[1])}</button>' for ch in par_champ)}</div>
</div>
<div class="vues"><button data-v="heure" class="on">🕒 Par heure</button><button data-v="champ">🏆 Par championnat</button></div>
<div id="vue-heure">{chrono or '<p class="vide">Aucun match dans les prochains jours.</p>'}</div>
<div id="vue-champ" hidden>{groupes or '<p class="vide">Aucun match dans les prochaines heures.</p>'}</div>
<p class="vide" id="aucun" hidden>Aucun match ne correspond.</p>
</div>

<div class="onglet" id="t-ticket" hidden>
<h2>✏️ Mon ticket <small>compose, l'expert vérifie</small></h2>
<div id="mt"></div>
</div>

<div class="onglet" id="t-mes" hidden>
<h2 id="mes-paris-t">✍️ Mes paris <small>enregistrés sur ce téléphone</small></h2>
<div id="mes-paris"><p class="vide">Touche « J'ai joué ce pari » sur un pari ou un combiné : il apparaîtra ici et sera réglé tout seul.</p></div>

</div>

<div class="onglet" id="t-bilan" hidden>
<h2>📊 Bilan de l'expert</h2>
{section_expert(infos.get("expert"))}
<h3 class="sous">🧠 Ce que l'agent a appris</h3>
{section_appris(infos.get("appris"))}
<h3 class="sous">Paris simples</h3>
{section_historique(historique, b)}
<h3 class="sous">Combinés</h3>
{section_combines(infos.get("combines") or [], infos.get("bilan_combines") or {"tous": {}, "conseilles": {}})}

<footer>
  <p><b>Comment lire :</b> la « proba marché » vient du bookmaker le plus juste (Pinnacle), marge retirée.
  Un value bet, c'est quand la meilleure cote en France paie plus que ce risque réel.
  L'« avantage » est le gain moyen espéré par euro misé, sur la durée.
  <b>Forme :</b> V victoire, N nul, D défaite, le match le plus récent à droite (source : football-data.co.uk).</p>
  <p>Aucun pari n'est sûr. Ne mise que ce que tu peux perdre et respecte les mises conseillées.
  Besoin d'aide : <b>Joueurs Info Service, 09 74 75 13 13</b> (appel non surtaxé).</p>
  <p>Généré automatiquement{credits}.</p>
  <p>{statut_ia(infos.get("ia"))}</p>
  <p>🔒 Code d'accès : <a href="#" onclick="reglerCode(); return false" id="lien-code">régler</a></p>
  <p>🧠 Mémoire de l'actu : {infos.get("memoire_equipes", 0)} équipe{'s' if infos.get("memoire_equipes", 0) > 1 else ''} suivie{'s' if infos.get("memoire_equipes", 0) > 1 else ''} (21 jours).</p>
</footer>
</div>
</main>

<nav class="barre-nav">
  <button data-t="jour" class="on"><i>🎯</i>Aujourd'hui</button>
  <button data-t="matchs"><i>📅</i>Matchs</button>
  <button data-t="ticket"><i>✏️</i>Mon ticket<span class="pastille" id="nb-ticket" hidden></span></button>
  <button data-t="mes"><i>✍️</i>Mes paris<span class="pastille" id="nb-attente" hidden></span></button>
  <button data-t="bilan"><i>📊</i>Bilan</button>
</nav>
<div class="toast" id="toast" hidden></div>
<script>
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {{}});
const appli = window.navigator.standalone || matchMedia("(display-mode: standalone)").matches;
const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
let vu = null; try {{ vu = localStorage.getItem("installer-vu"); }} catch (e) {{}}
if (ios && !appli && !vu) document.getElementById("installer").style.display = "block";
// ---- ma mise du jour : répartition sur les paris jouables
const champ = document.getElementById("somme");
const fmt = x => x.toFixed(2).replace(".", ",").replace(",00", "") + " €";
let jourActif = "{jours[0]["cle"]}", cartesV = [], tickets = [];
// plusieurs tickets cochables à la fois (ancienne clé « style-ticket » reprise si elle existe)
let stylesCoches = new Set(), choixPerso = false;
try {{
  const l = JSON.parse(localStorage.getItem("styles-tickets") || "null");
  if (Array.isArray(l)) {{ stylesCoches = new Set(l); choixPerso = true; }}
  else if (localStorage.getItem("style-ticket")) {{ stylesCoches = new Set([localStorage.getItem("style-ticket")]); choixPerso = true; }}
}} catch (e) {{}}
function majJour() {{
  const corps = document.querySelector(`.jour-corps[data-jour="${{jourActif}}"]`);
  cartesV = [...corps.querySelectorAll("article[data-poids]")].filter(c => +c.dataset.poids > 0);
  tickets = [...corps.querySelectorAll(".combo[data-style]")];
  document.querySelectorAll("#styles button").forEach(b => b.hidden = !tickets.some(t => t.dataset.style === b.dataset.s));
}}
const ticketsCoches = () => {{
  if (!choixPerso && tickets.length) return [tickets.find(t => t.dataset.style === "equilibre") || tickets[0]];
  return tickets.filter(t => stylesCoches.has(t.dataset.style));
}};
function choisirJour(cle) {{
  jourActif = cle;
  document.querySelectorAll(".jour-mot, .jour-corps").forEach(el => el.hidden = el.dataset.jour !== cle);
  document.querySelectorAll("#semaine button").forEach(b => b.classList.toggle("on", b.dataset.j === cle));
  const lbl = document.querySelector('label[for="somme"]');
  const b = document.querySelector(`#semaine button[data-j="${{cle}}"]`);
  lbl.textContent = cle === "{jours[0]["cle"]}" ? "Ma mise du jour" : "Ma mise pour " + (b.querySelector("span").textContent === "Demain" ? "demain" : b.querySelector("span").textContent.toLowerCase() + " " + b.querySelector("b").textContent);
  try {{ sessionStorage.setItem("jour", cle); }} catch (e) {{}}
  majJour(); repartir();
}}
function choisirStyle(st) {{
  if (!choixPerso) {{ stylesCoches = new Set(ticketsCoches().map(t => t.dataset.style)); choixPerso = true; }}
  if (stylesCoches.has(st)) stylesCoches.delete(st); else stylesCoches.add(st);
  try {{ localStorage.setItem("styles-tickets", JSON.stringify([...stylesCoches])); localStorage.removeItem("style-ticket"); }} catch (e) {{}}
  repartir();
}}
let mode = "combine";
try {{ mode = localStorage.getItem("mode-mise") || "combine"; }} catch (e) {{}}
function choisirMode(m) {{
  mode = m;
  document.querySelectorAll(".mode button").forEach(b => b.classList.toggle("on", b.dataset.m === m));
  try {{ localStorage.setItem("mode-mise", m); }} catch (e) {{}}
  repartir();
}}
function repartir() {{
  const total = Math.max(0, parseFloat(String(champ.value).replace(",", ".")) || 0);
  const res = document.getElementById("budget-res");
  document.querySelectorAll(".puces button").forEach(b => b.classList.toggle("on", +b.dataset.v === total));
  document.querySelectorAll(".calc").forEach(c => c.hidden = true);
  // cases cochées (même sans somme tapée)
  const coches = ticketsCoches();
  document.getElementById("styles").hidden = mode !== "combine" || !tickets.length;
  const actifs = new Set(coches.map(t => t.dataset.style));
  document.querySelectorAll("#styles button").forEach(b => b.classList.toggle("on", choixPerso ? stylesCoches.has(b.dataset.s) : actifs.has(b.dataset.s)));
  document.querySelectorAll(".combo[data-style]").forEach(t => t.classList.toggle("choisi", mode === "combine" && coches.includes(t)));
  if (!total) {{ res.innerHTML = mode === "combine" ? "Coche un ou plusieurs tickets, puis tape la somme que tu sors." : "Tape la somme que tu sors aujourd'hui."; return; }}
  if (mode === "combine") {{
    if (!tickets.length) {{ res.innerHTML = "<b>Pas de combiné ce jour-là.</b> Garde tes " + fmt(total) + " en poche."; return; }}
    if (!coches.length) {{ res.innerHTML = "👆 <b>Coche au moins un ticket</b> (Prudent, Équilibré, Gros gain, Buts, Mixte) pour répartir ta mise."; return; }}
    // part égale par ticket, au centime ; le reste va sur le dernier
    const centimes = Math.round(total * 100), part = Math.floor(centimes / coches.length);
    let maxi = 0, risque = 0, estime = 0;
    coches.forEach((t, i) => {{
      const mise = (i === coches.length - 1 ? centimes - part * (coches.length - 1) : part) / 100;
      const gain = mise * +t.dataset.cote;
      maxi += gain;
      if (t.classList.contains("risque")) risque++;
      if (t.classList.contains("estime")) estime++;
      const z = t.querySelector(".calc");
      z.innerHTML = `<div><span>Ta mise</span><b>${{fmt(mise)}}</b></div><div class="r"><span>Si ça passe, tu touches${{t.classList.contains("estime") ? " (au moins)" : ""}}</span><b>${{fmt(gain)}}</b></div>`;
      z.hidden = false;
    }});
    const noms = coches.map(t => t.dataset.nom).join(" + ");
    res.innerHTML = coches.length === 1
      ? `Tes <b>${{fmt(total)}}</b> sur le combiné <b>${{noms}}</b> : s'il passe, tu touches <b class="gros">${{fmt(maxi)}}</b>. Un seul raté et tu perds ${{fmt(total)}}.`
      : `<b>${{fmt(total)}}</b> répartis sur <b>${{coches.length}} tickets</b> (${{noms}}), soit ${{fmt(total / coches.length)}} chacun. ` +
        `Si tout passe : <b class="gros">${{fmt(maxi)}}</b>. Si rien ne passe : tu perds ${{fmt(total)}}. ` +
        `<br><small>Chaque combiné est indépendant : un raté dans un ticket ne fait perdre que ce ticket.</small>`;
    if (estime) res.innerHTML += `<br><small>⚽🔀 Buts et Mixte : gain calculé à la cote minimum à obtenir chez ton bookmaker.</small>`;
    if (risque) res.innerHTML += `<br><b>⚠️ ${{risque}} ticket${{risque > 1 ? "s" : ""}} non conseillé${{risque > 1 ? "s" : ""}} ce jour-là.</b>`;
    return;
  }}
  if (!cartesV.length) {{ res.innerHTML = "<b>Aucun bon pari ce jour-là.</b> Garde tes " + fmt(total) + " en poche : c'est la meilleure décision du jour."; return; }}
  const somme = cartesV.reduce((t, c) => t + +c.dataset.poids, 0);
  let reste = Math.round(total * 10), maxi = 0;
  cartesV.forEach((c, i) => {{
    const dixiemes = i === cartesV.length - 1 ? reste : Math.round(total * 10 * c.dataset.poids / somme);
    reste -= dixiemes;
    const mise = dixiemes / 10, gain = mise * +c.dataset.cote;
    maxi += gain;
    const z = c.querySelector(".calc");
    z.innerHTML = `<div><span>Ta mise</span><b>${{fmt(mise)}}</b></div><div class="r"><span>Si ça passe, tu touches</span><b>${{fmt(gain)}}</b></div>`;
    z.hidden = false;
  }});
  res.innerHTML = `<b>${{fmt(total)}}</b> répartis sur <b>${{cartesV.length}} pari${{cartesV.length > 1 ? "s" : ""}}</b>. ` +
    `Si tout passe : <b class="gros">${{fmt(maxi)}}</b>. Si rien ne passe : tu perds ${{fmt(total)}}.`;
}}
const sauverMise = () => {{ try {{ localStorage.setItem("mise-jour", JSON.stringify({{ jour: "{d:%Y-%m-%d}", v: champ.value }})); }} catch (e) {{}} }};
champ.addEventListener("input", () => {{ sauverMise(); repartir(); }});
document.querySelectorAll(".mode button").forEach(b => b.addEventListener("click", () => choisirMode(b.dataset.m)));
document.querySelectorAll("#styles button").forEach(b => b.addEventListener("click", () => choisirStyle(b.dataset.s)));
document.querySelectorAll(".combo[data-style]").forEach(t => t.addEventListener("click", ev => {{ if (mode === "combine" && !ev.target.closest(".joue")) choisirStyle(t.dataset.style); }}));
document.querySelectorAll("#semaine button").forEach(b => b.addEventListener("click", () => choisirJour(b.dataset.j)));
majJour();
try {{ const j = sessionStorage.getItem("jour"); if (j && document.querySelector(`#semaine button[data-j="${{j}}"]`)) choisirJour(j); else choisirJour(jourActif); }} catch (e) {{ choisirJour(jourActif); }}
document.querySelectorAll(".mode button").forEach(b => b.classList.toggle("on", b.dataset.m === mode));
document.querySelectorAll(".puces button").forEach(b => b.addEventListener("click", () => {{ champ.value = b.dataset.v; sauverMise(); repartir(); }}));
try {{ const m = JSON.parse(localStorage.getItem("mise-jour") || "null"); if (m && m.jour === "{d:%Y-%m-%d}") {{ champ.value = m.v; repartir(); }} }} catch (e) {{}}

// ---- mes vrais paris (gardés sur ce téléphone, réglés avec les résultats publiés par l'agent)
const RESULTATS = {json.dumps(infos.get("resultats") or {}, ensure_ascii=False)};
const lireMP = () => {{ try {{ return JSON.parse(localStorage.getItem("mes-paris") || "[]"); }} catch (e) {{ return []; }} }};
const ecrireMP = l => {{ try {{ localStorage.setItem("mes-paris", JSON.stringify(l)); }} catch (e) {{}} }};
function ouvrirJoue(btn) {{
  const carte = btn.closest("article"), f = carte.querySelector(".joue-f");
  const p = JSON.parse(carte.dataset.pari);
  const calc = carte.querySelector(".calc:not([hidden]) b");
  f.querySelector(".j-mise").value = calc ? calc.textContent.replace(/[^0-9,]/g, "").replace(",", ".") : "";
  f.querySelector(".jj-cote").value = p.cote;
  f.hidden = !f.hidden;
}}
function enregistrerJoue(btn) {{
  const carte = btn.closest("article"), f = carte.querySelector(".joue-f");
  const p = JSON.parse(carte.dataset.pari);
  const mise = parseFloat(f.querySelector(".j-mise").value), cote = parseFloat(f.querySelector(".jj-cote").value);
  if (!(mise > 0) || !(cote > 1)) {{ alert("Indique ta mise et la cote que tu as eue."); return; }}
  const l = lireMP();
  l.push({{ ...p, mise, cote, uid: Date.now() + "-" + Math.random().toString(36).slice(2, 6), joueLe: new Date().toISOString() }});
  ecrireMP(l); f.hidden = true; marquerJoues(); afficherMP();
  toast("✅ Ajouté à « Mes paris »");
}}
function resultat(id) {{
  const d = typeof resDirect === "function" ? resDirect(id) : null;
  return RESULTATS[id] || (d && d.fini ? d : null);
}}
function statutMP(p) {{
  if (p.manuel) return p.manuel;
  if (p.type === "buts") {{
    const r = resultat(p.id);
    if (!r || !r.score) return "en attente";
    const [d, x] = r.score.split("-").map(Number), t = d + x, btts = d > 0 && x > 0;
    const ok = {{ plus15: t >= 2, moins15: t < 2, plus25: t >= 3, moins25: t < 3, plus35: t >= 4, moins35: t < 4, btts: btts, pas_btts: !btts }}[p.marche];
    return ok === undefined ? "en attente" : ok ? "gagné" : "perdu";
  }}
  if (p.type === "combine") {{
    const r = p.jambes.map(j => {{
      const x = resultat(j.id);
      if (!x) return null;
      if (j.marche) {{
        if (!x.score) return null;
        const [d, e] = x.score.split("-").map(Number), t = d + e, b = d > 0 && e > 0;
        return {{ plus25: t >= 3, moins25: t < 3, btts: b, pas_btts: !b }}[j.marche] ?? null;
      }}
      return x.res === j.court;
    }});
    if (r.includes(false)) return "perdu";
    return r.every(x => x === true) ? "gagné" : "en attente";
  }}
  const r = resultat(p.id);
  return r ? (r.res === p.court ? "gagné" : "perdu") : "en attente";
}}
function marquerJoues() {{
  const ids = new Set(lireMP().map(p => p.id));
  document.querySelectorAll("article[data-pari]").forEach(c => {{
    const b = c.querySelector(".btn-joue");
    if (b && ids.has(JSON.parse(c.dataset.pari).id)) {{ b.classList.add("fait"); b.textContent = "✅ Joué — rejouer ?"; }}
  }});
}}
function regler(uid, v) {{ const l = lireMP(); const p = l.find(x => x.uid === uid); if (p) {{ p.manuel = v; ecrireMP(l); afficherMP(); }} }}
function suppr(uid) {{ if (confirm("Supprimer ce pari de ta liste ?")) {{ ecrireMP(lireMP().filter(x => x.uid !== uid)); afficherMP(); marquerJoues(); }} }}
function bilanToi() {{
  const z = document.getElementById("toi-bilan"); if (!z) return;
  const l = lireMP(); if (!l.length) {{ z.innerHTML = ""; return; }}
  let n = 0, g = 0, mises = 0, ben = 0;
  l.forEach(p => {{ const s = statutMP(p), m = +p.mise || 0;
    if (s === "gagné") {{ n++; g++; mises += m; ben += m * ((+p.cote || 1) - 1); }}
    else if (s === "perdu") {{ n++; mises += m; ben -= m; }} }});
  const att = l.length - n, c = ben >= 0 ? "vert" : "rouge", f = x => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(2).replace(".", ",") + " €";
  z.innerHTML = `<div class="toi"><div class="ex-t">✍️ Toi, avec tes vrais paris</div>
    <b class="g ${{c}}">${{n ? f(ben) : "—"}}</b> <span class="note">${{n}} réglé${{n > 1 ? "s" : ""}}, ${{g}} gagné${{g > 1 ? "s" : ""}}${{mises ? " · rendement " + (ben / mises * 100 >= 0 ? "+" : "") + (ben / mises * 100).toFixed(0) + " %" : ""}}${{att ? " · " + att + " en attente" : ""}}</span></div>`;
}}
function afficherMP() {{
  setTimeout(bilanToi, 0);
  const l = lireMP(), z = document.getElementById("mes-paris");
  if (!l.length) return;
  let mises = 0, gains = 0, n = 0, g = 0, att = 0, engage = 0, lignes = "";
  l.slice().sort((a, b) => (b.joueLe || "").localeCompare(a.joueLe || "")).forEach(p => {{
    const st = statutMP(p), gain = st === "gagné" ? p.mise * (p.cote - 1) : st === "perdu" ? -p.mise : 0;
    engage += p.mise;
    if (st === "en attente") att++; else {{ n++; mises += p.mise; gains += gain; if (st === "gagné") g++; }}
    const cls = {{ "gagné": "ok", "perdu": "bad" }}[st] || "att";
    let live = "";
    if (st === "en attente" && typeof resDirect === "function") {{
      const ok1 = (id, court, marche) => {{
        const d = resDirect(id); if (!d) return null;
        if (marche) {{ const [x, y] = d.score.split("-").map(Number), t = x + y, b = x > 0 && y > 0;
          return {{ plus25: t >= 3, moins25: t < 3, plus15: t >= 2, moins15: t < 2, plus35: t >= 4, moins35: t < 4, btts: b, pas_btts: !b }}[marche]; }}
        return d.res === court;
      }};
      const legs = p.type === "combine" ? p.jambes : [{{ id: p.id, court: p.court, marche: p.marche }}];
      const etats = legs.map(j => ok1(j.id, j.court, j.marche)).filter(x => x !== null && x !== undefined);
      if (etats.length) {{
        const bons = etats.filter(Boolean).length;
        live = `<small class="mp-live ${{bons === etats.length ? "ok" : "bad"}}">● en direct : ${{bons}}/${{legs.length}} ${{bons === etats.length ? "ça passe" : "ça ne passe pas"}} pour l'instant</small>`;
      }}
    }}
    const esc = t => String(t).replace(/[&<>"]/g, c => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }})[c]);
    lignes += `<tr><td>${{esc(p.pari)}}<small>${{esc(p.match)}} · cote ${{p.cote.toFixed(2)}} · ${{esc(p.bk || "")}}</small>${{live}}</td>
      <td class="r">${{fmt(p.mise)}}<small class="st ${{cls}}">${{st}}${{st !== "en attente" ? " " + (gain >= 0 ? "+" : "") + fmt(gain) : ""}}</small>
      <div class="mp-act"><button onclick="regler('${{p.uid}}','gagné')">✓</button><button onclick="regler('${{p.uid}}','perdu')">✗</button><button onclick="suppr('${{p.uid}}')">🗑</button></div></td></tr>`;
  }});
  const pa = document.getElementById("nb-attente"); pa.textContent = att; pa.hidden = !att;
  const roi = mises ? (gains >= 0 ? "+" : "") + (gains / mises * 100).toFixed(1).replace(".", ",") + " %" : "—";
  const c = gains >= 0 ? "vert" : "rouge";
  z.innerHTML = `<div class="bilan"><div><span>Paris réglés</span><b>${{n}}</b></div><div><span>Gagnés</span><b>${{g}}</b></div>
    <div><span>Bénéfice</span><b class="${{c}}">${{(gains >= 0 ? "+" : "") + fmt(gains)}}</b></div><div><span>Rendement</span><b class="${{c}}">${{roi}}</b></div></div>
    <p class="note">${{att}} en attente · misé au total ${{fmt(engage)}}. Réglés tout seuls avec les scores ; ✓ ✗ pour corriger à la main.</p>
    <table class="hist">${{lignes}}</table>`;
}}
marquerJoues(); afficherMP();

// ---- onglets
function ouvrirOnglet(t, haut = true) {{
  document.querySelectorAll(".onglet").forEach(o => o.hidden = o.id !== "t-" + t);
  document.querySelectorAll(".barre-nav button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  document.querySelector("header").classList.toggle("reduit", t !== "jour");
  try {{ sessionStorage.setItem("onglet", t); }} catch (e) {{}}
  if (haut) window.scrollTo({{ top: 0 }});
}}
document.querySelectorAll(".barre-nav button").forEach(b => b.addEventListener("click", () => ouvrirOnglet(b.dataset.t)));
try {{ const t = sessionStorage.getItem("onglet"); if (t) ouvrirOnglet(t, false); }} catch (e) {{}}

// ---- filtres des matchs
let ligue = "", jourM = "{jours[0]["cle"]}";
try {{ const v = sessionStorage.getItem("jour-m"); if (v !== null) jourM = v; }} catch (e) {{}}
let vueM = "heure";
try {{ vueM = localStorage.getItem("vue-matchs") || "heure"; }} catch (e) {{}}
function choisirVue(v) {{
  vueM = v;
  document.getElementById("vue-heure").hidden = v !== "heure";
  document.getElementById("vue-champ").hidden = v !== "champ";
  document.querySelectorAll(".vues button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  try {{ localStorage.setItem("vue-matchs", v); }} catch (e) {{}}
  filtrer();
}}
function filtrer() {{
  const q = document.getElementById("cherche").value.trim().toLowerCase();
  let visibles = 0;
  if (vueM === "heure") {{
    document.querySelectorAll("#vue-heure .ch-m").forEach(c => {{
      const m = c.querySelector(".match");
      const ok = (!ligue || c.dataset.l === ligue) && (!jourM || m.dataset.jour === jourM) && (!q || c.textContent.toLowerCase().includes(q));
      c.hidden = !ok; m.hidden = !ok; if (ok) visibles++;
    }});
    // on masque les repères d'heure et de jour devenus vides
    document.querySelectorAll("#vue-heure .ch-h").forEach(h => {{
      let el = h.nextElementSibling, n = 0;
      while (el && !el.classList.contains("ch-h")) {{ if (!el.hidden) n++; el = el.nextElementSibling; }}
      h.hidden = n === 0;
    }});
    document.querySelectorAll("#vue-heure .ch-jour").forEach(j => j.hidden = !j.querySelector(".ch-m:not([hidden])"));
    document.getElementById("aucun").hidden = visibles > 0;
    return;
  }}
  document.querySelectorAll("#t-matchs details").forEach(d => {{
    const okL = !ligue || d.dataset.l === ligue;
    let n = 0;
    d.querySelectorAll(".match").forEach(m => {{
      const ok = okL && (!jourM || m.dataset.jour === jourM) && (!q || m.textContent.toLowerCase().includes(q));
      m.hidden = !ok; if (ok) n++;
    }});
    d.hidden = n === 0;
    if (q || ligue || jourM) d.open = n > 0;
    const cpt = d.querySelector(".cpt-n"); if (cpt) cpt.textContent = n + " match" + (n > 1 ? "s" : "");
    visibles += n;
  }});
  document.getElementById("aucun").hidden = visibles > 0;
}}
document.getElementById("cherche").addEventListener("input", filtrer);
function choisirJourM(v) {{
  jourM = v;
  document.querySelectorAll("#jours-m button").forEach(b => b.classList.toggle("on", b.dataset.jm === v));
  try {{ sessionStorage.setItem("jour-m", v); }} catch (e) {{}}
  filtrer();
}}
document.querySelectorAll("#jours-m button").forEach(b => b.addEventListener("click", () => choisirJourM(b.dataset.jm)));
document.querySelectorAll(".vues button").forEach(b => b.addEventListener("click", () => choisirVue(b.dataset.v)));
choisirJourM(jourM); choisirVue(vueM);
document.querySelectorAll("#chips button").forEach(b => b.addEventListener("click", () => {{
  ligue = b.dataset.l;
  document.querySelectorAll("#chips button").forEach(x => x.classList.toggle("on", x === b));
  filtrer();
}}));

// ---- compte à rebours avant chaque match
function rebours() {{
  const now = Date.now();
  document.querySelectorAll(".cd").forEach(el => {{
    const dt = (new Date(el.dataset.ko) - now) / 60000;
    let t = "", c = "";
    if (dt > 24 * 60) t = "dans " + Math.round(dt / 1440) + " j";
    else if (dt > 60) t = "dans " + Math.floor(dt / 60) + " h " + String(Math.round(dt % 60)).padStart(2, "0");
    else if (dt > 0) {{ t = "dans " + Math.ceil(dt) + " min"; c = "bientot"; }}
    else if (dt > -110) {{ t = "● en cours"; c = "live"; }}
    else {{ t = "terminé"; c = "fini"; }}
    el.textContent = t; el.className = "cd " + c;
  }});
}}
rebours(); setInterval(rebours, 30000);

// ---- ⚡ scores en direct (ESPN, lus par le téléphone toutes les 45 s)
const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer";
var DIRECT = {{}};            // mid -> {{ h, a, etat, minute, fini }}
let directEnErreur = false;
const affichesParMid = () => {{
  const m = {{}};
  document.querySelectorAll(".affiche[data-mid]").forEach(el => (m[el.dataset.mid] = m[el.dataset.mid] || []).push(el));
  return m;
}};
function mesIds() {{
  const ids = new Set();
  lireMP().forEach(p => {{ if (statutMP(p) === "en attente") {{ ids.add(p.id); (p.jambes || []).forEach(j => ids.add(j.id)); }} }});
  return ids;
}}
function resDirect(mid) {{
  const d = DIRECT && DIRECT[mid];
  if (!d || d.etat === "pre") return null;
  return {{ res: d.h > d.a ? "1" : d.h < d.a ? "2" : "N", score: d.h + "-" + d.a, fini: d.fini }};
}}
async function majDirect() {{
  if (document.hidden) return;
  const parMid = affichesParMid(), now = Date.now(), aLire = {{}};
  Object.values(parMid).forEach(els => {{
    const el = els[0]; if (!el.dataset.espn) return;
    const ko = new Date(el.dataset.ko).getTime();
    if (now > ko - 15 * 60e3 && now < ko + 150 * 60e3) {{
      const [lig] = el.dataset.espn.split("|");
      const jour = new Date(ko).toISOString().slice(0, 10).replace(/-/g, "");
      aLire[lig + "|" + jour] = 1;
    }}
  }});
  const cles = Object.keys(aLire);
  if (!cles.length) {{ dessinerDirect(); return; }}
  const parEspn = {{}};
  await Promise.all(cles.map(async k => {{
    const [lig, jour] = k.split("|");
    try {{
      const r = await fetch(`${{ESPN}}/${{lig}}/scoreboard?dates=${{jour}}`, {{ cache: "no-store" }});
      const j = await r.json();
      (j.events || []).forEach(ev => parEspn[lig + "|" + ev.id] = ev);
      directEnErreur = false;
    }} catch (e) {{ directEnErreur = true; }}
  }}));
  const suivis = mesIds();
  Object.entries(parMid).forEach(([mid, els]) => {{
    const ev = parEspn[els[0].dataset.espn]; if (!ev) return;
    const c = ev.competitions[0], st = c.status.type;
    const h = +(c.competitors.find(x => x.homeAway === "home") || {{}}).score || 0;
    const a = +(c.competitors.find(x => x.homeAway === "away") || {{}}).score || 0;
    const avant = DIRECT[mid];
    const nouveau = {{ h, a, etat: st.state, fini: !!st.completed, minute: st.state === "in" ? (c.status.displayClock || st.shortDetail) : st.shortDetail }};
    // un but ? (on ne prévient pas au premier chargement)
    if (avant && avant.etat !== "pre" && h + a > avant.h + avant.a) {{
      const qui = h > avant.h ? els[0].dataset.dom : els[0].dataset.ext;
      const buteur = ((c.details || []).filter(d => d.scoringPlay).slice(-1)[0] || {{}});
      const nom = buteur.athletesInvolved && buteur.athletesInvolved[0] ? " · " + buteur.athletesInvolved[0].displayName : "";
      alerteBut(`⚽ BUT ${{qui}} !`, `${{els[0].dataset.dom}} ${{h}}-${{a}} ${{els[0].dataset.ext}} (${{nouveau.minute}})${{nom}}`, suivis.has(mid));
    }}
    if (avant && !avant.fini && nouveau.fini && suivis.has(mid)) alerteBut("🏁 Match terminé", `${{els[0].dataset.dom}} ${{h}}-${{a}} ${{els[0].dataset.ext}}`, true);
    DIRECT[mid] = nouveau;
    els.forEach(el => {{
      if (nouveau.etat === "pre") return;
      el.classList.add("en-direct"); el.classList.toggle("termine", nouveau.fini);
      el.querySelector(".ko-h").textContent = h + " - " + a;
      el.querySelector(".ko-j").textContent = nouveau.fini ? "Terminé" : nouveau.minute;
      const cd = el.querySelector(".cd"); cd.textContent = nouveau.fini ? "terminé" : "● en direct"; cd.className = "cd " + (nouveau.fini ? "fini" : "live");
    }});
  }});
  dessinerDirect(); afficherMP();
}}
function dessinerDirect() {{
  const z = document.getElementById("direct"), l = document.getElementById("direct-l");
  const parMid = affichesParMid(), suivis = mesIds();
  const enCours = Object.entries(DIRECT).filter(([mid, d]) => d.etat === "in" || (d.fini && suivis.has(mid)));
  enCours.sort((x, y) => (suivis.has(y[0]) - suivis.has(x[0])));
  if (!enCours.length) {{ z.hidden = true; return; }}
  z.hidden = false;
  l.innerHTML = enCours.slice(0, 8).map(([mid, d]) => {{
    const el = parMid[mid][0];
    return `<div class="dl${{suivis.has(mid) ? " moi" : ""}}"><span class="dl-e">${{el.dataset.dom}}</span>
      <b>${{d.h}} - ${{d.a}}</b><span class="dl-e r">${{el.dataset.ext}}</span>
      <small>${{d.fini ? "Terminé" : "● " + d.minute}}${{suivis.has(mid) ? " · ton pari" : ""}}</small></div>`;
  }}).join("") + (directEnErreur ? '<p class="note">Scores en direct momentanément indisponibles.</p>' : "");
}}
function alerteBut(titre, texte, important) {{
  toast(titre + " " + texte, 6000);
  let ok = false; try {{ ok = localStorage.getItem("alertes") === "1"; }} catch (e) {{}}
  let tous = false; try {{ tous = localStorage.getItem("alertes-tous") === "1"; }} catch (e) {{}}
  if (!ok || !(important || tous) || !("Notification" in window) || Notification.permission !== "granted") return;
  navigator.serviceWorker.getRegistration().then(r => r && r.showNotification(titre, {{ body: texte, icon: "icon-192.png", tag: titre + texte }}));
}}
async function activerAlertes() {{
  if (!("Notification" in window)) {{ toast("Installe d'abord l'appli sur l'écran d'accueil pour les alertes."); return; }}
  const p = await Notification.requestPermission();
  if (p === "granted") {{
    try {{ localStorage.setItem("alertes", "1"); }} catch (e) {{}}
    document.getElementById("btn-alertes").textContent = "🔔 Alertes activées";
    toast("🔔 Tu seras prévenu à chaque but sur tes paris.");
  }} else toast("Alertes refusées : tu peux les autoriser dans Réglages > Prono Malin.");
}}
try {{ if (localStorage.getItem("alertes") === "1") document.getElementById("btn-alertes").textContent = "🔔 Alertes activées"; }} catch (e) {{}}
majDirect(); setInterval(majDirect, 45000);
document.addEventListener("visibilitychange", () => {{ if (!document.hidden) majDirect(); }});

// ---- ✏️ Mon ticket : tu composes, l'expert vérifie
const MATCHS = {donnees_json};
const LIB_BUTS = {{ plus25: "Plus de 2,5 buts", moins25: "Moins de 2,5 buts", btts: "Les 2 équipes marquent", pas_btts: "Les 2 ne marquent pas" }};
const lireT = () => {{ try {{ return JSON.parse(localStorage.getItem("mon-ticket") || "[]"); }} catch (e) {{ return []; }} }};
const ecrireT = l => {{ try {{ localStorage.setItem("mon-ticket", JSON.stringify(l)); }} catch (e) {{}} }};
function selection(s) {{
  const m = MATCHS[s.id]; if (!m) return null;
  if (["1", "N", "2"].includes(s.choix)) {{
    const i = m.issues[s.choix];
    return {{ lib: i.lib, p: i.p, cote: s.cote || i.c, coteMarche: i.c, bk: i.bk, buts: false }};
  }}
  if (!m.buts) return null;
  const b = m.buts;
  const p = {{ plus25: b.plus25, moins25: 1 - b.plus25, btts: b.btts, pas_btts: 1 - b.btts }}[s.choix];
  return {{ lib: LIB_BUTS[s.choix], p, cote: s.cote || null, coteJuste: 1 / p, buts: true }};
}}
function ajouterAuTicket(id, choix) {{
  let l = lireT();
  const deja = l.findIndex(x => x.id === id && x.choix === choix);
  if (deja >= 0) {{ l.splice(deja, 1); toast("Retiré de ton ticket"); }}
  else {{
    if (l.some(x => x.id === id)) toast("⚠️ Tu as déjà un pari sur ce match : vérifie que les deux vont ensemble.", 3500);
    l.push({{ id, choix }}); toast("✅ Ajouté à « Mon ticket » (" + l.length + ")");
  }}
  ecrireT(l); dessinerTicket();
}}
function verdictSel(v) {{
  if (v.cote == null) return {{ cls: "att", txt: `Cote juste ${{v.coteJuste.toFixed(2)}} : joue-le à ${{(v.coteJuste * 1.05).toFixed(2)}} ou plus` }};
  const edge = v.p * v.cote - 1;
  if (edge >= 0.03) return {{ cls: "ok", txt: `✅ Bonne valeur (${{edge >= 0 ? "+" : ""}}${{(edge * 100).toFixed(1).replace(".", ",")}} %)`, edge }};
  if (edge >= -0.065) return {{ cls: "moy", txt: `👌 Cote correcte (${{(edge * 100).toFixed(1).replace(".", ",")}} %)`, edge }};
  return {{ cls: "bad", txt: `⚠️ Trop cher (${{(edge * 100).toFixed(1).replace(".", ",")}} %) : la vraie cote serait ${{(1 / v.p).toFixed(2)}}`, edge }};
}}
function dessinerTicket() {{
  const z = document.getElementById("mt"), l = lireT();
  const pt = document.getElementById("nb-ticket"); pt.textContent = l.length; pt.hidden = !l.length;
  document.querySelectorAll("[data-ajout]").forEach(b => {{ const [id, c] = b.dataset.ajout.split("|"); b.classList.toggle("pris", l.some(x => x.id === id && x.choix === c)); }});
  if (!l.length) {{
    z.innerHTML = `<div class="rien"><div class="sifflet">✏️</div><b>Ton ticket est vide.</b>
      <p>Va dans <b>📅 Matchs</b> et touche <b>1, N, 2</b> ou un pari de buts sous chaque match pour l'ajouter. L'expert vérifiera chaque choix.</p>
      <button class="btn-plein" onclick="ouvrirOnglet('matchs')">📅 Choisir des matchs</button></div>`;
    return;
  }}
  let chance = 1, cote = 1, coteConnue = true, juste = 1, lignes = "", alertes = [], tousEdge = [];
  const AV = avisT(), ICO = {{ ok: "✅", prudence: "⚠️", eviter: "❌" }};
  const vus = {{}};
  l.forEach((s, k) => {{
    const m = MATCHS[s.id], v = selection(s);
    if (!m || !v) {{ lignes += `<div class="mt-l"><b>Match plus disponible</b><button onclick="retirerT(${{k}})">✕</button></div>`; return; }}
    vus[s.id] = (vus[s.id] || 0) + 1;
    chance *= v.p; juste *= 1 / v.p;
    if (v.cote) cote *= v.cote; else coteConnue = false;
    const vd = verdictSel(v); if (vd.edge !== undefined) tousEdge.push(vd.edge);
    if (vd.cls === "bad") alertes.push(`« ${{v.lib}} » (${{m.dom}} – ${{m.ext}}) est trop cher : retire-le ou cherche une meilleure cote.`);
    if (v.p < 0.25) alertes.push(`« ${{v.lib}} » n'a que ${{Math.round(v.p * 100)}} % de chances : c'est lui qui risque de faire tomber le ticket.`);
    const d = new Date(m.ko);
    lignes += `<div class="mt-l">
      <div class="mt-h"><b>${{v.buts ? "⚽" : "🎯"}} ${{v.lib}}</b><button onclick="retirerT(${{k}})" aria-label="Retirer">✕</button></div>
      <small>${{m.dom}} – ${{m.ext}} · ${{m.champ}} · ${{d.toLocaleDateString("fr-FR", {{ weekday: "short", day: "numeric" }})}} ${{d.toLocaleTimeString("fr-FR", {{ hour: "2-digit", minute: "2-digit" }})}}</small>
      <div class="mt-g"><span>Chance <b>${{Math.round(v.p * 100)}} %</b></span>
        <label>Ta cote <input type="number" inputmode="decimal" step="0.01" min="1" value="${{s.cote || (v.buts ? "" : v.coteMarche)}}" placeholder="${{v.buts ? (v.coteJuste * 1.05).toFixed(2) + "+" : ""}}" onchange="coteT(${{k}}, this.value)"></label></div>
      ${{v.buts ? "" : `<small>Meilleure cote : ${{v.coteMarche.toFixed(2)}} chez ${{v.bk}}</small>`}}
      <div class="mt-v ${{vd.cls}}">${{vd.txt}}</div>
      ${{(() => {{ const a = AV && (AV.selections || []).find(x => +x.n === k + 1);
        return a ? `<div class="mt-exp ${{a.avis}}">🤖 ${{ICO[a.avis] || "⚠️"}} ${{a.texte}}</div>` : (m.avis ? `<small class="mt-ia">🤖 ${{m.avis}}</small>` : ""); }})()}}
    </div>`;
  }});
  Object.entries(vus).forEach(([id, n]) => {{ if (n > 1) alertes.push(`Deux paris sur ${{MATCHS[id].dom}} – ${{MATCHS[id].ext}} : beaucoup de bookmakers refusent de les combiner.`); }});
  if (l.length > 4) alertes.push(`${{l.length}} matchs : la marge du bookmaker se multiplie à chaque match ajouté. 2 à 4 matchs, c'est plus sain.`);
  // meilleur bookmaker unique pour les paris 1-N-2
  let bkTxt = "";
  const seulement1n2 = l.every(s => ["1", "N", "2"].includes(s.choix));
  if (seulement1n2) {{
    const noms = new Set(); l.forEach(s => Object.keys((MATCHS[s.id] || {{}}).bks || {{}}).forEach(n => noms.add(n)));
    const offres = [...noms].map(n => [n, l.reduce((c, s) => c * (((MATCHS[s.id] || {{}}).bks || {{}})[n] || {{}})[s.choix] || NaN, 1)]).filter(x => x[1] > 1).sort((a, b) => b[1] - a[1]);
    if (offres.length) bkTxt = `<p class="note">🏆 Meilleur bookmaker pour tout le ticket : <b>${{offres[0][0]}} à ${{offres[0][1].toFixed(2)}}</b>${{offres[1] ? ` · puis ${{offres[1][0]}} à ${{offres[1][1].toFixed(2)}}` : ""}}.</p>`;
  }}
  const edgeT = coteConnue ? chance * cote - 1 : null;
  let verdict;
  if (chance < 0.05) verdict = ["bad", "🎰 Loterie", `Seulement ${{(chance * 100).toFixed(1).replace(".", ",")}} % de chances : à peine 1 fois sur ${{Math.round(1 / chance)}}. Mise très petit, ou retire un match.`];
  else if (edgeT === null) verdict = ["moy", "🔍 À vérifier", `Entre les cotes de ton bookmaker pour les paris de buts : le ticket vaut le coup si sa cote totale atteint <b>${{(juste * 1.05).toFixed(2)}}</b>.`];
  else if (edgeT >= 0.05) verdict = ["ok", "✅ Très bon ticket", "Les cotes paient plus que le vrai risque. L'expert valide."];
  else if (edgeT >= 0) verdict = ["ok", "👍 Bon ticket", "Prix juste, légèrement en ta faveur."];
  else if (edgeT >= -0.10) verdict = ["moy", "😐 Ticket moyen", "Le bookmaker garde sa marge habituelle : jouable pour le plaisir, pas rentable sur la durée."];
  else verdict = ["bad", "❌ À éviter", "Trop cher par rapport au vrai risque : sur la durée, ce genre de ticket fait perdre."];
  z.innerHTML = `
    <section class="mt-res ${{verdict[0]}}">
      <div class="mt-t">${{verdict[1]}}</div><p>${{verdict[2]}}</p>
      <div class="chance"><div class="chance-b"><span style="width:${{Math.max(3, Math.round(chance * 100))}}%"></span></div>
        <b>${{Math.round(chance * 100)}} %</b><small>de chances que ça passe · 1 fois sur ${{Math.max(1, Math.round(1 / chance))}}</small></div>
      <div class="grille"><div><span>Matchs</span><b>${{l.length}}</b></div>
        <div><span>Cote totale</span><b>${{coteConnue ? cote.toFixed(2) : "?"}}</b></div>
        <div><span>Cote juste</span><b>${{juste.toFixed(2)}}</b></div></div>
      ${{alertes.length ? `<ul class="mt-al">${{alertes.map(a => `<li>${{a}}</li>`).join("")}}</ul>` : ""}}
      ${{bkTxt}}
    </section>
    ${{AV && AV.global ? `<section class="mt-expg ${{AV.global.avis}}"><div class="mt-t">🤖 ${{ICO[AV.global.avis] || "⚠️"}} L'avis de l'expert</div>
      <p>${{AV.global.texte}}</p>${{AV.global.changer ? `<p><b>Ce qu'il changerait :</b> ${{AV.global.changer}}</p>` : ""}}
      <small>Actu lue le ${{new Date(AV.quand).toLocaleString("fr-FR", {{ day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }})}}</small></section>` : ""}}
    ${{lignes}}
    <section class="mt-cle" id="mt-cle" hidden>
      <b>🔑 Une seule fois : ta clé Anthropic</b>
      <p>Pour que l'expert réponde ici, colle ta clé (elle commence par <code>sk-ant-</code>). Elle reste <b>uniquement sur ce téléphone</b> : elle n'est jamais publiée sur le site ni sur GitHub.
      Crée-la sur <b>console.anthropic.com</b> → Clés API. Conseil : fixe une limite de dépense mensuelle sur ton compte.</p>
      <input id="mt-cle-in" type="password" placeholder="sk-ant-…" autocomplete="off">
      <button class="btn-plein" onclick="enregistrerCle()">Enregistrer et demander l'avis</button>
    </section>
    <div class="mt-act">
      <button class="btn-plein" onclick="expertIA()" ${{expertEnCours ? "disabled" : ""}}>${{expertEnCours ? "⏳ L'expert lit l'actu… (30 s à 1 min)" : AV ? "🔄 Redemander l'avis de l'expert" : "🤖 Demander l'avis de l'expert sur l'actu"}}</button>
      <button onclick="copierT()">📋 Copier le ticket</button>
      <button onclick="jouerT(${{coteConnue ? cote.toFixed(2) : (juste * 1.05).toFixed(2)}})">✍️ J'ai joué ce ticket</button>
      <button onclick="if (confirm('Vider ton ticket ?')) {{ ecrireT([]); dessinerTicket(); }}">🗑 Vider</button>
    </div>
    <p class="note">L'expert lit l'actu (blessés, compos, forme, pronostiqueurs) seulement quand tu le demandes : environ quelques centimes par avis.
      ${{cleIA() ? `<a href="#" onclick="oublierCle(); return false">Supprimer ma clé de ce téléphone</a> · ` : ""}}<a href="#" onclick="expertDansClaude(); return false">Ouvrir plutôt dans Claude</a></p>`;
}}
function retirerT(k) {{ const l = lireT(); l.splice(k, 1); ecrireT(l); dessinerTicket(); }}
function coteT(k, v) {{ const l = lireT(); const c = parseFloat(String(v).replace(",", ".")); l[k].cote = c > 1 ? c : undefined; ecrireT(l); dessinerTicket(); }}
function texteTicket() {{
  return lireT().map((s, k) => {{
    const m = MATCHS[s.id], v = selection(s); if (!m || !v) return "";
    const d = new Date(m.ko).toLocaleString("fr-FR", {{ weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }});
    return `${{k + 1}}. ${{m.dom}} – ${{m.ext}} (${{m.champ}}, ${{d}}) : ${{v.lib}}${{v.cote ? " à " + v.cote.toFixed(2) : ""}}`;
  }}).filter(Boolean).join("\\n");
}}
// ---- 🤖 l'expert lit l'actu, directement dans l'appli (clé gardée sur ce téléphone uniquement)
const cleIA = () => {{ try {{ return localStorage.getItem("cle-ia") || ""; }} catch (e) {{ return ""; }} }};
const sigT = () => JSON.stringify(lireT().map(s => [s.id, s.choix]));
const avisT = () => {{ try {{ const a = JSON.parse(localStorage.getItem("avis-ticket") || "null"); return a && a.sig === sigT() ? a : null; }} catch (e) {{ return null; }} }};
let expertEnCours = false;
function expertIA() {{
  if (!cleIA()) {{ document.getElementById("mt-cle").hidden = false; document.getElementById("mt-cle").scrollIntoView({{ behavior: "smooth", block: "center" }}); return; }}
  lancerExpert();
}}
function enregistrerCle() {{
  const v = document.getElementById("mt-cle-in").value.trim();
  if (!v.startsWith("sk-ant-")) {{ toast("Cette clé ne ressemble pas à une clé Anthropic (sk-ant-…)", 3500); return; }}
  try {{ localStorage.setItem("cle-ia", v); }} catch (e) {{}}
  document.getElementById("mt-cle").hidden = true; toast("🔑 Clé enregistrée sur ce téléphone"); lancerExpert();
}}
function oublierCle() {{ try {{ localStorage.removeItem("cle-ia"); }} catch (e) {{}} toast("Clé supprimée de ce téléphone"); dessinerTicket(); }}
async function lancerExpert() {{
  if (expertEnCours || !lireT().length) return;
  expertEnCours = true; dessinerTicket();
  const sig = sigT();
  const consigne = "Tu es un pronostiqueur football expérimenté et prudent. Voici le ticket combiné que je veux jouer :\\n" + texteTicket() +
    "\\n\\nCherche sur le web les infos les plus récentes pour chaque match (compositions probables, blessés et suspendus, forme, enjeu, déclarations des coachs, avis des pronostiqueurs)." +
    "\\nRéponds UNIQUEMENT avec ce JSON, en français, phrases courtes :" +
    '\\n{{"selections":[{{"n":1,"avis":"ok|prudence|eviter","texte":"2 phrases"}}],"global":{{"avis":"ok|prudence|eviter","texte":"2 phrases","changer":"ce que tu changerais, ou vide"}}}}';
  try {{
    const r = await fetch("https://api.anthropic.com/v1/messages", {{
      method: "POST",
      headers: {{ "x-api-key": cleIA(), "anthropic-version": "2023-06-01", "content-type": "application/json",
                 "anthropic-dangerous-direct-browser-access": "true" }},
      body: JSON.stringify({{ model: "claude-sonnet-5-5", max_tokens: 3000,
        tools: [{{ type: "web_search_20250305", name: "web_search", max_uses: 6 }}],
        messages: [{{ role: "user", content: consigne }}] }})
    }});
    const j = await r.json();
    if (!r.ok) throw new Error((j.error && j.error.message) || ("erreur " + r.status));
    const t = (j.content || []).filter(x => x.type === "text").map(x => x.text).join("");
    const avis = JSON.parse(t.slice(t.indexOf("{{"), t.lastIndexOf("}}") + 1));
    try {{ localStorage.setItem("avis-ticket", JSON.stringify({{ sig, ...avis, quand: new Date().toISOString() }})); }} catch (e) {{}}
    toast("🤖 L'expert a rendu son avis");
  }} catch (e) {{
    const msg = String(e.message || e);
    if (/api.key|authentication|invalid x-api-key/i.test(msg)) {{ try {{ localStorage.removeItem("cle-ia"); }} catch (_) {{}} toast("🔑 Clé refusée : colle une nouvelle clé.", 4000); }}
    else if (/credit|billing/i.test(msg)) toast("💳 Plus de crédit sur ton compte Anthropic.", 4000);
    else toast("😕 L'expert n'a pas pu répondre : " + msg.slice(0, 90), 5000);
  }}
  expertEnCours = false; dessinerTicket();
}}
function expertDansClaude() {{
  const q = "Tu es un pronostiqueur football expérimenté et prudent. Voici le ticket combiné que je veux jouer :\\n" + texteTicket() +
    "\\n\\nCherche sur le web les infos les plus récentes pour chaque match et dis-moi pour chacun si mon choix tient la route (✅ / ⚠️ / ❌), puis un verdict global. Réponds en français, simplement.";
  window.open("https://claude.ai/new?q=" + encodeURIComponent(q), "_blank");
}}
function copierT() {{
  const t = "🎟️ Mon ticket Prono Malin\\n" + texteTicket();
  (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => toast("📋 Ticket copié"), () => prompt("Copie ton ticket :", t));
}}
function jouerT(coteDefaut) {{
  const l = lireT(); if (!l.length) return;
  const mise = parseFloat(String(prompt("Combien as-tu misé (€) ?", "") || "").replace(",", "."));
  if (!(mise > 0)) return;
  const cote = parseFloat(String(prompt("Cote totale obtenue chez ton bookmaker ?", coteDefaut) || "").replace(",", "."));
  if (!(cote > 1)) return;
  const premiers = l.map(s => MATCHS[s.id]).filter(Boolean);
  const mp = lireMP();
  mp.push({{ type: "combine", id: "mon-ticket-" + Date.now(), date: premiers[0] ? premiers[0].ko : "", pari: "Mon ticket · " + l.length + " matchs",
    match: premiers.map(m => m.dom + " – " + m.ext).join(" + "), cote, mise, bk: "ton bookmaker",
    jambes: l.map(s => ({{ id: s.id, pari: (selection(s) || {{}}).lib, ...(["1", "N", "2"].includes(s.choix) ? {{ court: s.choix }} : {{ marche: s.choix }}) }})),
    uid: Date.now() + "-t", joueLe: new Date().toISOString() }});
  ecrireMP(mp); afficherMP(); toast("✅ Ticket ajouté à « Mes paris »");
}}
document.addEventListener("click", ev => {{
  const b = ev.target.closest("[data-ajout]"); if (!b) return;
  const [id, c] = b.dataset.ajout.split("|"); ajouterAuTicket(id, c);
}});
dessinerTicket();

// ---- 🔒 code d'accès (gardé sur ce téléphone, sous forme d'empreinte)
async function empreinte(code) {{
  try {{
    const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("prono-malin:" + code));
    return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
  }} catch (e) {{ let h = 0; for (const c of "prono-malin:" + code) h = (h * 31 + c.charCodeAt(0)) | 0; return "f" + h; }}
}}
const VR = {{ mode: "entrer", saisie: "", premier: "", essais: 0, bloqueJusqu: 0 }};
function vrDessiner() {{
  document.querySelectorAll("#vr-pts i").forEach((p, i) => p.classList.toggle("on", i < VR.saisie.length));
  const t = {{ entrer: "Entre ton code", creer: "Choisis ton code", confirmer: "Confirme ton code" }}[VR.mode];
  document.getElementById("vr-t").textContent = t;
  document.getElementById("vr-plus").style.visibility = VR.mode === "entrer" ? "hidden" : "visible";
  document.getElementById("vr-reste").style.display = VR.mode === "entrer" ? "" : "none";
  document.getElementById("vr-oubli").style.display = VR.mode === "entrer" ? "" : "none";
}}
function vrMessage(txt, erreur) {{
  const el = document.getElementById("vr-s"); el.textContent = txt; el.classList.toggle("err", !!erreur);
  if (erreur) {{ const b = document.getElementById("vr-pts"); b.classList.remove("secoue"); void b.offsetWidth; b.classList.add("secoue"); }}
}}
function vrOuvrir(mode) {{
  VR.mode = mode; VR.saisie = ""; VR.premier = "";
  document.getElementById("verrou").hidden = false;
  vrMessage(mode === "entrer" ? "Prono Malin est verrouillé" : "4 chiffres, rien que pour toi. Il reste sur ce téléphone.");
  vrDessiner();
}}
function vrFermer() {{
  document.getElementById("verrou").hidden = true;
  document.documentElement.classList.remove("verrouille");
}}
async function vrTouche(k) {{
  if (k === "del") {{ VR.saisie = VR.saisie.slice(0, -1); return vrDessiner(); }}
  if (k === "plus") {{ try {{ localStorage.setItem("pin-plus-tard", "1"); }} catch (e) {{}} return vrFermer(); }}
  if (Date.now() < VR.bloqueJusqu) return vrMessage("Trop d'essais : attends quelques secondes.", true);
  if (VR.saisie.length >= 4) return;
  VR.saisie += k; vrDessiner();
  if (VR.saisie.length < 4) return;
  const code = VR.saisie;
  setTimeout(async () => {{
    if (VR.mode === "entrer") {{
      if (await empreinte(code) === localStorage.getItem("pin")) {{
        try {{
          sessionStorage.setItem("pin-ok", "1");
          if (document.getElementById("vr-rc").checked) localStorage.setItem("pin-ok-jusqu", Date.now() + 30 * 864e5);
        }} catch (e) {{}}
        VR.essais = 0; vrFermer();
      }} else {{
        VR.essais++; VR.saisie = ""; vrDessiner();
        if (VR.essais >= 5) {{ VR.bloqueJusqu = Date.now() + 30e3; VR.essais = 0; vrMessage("Code faux 5 fois : patiente 30 secondes.", true); }}
        else vrMessage("Code incorrect", true);
      }}
    }} else if (VR.mode === "creer") {{
      VR.premier = code; VR.saisie = ""; VR.mode = "confirmer"; vrMessage("Tape-le une deuxième fois."); vrDessiner();
    }} else {{
      if (code === VR.premier) {{
        try {{ localStorage.setItem("pin", await empreinte(code)); sessionStorage.setItem("pin-ok", "1"); localStorage.removeItem("pin-ok-jusqu"); }} catch (e) {{}}
        vrFermer(); majLienCode(); toast("🔒 Code enregistré : il sera demandé à l'ouverture de l'appli.", 3500);
      }} else {{ VR.mode = "creer"; VR.saisie = ""; VR.premier = ""; vrMessage("Les deux codes ne correspondent pas. Recommence.", true); vrDessiner(); }}
    }}
  }}, 120);
}}
document.querySelectorAll(".vr-pad button").forEach(b => b.addEventListener("click", () => vrTouche(b.dataset.k)));
document.getElementById("vr-oubli").addEventListener("click", () => {{
  if (!confirm("Code oublié : pour protéger tes données, on efface tout ce que l'appli garde sur ce téléphone (mes paris, mon ticket, réglages, clé de l'expert). Continuer ?")) return;
  try {{ localStorage.clear(); sessionStorage.clear(); }} catch (e) {{}}
  location.reload();
}});
function majLienCode() {{
  let a = false; try {{ a = !!localStorage.getItem("pin"); }} catch (e) {{}}
  document.getElementById("lien-code").textContent = a ? "activé · changer ou retirer" : "désactivé · créer un code";
}}
async function reglerCode() {{
  let a = false; try {{ a = !!localStorage.getItem("pin"); }} catch (e) {{}}
  if (!a) return vrOuvrir("creer");
  if (confirm("Retirer le code d'accès ? (Annuler pour le changer)")) {{
    try {{ localStorage.removeItem("pin"); localStorage.removeItem("pin-ok-jusqu"); }} catch (e) {{}}
    majLienCode(); toast("🔓 Code retiré");
  }} else vrOuvrir("creer");
}}
(function () {{
  let pin = null, plusTard = null;
  try {{ pin = localStorage.getItem("pin"); plusTard = localStorage.getItem("pin-plus-tard"); }} catch (e) {{}}
  if (document.documentElement.classList.contains("verrouille")) vrOuvrir("entrer");
  else if (!pin && !plusTard) vrOuvrir("creer");   // première ouverture : on propose de créer son code
  majLienCode();
}})();

// ---- petit message
function toast(txt, duree = 2200) {{
  const t = document.getElementById("toast"); t.textContent = txt; t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, duree);
}}

function fermer() {{
  document.getElementById("installer").style.display = "none";
  try {{ localStorage.setItem("installer-vu", "1"); }} catch (e) {{}}
}}
document.addEventListener("visibilitychange", () => {{
  // l'appli revient au premier plan après plus d'une heure : on recharge les pronos
  if (document.visibilityState === "visible" && Date.now() - performance.timeOrigin > 3600e3) location.reload();
}});
</script>
</body>
</html>"""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(html, encoding="utf-8")
    # fichiers de l'appli (icônes, manifeste, mode hors ligne)
    app = Path(__file__).parent / "app"
    for f in app.glob("*"):
        shutil.copy(f, chemin.parent / f.name)
