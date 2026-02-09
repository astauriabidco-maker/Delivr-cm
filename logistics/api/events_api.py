"""
LOGISTICS App - Traffic Events API

REST API for couriers to report and view real-time traffic events
(Waze-like incident reporting system).

Endpoints:
    GET    /api/traffic/events/           → List active events near location
    POST   /api/traffic/events/           → Report a new event
    GET    /api/traffic/events/<id>/       → Event detail
    POST   /api/traffic/events/<id>/vote/  → Upvote/downvote an event
    DELETE /api/traffic/events/<id>/       → Delete own event (reporter only)
"""

import logging
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from ..models import (
    TrafficEvent, TrafficEventVote,
    TrafficEventType, TrafficEventSeverity
)

logger = logging.getLogger(__name__)


def _serialize_event(event, user=None):
    """Serialize a TrafficEvent to dict."""
    data = {
        'id': str(event.id),
        'event_type': event.event_type,
        'event_type_display': event.get_event_type_display(),
        'severity': event.severity,
        'severity_display': event.get_severity_display(),
        'latitude': event.latitude,
        'longitude': event.longitude,
        'address': event.address,
        'description': event.description,
        'photo_url': event.photo.url if event.photo else None,
        'upvotes': event.upvotes,
        'downvotes': event.downvotes,
        'confidence_score': event.confidence_score,
        'reporter_name': event.reporter.get_full_name() or event.reporter.phone,
        'is_own': str(event.reporter_id) == str(user.id) if user else False,
        'created_at': event.created_at.isoformat() if event.created_at else None,
        'expires_at': event.expires_at.isoformat() if event.expires_at else None,
        'time_ago': _time_ago(event.created_at),
        'time_remaining': _time_remaining(event.expires_at),
    }
    
    # Add user's vote if authenticated
    if user and user.is_authenticated:
        vote = TrafficEventVote.objects.filter(
            event=event, voter=user
        ).first()
        data['user_vote'] = 'up' if (vote and vote.is_upvote) else ('down' if vote else None)
    
    return data


def _time_ago(dt):
    """Human-readable time ago."""
    if not dt:
        return ""
    delta = timezone.now() - dt
    minutes = int(delta.total_seconds() / 60)
    if minutes < 1:
        return "À l'instant"
    elif minutes < 60:
        return f"Il y a {minutes} min"
    elif minutes < 1440:
        hours = minutes // 60
        return f"Il y a {hours}h"
    else:
        days = minutes // 1440
        return f"Il y a {days}j"


def _time_remaining(dt):
    """Human-readable time remaining."""
    if not dt:
        return ""
    delta = dt - timezone.now()
    minutes = int(delta.total_seconds() / 60)
    if minutes <= 0:
        return "Expiré"
    elif minutes < 60:
        return f"{minutes} min restantes"
    elif minutes < 1440:
        hours = minutes // 60
        return f"{hours}h restantes"
    else:
        days = minutes // 1440
        return f"{days}j restantes"


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def traffic_events_list(request):
    """
    GET:  List active traffic events, optionally filtered by location.
    POST: Report a new traffic event (requires authentication).
    """
    if request.method == 'GET':
        return _list_events(request)
    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentification requise pour signaler un événement'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return _create_event(request)


