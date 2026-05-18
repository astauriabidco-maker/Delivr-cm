# 🏠 Module `home/` — Landing Page & Page de Commande Publique

> L'entrée du système. Landing page marketing + formulaire de commande publique pour les clients.

---

## 🎯 Rôle en une phrase

> Ce module gère la **vitrine publique** de RELAY237 : la page d'accueil qui convertit les visiteurs en utilisateurs, et le **formulaire de commande** accessible sans inscription.

---

## 🖥️ Pages

| Page | URL | Description |
|---|---|---|
| 🏠 Landing Page | `/` | Page d'accueil marketing |
| 📦 Commande publique | `/book/<shop_slug>/` | Formulaire personnalisé par vendeur |

---

## 🔗 Le "Lien Magique"

Chaque vendeur BUSINESS a un slug unique (ex: `marie-fashion-bijoux`) qui génère une URL publique :

```
relay237.com/book/marie-fashion-bijoux/
```

Cette page affiche :
- Le **logo** du vendeur
- La **couleur** personnalisée
- Le **message de bienvenue**
- Un formulaire de commande (nom, téléphone, adresse, quartier)
- Le **prix estimé** en temps réel

> **Aucune inscription nécessaire** pour le client — il suffit de remplir le formulaire !

---

*📖 Retour au [README principal](../README.md)*
