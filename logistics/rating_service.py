"""
Rating Service for DELIVR-CM

Handles rating submission and average calculation.
"""

import logging
from typing import Optional
from django.db import transaction

from core.models import User
from logistics.models import Delivery, Rating, RatingType, DeliveryStatus

logger = logging.getLogger(__name__)


class RatingService:
    """
    Service for handling delivery ratings.
    """
    
    @staticmethod
    @transaction.atomic
    def submit_courier_rating(
        delivery: Delivery,
        score: int,
        comment: str = ""
    ) -> Optional[Rating]:
        """
        Submit a rating for the courier (by the client/sender).
        
        Args:
            delivery: The completed delivery
            score: Rating score (1-5)
            comment: Optional comment
            
        Returns:
            Rating object if successful, None if failed
        """
        if delivery.status != DeliveryStatus.COMPLETED:
            logger.warning(f"Cannot rate incomplete delivery {delivery.id}")
            return None
        
        if not delivery.courier:
            logger.warning(f"Delivery {delivery.id} has no courier assigned")
            return None
        
        # Check if rating already exists
        existing = Rating.objects.filter(
            delivery=delivery,
            rater=delivery.sender,
            rated=delivery.courier
        ).first()
        
        if existing:
            logger.info(f"Rating already exists for delivery {delivery.id}")
            return existing
        
        try:
            rating = Rating.objects.create(
                delivery=delivery,
                rater=delivery.sender,
                rated=delivery.courier,
                rating_type=RatingType.COURIER,
                score=score,
                comment=comment
            )
            logger.info(f"Rating created: {delivery.id} → {score}⭐")
            return rating
            
        except Exception as e:
            logger.error(f"Error creating rating: {e}")
            return None
    
    @staticmethod
    @transaction.atomic
    def submit_sender_rating(
        delivery: Delivery,
        score: int,
        comment: str = ""
    ) -> Optional[Rating]:
        """
        Submit a rating for the sender/client (by the courier).
        
        Args:
            delivery: The completed delivery
            score: Rating score (1-5)
            comment: Optional comment
            
        Returns:
            Rating object if successful, None if failed
        """
        if delivery.status != DeliveryStatus.COMPLETED:
            return None
        
        if not delivery.courier:
            return None
        
        # Check if rating already exists
        existing = Rating.objects.filter(
            delivery=delivery,
            rater=delivery.courier,
            rated=delivery.sender
        ).first()
        
        if existing:
            return existing
        
        try:
            rating = Rating.objects.create(
                delivery=delivery,
                rater=delivery.courier,
                rated=delivery.sender,
                rating_type=RatingType.SENDER,
                score=score,
                comment=comment
            )
            return rating
            
        except Exception as e:
            logger.error(f"Error creating sender rating: {e}")
            return None
    
    @staticmethod
    def get_user_rating(user: User) -> dict:
        """
        Get rating summary for a user.
        
        Returns:
            dict with average, count, and breakdown
        """
        from django.db.models import Count
        
        ratings = Rating.objects.filter(rated=user)
        
        breakdown = ratings.values('score').annotate(
            count=Count('id')
        ).order_by('score')
        
        return {
            'average': user.average_rating,
            'count': user.total_ratings_count,
            'breakdown': {item['score']: item['count'] for item in breakdown}
        }
    
    @staticmethod
    def send_rating_request_via_whatsapp(delivery: Delivery):
        """
        Send WhatsApp message asking recipient to rate the delivery.
        Called after delivery completion.
        """
        from bot.services import send_whatsapp_message
        
        recipient_phone = delivery.recipient_phone
        courier_name = delivery.courier.full_name if delivery.courier else "votre coursier"
        
        message = (
            f"✅ Votre colis a été livré !\n\n"
            f"Comment évaluez-vous {courier_name} ?\n\n"
            f"Répondez avec une note de 1 à 5 ⭐\n"
            f"(1 = Mauvais, 5 = Excellent)"
        )
        
        try:
            send_whatsapp_message(recipient_phone, message)
            logger.info(f"Rating request sent for delivery {delivery.id}")
        except Exception as e:
            logger.error(f"Failed to send rating request: {e}")
    
    @staticmethod
    def process_rating_response(phone: str, score_text: str) -> Optional[Rating]:
        """
        Process a rating response from WhatsApp.
        
        Args:
            phone: Phone number of the rater
            score_text: Text containing the score (e.g., "5", "4 étoiles")
            
        Returns:
            Rating if successful
        """
        # Extract numeric score
        import re
        match = re.search(r'[1-5]', score_text)
        if not match:
            return None
        
        score = int(match.group())
        
        # Find the most recent completed delivery for this recipient
        recent_delivery = Delivery.objects.filter(
            recipient_phone__endswith=phone[-9:],  # Match last 9 digits
            status=DeliveryStatus.COMPLETED
        ).order_by('-completed_at').first()
        
        if not recent_delivery:
            return None
        
        # Check if already rated
        existing = Rating.objects.filter(
            delivery=recent_delivery,
            rated=recent_delivery.courier
        ).exists()
        
        if existing:
            return None
        
        # Create rating (using sender as rater since recipient isn't a user)
        # In a full implementation, we might create a lightweight user or use phone
        return RatingService.submit_courier_rating(
            delivery=recent_delivery,
            score=score
        )