def _list_events(request):
    """List active, non-expired events."""
    try:
        now = timezone.now()
        
        events = TrafficEvent.objects.filter(
            is_active=True,
            expires_at__gt=now,
        )
        
        # Optional: filter by proximity to a point
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius_km = float(request.query_params.get('radius', 10))
        
        if lat and lng:
            try:
                point = Point(float(lng), float(lat), srid=4326)
                events = events.filter(
                    location__distance_lte=(point, D(km=radius_km))
                ).annotate(
                    distance=Distance('location', point)
                ).order_by('distance')
            except (ValueError, TypeError):
                pass
        
        # Optional: filter by event type
        event_type = request.query_params.get('type')
        if event_type:
            events = events.filter(event_type=event_type)
        
        # Auto-deactivate expired events with low confidence
        expired_low_conf = events.filter(
            expires_at__lt=now,
        )
        expired_low_conf.update(is_active=False)
        
        # Limit results
        events = events[:50]
        
        user = request.user if request.user.is_authenticated else None
        serialized = [_serialize_event(e, user) for e in events]
        
        return Response({
            'events': serialized,
            'count': len(serialized),
            'event_types': [
                {
                    'value': choice[0],
                    'label': choice[1],
                    'default_ttl_minutes': TrafficEvent.default_ttl_minutes(choice[0]),
                }
                for choice in TrafficEventType.choices
            ],
        })
    except Exception as e:
        logger.error(f"[EVENTS API] List error: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération des événements'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _create_event(request):
    """Create a new traffic event."""
    try:
        event_type = request.data.get('event_type')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        # Validation
        if not event_type:
            return Response(
                {'error': 'Le type d\'événement est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_types = [c[0] for c in TrafficEventType.choices]
        if event_type not in valid_types:
            return Response(
                {'error': f'Type invalide. Choix: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not latitude or not longitude:
            return Response(
                {'error': 'La position GPS (latitude, longitude) est requise'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lat = float(latitude)
            lng = float(longitude)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Coordonnées GPS invalides'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create event
        severity = request.data.get('severity', TrafficEventSeverity.MEDIUM)
        if severity not in [c[0] for c in TrafficEventSeverity.choices]:
            severity = TrafficEventSeverity.MEDIUM
        
        event = TrafficEvent(
            reporter=request.user,
            event_type=event_type,
            severity=severity,
            location=Point(lng, lat, srid=4326),
            address=request.data.get('address', ''),
            description=request.data.get('description', ''),
        )
        
        # Handle optional photo
        if 'photo' in request.FILES:
            event.photo = request.FILES['photo']
        
        event.save()  # save() auto-sets expires_at
        
        logger.info(
            f"[EVENTS] Nouveau signalement: {event.get_event_type_display()} "
            f"par {request.user} à ({lat}, {lng})"
        )
        
        return Response(
            _serialize_event(event, request.user),
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.error(f"[EVENTS API] Create error: {e}")
        return Response(
            {'error': 'Erreur lors de la création de l\'événement'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'DELETE'])
@permission_classes([AllowAny])
def traffic_event_detail(request, event_id):
    """Get or delete a specific event."""
    try:
        event = TrafficEvent.objects.get(id=event_id)
    except TrafficEvent.DoesNotExist:
        return Response(
            {'error': 'Événement introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        user = request.user if request.user.is_authenticated else None
        return Response(_serialize_event(event, user))
    
    elif request.method == 'DELETE':
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentification requise'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        # Only reporter or admin can delete
        if event.reporter != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Vous ne pouvez supprimer que vos propres signalements'},
                status=status.HTTP_403_FORBIDDEN
            )
        event.is_active = False
        event.resolved_at = timezone.now()
        event.save()
        return Response({'message': 'Événement supprimé'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def traffic_event_vote(request, event_id):
    """
    Vote on an event (confirm or deny).
    
    Body: { "vote": "up" | "down" }
    """
    try:
        event = TrafficEvent.objects.get(id=event_id, is_active=True)
    except TrafficEvent.DoesNotExist:
        return Response(
            {'error': 'Événement introuvable ou inactif'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Can't vote on own event
    if event.reporter == request.user:
        return Response(
            {'error': 'Vous ne pouvez pas voter sur votre propre signalement'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    vote_value = request.data.get('vote', '').lower()
    if vote_value not in ('up', 'down'):
        return Response(
            {'error': 'Vote invalide. Utiliser "up" ou "down"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    is_upvote = vote_value == 'up'
    
    # Check if already voted
    existing_vote = TrafficEventVote.objects.filter(
        event=event, voter=request.user
    ).first()
    
    if existing_vote:
        if existing_vote.is_upvote == is_upvote:
            return Response(
                {'error': 'Vous avez déjà voté dans ce sens'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Change vote direction
        if existing_vote.is_upvote:
            event.upvotes = max(0, event.upvotes - 1)
            event.downvotes += 1
        else:
            event.downvotes = max(0, event.downvotes - 1)
            event.upvotes += 1
        existing_vote.is_upvote = is_upvote
        existing_vote.save()
    else:
        # New vote
        TrafficEventVote.objects.create(
            event=event,
            voter=request.user,
            is_upvote=is_upvote,
        )
        if is_upvote:
            event.upvotes += 1
        else:
            event.downvotes += 1
    
    # Auto-deactivate if too many downvotes
    if event.downvotes >= 5 and event.confidence_score < 30:
        event.is_active = False
        event.resolved_at = timezone.now()
        logger.info(f"[EVENTS] Auto-désactivé: {event} (confiance: {event.confidence_score}%)")
    
    event.save()
    
    return Response({
        'message': 'Vote enregistré' if not existing_vote else 'Vote modifié',
        'upvotes': event.upvotes,
        'downvotes': event.downvotes,
        'confidence_score': event.confidence_score,
        'is_active': event.is_active,
    })
