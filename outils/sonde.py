"""Sonde (gratuite) : teste la note de force sur le passé et regarde la structure des compos ESPN."""
import csv, io, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import force, stats, direct

out = {"quand": datetime.now(timezone.utc).isoformat(), "elo": {}, "espn": {}}
for code in ("I1", "E0", "F1", "D1", "SP1", "N1", "P1", "E1"):
    lignes, cotes = [], []
    for saison in ("2425", "2526"):
        try:
            t = stats._telecharger(f"{stats.BASE}/mmz4281/{saison}/{code}.csv")
        except Exception as e:
            out["elo"][code + saison] = str(e); continue
        for r in csv.DictReader(io.StringIO(t)):
            if not r.get("HomeTeam") or r.get("FTHG") in (None, ""):
                continue
            lignes.append((stats._date(r["Date"]), r["HomeTeam"], r["AwayTeam"], int(float(r["FTHG"])), int(float(r["FTAG"]))))
            try:
                cotes.append({"1": float(r.get("AvgH") or r["B365H"]), "N": float(r.get("AvgD") or r["B365D"]), "2": float(r.get("AvgA") or r["B365A"])})
            except Exception:
                cotes.append(None)
    out["elo"][code] = force.evaluer(lignes, cotes)
    # le favori du marché quand l'Elo le contredit : gagne-t-il moins que prévu ?
    elo, nuls, g = {}, 0, {"suspect": [0, 0, 0.0, 0.0], "confirme": [0, 0, 0.0, 0.0], "autre": [0, 0, 0.0, 0.0]}
    for idx, ((_, h, a, hg, ag), c) in enumerate(zip(lignes, cotes)):
        eh, ea = elo.get(h, 1500), elo.get(a, 1500)
        res = "1" if hg > ag else "N" if hg == ag else "2"
        if idx >= 150 and c:
            inv = {k: 1 / c[k] for k in "1N2"}; s = sum(inv.values()); pm = {k: v / s for k, v in inv.items()}
            p = force.probas(eh, ea, nuls / idx)
            fav = max(("1", "2"), key=pm.get)
            if pm[fav] >= 0.5:
                cle = "suspect" if p[fav] < pm[fav] - force.DIVERGENCE else "confirme" if p[fav] >= pm[fav] - 0.03 else "autre"
                g[cle][0] += 1; g[cle][1] += res == fav; g[cle][2] += pm[fav]
                g[cle][3] += c[fav] - 1 if res == fav else -1
        att = force._attendu(eh + force.AVANTAGE - ea); r = 1.0 if res == "1" else 0.5 if res == "N" else 0.0
        ecart = abs(hg - ag); mult = 1 if ecart <= 1 else 1.5 if ecart == 2 else (11 + ecart) / 8
        d = force.K * mult * (r - att); elo[h], elo[a] = eh + d, ea - d; nuls += res == "N"
    out["elo"][code + "_favoris"] = {k: {"n": v[0], "reel": round(v[1] / v[0], 3) if v[0] else None,
                                         "annonce": round(v[2] / v[0], 3) if v[0] else None,
                                         "roi": round(v[3] / v[0], 3) if v[0] else None} for k, v in g.items()}

    # test des alertes « match piège » : le favori du marché gagne-t-il moins que prévu ?
    import pieges
    pg = {}
    for idx, ((dt, h, a, hg, ag), c) in enumerate(zip(lignes, cotes)):
        if idx < 150 or not c:
            continue
        inv = {k: 1 / c[k] for k in "1N2"}; s_ = sum(inv.values()); pm = {k: v / s_ for k, v in inv.items()}
        fav = max(("1", "2"), key=pm.get)
        if pm[fav] < 0.5:
            continue
        passe = lignes[:idx]
        st = {"domicile": stats._forme(passe, h, "dom"), "exterieur": stats._forme(passe, a, "ext"),
              "face": stats._face_a_face(passe, h, a)}
        m = {"domicile": h, "exterieur": a, "stats": st, "issues": []}
        al = pieges.analyser(m).get(fav, [])
        res = "1" if hg > ag else "N" if hg == ag else "2"
        cles = {r.split(" :")[0] if " :" in r else ("invaincu" if "invaincu" in r else "exterieur" if "extérieur" in r else r[:20]) for r in al} or {"aucune"}
        if al:
            cles.add("au_moins_une")
        for k in cles:
            g_ = pg.setdefault(k, [0, 0, 0.0, 0.0])
            g_[0] += 1; g_[1] += res == fav; g_[2] += pm[fav]; g_[3] += c[fav] - 1 if res == fav else -1
    out["elo"][code + "_pieges"] = {k: {"n": v[0], "reel": round(v[1] / v[0], 3), "annonce": round(v[2] / v[0], 3),
                                        "roi": round(v[3] / v[0], 3)} for k, v in pg.items()}

def court(x, n=600):
    s = json.dumps(x, ensure_ascii=False)
    return s[:n]

try:
    sm = direct._get(f"{direct.BASE}/uefa.europa/summary?event=401915534")
    out["espn"]["cles"] = list(sm.keys())
    ro = sm.get("rosters") or []
    out["espn"]["rosters_n"] = len(ro)
    if ro:
        out["espn"]["roster_cles"] = list(ro[0].keys())
        out["espn"]["roster_equipe"] = court(ro[0].get("team"), 300)
        r0 = ro[0].get("roster") or []
        out["espn"]["roster_len"] = len(r0)
        out["espn"]["roster_ex"] = [court(x, 700) for x in r0[:2]]
    for k in ("boxscore", "header", "lastFiveGames", "headToHeadGames", "standings", "keyEvents", "injuries"):
        if k in sm:
            out["espn"][k] = court(sm[k], 900)
    tid = (((sm.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or [{}])[0].get("id")
    out["espn"]["team_id"] = tid
    for url in (f"{direct.BASE}/uefa.europa/teams/{tid}/schedule", f"{direct.BASE}/all/teams/{tid}/schedule",
                f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/all/teams/{tid}/schedule?fixture=false"):
        try:
            sc = direct._get(url)
            evs = sc.get("events") or []
            out["espn"][url] = {"n": len(evs), "ex": court(evs[-1] if evs else sc, 500),
                                "ligues": sorted({(e.get("league") or {}).get("abbreviation", "?") if isinstance(e.get("league"), dict) else str(e.get("league")) for e in evs})[:10]}
        except Exception as e:
            out["espn"][url] = str(e)
except Exception as e:
    out["espn"]["erreur"] = str(e)

Path("data/sonde.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
