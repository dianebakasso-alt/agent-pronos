"""Rattrapage des autopsies en une fois : les plus grosses surprises d'abord, budget strict."""
import json, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.getcwd())
import agent, autopsie, expert

BUDGET_RATTRAPAGE = float(os.environ.get("BUDGET", "2.0"))
maintenant = datetime.now(timezone.utc)
cfg = agent.charger_config()
cle = os.environ.get("ANTHROPIC_API_KEY", "")
carnet = expert.charger(agent.DATA / "carnet.json")
lecons = autopsie.charger(agent.DATA / "lecons.json")

# budget dédié : ne touche pas au plafond du mois
agent.BUDGET.update(mois="rattrapage", depense=0.0, run=0.0, max=BUDGET_RATTRAPAGE, prix=cfg.get("prix_ia", {}),
                    appels=0, bloque=0, max_jour=None)
autopsie.MAX_AUTOPSIES = 1000
a_faire = []
vus = set()
for p in carnet:
    for j in p["jambes"]:
        cle_j = (j["id"], j.get("court") or j.get("marche"))
        if j.get("ok") is False and "autopsie" not in j and j.get("score") and cle_j not in vus:
            vus.add(cle_j)
            a_faire.append(j)
a_faire.sort(key=lambda j: -(j.get("proba") or 0))      # la plus grosse surprise d'abord
if os.environ.get("MODE", "gratuit") == "gratuit":
    # autopsie gratuite : les faits du match publiés par ESPN, sans IA, sans coût
    n = autopsie.autopsies_gratuites(carnet, lecons, maintenant, n=100000, jours=3650)
    sauver = None
    (agent.DATA / "carnet.json").write_text(json.dumps(carnet, ensure_ascii=False, indent=1), encoding="utf-8")
    (agent.DATA / "lecons.json").write_text(json.dumps(lecons, ensure_ascii=False, indent=1), encoding="utf-8")
    reste = sum(1 for j in a_faire if "autopsie" not in j)
    (agent.DATA / "rattrapage.json").write_text(json.dumps({"quand": maintenant.isoformat(), "mode": "gratuit", "faites": n,
        "restantes": reste, "cout_estime": 0}, ensure_ascii=False), encoding="utf-8")
    print(f"{n} autopsies gratuites faites, {reste} restantes (sans données ESPN), coût 0 €")
    sys.exit(0)
print(f"{len(a_faire)} erreurs sans autopsie, budget {BUDGET_RATTRAPAGE} €")
faites = 0
echecs = 0
MAX = int(os.environ.get("MAX", "100000"))


def sauver():
    (agent.DATA / "carnet.json").write_text(json.dumps(carnet, ensure_ascii=False, indent=1), encoding="utf-8")
    (agent.DATA / "lecons.json").write_text(json.dumps(lecons, ensure_ascii=False, indent=1), encoding="utf-8")


for j in a_faire[:MAX]:
    try:
        res = agent.appel_ia(autopsie.consigne(j), cfg, cle, max_uses=2, max_tokens=3000)
        autopsie.noter_autopsie(carnet, lecons, j, res, maintenant)
        faites += 1
        echecs = 0
        if faites % 10 == 0:
            sauver()
            print(f"  {faites} faites, {agent.BUDGET['run']:.2f} €", flush=True)
    except RuntimeError as e:          # plafond atteint
        print("stop :", e)
        break
    except Exception as e:
        print("  !", j["domicile"], e, flush=True)
        echecs += 1
        if "credit balance" in str(e) or echecs >= 3:   # disjoncteur : 3 échecs de suite = on arrête de payer
            print("stop : 3 échecs de suite")
            break
autopsie.MAX_AUTOPSIES = 5
sauver()
(agent.DATA / "rattrapage.json").write_text(json.dumps({"quand": maintenant.isoformat(), "faites": faites,
    "restantes": len(a_faire) - faites, "cout_estime": round(agent.BUDGET["run"], 3)}, ensure_ascii=False), encoding="utf-8")
print(f"{faites} autopsies faites, coût estimé {agent.BUDGET['run']:.2f} €")
