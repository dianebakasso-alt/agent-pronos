"""Relie chaque match à son équivalent sur le tableau des scores public d'ESPN.

Pendant la génération du site (sur GitHub), on cherche l'identifiant ESPN de chaque match.
Ensuite c'est le téléphone qui va lire les scores en direct, toutes les 45 secondes, sans crédit.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from stats import _ressemblance

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LIGUES_ESPN = {
    "soccer_epl": "eng.1", "soccer_efl_champ": "eng.2", "soccer_england_league1": "eng.3",
    "soccer_england_league2": "eng.4", "soccer_spl": "sco.1", "soccer_germany_bundesliga": "ger.1",
    "soccer_germany_bundesliga2": "ger.2", "soccer_italy_serie_a": "ita.1", "soccer_italy_serie_b": "ita.2",
    "soccer_spain_la_liga": "esp.1", "soccer_spain_segunda_division": "esp.2", "soccer_france_ligue_one": "fra.1",
    "soccer_france_ligue_two": "fra.2", "soccer_netherlands_eredivisie": "ned.1", "soccer_belgium_first_div": "bel.1",
    "soccer_portugal_primeira_liga": "por.1", "soccer_turkey_super_league": "tur.1", "soccer_greece_super_league": "gre.1",
    "soccer_uefa_champs_league": "uefa.champions", "soccer_uefa_europa_league": "uefa.europa",
    "soccer_uefa_europa_conference_league": "uefa.europa.conf", "soccer_brazil_campeonato": "bra.1",
    "soccer_argentina_primera_division": "arg.1", "soccer_usa_mls": "usa.1", "soccer_japan_j_league": "jpn.1",
    "soccer_mexico_ligamx": "mex.1", "soccer_austria_bundesliga": "aut.1", "soccer_denmark_superliga": "den.1",
    "soccer_norway_eliteserien": "nor.1", "soccer_sweden_allsvenskan": "swe.1", "soccer_switzerland_superleague": "sui.1",
    "soccer_saudi_arabia_pro_league": "ksa.1", "soccer_australia_aleague": "aus.1",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 prono-malin", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corps = e.read().decode("utf-8", "replace")[:160]
        raise RuntimeError(f"HTTP {e.code} {corps}") from None


def _evenements(slug, maintenant, nb_jours):
    """Matchs ESPN de la semaine : d'abord en une requête, sinon jour par jour."""
    d0 = maintenant.strftime("%Y%m%d")
    d1 = (maintenant + timedelta(days=nb_jours)).strftime("%Y%m%d")
    erreur = None
    evs, vus = [], set()
    for k in range(nb_jours + 1):
        d = (maintenant + timedelta(days=k)).strftime("%Y%m%d")
        try:
            for ev in _get(f"{BASE}/{slug}/scoreboard?dates={d}").get("events", []):
                if ev["id"] not in vus:
                    vus.add(ev["id"]); evs.append(ev)
        except Exception as e:
            erreur = str(e)
    return evs, (None if evs else erreur)


def _equipes(ev):
    comp = (ev.get("competitions") or [{}])[0]
    dom = ext = ""
    for c in comp.get("competitors", []):
        noms = [c.get("team", {}).get(k, "") for k in ("displayName", "shortDisplayName", "name")]
        if c.get("homeAway") == "home":
            dom = noms
        else:
            ext = noms
    return dom, ext


def relier(analyses, maintenant, nb_jours=7):
    """Ajoute m['espn'] = {'ligue', 'id'} aux matchs retrouvés. Renvoie un petit journal."""
    journal = {"ligues": {}, "relies": 0, "manques": []}
    par_ligue = {}
    for m in analyses:
        par_ligue.setdefault(m.get("sport_key"), []).append(m)
    for sk, ms in par_ligue.items():
        slug = LIGUES_ESPN.get(sk)
        if not slug:
            continue
        evs, erreur = _evenements(slug, maintenant, nb_jours)
        if erreur:
            journal["ligues"][sk] = f"erreur {erreur}"[:220]
            continue
        journal["ligues"][sk] = len(evs)
        for m in ms:
            ko = datetime.fromisoformat(m["debut"].replace("Z", "+00:00"))
            meilleur, score = None, 0.0
            for ev in evs:
                try:
                    t = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                except Exception:
                    continue
                if abs((t - ko).total_seconds()) > 4 * 3600:
                    continue
                dom, ext = _equipes(ev)
                if not dom or not ext:
                    continue
                s = (max(_ressemblance(m["domicile"], n) for n in dom if n)
                     + max(_ressemblance(m["exterieur"], n) for n in ext if n)) / 2
                if s > score:
                    meilleur, score = ev, s
            if meilleur and score >= 0.62:
                m["espn"] = {"ligue": slug, "id": str(meilleur["id"])}
                journal["relies"] += 1
            else:
                journal["manques"].append(f"{sk}: {m['domicile']} - {m['exterieur']}")
    return journal
