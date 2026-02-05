"""
Tracking API Endpoints for Enhanced Tracking Page

Features:
- Share link generation
- ETA calculation via OSRM
- Delivery proof upload
- Step history
"""

import uuid
import hashlib
import requests
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from logistics.models import Delivery


class ShareLinkView(View):
    """Generate a temporary share link for delivery tracking."""
    
    def post(self, request, delivery_id):
        delivery = get_object_or_404(Delivery, id=delivery_id)
        
        # Generate unique share token (valid 24h)
        share_token = hashlib.sha256(
            f"{delivery_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Cache the mapping (24 hours)
        cache_key = f"share_link_{share_token}"
        cache.set(cache_key, str(delivery_id), timeout=86400)
        
        # Build share URL
        base_url = request.build_absolute_uri('/').rstrip('/')
        share_url = f"{base_url}/track/s/{share_token}/"
        
        return JsonResponse({
            'success': True,
            'share_url': share_url,
            'expires_in': '24 heures'
        })


class ETACalculationView(View):
    """Calculate ETA using OSRM routing engine."""
    
    OSRM_URL = getattr(settings, 'OSRM_URL', 'http://router.project-osrm.org')
    
    def get(self, request, delivery_id):
        delivery = get_object_or_404(Delivery, id=delivery_id)
        
        # Get courier position from cache (updated by WebSocket)
        courier_pos = cache.get(f"courier_pos_{delivery.courier_id}")
        
        if not courier_pos or not delivery.dropoff_geo:
            return JsonResponse({
                'success': False,
                'message': 'Position non disponible'
            })
        
        # Call OSRM for route
        try:
            origin = f"{courier_pos['lng']},{courier_pos['lat']}"
            dest = f"{delivery.dropoff_geo.x},{delivery.dropoff_geo.y}"
            
            response = requests.get(
                f"{self.OSRM_URL}/route/v1/driving/{origin};{dest}",
                params={'overview': 'false'},
                timeout=5
            )
            data = response.json()
            
            if data.get('code') == 'Ok' and data.get('routes'):
                route = data['routes'][0]
                duration_minutes = round(route['duration'] / 60)
                distance_km = round(route['distance'] / 1000, 1)
                
                return JsonResponse({
                    'success': True,
                    'eta_minutes': duration_minutes,
                    'distance_km': distance_km,
                    'updated_at': timezone.now().isoformat()
                })
        except Exception as e:
            pass
        
        return JsonResponse({
            'success': False,
            'message': 'Calcul ETA indisponible'
        })


class DeliveryHistoryView(View):
    """Get detailed step history for a delivery."""
    
    def get(self, request, delivery_id):
        delivery = get_object_or_404(Delivery, id=delivery_id)
        
        # Build history from timestamps
        history = []
        
        if delivery.created_at:
            history.append({
                'step': 'created',
                'label': 'Commande créée',
                'icon': '📦',
                'timestamp': delivery.created_at.isoformat(),
                'time_display': delivery.created_at.strftime('%H:%M'),
                'date_display': delivery.created_at.strftime('%d/%m/%Y'),
                'location': delivery.pickup_address or 'Point de ramassage'
            })
        
        if delivery.assigned_at:
            courier_name = delivery.courier.get_full_name() if delivery.courier else 'Coursier'
            history.append({
                'step': 'assigned',
                'label': 'Coursier assigné',
                'icon': '🏍️',
                'timestamp': delivery.assigned_at.isoformat(),
                'time_display': delivery.assigned_at.strftime('%H:%M'),
                'date_display': delivery.assigned_at.strftime('%d/%m/%Y'),
                'location': f'{courier_name} prend en charge'
            })
        
        if delivery.picked_up_at:
            history.append({
                'step': 'picked_up',
                'label': 'Colis récupéré',
                'icon': '📤',
                'timestamp': delivery.picked_up_at.isoformat(),
                'time_display': delivery.picked_up_at.strftime('%H:%M'),
                'date_display': delivery.picked_up_at.strftime('%d/%m/%Y'),
                'location': delivery.pickup_address or 'Point de ramassage'
            })
        
        if delivery.in_transit_at:
            history.append({
                'step': 'in_transit',
                'label': 'En route',
                'icon': '🚀',
                'timestamp': delivery.in_transit_at.isoformat(),
                'time_display': delivery.in_transit_at.strftime('%H:%M'),
                'date_display': delivery.in_transit_at.strftime('%d/%m/%Y'),
                'location': 'Vers destination'
            })
        
        if delivery.completed_at:
            history.append({
                'step': 'completed',
                'label': 'Livré',
                'icon': '✅',
                'timestamp': delivery.completed_at.isoformat(),
                'time_display': delivery.completed_at.strftime('%H:%M'),
                'date_display': delivery.completed_at.strftime('%d/%m/%Y'),
                'location': delivery.dropoff_address or 'Destination'
            })
        
        # Add proof photo if available
        proof_url = None
        if delivery.proof_photo:
            proof_url = request.build_absolute_uri(delivery.proof_photo.url)
        
        return JsonResponse({
            'success': True,
            'delivery_id': str(delivery.id),
            'current_status': delivery.status,
            'history': history,
            'proof_photo': proof_url,
            'recipient_name': delivery.recipient_name,
            'distance_km': delivery.distance_km
        })


class ProofUploadView(View):
    """Upload delivery proof photo (for courier app)."""
    
    def post(self, request, delivery_id):
        delivery = get_object_or_404(Delivery, id=delivery_id)
        
        if 'photo' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': 'Aucune photo fournie'
            }, status=400)
        
        delivery.proof_photo = request.FILES['photo']
        delivery.save(update_fields=['proof_photo'])
        
        return JsonResponse({
            'success': True,
            'message': 'Photo de preuve enregistrée',
            'photo_url': request.build_absolute_uri(delivery.proof_photo.url)
        })


class SharedTrackingView(View):
    """Access tracking via shared link."""
    
    def get(self, request, share_token):
        # Look up delivery ID from cache
        cache_key = f"share_link_{share_token}"
        delivery_id = cache.get(cache_key)
        
        if not delivery_id:
            return JsonResponse({
                'success': False,
                'message': 'Lien expiré ou invalide'
            }, status=404)
        
        # Return delivery ID for redirect
        return JsonResponse({
            'success': True,
            'delivery_id': delivery_id
        })
