"""Fabrique la page web (une seule page, pensée pour le téléphone)."""
import json
import shutil
from collections import OrderedDict
from pathlib import Path
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from ecussons import championnat, couleur_ligue, ecusson

PARIS = ZoneInfo("Europe/Paris")
JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


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
        segs += f'<span class="{cls}{on}" style="flex:{i["proba"]:.3f}"></span>'
    return f'<div class="barre-p">{segs}</div>'


def affiche(m, grand=False):
    t = 52 if grand else 40
    d = datetime.fromisoformat(m["debut"].replace("Z", "+00:00")).astimezone(PARIS)
    jour = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"
    return f"""<div class="affiche{' grande' if grand else ''}">
        <div class="eq">{ecusson(m["domicile"], t)}<span>{e(m["domicile"])}</span></div>
        <div class="ko"><b>{d:%H:%M}</b><small>{jour}</small></div>
        <div class="eq">{ecusson(m["exterieur"], t)}<span>{e(m["exterieur"])}</span></div>
      </div>"""


def tag_champ(m):
    drap, nom = championnat(m.get("sport_key", ""), m["championnat"])
    return f'<span class="champ"><i>{drap}</i>{e(nom)}</span>'


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
      <div class="src">Réf. : {e(m["source_proba"])} · {m["nb_bookmakers"]} bookmakers comparés</div>{avis_html}
      {BOUTON_JOUE}
    </article>"""


def ligne_match(m):
    vcourt = m["value"]["court"] if m["value"] else None
    cases = ""
    for i in m["issues"]:
        cls = "case val" if i["court"] == vcourt else "case"
        cases += f"""<div class="{cls}"><span class="k">{i["court"]}</span>
          <b>{i["cote"]:.2f}</b><span class="p">{pct(i["proba"])}</span></div>"""
    return f"""
      <div class="match">
        {affiche(m)}
        {barre_probas(m, vcourt)}
        {bloc_stats(m, compact=True)}
        <div class="cases">{cases}</div>
      </div>"""


def avis_jambe(j):
    a = j.get("avis")
    if not a:
        return ""
    cls, titre = AVIS.get(a.get("avis"), AVIS["prudence"])
    return f"""<li class="avis-j {cls}"><b>{titre} :</b> {e(a.get("resume", ""))}</li>"""


def carte_combine(c):
    if not c:
        return """<article class="carte combo vide-c"><div class="combo-t">🎟️ Pas de combiné aujourd'hui</div>
      <p class="src">Pas assez de matchs avec des cotes correctes chez un même bookmaker.</p></article>"""
    jambes = ""
    for j in c["jambes"]:
        m = j["match"]
        jambes += f"""<li>{ecusson(m["domicile"], 26)}{ecusson(m["exterieur"], 26)}
          <div class="j-txt"><b>{e(j["issue"])}</b><small>{e(m["domicile"])} – {e(m["exterieur"])} · {heure(m["debut"])}</small></div>
          <span class="j-cote">{j["cote"]:.2f}</span></li>{avis_jambe(j)}"""
    if c["conseille"]:
        entete = f'<div class="combo-t">Ton combiné du jour <span class="badge c-bonne">Conseillé</span></div>'
        note = f'Chaque match a un avantage chez {e(c["bookmaker"])} : le ticket garde un avantage de <b class="vert">{pct(c["edge"], True)}</b>.'
    else:
        entete = f'<div class="combo-t">Combiné à risque <span class="badge c-risque">Non conseillé</span></div>'
        perte = -c["edge"] * 10
        note = (f'Aucun combiné rentable aujourd\'hui. Celui-ci est le moins coûteux, mais sur la durée '
                f'il fait perdre environ <b class="rouge">{euros(perte)} pour 10 € joués</b>. À toi de voir.')
    return f"""
    <article class="carte combo{'' if c['conseille'] else ' risque'}" id="combo" data-cote="{c['cote']:.4f}" data-pari="{e(json.dumps({"type": "combine", "id": "combo-" + c["jambes"][0]["match"]["id"], "date": c["jambes"][0]["match"]["debut"], "match": " + ".join(j["match"]["domicile"] + " – " + j["match"]["exterieur"] for j in c["jambes"]), "pari": "Combiné " + str(len(c["jambes"])) + " matchs", "cote": round(c["cote"], 2), "bk": c["bookmaker"], "jambes": [{"id": j["match"]["id"], "court": j["court"], "pari": j["issue"]} for j in c["jambes"]]}, ensure_ascii=False))}">
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


