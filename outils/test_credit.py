"""Vérifie que la clé IA marche et qu'il reste du crédit (une question d'un mot, coût quasi nul)."""
import json, os, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

cle = os.environ.get("ANTHROPIC_API_KEY", "")
res = {"quand": datetime.now(timezone.utc).isoformat(), "cle_presente": bool(cle)}
if cle:
    corps = {"model": json.loads(Path("config.json").read_text())["modele_ia"], "max_tokens": 5,
             "messages": [{"role": "user", "content": "Réponds juste OK."}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(corps).encode(),
                                 headers={"x-api-key": cle, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            res.update(ok=True, reponse="".join(b.get("text", "") for b in d.get("content", [])))
    except urllib.error.HTTPError as e:
        res.update(ok=False, code=e.code, erreur=e.read().decode()[:300])
    except Exception as e:
        res.update(ok=False, erreur=str(e)[:300])
Path("data/test_credit.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(res.get("ok"), res.get("code"), res.get("erreur", "")[:120])
