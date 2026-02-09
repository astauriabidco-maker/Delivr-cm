"""
LOGISTICS App - Traffic API Endpoints

REST API endpoints for serving real-time traffic data
to the mobile app and admin dashboard.

Endpoints:
    GET  /api/traffic/heatmap/      → Traffic heatmap (grid cells with levels)
    GET  /api/traffic/stats/        → City-wide traffic statistics
    POST /api/traffic/route/        → Traffic along a specific route
    GET  /api/traffic/cell/<id>/    → Traffic for a specific cell
    POST /api/traffic/smart-route/  → Smart optimized route with nav deep links
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from ..services.traffic_service import TrafficService
from ..services.smart_routing import SmartRoutingService

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def traffic_heatmap(request):
    """
    Get traffic heatmap data.
    
    Returns a list of grid cells with their traffic levels.
    
    Query Parameters:
        min_lat (float): Minimum latitude for bounding box filter
        max_lat (float): Maximum latitude for bounding box filter
        min_lng (float): Minimum longitude for bounding box filter
        max_lng (float): Maximum longitude for bounding box filter
    
    Response:
    {
        "cells": [
            {
                "cell_id": "cell_50_80",
                "lat": 4.0409,
                "lng": 9.744,
                "avg_speed": 18.5,
                "level": "MODERE",
                "color": "#FF9800",
                "samples": 5,
                "updated": "2026-02-08T22:00:00"
            },
            ...
        ],
        "count": 42,
        "legend": {
            "FLUIDE": {"color": "#4CAF50", "min_speed": 25, "label": "Fluide"},
            "MODERE": {"color": "#FF9800", "min_speed": 15, "label": "Modéré"},
            "DENSE":  {"color": "#F44336", "min_speed": 5,  "label": "Dense"},
            "BLOQUE": {"color": "#880E4F", "min_speed": 0,  "label": "Bloqué"}
        }
    }
    """
    try:
        min_lat = _parse_float(request.query_params.get('min_lat'))
        max_lat = _parse_float(request.query_params.get('max_lat'))
        min_lng = _parse_float(request.query_params.get('min_lng'))
        max_lng = _parse_float(request.query_params.get('max_lng'))
        
        cells = TrafficService.get_traffic_heatmap(
            min_lat=min_lat, max_lat=max_lat,
            min_lng=min_lng, max_lng=max_lng
        )
        
        return Response({
            'cells': cells,
            'count': len(cells),
            'legend': {
                'FLUIDE': {'color': '#4CAF50', 'min_speed': 25, 'label': 'Fluide'},
                'MODERE': {'color': '#FF9800', 'min_speed': 15, 'label': 'Modéré'},
                'DENSE':  {'color': '#F44336', 'min_speed': 5,  'label': 'Dense'},
                'BLOQUE': {'color': '#880E4F', 'min_speed': 0,  'label': 'Bloqué'},
            }
        })
    except Exception as e:
        logger.error(f"[TRAFFIC API] Heatmap error: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération des données trafic'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def traffic_stats(request):
    """
    Get city-wide traffic statistics.
    
    Response:
    {
        "active_cells": 42,
        "online_couriers": 12,
        "avg_city_speed_kmh": 22.5,
        "overall_level": "MODERE",
        "cells_by_level": {
            "FLUIDE": 20,
            "MODERE": 15,
            "DENSE": 5,
            "BLOQUE": 2
        }
    }
    """
    try:
        stats = TrafficService.get_traffic_stats()
        return Response(stats)
    except Exception as e:
        logger.error(f"[TRAFFIC API] Stats error: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération des statistiques trafic'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def traffic_route(request):
    """
    Get traffic data along a specific route.
    
    Useful for coloring a route polyline with traffic levels.
    
    Request body:
    {
        "waypoints": [
            [4.0500, 9.7000],
            [4.0510, 9.7010],
            ...
        ]
    }
    
    Response:
    {
        "segments": [
            {
                "cell_id": "cell_50_80",
                "lat": 4.0409,
                "lng": 9.744,
                "avg_speed_kmh": 18.5,
                "level": "MODERE",
                "sample_count": 5
            },
            ...
        ]
    }
    """
    try:
        waypoints = request.data.get('waypoints', [])
        
        if not waypoints:
            return Response(
                {'error': 'Au moins un waypoint requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate waypoints format
        validated = []
        for wp in waypoints:
            if isinstance(wp, (list, tuple)) and len(wp) == 2:
                try:
                    validated.append((float(wp[0]), float(wp[1])))
                except (ValueError, TypeError):
                    continue
        
        if not validated:
            return Response(
                {'error': 'Format de waypoints invalide. Utiliser [[lat, lng], ...]'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        segments = TrafficService.get_route_traffic(validated)
        
        return Response({
            'segments': segments,
            'count': len(segments),
        })
    except Exception as e:
        logger.error(f"[TRAFFIC API] Route error: {e}")
        return Response(
            {'error': 'Erreur lors de l\'analyse du trafic sur route'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def traffic_cell_detail(request, cell_id):
    """
    Get detailed traffic data for a specific cell.
    
    Response:
    {
        "cell_id": "cell_50_80",
        "lat": 4.0409,
        "lng": 9.744,
        "avg_speed_kmh": 18.5,
        "level": "MODERE",
        "sample_count": 5,
        "last_updated": "2026-02-08T22:00:00"
    }
    """
    try:
        cell = TrafficService.get_cell_traffic(cell_id)
        
        if not cell:
            return Response(
                {'error': 'Aucune donnée pour cette cellule', 'cell_id': cell_id},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(cell.to_dict())
    except Exception as e:
        logger.error(f"[TRAFFIC API] Cell detail error: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération des données cellule'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _parse_float(value):
    """Parse a string to float, return None if invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ============================================
