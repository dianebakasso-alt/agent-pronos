import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import direct
sm = direct._get(f"{direct.BASE}/uefa.europa/summary?event=401915534")
ke = sm.get("keyEvents") or []
out = {"types": sorted({(k.get("type") or {}).get("type", "?") for k in ke}),
       "ex": [json.dumps({x: k.get(x) for x in ("type", "text", "clock", "team", "scoringPlay", "participants")}, ensure_ascii=False)[:500]
              for k in ke if (k.get("type") or {}).get("type") not in ("kickoff", "halftime", "end-regular-time")][:6],
       "stats": [[(s.get("name"), s.get("displayValue")) for s in t.get("statistics", [])] for t in (sm.get("boxscore") or {}).get("teams", [])],
       "teams": [(t.get("team") or {}).get("id") for t in (sm.get("boxscore") or {}).get("teams", [])],
       "header_comp": json.dumps([{k: c.get(k) for k in ("id", "homeAway", "score", "winner")} for c in sm["header"]["competitions"][0]["competitors"]])}
Path("data/sonde2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
