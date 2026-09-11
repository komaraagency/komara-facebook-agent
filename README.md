# Komara Facebook Agent 🤖🇬🇳

Agent Facebook autonome — répond automatiquement aux **messages privés** et aux **commentaires** de la page Komara Agency.

**100% déterministe** : aucune IA externe, pas de coût API. Les réponses viennent de règles locales (`kb.json`) et de la FAQ (`docs/faq.md`).

## Fonctionnalités
- ✅ Réponses automatiques aux commentaires
- ✅ Réponses automatiques aux messages privés
- ✅ Base de connaissance locale (kb.json) : tarifs, logo, affiche, vidéo IA, contact...
- ✅ FAQ matching intelligent
- ✅ Mémoire SQLite : anti-doublons + historique conversations
- ✅ Mode DRY_RUN pour tester sans envoyer

## Démarrage local

```bash
pip install -r requirements.txt
cp .env.example .env   # remplis tes clés
python worker.py
```

Test : http://localhost:8000/health

## Déploiement Railway

1. Va sur https://railway.app → New Project → Deploy from GitHub repo
2. Ajoute les variables :
   - `FACEBOOK_PAGE_ACCESS_TOKEN`
   - `FACEBOOK_VERIFY_TOKEN`
   - `FACEBOOK_PAGE_ID`
   - `DRY_RUN=false` (pour passer en live)
3. Railway détecte le Dockerfile automatiquement

## Configuration du webhook Meta

Dans https://developers.facebook.com → ton app → Webhooks :
1. Callback URL : `https://ton-url-railway.up.railway.app/webhook`
2. Verify Token : la valeur de `FACEBOOK_VERIFY_TOKEN`
3. Abonne-toi aux champs : `feed` (commentaires) + `messages` (MP)

> ⚠️ Le token de Page expire — régénère-le dans le Graph API Explorer avec les permissions `pages_messaging`, `pages_manage_engagement`, `pages_read_engagement` si les réponses cessent.

## Test sans Facebook (DRY_RUN)

Avec `DRY_RUN=true` (défaut), aucune requête n'est envoyée à Facebook :

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"field":"feed","value":{"comment_id":"123","message":"vos tarifs ?","from":{"id":"999","name":"Awa"}}}}]}]}'
```

Réponse attendue : les tarifs Komara Agency, statut `dry_run`.

---
Komara Agency 🇬🇳 — Vision. Impact. Excellence.
