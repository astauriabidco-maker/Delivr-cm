# RELAY237 Production Readiness

Checklist technique avant bascule pre-prod puis production.

## 1. Configuration

- `DJANGO_ENV=production`
- `DEBUG=False`
- `SECRET_KEY` unique, long, non partage.
- `PUBLIC_DOMAIN=relay237.com`
- `ALLOWED_HOSTS=relay237.com,www.relay237.com`
- `CSRF_TRUSTED_ORIGINS=https://relay237.com,https://www.relay237.com`
- `CORS_ALLOWED_ORIGINS=https://relay237.com,https://www.relay237.com`
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` explicites.
- `DB_PASSWORD` different du mot de passe de developpement.

Le fichier `.env.production.example` sert de base. Ne jamais commiter le vrai `.env`.

## 2. HTTPS et WebSocket

- Certificat TLS actif pour `relay237.com` et `www.relay237.com`.
- Reverse proxy configure avec `X-Forwarded-Proto: https`.
- WebSocket tracking valide en `wss://relay237.com/ws/...`.
- Smoke test navigateur sur la page tracking: pas de tentative `ws://` en HTTPS.
- Smoke test mobile: API en `https://relay237.com`, WebSocket natif autorise sans header `Origin`.

## 3. Migrations et donnees

Avant migration prod:

```sql
SELECT delivery_id, user_id, transaction_type, COUNT(*)
FROM finance_transaction
WHERE delivery_id IS NOT NULL
  AND transaction_type IN ('COMMISSION', 'DELIVERY_CREDIT')
GROUP BY delivery_id, user_id, transaction_type
HAVING COUNT(*) > 1;
```

La requete doit retourner 0 ligne avant d'appliquer la contrainte `unique_completed_delivery_wallet_tx`.

Commandes pre-prod:

```bash
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
```

## 4. Paiements et webhooks

- MTN MoMo en environnement `production` uniquement avec:
  - `MTN_MOMO_SUBSCRIPTION_KEY`
  - `MTN_MOMO_API_USER`
  - `MTN_MOMO_API_KEY`
  - `MTN_MOMO_CALLBACK_URL`
  - `MTN_MOMO_WEBHOOK_SECRET`
- Orange Money en environnement `production` uniquement avec:
  - `ORANGE_MONEY_MERCHANT_KEY`
  - `ORANGE_MONEY_MERCHANT_SECRET`
  - `ORANGE_MONEY_CALLBACK_URL`
  - `ORANGE_MONEY_RETURN_URL`
- Tester callback success, failed, reference inconnue, callback rejoue.
- Verifier que les paiements deja traites restent idempotents.

## 5. WhatsApp, SMS et documents

- `WHATSAPP_NOTIFICATIONS_ENABLED=True` seulement quand le provider est configure.
- Meta:
  - `META_API_TOKEN`
  - `META_PHONE_NUMBER_ID`
  - `META_VERIFY_TOKEN`
  - `META_APP_SECRET`
- Twilio:
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_WHATSAPP_NUMBER`
- Tester message entrant, signature invalide, document PDF envoye, provider indisponible.
- En pre-prod, verifier qu'aucun message reel ne part vers des numeros clients non QA.

## 6. Backups et restauration

- Backup PostgreSQL quotidien minimum, retention 7/30 jours.
- Backup media quotidien: preuves photo, factures PDF, logos boutiques.
- Test de restauration sur une base separee avant prod.
- Documenter le RPO/RTO cible.
- Verifier que les secrets ne sont pas inclus dans les dumps partages.

## 7. Monitoring minimum

Surveiller:

- erreurs HTTP 5xx;
- latence API mobile et checkout;
- echecs webhooks MTN/Orange;
- transactions wallet creees par livraison;
- generation de PDF;
- echecs envoi WhatsApp/SMS;
- erreurs WebSocket;
- taille DB et espace disque media.

Configurer `SENTRY_DSN` en pre-prod/prod si disponible.

## 8. Smoke test pre-prod

- Landing: chargement, liens footer, CTA vendeur/coursier.
- Vendeur: inscription, validation, creation commande, paiement, suivi.
- Coursier mobile: login, GPS, acceptation, pickup photo, dropoff OTP, wallet.
- Client final: tracking public, OTP, notification.
- Admin/backoffice: dispatch, support, remboursement, incidents.
- WooCommerce: checkout, creation livraison, webhook retour statut, metas commande.
- Flutter: navigation, offline, permissions GPS/photo.

Critere de sortie: tous les parcours critiques passent sans erreur serveur, sans mutation financiere incoherente, et avec logs exploitables.
