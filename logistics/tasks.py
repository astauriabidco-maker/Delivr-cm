"""
LOGISTICS App - Celery Tasks

Periodic tasks for traffic data management and other logistics operations.
"""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(name='logistics.tasks.cleanup_traffic_data')
def cleanup_traffic_data():
    """
    Clean up stale traffic observations.
    
    Runs every 5 minutes to remove expired speed observations
    and refresh the aggregated heatmap cache.
    """
    try:
        from logistics.services.traffic_service import TrafficService
        cleaned = TrafficService.cleanup_stale_data()
        logger.info(f"[TRAFFIC TASK] Cleaned {cleaned} stale observations")
        return cleaned
    except Exception as e:
        logger.error(f"[TRAFFIC TASK] Cleanup failed: {e}")
        return 0


@shared_task(name='logistics.tasks.aggregate_traffic_heatmap')
def aggregate_traffic_heatmap():
    """
    Force-refresh the traffic heatmap cache.
    
    Runs every 2 minutes to ensure the heatmap API
    serves fresh data.
    """
    try:
        from logistics.services.traffic_service import TrafficService
        cells = TrafficService.get_traffic_heatmap()
        stats = TrafficService.get_traffic_stats()
        logger.info(
            f"[TRAFFIC TASK] Heatmap refreshed: {len(cells)} cells, "
            f"avg speed: {stats.get('avg_city_speed_kmh', 0)} km/h"
        )
        return {
            'cells': len(cells),
            'avg_speed': stats.get('avg_city_speed_kmh', 0),
            'level': stats.get('overall_level', 'UNKNOWN'),
        }
    except Exception as e:
        logger.error(f"[TRAFFIC TASK] Heatmap refresh failed: {e}")
        return {}
