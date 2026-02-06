"""
BOT App - Courier-Specific Commands for WhatsApp Bot

Handles courier interactions via WhatsApp:
- Stats commands (STATS, MES STATS)
- Wallet balance (SOLDE, PORTEFEUILLE)
- Online/Offline toggle (ENLINE, HORSLIGNE)
- Recent deliveries (COURSES)
- Level and badges (NIVEAU, BADGES)
"""

import logging
from typing import Optional, Tuple
from django.utils import timezone
from datetime import timedelta

from core.models import User, UserRole
from core.gamification import (
    GamificationService, get_courier_badges_summary,
    LEVEL_THRESHOLDS
)

logger = logging.getLogger(__name__)


class CourierBotCommands:
    """
    Handler for courier-specific bot commands.
    
    All methods return (response_text, should_continue) tuples.
    should_continue indicates if the bot should process further.
    """
    
    # Command keywords (case insensitive)
    STATS_COMMANDS = ['stats', 'mes stats', 'statistiques', 'perf', 'performance']
    WALLET_COMMANDS = ['solde', 'portefeuille', 'wallet', 'argent', 'gains']
    ONLINE_COMMANDS = ['enligne', 'en ligne', 'online', 'dispo', 'disponible']
    OFFLINE_COMMANDS = ['horsligne', 'hors ligne', 'offline', 'indispo', 'pause']
    COURSES_COMMANDS = ['courses', 'livraisons', 'historique', 'mes courses']
    LEVEL_COMMANDS = ['niveau', 'level', 'rang', 'classement']
    BADGES_COMMANDS = ['badges', 'succès', 'trophées', 'achievements']
    STATUS_COMMANDS = ['statut', 'status', 'mon statut']
    
    @classmethod
    def get_courier_by_phone(cls, phone: str) -> Optional[User]:
        """Get courier user by phone number."""
        # Normalize phone
        phone = phone.replace('whatsapp:', '').strip()
        if not phone.startswith('+'):
            if phone.startswith('237'):
                phone = f'+{phone}'
            else:
                phone = f'+237{phone}'
        
        try:
            return User.objects.get(
                phone_number=phone,
                role=UserRole.COURIER,
                is_active=True
            )
        except User.DoesNotExist:
            return None
    
    @classmethod
    def is_courier_command(cls, text: str) -> bool:
        """Check if the message is a courier-specific command."""
        text_lower = text.lower().strip()
        
        all_commands = (
            cls.STATS_COMMANDS + cls.WALLET_COMMANDS + 
            cls.ONLINE_COMMANDS + cls.OFFLINE_COMMANDS +
            cls.COURSES_COMMANDS + cls.LEVEL_COMMANDS +
            cls.BADGES_COMMANDS + cls.STATUS_COMMANDS
        )
        
        return text_lower in all_commands
    
    @classmethod
    def handle_command(cls, phone: str, text: str) -> Tuple[str, bool]:
        """
        Handle a courier command.
        
        Args:
            phone: Courier's phone number
            text: Command text
            
        Returns:
            (response_text, was_handled) tuple
        """
        text_lower = text.lower().strip()
        
        # Get courier
        courier = cls.get_courier_by_phone(phone)
        if not courier:
            return None, False  # Not a courier, let normal flow handle
        
        # Match command
        if text_lower in cls.STATS_COMMANDS:
            return cls.handle_stats(courier), True
        
        if text_lower in cls.WALLET_COMMANDS:
            return cls.handle_wallet(courier), True
        
        if text_lower in cls.ONLINE_COMMANDS:
            return cls.handle_go_online(courier), True
        
        if text_lower in cls.OFFLINE_COMMANDS:
            return cls.handle_go_offline(courier), True
        
        if text_lower in cls.COURSES_COMMANDS:
            return cls.handle_recent_deliveries(courier), True
        
        if text_lower in cls.LEVEL_COMMANDS:
            return cls.handle_level(courier), True
        
        if text_lower in cls.BADGES_COMMANDS:
            return cls.handle_badges(courier), True
        
        if text_lower in cls.STATUS_COMMANDS:
            return cls.handle_status(courier), True
        
        return None, False  # Not a courier command
    
    @classmethod
    def handle_stats(cls, courier: User) -> str:
        """Handle STATS command - show today's and week's statistics."""
        from courier.services import CourierStatsService
        
        today = CourierStatsService.get_today_stats(courier)
        week = CourierStatsService.get_week_stats(courier)
        rank = CourierStatsService.get_courier_rank(courier)
        
        level_info = LEVEL_THRESHOLDS[courier.courier_level]
        
        message = (
            f"📊 *Vos Statistiques*\n\n"
            f"━━━━━ AUJOURD'HUI ━━━━━\n"
            f"📦 Courses: *{today['deliveries_count']}*\n"
            f"💰 Gains: *{today['earnings']:,.0f} XAF*\n"
            f"🚴 Distance: *{today['distance_km']:.1f} km*\n\n"
            f"━━━━━ CETTE SEMAINE ━━━━━\n"
            f"📦 Courses: *{week['total_deliveries']}*\n"
            f"💰 Gains: *{week['total_earnings']:,.0f} XAF*\n"
            f"🚴 Distance: *{week['total_distance']:.1f} km*\n\n"
            f"━━━━━ CLASSEMENT ━━━━━\n"
            f"🏆 Rang: *#{rank['rank']}* sur {rank['total_couriers']}\n"
            f"📈 Top *{rank['top_percent']:.0f}%*\n\n"
            f"{level_info['icon']} Niveau: *{level_info['label']}*\n"
            f"🔥 Série: *{today['current_streak']}* courses"
        )
        
        return message
    
    @classmethod
    def handle_wallet(cls, courier: User) -> str:
        """Handle SOLDE command - show wallet balance and debt."""
        from courier.services import CourierStatsService
        
        wallet = CourierStatsService.get_wallet_summary(courier)
        
        # Balance emoji based on status
        if wallet['balance'] >= 0:
            balance_emoji = "💰"
            balance_status = "Crédit"
        else:
            balance_emoji = "💸"
            balance_status = "Dette"
        
        message = (
            f"💳 *Votre Portefeuille*\n\n"
            f"{balance_emoji} Solde: *{wallet['balance']:,.0f} XAF*\n"
        )
        
        if wallet['balance'] < 0:
            message += (
                f"\n━━━━━ DETTE ━━━━━\n"
                f"⚠️ Utilisé: *{wallet['debt_used']:,.0f} XAF*\n"
                f"📊 Plafond: *{wallet['debt_ceiling']:,.0f} XAF*\n"
                f"📈 Usage: *{wallet['debt_percentage']:.1f}%*"
            )
            
            if wallet['is_blocked']:
                message += (
                    f"\n\n🚫 *COMPTE BLOQUÉ*\n"
                    f"Remboursez votre dette pour continuer à recevoir des courses."
                )
        
        message += (
            f"\n\n━━━━━ TOTAL GAGNÉ ━━━━━\n"
            f"💵 Total gains: *{wallet['total_earned']:,.0f} XAF*\n"
            f"💸 Commissions: *{wallet['total_commission']:,.0f} XAF*"
        )
        
        if wallet['available_for_withdrawal'] > 0:
            message += f"\n\n✅ Disponible au retrait: *{wallet['available_for_withdrawal']:,.0f} XAF*"
        
        return message
    
    @classmethod
    def handle_go_online(cls, courier: User) -> str:
        """Handle ENLIGNE command - set courier as available."""
        if not courier.is_verified:
            return (
                "⚠️ *Compte non vérifié*\n\n"
                "Vos documents sont en cours de vérification. "
                "Vous pourrez passer en ligne une fois validé."
            )
        
        if courier.is_courier_blocked:
            return (
                "🚫 *Compte bloqué*\n\n"
                "Votre plafond de dette est atteint. "
                "Remboursez pour continuer à recevoir des courses."
            )
        
        from courier.services import AvailabilityService
        AvailabilityService.set_online(courier, True)
        
        return (
            "🟢 *Vous êtes maintenant EN LIGNE*\n\n"
            "📦 Vous recevrez les nouvelles demandes de courses.\n\n"
            "Pour passer hors ligne, tapez *HORSLIGNE*"
        )
    
    @classmethod
    def handle_go_offline(cls, courier: User) -> str:
        """Handle HORSLIGNE command - set courier as unavailable."""
        from courier.services import AvailabilityService
        AvailabilityService.set_online(courier, False)
        
        return (
            "🔴 *Vous êtes maintenant HORS LIGNE*\n\n"
            "📴 Vous ne recevrez plus de demandes de courses.\n\n"
            "Pour revenir en ligne, tapez *ENLIGNE*"
        )
    
    @classmethod
    def handle_recent_deliveries(cls, courier: User) -> str:
        """Handle COURSES command - show recent deliveries."""
        from courier.services import CourierStatsService
        
        deliveries = CourierStatsService.get_recent_deliveries(courier, limit=5)
        
        if not deliveries:
            return (
                "📦 *Historique des Courses*\n\n"
                "Vous n'avez pas encore de courses.\n\n"
                "Passez en ligne pour recevoir des demandes!"
            )
        
        message = "📦 *5 Dernières Courses*\n\n"
        
        for d in deliveries:
            status_emoji = {
                'COMPLETED': '✅',
                'CANCELLED': '❌',
                'PENDING': '⏳',
                'ASSIGNED': '🏃',
                'PICKED_UP': '📦',
            }.get(d['status'], '❓')
            
            message += (
                f"{status_emoji} *{d['pickup_address'][:15]}* → *{d['dropoff_address'][:15]}*\n"
                f"   💰 {d['earning']:,.0f} XAF | 📏 {d['distance_km']:.1f} km\n\n"
            )
        
        message += "_Consultez le dashboard web pour plus de détails_"
        
        return message
    
    @classmethod
    def handle_level(cls, courier: User) -> str:
        """Handle NIVEAU command - show level and progression."""
        performance = GamificationService.get_courier_stats(courier)
        next_level = GamificationService.get_next_level_progress(courier)
        level_info = LEVEL_THRESHOLDS[courier.courier_level]
        
        message = (
            f"{level_info['icon']} *Niveau: {level_info['label']}*\n\n"
            f"📦 Total courses: *{performance['total_deliveries']}*\n"
            f"⭐ Note moyenne: *{performance['average_rating']:.1f}/5*\n"
            f"🔥 Série actuelle: *{performance['current_streak']}*\n"
            f"🏆 Meilleure série: *{performance['best_streak']}*\n\n"
            f"━━━━━ AVANTAGES ━━━━━\n"
        )
        
        for perk in level_info['perks']:
            message += f"✓ {perk}\n"
        
        if next_level['next_level']:
            next_info = next_level['next_level_info']
            message += (
                f"\n━━━━━ PROCHAIN NIVEAU ━━━━━\n"
                f"{next_info['icon']} *{next_info['label']}*\n"
                f"📊 Progression: *{next_level['progress_percent']:.0f}%*\n"
                f"📦 Encore *{next_level['deliveries_needed']}* courses\n"
                f"⭐ Note requise: *{next_level['rating_needed']}*"
            )
        else:
            message += "\n\n🏆 *Vous avez atteint le niveau maximum!*"
        
        return message
    
    @classmethod
    def handle_badges(cls, courier: User) -> str:
        """Handle BADGES command - show earned badges."""
        badges = get_courier_badges_summary(courier)
        
        message = (
            f"🏅 *Vos Badges*\n"
            f"({badges['total_badges']}/{badges['available_badges']} - "
            f"{badges['completion_percent']:.0f}%)\n\n"
        )
        
        if badges['badges']:
            for badge in badges['badges'][:10]:  # Limit to 10
                message += f"{badge['icon']} *{badge['display']}*\n"
        else:
            message += (
                "_Pas encore de badges._\n\n"
                "Continuez à livrer pour débloquer des succès! 🚀"
            )
        
        return message
    
    @classmethod
    def handle_status(cls, courier: User) -> str:
        """Handle STATUT command - show quick status overview."""
        level_info = LEVEL_THRESHOLDS[courier.courier_level]
        
        online_status = "🟢 EN LIGNE" if courier.is_online else "🔴 HORS LIGNE"
        verified_status = "✅ Vérifié" if courier.is_verified else "⏳ Non vérifié"
        
        message = (
            f"📋 *Votre Statut*\n\n"
            f"📍 {online_status}\n"
            f"📄 {verified_status}\n"
            f"{level_info['icon']} Niveau: *{level_info['label']}*\n"
            f"💰 Solde: *{float(courier.wallet_balance):,.0f} XAF*\n"
            f"📦 Courses: *{courier.total_deliveries_completed}*\n"
            f"⭐ Note: *{courier.average_rating:.1f}/5*\n"
        )
        
        if courier.is_courier_blocked:
            message += "\n🚫 *COMPTE BLOQUÉ* - Remboursez votre dette"
        
        message += (
            "\n\n━━━━━ COMMANDES ━━━━━\n"
            "📊 *STATS* - Statistiques\n"
            "💰 *SOLDE* - Portefeuille\n"
            "🟢 *ENLIGNE* - Disponible\n"
            "🔴 *HORSLIGNE* - Pause\n"
            "📦 *COURSES* - Historique\n"
            "🏅 *BADGES* - Succès"
        )
        
        return message
    
    @classmethod
    def get_courier_help_message(cls) -> str:
        """Get help message for courier commands."""
        return (
            "🏍️ *Commandes Coursier DELIVR*\n\n"
            "━━━━━ STATUT ━━━━━\n"
            "📋 *STATUT* - Vue d'ensemble\n"
            "🟢 *ENLIGNE* - Devenir disponible\n"
            "🔴 *HORSLIGNE* - Mode pause\n\n"
            "━━━━━ PERFORMANCES ━━━━━\n"
            "📊 *STATS* - Statistiques jour/semaine\n"
            "🏆 *NIVEAU* - Niveau et progression\n"
            "🏅 *BADGES* - Vos succès\n\n"
            "━━━━━ FINANCES ━━━━━\n"
            "💰 *SOLDE* - Portefeuille\n"
            "📦 *COURSES* - Historique récent\n\n"
            "_Accédez au dashboard web pour plus de détails_"
        )
