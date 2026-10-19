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


# ---------------------------------------------------------------- fatigue (gratuit)
EUROPE = ("uefa.champions", "uefa.europa", "uefa.europa.conf")


def matchs_europeens(maintenant, avant=4, apres=7):
    """[(date, [noms équipe dom], [noms équipe ext], compétition)] des coupes d'Europe autour d'aujourd'hui."""
    out, vus = [], set()
    for slug in EUROPE:
        for k in range(-avant, apres + 1):
            d = (maintenant + timedelta(days=k)).strftime("%Y%m%d")
            try:
                evs = _get(f"{BASE}/{slug}/scoreboard?dates={d}").get("events", [])
            except Exception:
                continue
            for ev in evs:
                if ev["id"] in vus:
                    continue
                vus.add(ev["id"])
                try:
                    t = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                except Exception:
                    continue
                dom, ext = _equipes(ev)
                if dom and ext:
                    out.append((t, dom, ext, slug, str(ev["id"])))
    return out


NOMS_COUPES = {"uefa.champions": "Ligue des champions", "uefa.europa": "Europa League", "uefa.europa.conf": "Conference League"}


def marquer_fatigue(analyses, europe, jours=3):
    """m['fatigue'] = {'1': 'texte', '2': 'texte'} si l'équipe joue en Europe 3 jours avant ou après."""
    n = 0
    for m in analyses:
        ko = datetime.fromisoformat(m["debut"].replace("Z", "+00:00"))
        mon_id = (m.get("espn") or {}).get("id")
        fat = {}
        for court, nom in (("1", m["domicile"]), ("2", m["exterieur"])):
            for t, dom, ext, slug, eid in europe:
                if eid == mon_id:
                    continue
                ecart = (t - ko).total_seconds() / 86400
                if abs(ecart) > jours or abs(ecart) < 0.2:
                    continue
                if max(max(_ressemblance(nom, x) for x in dom if x), max(_ressemblance(nom, x) for x in ext if x)) >= 0.8:
                    quand = f"il y a {round(-ecart)} jour{'s' if round(-ecart) > 1 else ''}" if ecart < 0 else \
                        f"dans {round(ecart)} jour{'s' if round(ecart) > 1 else ''}"
                    fat[court] = f"{nom} joue en {NOMS_COUPES[slug]} {quand}"
                    break
        if fat:
            m["fatigue"] = fat
            n += 1
    return n


# ---------------------------------------------------------------- mode secours : cotes ESPN (gratuites)
def _americaine(v):
    try:
        s = str(v).strip().replace("EVEN", "+100")
        x = float(s)
    except Exception:
        return None
    if x == 0:
        return None
    return round(1 + (x / 100 if x > 0 else 100 / -x), 3)


def _cotes_ev(ev):
    """(dom, nul, ext) en cotes décimales depuis les cotes publiées par ESPN, ou None."""
    comp = (ev.get("competitions") or [{}])[0] or {}
    for o in comp.get("odds") or []:
        if not isinstance(o, dict):
            continue
        try:
            r = _cotes_une(o)
        except Exception:
            r = None
        if r:
            return r
    return None


def _cotes_une(o):
    if True:
        h = _americaine((o.get("homeTeamOdds") or {}).get("moneyLine"))
        a = _americaine((o.get("awayTeamOdds") or {}).get("moneyLine"))
        d = _americaine((o.get("drawOdds") or {}).get("moneyLine"))
        if not (h and a and d):
            ml = o.get("moneyline") or {}
            pick = lambda k: _americaine(((ml.get(k) or {}).get("close") or (ml.get(k) or {}).get("open") or {}).get("odds"))
            h, a = h or pick("home"), a or pick("away")
            d = d or _americaine(((o.get("drawOdds") or {}).get("moneyLine")) or ((ml.get("draw") or {}).get("close") or {}).get("odds"))
        if h and a and d:
            return h, d, a, (o.get("provider") or {}).get("name") or "ESPN"
    return None


def cotes_espn(maintenant, nb_jours=7, journal=None):
    """Matchs au format de la source de cotes habituelle, à partir des tableaux ESPN (1 bookmaker)."""
    matchs = []
    for sk, slug in LIGUES_ESPN.items():
        evs, err = _evenements(slug, maintenant, nb_jours)
        avec = 0
        for ev in evs:
            try:
                t = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            except Exception:
                continue
            if t <= maintenant:
                continue
            c = _cotes_ev(ev)
            dom, ext = _equipes(ev)
            if not c or not dom or not ext:
                continue
            h, d, a, prov = c
            avec += 1
            matchs.append({"id": f"espn-{ev['id']}", "sport_key": sk, "sport_title": slug, "commence_time": ev["date"],
                           "home_team": dom[0], "away_team": ext[0], "_espn": {"ligue": slug, "id": str(ev["id"])},
                           "bookmakers": [{"key": "espn", "title": prov, "markets": [{"key": "h2h", "outcomes": [
                               {"name": dom[0], "price": h}, {"name": ext[0], "price": a}, {"name": "Draw", "price": d}]}]}]})
        if journal is not None:
            ex = next((((e.get("competitions") or [{}])[0] or {}).get("odds") for e in evs if ((e.get("competitions") or [{}])[0] or {}).get("odds")), None)
            journal[slug] = {"matchs": len(evs), "avec_cotes": avec, "erreur": err,
                             "exemple": json.dumps(ex, ensure_ascii=False)[:600] if ex and not avec else None}
    return matchs