def generer(chemin, analyses, values, historique, b, infos, combine=None):
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
      <div class="leg">{''.join(f'<span><i class="{ {"1":"s1","N":"sn","2":"s2"}[i["court"]] }"></i>{e(i["issue"])} <b>{pct(i["proba"])}</b> · {i["cote"]:.2f}</span>' for i in choc["issues"])}</div>
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
    <details style="--lig:{couleur_ligue(ms[0].get('sport_key', ''))}"{' open' if nv else ''}><summary><span class="champ g"><i>{champ[0]}</i>{e(champ[1])}</span><span class="cpt">{tag}{len(ms)} match{'s' if len(ms) > 1 else ''}</span></summary>
      {''.join(ligne_match(m) for m in ms)}
    </details>"""

    bandeau_demo = '<div class="demo">Mode démo : données fictives</div>' if infos.get("demo") else ""
    credits = ""
    if infos.get("credits_restants") is not None:
        credits = f" · {infos['credits_restants']} crédits API restants"

    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#060b09">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Pronos">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" href="icon-192.png">
<title>Pronos du jour</title>
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
.ballon {{ display:inline-block; animation:roule 6s linear infinite; }}
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
.combo:not(.risque) .combo-t {{ background:var(--grad-ticket); -webkit-background-clip:text; background-clip:text; color:transparent; }}
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
@media (prefers-reduced-motion: reduce) {{ .ballon, .pari::after {{ animation:none; }} }}
@media (max-width:380px) {{ .bilan {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
{bandeau_demo}
<header>
  <div class="haut"><div class="date">{date_txt} · mis à jour {d:%H:%M}</div>
    <button class="maj" onclick="location.reload()">Actualiser</button></div>
  <h1>Pronos <em>du jour</em> <span class="ballon">⚽</span></h1>
  <div class="resume">
    <div><span>Matchs analysés</span><b>{len(analyses)}</b></div>
    <div><span>Value bets</span><b>{len(values)}</b></div>
    <div><span>Championnats</span><b>{len({m["sport_key"] for m in analyses})}</b></div>
  </div>
  <div class="installer" id="installer"><button onclick="fermer()" aria-label="Fermer">×</button>
    <b>Installe l'appli :</b> touche <b>Partager</b> en bas de Safari, puis <b>Sur l'écran d'accueil</b>.</div>
</header>

<section class="budget">
  <label for="somme">Ma mise du jour</label>
  <div class="saisie"><input id="somme" type="number" inputmode="decimal" min="0" step="0.5" placeholder="Ex. 6"><span>€</span></div>
  <div class="puces">{''.join(f'<button data-v="{x}">{x} €</button>' for x in (5, 10, 20, 50))}</div>
  <div class="mode"><button data-m="combine" class="on">🎟️ En combiné</button><button data-m="simples">Paris séparés</button></div>
  <p class="budget-res" id="budget-res">Tape la somme que tu sors aujourd'hui.</p>
</section>

<h2>🎟️ Combiné <small>un seul ticket, chez un seul bookmaker</small></h2>
{carte_combine(combine)}

<h2>🎯 Paris simples <small>selon l'avantage de chaque pari</small></h2>
{cartes}

<h2>📅 Tous les matchs <small>meilleure cote · proba marché</small></h2>
{groupes or '<p class="vide">Aucun match dans les prochaines heures.</p>'}

<h2 id="mes-paris-t">✍️ Mes paris <small>enregistrés sur ce téléphone</small></h2>
<div id="mes-paris"><p class="vide">Touche « J'ai joué ce pari » sur un pari ou un combiné : il apparaîtra ici et sera réglé tout seul.</p></div>

<h2>📊 Bilan de l'agent</h2>
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
  <p>🧠 Mémoire de l'actu : {infos.get("memoire_equipes", 0)} équipe{'s' if infos.get("memoire_equipes", 0) > 1 else ''} suivie{'s' if infos.get("memoire_equipes", 0) > 1 else ''} (21 jours).</p>
</footer>
<script>
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {{}});
const appli = window.navigator.standalone || matchMedia("(display-mode: standalone)").matches;
const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
let vu = null; try {{ vu = localStorage.getItem("installer-vu"); }} catch (e) {{}}
if (ios && !appli && !vu) document.getElementById("installer").style.display = "block";
// ---- ma mise du jour : répartition sur les paris jouables
const champ = document.getElementById("somme");
const cartesV = [...document.querySelectorAll("article[data-poids]")].filter(c => +c.dataset.poids > 0);
const fmt = x => x.toFixed(2).replace(".", ",").replace(",00", "") + " €";
const combo = document.getElementById("combo");
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
  try {{ localStorage.setItem("mise-jour", JSON.stringify({{ jour: "{d:%Y-%m-%d}", v: champ.value }})); }} catch (e) {{}}
  if (!total) {{ res.innerHTML = "Tape la somme que tu sors aujourd'hui."; return; }}
  if (mode === "combine") {{
    if (!combo) {{ res.innerHTML = "<b>Pas de combiné aujourd'hui.</b> Garde tes " + fmt(total) + " en poche."; return; }}
    const gain = total * +combo.dataset.cote;
    const z = combo.querySelector(".calc");
    z.innerHTML = `<div><span>Ta mise</span><b>${{fmt(total)}}</b></div><div class="r"><span>Si ça passe, tu touches</span><b>${{fmt(gain)}}</b></div>`;
    z.hidden = false;
    res.innerHTML = `Tes <b>${{fmt(total)}}</b> sur le combiné : si les ${{combo.querySelectorAll(".jambes li").length}} matchs passent, tu touches <b class="gros">${{fmt(gain)}}</b>. ` +
      `Un seul raté et tu perds ${{fmt(total)}}.` + (combo.classList.contains("risque") ? " <b>⚠️ Combiné non conseillé aujourd'hui.</b>" : "");
    return;
  }}
  if (!cartesV.length) {{ res.innerHTML = "<b>Aucun bon pari aujourd'hui.</b> Garde tes " + fmt(total) + " en poche : c'est la meilleure décision du jour."; return; }}
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
champ.addEventListener("input", repartir);
document.querySelectorAll(".mode button").forEach(b => b.addEventListener("click", () => choisirMode(b.dataset.m)));
document.querySelectorAll(".mode button").forEach(b => b.classList.toggle("on", b.dataset.m === mode));
document.querySelectorAll(".puces button").forEach(b => b.addEventListener("click", () => {{ champ.value = b.dataset.v; repartir(); }}));
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
  document.getElementById("mes-paris-t").scrollIntoView({{ behavior: "smooth" }});
}}
function statutMP(p) {{
  if (p.manuel) return p.manuel;
  if (p.type === "combine") {{
    const r = p.jambes.map(j => RESULTATS[j.id] ? RESULTATS[j.id].res === j.court : null);
    if (r.includes(false)) return "perdu";
    return r.every(x => x === true) ? "gagné" : "en attente";
  }}
  const r = RESULTATS[p.id];
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
function afficherMP() {{
  const l = lireMP(), z = document.getElementById("mes-paris");
  if (!l.length) return;
  let mises = 0, gains = 0, n = 0, g = 0, att = 0, lignes = "";
  l.slice().sort((a, b) => b.joueLe.localeCompare(a.joueLe)).forEach(p => {{
    const st = statutMP(p), gain = st === "gagné" ? p.mise * (p.cote - 1) : st === "perdu" ? -p.mise : 0;
    if (st === "en attente") att++; else {{ n++; mises += p.mise; gains += gain; if (st === "gagné") g++; }}
    const cls = {{ "gagné": "ok", "perdu": "bad" }}[st] || "att";
    const esc = t => String(t).replace(/[&<>"]/g, c => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }})[c]);
    lignes += `<tr><td>${{esc(p.pari)}}<small>${{esc(p.match)}} · cote ${{p.cote.toFixed(2)}} · ${{esc(p.bk || "")}}</small></td>
      <td class="r">${{fmt(p.mise)}}<small class="st ${{cls}}">${{st}}${{st !== "en attente" ? " " + (gain >= 0 ? "+" : "") + fmt(gain) : ""}}</small>
      <div class="mp-act"><button onclick="regler('${{p.uid}}','gagné')">✓</button><button onclick="regler('${{p.uid}}','perdu')">✗</button><button onclick="suppr('${{p.uid}}')">🗑</button></div></td></tr>`;
  }});
  const roi = mises ? (gains >= 0 ? "+" : "") + (gains / mises * 100).toFixed(1).replace(".", ",") + " %" : "—";
  const c = gains >= 0 ? "vert" : "rouge";
  z.innerHTML = `<div class="bilan"><div><span>Paris réglés</span><b>${{n}}</b></div><div><span>Gagnés</span><b>${{g}}</b></div>
    <div><span>Bénéfice</span><b class="${{c}}">${{(gains >= 0 ? "+" : "") + fmt(gains)}}</b></div><div><span>Rendement</span><b class="${{c}}">${{roi}}</b></div></div>
    <p class="note">${{att}} en attente · misé au total ${{fmt(mises)}}. Réglés tout seuls avec les scores ; ✓ ✗ pour corriger à la main.</p>
    <table class="hist">${{lignes}}</table>`;
}}
marquerJoues(); afficherMP();

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
