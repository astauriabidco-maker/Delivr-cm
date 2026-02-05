"""
LOGISTICS App - WebSocket Consumers for Real-time Tracking

Provides real-time updates for:
- Delivery tracking (customers/senders)
- Courier location and order notifications
- Dispatch zone monitoring (admins)
"""

import json
import logging
from typing import Dict, Any
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class DeliveryTrackingConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for tracking a specific delivery.
    
    Clients connect to: ws://host/ws/delivery/<delivery_id>/
    
    Events received:
    - delivery_status_update: Status changed (PENDING -> ASSIGNED -> PICKED_UP -> COMPLETED)
    - courier_location_update: Courier GPS position updated
    - delivery_eta_update: Estimated time of arrival updated
    """
    
    async def connect(self):
        self.delivery_id = self.scope['url_route']['kwargs']['delivery_id']
        self.room_group_name = f'delivery_{self.delivery_id}'
        
        # Verify delivery exists
        delivery = await self.get_delivery()
        if not delivery:
            await self.close(code=4004)
            return
        
        # Join delivery tracking room
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial state
        await self.send_json({
            'type': 'connection_established',
            'delivery_id': self.delivery_id,
            'status': delivery['status'],
            'courier_location': delivery.get('courier_location'),
        })
        
        logger.info(f"[WS] Client connected to delivery {self.delivery_id[:8]}")
    
    async def disconnect(self, close_code):
        # Leave delivery tracking room
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"[WS] Client disconnected from delivery {self.delivery_id[:8]}")
    
    async def receive_json(self, content):
        """Handle incoming WebSocket messages from clients."""
        message_type = content.get('type')
        
        if message_type == 'ping':
            await self.send_json({'type': 'pong'})
    
    # ============================================
    # Event Handlers (called via channel_layer.group_send)
    # ============================================
    
    async def delivery_status_update(self, event):
        """Send delivery status update to connected clients."""
        await self.send_json({
            'type': 'status_update',
            'status': event['status'],
            'timestamp': event['timestamp'],
            'message': event.get('message', ''),
        })
    
    async def courier_location_update(self, event):
        """Send courier location update to connected clients."""
        await self.send_json({
            'type': 'location_update',
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'timestamp': event['timestamp'],
        })
    
    async def delivery_eta_update(self, event):
        """Send ETA update to connected clients."""
        await self.send_json({
            'type': 'eta_update',
            'eta_minutes': event['eta_minutes'],
            'distance_km': event['distance_km'],
        })
    
    # ============================================
    # Database helpers
    # ============================================
    
    @database_sync_to_async
    def get_delivery(self) -> Dict[str, Any]:
        """Fetch delivery from database."""
        from logistics.models import Delivery
        
        try:
            delivery = Delivery.objects.select_related('courier').get(pk=self.delivery_id)
            result = {
                'status': delivery.status,
                'courier_location': None,
            }
            
            if delivery.courier and delivery.courier.last_location:
                result['courier_location'] = {
                    'latitude': delivery.courier.last_location.y,
                    'longitude': delivery.courier.last_location.x,
                }
            
            return result
        except Delivery.DoesNotExist:
            return None


class CourierConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for courier mobile app.
    
    Clients connect to: ws://host/ws/courier/
    
    Events sent by courier:
    - location_update: Report current GPS position
    - accept_order: Accept a pending delivery
    - update_status: Mark pickup/delivery complete
    
    Events received by courier:
    - new_order_available: New delivery in their zone
    - order_assigned: They were assigned an order
    - order_cancelled: An assigned order was cancelled
    """
    
    courier_id = None
    city_group = None
    
    async def connect(self):
        # Require authentication
        user = self.scope.get('user')
        
        if not user or user.is_anonymous:
            # For development, accept all connections
            # In production, add proper auth check
            pass
        
        await self.accept()
        
        await self.send_json({
            'type': 'connection_established',
            'message': 'Connecté en tant que coursier. Envoyez votre position GPS.',
        })
        
        logger.info("[WS] Courier connected")
    
    async def disconnect(self, close_code):
        if self.city_group:
            await self.channel_layer.group_discard(
                self.city_group,
                self.channel_name
            )
        
        if self.courier_id:
            await self.channel_layer.group_discard(
                f'courier_{self.courier_id}',
                self.channel_name
            )
        
        logger.info(f"[WS] Courier {self.courier_id} disconnected")
    
    async def receive_json(self, content):
        """Handle incoming messages from courier app."""
        message_type = content.get('type')
        
        if message_type == 'authenticate':
            # Authenticate courier by phone number
            phone = content.get('phone_number')
            courier = await self.authenticate_courier(phone)
            
            if courier:
                self.courier_id = str(courier['id'])
                self.city_group = f"dispatch_{courier.get('city', 'DOUALA')}"
                
                # Join courier-specific and city groups
                await self.channel_layer.group_add(
                    f'courier_{self.courier_id}',
                    self.channel_name
                )
                await self.channel_layer.group_add(
                    self.city_group,
                    self.channel_name
                )
                
                await self.send_json({
                    'type': 'authenticated',
                    'courier_id': self.courier_id,
                    'name': courier['name'],
                    'wallet_balance': str(courier['wallet_balance']),
                })
            else:
                await self.send_json({
                    'type': 'error',
                    'message': 'Numéro de téléphone non reconnu',
                })
        
        elif message_type == 'location_update':
            # Update courier's GPS position
            latitude = content.get('latitude')
            longitude = content.get('longitude')
            
            if latitude and longitude:
                await self.update_courier_location(latitude, longitude)
                
                await self.send_json({
                    'type': 'location_confirmed',
                    'latitude': latitude,
                    'longitude': longitude,
                })
        
        elif message_type == 'accept_order':
            order_id = content.get('order_id')
            result = await self.accept_order(order_id)
            
            await self.send_json({
                'type': 'order_acceptance_result',
                'success': result['success'],
                'message': result['message'],
                'order_id': order_id,
            })
        
        elif message_type == 'ping':
            await self.send_json({'type': 'pong'})
    
    # ============================================
    # Event Handlers (received from channel_layer)
    # ============================================
    
    async def new_order_available(self, event):
        """Notify courier of a new available order."""
        await self.send_json({
            'type': 'new_order',
            'order_id': event['order_id'],
            'pickup_address': event.get('pickup_address', ''),
            'dropoff_address': event.get('dropoff_address', ''),
            'distance_km': event['distance_km'],
            'total_price': event['total_price'],
            'courier_earning': event['courier_earning'],
            'distance_to_pickup': event.get('distance_to_pickup', 0),
        })
    
    async def order_assigned(self, event):
        """Notify courier they were assigned an order."""
        await self.send_json({
            'type': 'order_assigned',
            'order_id': event['order_id'],
            'message': 'Vous avez été assigné à une nouvelle commande!',
        })
    
    # ============================================
    # Database helpers
    # ============================================
    
    @database_sync_to_async
    def authenticate_courier(self, phone_number: str) -> Dict[str, Any]:
        """Authenticate courier by phone number."""
        from core.models import User, UserRole
        
        try:
            courier = User.objects.get(
                phone_number=phone_number,
                role=UserRole.COURIER,
                is_active=True
            )
            return {
                'id': courier.id,
                'name': courier.full_name,
                'wallet_balance': courier.wallet_balance,
                'city': 'DOUALA',  # TODO: Get from courier profile
            }
        except User.DoesNotExist:
            return None
    
    @database_sync_to_async
    def update_courier_location(self, latitude: float, longitude: float):
        """Update courier's GPS position in database."""
        from django.contrib.gis.geos import Point
        from django.utils import timezone
        from core.models import User
        
        if not self.courier_id:
            return
        
        try:
            User.objects.filter(pk=self.courier_id).update(
                last_location=Point(longitude, latitude, srid=4326),
                last_location_updated=timezone.now()
            )
        except Exception as e:
            logger.error(f"[WS] Failed to update courier location: {e}")
    
    @database_sync_to_async
    def accept_order(self, order_id: str) -> Dict[str, Any]:
        """Accept an order for this courier."""
        from logistics.services.dispatch import accept_order
        from core.models import User
        
        if not self.courier_id:
            return {'success': False, 'message': 'Non authentifié'}
        
        try:
            courier = User.objects.get(pk=self.courier_id)
            accept_order(order_id, courier)
            return {'success': True, 'message': 'Commande acceptée!'}
        except ValueError as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            logger.error(f"[WS] Failed to accept order: {e}")
            return {'success': False, 'message': 'Erreur interne'}


class DispatchZoneConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for dispatch zone monitoring (admin dashboard).
    
    Clients connect to: ws://host/ws/dispatch/<city>/
    
    Events received:
    - all_couriers_update: List of all active couriers with positions
    - all_deliveries_update: List of all active deliveries
    - new_delivery: A new delivery was created
    - delivery_status_change: A delivery changed status
    """
    
    async def connect(self):
        self.city = self.scope['url_route']['kwargs']['city'].upper()
        self.room_group_name = f'dispatch_{self.city}'
        
        # Join city dispatch room
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial state
        status = await self.get_zone_status()
        
        await self.send_json({
            'type': 'connection_established',
            'city': self.city,
            'active_couriers': status['courier_count'],
            'pending_deliveries': status['pending_count'],
        })
        
        logger.info(f"[WS] Dispatch monitor connected for {self.city}")
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive_json(self, content):
        """Handle incoming messages from dispatch dashboard."""
        message_type = content.get('type')
        
        if message_type == 'refresh':
            status = await self.get_zone_status()
            await self.send_json({
                'type': 'zone_status',
                'couriers': status['couriers'],
                'deliveries': status['deliveries'],
            })
        
        elif message_type == 'ping':
            await self.send_json({'type': 'pong'})
    
    # ============================================
    # Event Handlers
    # ============================================
    
    async def new_delivery(self, event):
        """Notify of a new delivery in the zone."""
        await self.send_json({
            'type': 'new_delivery',
            'delivery': event['delivery'],
        })
    
    async def delivery_status_change(self, event):
        """Notify of a delivery status change."""
        await self.send_json({
            'type': 'delivery_update',
            'delivery_id': event['delivery_id'],
            'new_status': event['new_status'],
        })
    
    async def courier_location_update(self, event):
        """Notify of a courier location update."""
        await self.send_json({
            'type': 'courier_moved',
            'courier_id': event['courier_id'],
            'latitude': event['latitude'],
            'longitude': event['longitude'],
        })
    
    # ============================================
    # Database helpers
    # ============================================
    
    @database_sync_to_async
    def get_zone_status(self) -> Dict[str, Any]:
        """Get current status of the dispatch zone."""
        from core.models import User, UserRole
        from logistics.models import Delivery, DeliveryStatus
        
        # Get active couriers with location
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_active=True,
            last_location__isnull=False
        ).values('id', 'full_name', 'phone_number', 'wallet_balance', 'last_location')
        
        courier_list = []
        for c in couriers:
            courier_list.append({
                'id': str(c['id']),
                'name': c['full_name'],
                'phone': c['phone_number'],
                'balance': str(c['wallet_balance']),
                'latitude': c['last_location'].y if c['last_location'] else None,
                'longitude': c['last_location'].x if c['last_location'] else None,
            })
        
        # Get pending/active deliveries
        active_statuses = [
            DeliveryStatus.PENDING,
            DeliveryStatus.ASSIGNED,
            DeliveryStatus.PICKED_UP,
            DeliveryStatus.IN_TRANSIT,
        ]
        
        deliveries = Delivery.objects.filter(
            status__in=active_statuses
        ).select_related('sender', 'courier').order_by('-created_at')[:50]
        
        delivery_list = []
        for d in deliveries:
            delivery_list.append({
                'id': str(d.id),
                'status': d.status,
                'total_price': str(d.total_price),
                'pickup_lat': d.pickup_geo.y if d.pickup_geo else None,
                'pickup_lng': d.pickup_geo.x if d.pickup_geo else None,
                'dropoff_lat': d.dropoff_geo.y if d.dropoff_geo else None,
                'dropoff_lng': d.dropoff_geo.x if d.dropoff_geo else None,
                'courier_id': str(d.courier.id) if d.courier else None,
            })
        
        return {
            'courier_count': len(courier_list),
            'pending_count': sum(1 for d in delivery_list if d['status'] == 'PENDING'),
            'couriers': courier_list,
            'deliveries': delivery_list,
        }