# SMART ROUTE
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def smart_route(request):
    """
    POST /api/traffic/smart-route/
    
    Calculate the best route considering real-time traffic and events.
    Returns optimized waypoints + deep links for Google Maps / Waze.
    
    Request body:
        {
            "origin": [4.0480, 9.6920],        # [lat, lng]
            "destination": [4.0350, 9.7100],   # [lat, lng]
        }
    
    Response:
        {
            "coordinates": [[lat, lng], ...],
            "waypoints": [[lat, lng], ...],
            "distance_km": 5.2,
            "base_eta_minutes": 12.5,
            "smart_eta_minutes": 18.2,
            "traffic_score": 35.0,
            "warnings": [...],
            "alternatives": [...],
            "navigation": {
                "google_maps": "https://...",
                "waze": "https://...",
                "apple_maps": "https://..."
            }
        }
    """
    data = request.data
    origin = data.get('origin')
    destination = data.get('destination')
    
    # Validate inputs
    if not origin or not destination:
        return Response(
            {'error': 'origin et destination requis ([lat, lng])'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        origin_lat = float(origin[0])
        origin_lng = float(origin[1])
        dest_lat = float(destination[0])
        dest_lng = float(destination[1])
    except (IndexError, TypeError, ValueError):
        return Response(
            {'error': 'Format invalide. Attendu: [lat, lng]'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        route = SmartRoutingService.get_smart_route(
            origin_lat, origin_lng,
            dest_lat, dest_lng,
        )
        
        if not route:
            return Response(
                {'error': 'Impossible de calculer un itinéraire'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        result = route.to_dict()
        
        # Restructure nav links for cleaner API
        result['navigation'] = {
            'google_maps': result.pop('google_maps_url'),
            'waze': result.pop('waze_url'),
            'apple_maps': result.pop('apple_maps_url'),
        }
        
        logger.info(
            f"[SMART-ROUTE] {origin_lat:.4f},{origin_lng:.4f} → "
            f"{dest_lat:.4f},{dest_lng:.4f} | "
            f"{route.distance_km}km | "
            f"ETA: {route.base_eta_minutes}→{route.smart_eta_minutes}min | "
            f"Score: {route.traffic_score} | "
            f"Warnings: {len(route.warnings)}"
        )
        
        return Response(result)
        
    except Exception as e:
        logger.exception(f"[SMART-ROUTE] Error: {e}")
        return Response(
            {'error': 'Erreur lors du calcul de l\'itinéraire'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

