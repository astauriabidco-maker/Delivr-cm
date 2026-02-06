"""
BOT App - Mobile Push Notification Service via WebSocket

Sends real-time push notifications to the courier mobile app
via Django Channels WebSocket instead of Firebase/APNs.
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class MobilePushService:
    """
    Service for sending push notifications to courier mobile app via WebSocket.
    
    The mobile app maintains a persistent WebSocket connection to receive
    real-time notifications about new orders, status updates, wallet changes, etc.
    """
    
    @staticmethod
    def _get_channel_layer():
        """Get the channel layer for WebSocket communication."""
        return get_channel_layer()
    
    @classmethod
    def send_to_courier(
        cls,
        courier_id: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Send a push notification to a specific courier's mobile app.
        
        Args:
            courier_id: UUID of the courier
            event_type: Type of event (new_order, order_assigned, wallet_update, etc.)
            data: Event payload data
            
        Returns:
            True if message was sent successfully
        """
        try:
            channel_layer = cls._get_channel_layer()
            
            if not channel_layer:
                logger.warning("[MOBILE_PUSH] No channel layer configured")
                return False
            
            group_name = f"courier_{courier_id}"
            
            # Send to courier's WebSocket group
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": event_type,
                    **data
                }
            )
            
            logger.info(f"[MOBILE_PUSH] Sent {event_type} to courier {str(courier_id)[:8]}")
            return True
            
        except Exception as e:
            logger.error(f"[MOBILE_PUSH] Failed to send to courier {courier_id}: {e}")
            return False
    
    @classmethod
    def send_new_order(
        cls,
        courier_id: str,
        order_id: str,
        pickup_address: str,
        dropoff_address: str,
        distance_km: float,
        total_price: Decimal,
        courier_earning: Decimal,
        distance_to_pickup: Optional[int] = None
    ) -> bool:
        """
        Notify courier about a new available order.
        
        Args:
            courier_id: UUID of the courier
            order_id: UUID of the delivery
            pickup_address: Pickup location description
            dropoff_address: Dropoff location description
            distance_km: Total delivery distance
            total_price: Total order price
            courier_earning: Courier's earning for this delivery
            distance_to_pickup: Distance from courier to pickup in meters
            
        Returns:
            True if notification sent successfully
        """
        return cls.send_to_courier(
            courier_id=courier_id,
            event_type="new_order_available",
            data={
                "order_id": str(order_id),
                "pickup_address": pickup_address or "À déterminer",
                "dropoff_address": dropoff_address or "À déterminer",
                "distance_km": float(distance_km),
                "total_price": str(total_price),
                "courier_earning": str(courier_earning),
                "distance_to_pickup": distance_to_pickup or 0,
            }
        )
    
    @classmethod
    def send_order_assigned(
        cls,
        courier_id: str,
        order_id: str,
        pickup_address: str,
        dropoff_address: str,
        sender_phone: str,
        pickup_otp: Optional[str] = None
    ) -> bool:
        """
        Notify courier that an order has been assigned to them.
        
        Args:
            courier_id: UUID of the courier
            order_id: UUID of the delivery
            pickup_address: Pickup location
            dropoff_address: Dropoff location
            sender_phone: Sender's phone for contact
            pickup_otp: OTP code for pickup verification
            
        Returns:
            True if notification sent successfully
        """
        return cls.send_to_courier(
            courier_id=courier_id,
            event_type="order_assigned",
            data={
                "order_id": str(order_id),
                "pickup_address": pickup_address or "À déterminer",
                "dropoff_address": dropoff_address or "À déterminer",
                "sender_phone": sender_phone,
                "pickup_otp": pickup_otp,
                "message": "Vous avez été assigné à une nouvelle commande!",
            }
        )
    
    @classmethod
    def send_order_cancelled(
        cls,
        courier_id: str,
        order_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Notify courier that an assigned order was cancelled.
        
        Args:
            courier_id: UUID of the courier
            order_id: UUID of the delivery
            reason: Cancellation reason
            
        Returns:
            True if notification sent successfully
        """
        return cls.send_to_courier(
            courier_id=courier_id,
            event_type="order_cancelled",
            data={
                "order_id": str(order_id),
                "reason": reason or "Annulée par le client",
                "message": "Une commande assignée a été annulée.",
            }
        )
    
    @classmethod
    def send_wallet_update(
        cls,
        courier_id: str,
        transaction_type: str,
        amount: Decimal,
        new_balance: Decimal,
        description: Optional[str] = None
    ) -> bool:
        """
        Notify courier about a wallet balance change.
        
        Args:
            courier_id: UUID of the courier
            transaction_type: 'credit' or 'debit'
            amount: Transaction amount
            new_balance: New wallet balance
            description: Transaction description
            
        Returns:
            True if notification sent successfully
        """
        return cls.send_to_courier(
            courier_id=courier_id,
            event_type="wallet_update",
            data={
                "type": transaction_type,
                "amount": str(amount),
                "balance": str(new_balance),
                "description": description or "",
            }
        )
    
    @classmethod
    def send_level_up(
        cls,
        courier_id: str,
        old_level: str,
        new_level: str,
        perks: Optional[list] = None
    ) -> bool:
        """
        Notify courier about a level promotion.
        
        Args:
            courier_id: UUID of the courier
            old_level: Previous level (BRONZE, SILVER, GOLD, PLATINUM)
            new_level: New level
            perks: List of new perks unlocked
            
        Returns:
            True if notification sent successfully
        """
        return cls.send_to_courier(
            courier_id=courier_id,
            event_type="level_up",
            data={
                "old_level": old_level,
                "new_level": new_level,
                "perks": perks or [],
                "message": f"Félicitations! Vous êtes passé au niveau {new_level}!",
            }
        )
    
    @classmethod
    def send_badge_unlocked(
        cls,
        courier_id: str,
        badge_id: str,
        badge_name: str,
        badge_description: str
    ) -> bool:
        """
        Notify courier about a new badge earned.
        
        Args:
            courier_id: UUID of the courier
            badge_id: Badge identifier
            badge_name: Human-readable badge name
            badge_description: Badge description
            
        Returns:
            True if notification sent successfully
        """
        return cls.send_to_courier(
            courier_id=courier_id,
            event_type="badge_unlocked",
            data={
                "badge_id": badge_id,
                "badge_name": badge_name,
                "badge_description": badge_description,
            }
        )
    
    @classmethod
    def broadcast_to_zone(
        cls,
        city: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Broadcast a notification to all online couriers in a city/zone.
        
        Args:
            city: City name (DOUALA, YAOUNDE)
            event_type: Type of event
            data: Event payload data
            
        Returns:
            True if message was sent successfully
        """
        try:
            channel_layer = cls._get_channel_layer()
            
            if not channel_layer:
                logger.warning("[MOBILE_PUSH] No channel layer configured")
                return False
            
            group_name = f"dispatch_{city.upper()}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": event_type,
                    **data
                }
            )
            
            logger.info(f"[MOBILE_PUSH] Broadcast {event_type} to zone {city}")
            return True
            
        except Exception as e:
            logger.error(f"[MOBILE_PUSH] Failed to broadcast to zone {city}: {e}")
            return False
