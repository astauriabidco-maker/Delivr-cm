# 🔌 Module `integrations/` — API Partenaires & E-commerce

> Connecte DELIVR-CM aux plateformes e-commerce externes (WooCommerce, Shopify, etc.) via des plugins et APIs.

---

## 🎯 Rôle en une phrase

> Ce module permet aux vendeurs avec un **site e-commerce** d'automatiser la création de livraisons directement depuis leurs commandes en ligne.

---

## 🔗 Intégrations supportées

| Plateforme | Méthode | Statut |
|---|---|---|
| **WooCommerce** | Plugin WordPress (`wp-plugin/`) | ✅ Disponible |
| **Shopify** | Webhooks + API | 🔄 En développement |
| **Custom** | API REST + Webhooks | ✅ Via `partners/` |

---

## 🔧 Plugin WooCommerce

Le dossier `wp-plugin/` contient un plugin WordPress/WooCommerce qui :
1. Ajoute "DELIVR-CM" comme méthode d'expédition
2. Envoie automatiquement les commandes à l'API DELIVR-CM
3. Affiche le statut de livraison dans le backoffice WooCommerce
4. Met à jour le statut WooCommerce quand la livraison est terminée (via webhook)

---

*📖 Retour au [README principal](../README.md)*
