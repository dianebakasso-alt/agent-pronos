# Prono Malin ⚽ — ton agent de pronostics

Chaque matin, l'agent :

1. récupère les matchs de foot des prochaines 36 h et les cotes de 10 bookmakers ;
2. calcule la **vraie probabilité du marché** à partir de Pinnacle (le bookmaker le plus juste), marge retirée ;
3. compare avec la **meilleure cote chez les bookmakers français** (Betclic, Winamax, Unibet, PMU, NetBet) ;
4. garde seulement les **value bets** : quand la cote paie plus que le risque réel ;
5. demande à l'IA de vérifier l'actu de ces matchs (compos, blessés, avis de pronostiqueurs, presse locale) ;
6. publie tout sur un **site consultable sur ton téléphone**, avec la mise conseillée et le bilan de l'agent.

---

## Installation (environ 20 minutes, sans coder)

### 1. Créer la clé des cotes (gratuit)
- Va sur **the-odds-api.com**, choisis le plan *Starter* (gratuit), entre ton email.
- Tu reçois ta clé par mail. Garde-la.

### 2. Créer la clé de l'IA (optionnel mais conseillé)
- Va sur **console.anthropic.com**, crée un compte, ajoute un peu de crédit (5 € suffisent pour commencer).
- Menu *API Keys* → *Create Key*. Garde-la.
- Sans cette clé, l'agent marche quand même, mais sans la vérification de l'actu.

### 3. Mettre le projet sur GitHub
- Crée un compte sur **github.com**.
- Bouton **+** → *New repository* → nom : `agent-pronos` → **Public** → *Create*.
- Clique *uploading an existing file* et glisse **tout le contenu du dossier** (y compris le dossier `.github`).
  Astuce : depuis un ordinateur c'est plus simple ; sur Mac, `Cmd + Maj + .` affiche les dossiers cachés.

### 4. Donner les clés à GitHub
- Dans ton dépôt : *Settings* → *Secrets and variables* → *Actions* → *New repository secret*.
- Nom `ODDS_API_KEY`, valeur : ta clé des cotes.
- Nom `ANTHROPIC_API_KEY`, valeur : ta clé IA (si tu l'as).

### 5. Activer le site
- *Settings* → *Pages* → *Source* : choisis **GitHub Actions**.

### 6. Premier lancement
- Onglet *Actions* → *Pronos du jour* → *Run workflow*.
- Après 2 à 5 minutes, ton site est en ligne à l'adresse :
  `https://TON-PSEUDO.github.io/agent-pronos/`
- Ajoute-le à l'écran d'accueil de ton téléphone (Safari/Chrome → *Partager* → *Sur l'écran d'accueil*).

Ensuite, il se met à jour **tout seul chaque matin vers 6 h 45**.

---

## Réglages (fichier `config.json`)

| Réglage | Par défaut | Ce que ça fait |
|---|---|---|
| `bankroll_euros` | 200 | L'argent que tu dédies aux paris. **Mets ton vrai montant.** |
| `mise_max_pourcent` | 2 | Jamais plus de 2 % de la bankroll sur un pari. |
| `fraction_kelly` | 0.25 | Prudence des mises (0.25 = prudent, ne monte pas au-dessus de 0.5). |
| `edge_minimum_pourcent` | 3 | Avantage minimum pour conseiller un pari. |
| `cote_max` | 6 | Ignore les cotes plus hautes (trop de hasard). |
| `credits_max_par_jour` | 12 | Nombre max de championnats analysés par jour. |
| `championnats_prioritaires` | Top 5, coupes d'Europe… | Analysés en premier. |

### Le monde entier : une question de forfait
- **Gratuit (500 crédits/mois)** : environ 12 championnats par jour, les plus importants en priorité.
- **Plan 20K (30 $/mois)** : passe `credits_max_par_jour` à 60 → quasiment tous les championnats du monde.

Commence en gratuit pendant un mois : tu verras si l'agent te plaît avant de payer.

---

## Tester sans clé
Sur un ordinateur avec Python : `python agent.py --demo` puis ouvre `site/index.html`.

---

## À savoir, honnêtement
- Aucun pari n'est sûr. Un bon agent **perd souvent** : il gagne sur la durée parce que les cotes jouées paient plus que le risque.
- Juge-le sur **200 paris minimum**, avec la ligne *Rendement* du bilan, pas sur une semaine.
- Les bookmakers limitent parfois les comptes qui gagnent régulièrement : c'est normal, ouvre plusieurs comptes.
- En France, ne joue que chez les opérateurs agréés par l'ANJ (ceux de la liste « jouables »).
- Le site est public mais non référencé sur Google : ne partage l'adresse qu'avec qui tu veux.
- Besoin d'aide : **Joueurs Info Service, 09 74 75 13 13**.
