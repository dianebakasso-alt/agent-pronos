import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import direct, expert
out = {}
for d in ("20261107", "20261106"):
    try:
        evs = direct._get(f"{direct.BASE}/eng.2/scoreboard?dates={d}").get("events", [])
        out[d] = [(e["id"], e.get("name"), (e.get("status") or {}).get("type", {}).get("completed"),
                   ((e.get("competitions") or [{}])[0].get("status") or {}).get("type", {}).get("name"),
                   expert._score_espn(e)) for e in evs][:15]
    except Exception as x:
        out[d] = str(x)
Path("data/sonde2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
