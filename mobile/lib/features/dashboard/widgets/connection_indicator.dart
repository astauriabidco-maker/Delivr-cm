import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';
import '../../../core/websocket/websocket_service.dart';

/// Widget showing WebSocket connection status
class ConnectionIndicator extends ConsumerWidget {
  const ConnectionIndicator({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wsState = ref.watch(wsStateProvider);
    
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: _getBackgroundColor(wsState),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildIndicator(wsState),
          const SizedBox(width: 6),
          Text(
            _getStatusText(wsState),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: _getTextColor(wsState),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIndicator(WebSocketState state) {
    if (state == WebSocketState.connecting || 
        state == WebSocketState.reconnecting) {
      return SizedBox(
        width: 10,
        height: 10,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation(_getTextColor(state)),
        ),
      );
    }
    
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _getIndicatorColor(state),
      ),
    );
  }

  Color _getIndicatorColor(WebSocketState state) {
    switch (state) {
      case WebSocketState.connected:
        return DelivrColors.online;
      case WebSocketState.disconnected:
        return DelivrColors.offline;
      case WebSocketState.error:
        return DelivrColors.error;
      default:
        return DelivrColors.warning;
    }
  }

  Color _getBackgroundColor(WebSocketState state) {
    switch (state) {
      case WebSocketState.connected:
        return DelivrColors.successLight;
      case WebSocketState.error:
        return DelivrColors.errorLight;
      default:
        return Colors.grey.shade200;
    }
  }

  Color _getTextColor(WebSocketState state) {
    switch (state) {
      case WebSocketState.connected:
        return DelivrColors.success;
      case WebSocketState.error:
        return DelivrColors.error;
      default:
        return DelivrColors.textSecondary;
    }
  }

  String _getStatusText(WebSocketState state) {
    switch (state) {
      case WebSocketState.connected:
        return 'Connecté';
      case WebSocketState.connecting:
        return 'Connexion...';
      case WebSocketState.reconnecting:
        return 'Reconnexion...';
      case WebSocketState.disconnected:
        return 'Déconnecté';
      case WebSocketState.error:
        return 'Erreur';
    }
  }
}
