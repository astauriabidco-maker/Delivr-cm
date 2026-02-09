import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../providers/traffic_provider.dart';

/// Traffic heatmap overlay for flutter_map
///
/// Displays colored rectangles on the map representing traffic
/// conditions in each grid cell (~200m x 200m).
///
/// Usage:
/// ```dart
/// FlutterMap(
///   children: [
///     TileLayer(...),
///     TrafficHeatmapLayer(),
///     MarkerLayer(...),
///   ],
/// )
/// ```
class TrafficHeatmapLayer extends ConsumerStatefulWidget {
  /// Whether to show the traffic legend
  final bool showLegend;
  
  /// Whether to show the traffic stats bar
  final bool showStats;

  const TrafficHeatmapLayer({
    super.key,
    this.showLegend = true,
    this.showStats = true,
  });

  @override
  ConsumerState<TrafficHeatmapLayer> createState() =>
      _TrafficHeatmapLayerState();
}

class _TrafficHeatmapLayerState extends ConsumerState<TrafficHeatmapLayer> {
  bool _isVisible = true;

  @override
  void initState() {
    super.initState();
    // Start auto-refresh when widget is created
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(trafficHeatmapProvider.notifier).startAutoRefresh();
      ref.read(trafficHeatmapProvider.notifier).fetchStats();
    });
  }

  @override
  void dispose() {
    super.dispose();
  }

  /// Size of each cell in degrees (~200m)
  static const double cellSize = 0.0018;

  @override
  Widget build(BuildContext context) {
    final trafficState = ref.watch(trafficHeatmapProvider);

    return Stack(
      children: [
        // Heatmap rectangles
        if (_isVisible && trafficState.cells.isNotEmpty)
          PolygonLayer(
            polygons: trafficState.cells.map((cell) {
              final halfCell = cellSize / 2;
              return Polygon(
                points: [
                  LatLng(cell.lat - halfCell, cell.lng - halfCell),
                  LatLng(cell.lat - halfCell, cell.lng + halfCell),
                  LatLng(cell.lat + halfCell, cell.lng + halfCell),
                  LatLng(cell.lat + halfCell, cell.lng - halfCell),
                ],
                color: Color(cell.level.colorValue)
                    .withValues(alpha: cell.level.opacity),
                borderColor: Color(cell.level.colorValue).withValues(alpha: 0.3),
                borderStrokeWidth: 0.5,
              );
            }).toList(),
          ),

        // Toggle button + Legend + Stats
        Positioned(
          top: 8,
          right: 8,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              // Toggle traffic visibility
              _buildToggleButton(trafficState),

              if (_isVisible && widget.showStats && trafficState.stats != null)
                _buildStatsBar(trafficState.stats!),

              if (_isVisible && widget.showLegend)
                _buildLegend(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildToggleButton(TrafficHeatmapState state) {
    return Material(
      elevation: 2,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => setState(() => _isVisible = !_isVisible),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: _isVisible
                ? Colors.blue.shade700
                : Colors.grey.shade100,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.traffic,
                size: 16,
                color: _isVisible ? Colors.white : Colors.grey.shade600,
              ),
              const SizedBox(width: 4),
              Text(
                'Trafic',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: _isVisible ? Colors.white : Colors.grey.shade600,
                ),
              ),
              if (state.isLoading) ...[
                const SizedBox(width: 4),
                SizedBox(
                  width: 10,
                  height: 10,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: _isVisible ? Colors.white : Colors.grey,
                  ),
                ),
              ],
              if (!state.isLoading && state.cells.isNotEmpty) ...[
                const SizedBox(width: 4),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: _isVisible
                        ? Colors.white.withValues(alpha: 0.2)
                        : Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${state.cells.length}',
                    style: TextStyle(
                      fontSize: 10,
                      color: _isVisible ? Colors.white : Colors.grey.shade600,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatsBar(TrafficStats stats) {
    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            stats.overallLevel.emoji,
            style: const TextStyle(fontSize: 14),
          ),
          const SizedBox(width: 4),
          Text(
            '${stats.avgCitySpeed.toStringAsFixed(0)} km/h',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: Color(stats.overallLevel.colorValue),
            ),
          ),
          const SizedBox(width: 8),
          Icon(Icons.people, size: 12, color: Colors.grey.shade600),
          const SizedBox(width: 2),
          Text(
            '${stats.onlineCouriers}',
            style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }

  Widget _buildLegend() {
    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _legendItem(TrafficLevel.fluide),
          _legendItem(TrafficLevel.modere),
          _legendItem(TrafficLevel.dense),
          _legendItem(TrafficLevel.bloque),
        ],
      ),
    );
  }

  Widget _legendItem(TrafficLevel level) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: Color(level.colorValue).withValues(alpha: level.opacity),
              border: Border.all(
                color: Color(level.colorValue),
                width: 0.5,
              ),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 4),
          Text(
            level.label,
            style: TextStyle(fontSize: 10, color: Colors.grey.shade700),
          ),
        ],
      ),
    );
  }
}
