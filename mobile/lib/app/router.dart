import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/auth_provider.dart';
import '../features/auth/screens/splash_screen.dart';
import '../features/auth/screens/login_screen.dart';
import '../features/auth/screens/activation_screen.dart';
import '../features/dashboard/screens/dashboard_screen.dart';
import '../features/deliveries/screens/deliveries_screen.dart';
import '../features/deliveries/screens/delivery_detail_screen.dart';
import '../features/deliveries/screens/active_deliveries_screen.dart';
import '../features/deliveries/screens/pickup_screen.dart';
import '../features/deliveries/screens/dropoff_screen.dart';
import '../features/deliveries/screens/history_screen.dart';
import '../features/wallet/screens/wallet_screen.dart';
import '../features/earnings/screens/earnings_screen.dart';
import '../features/gamification/screens/badges_screen.dart';
import '../features/gamification/screens/leaderboard_screen.dart';
import '../features/profile/screens/profile_screen.dart';
import '../features/support/screens/support_screen.dart';
import '../shared/widgets/main_shell.dart';

/// Route names for navigation
class AppRoutes {
  static const splash = '/';
  static const login = '/login';
  static const activation = '/activation';
  static const dashboard = '/dashboard';
  static const deliveries = '/deliveries';
  static const deliveryDetail = '/deliveries/:id';
  static const pickup = '/deliveries/:id/pickup';
  static const dropoff = '/deliveries/:id/dropoff';
  static const history = '/history';
  static const wallet = '/wallet';
  static const earnings = '/earnings';
  static const badges = '/badges';
  static const leaderboard = '/leaderboard';
  static const profile = '/profile';
  static const support = '/support';
  static const activeDeliveries = '/deliveries/active';
}

/// GoRouter configuration provider
final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authStateProvider);
  
  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: true,
    redirect: (context, state) {
      final isAuthenticated = authState.isAuthenticated;
      final isLoading = authState.isLoading;
      final currentPath = state.matchedLocation;
      
      // Don't redirect while loading
      if (isLoading) return null;
      
      // Auth routes
      final authRoutes = [
        AppRoutes.splash,
        AppRoutes.login,
        AppRoutes.activation,
      ];
      final isAuthRoute = authRoutes.contains(currentPath);
      
      // If not authenticated and trying to access protected route
      if (!isAuthenticated && !isAuthRoute) {
        return AppRoutes.login;
      }
      
      // If authenticated and on auth route, go to dashboard
      if (isAuthenticated && isAuthRoute) {
        return AppRoutes.dashboard;
      }
      
      return null;
    },
    routes: [
      // Splash screen
      GoRoute(
        path: AppRoutes.splash,
        builder: (context, state) => const SplashScreen(),
      ),
      
      // Auth routes
      GoRoute(
        path: AppRoutes.login,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.activation,
        builder: (context, state) => const ActivationScreen(),
      ),
      
      // Main app shell with bottom navigation
      ShellRoute(
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.dashboard,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: DashboardScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.deliveries,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: DeliveriesScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.wallet,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: WalletScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.profile,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: ProfileScreen(),
            ),
          ),
        ],
      ),
      
      // Detail routes (outside shell)
      // Active deliveries must come BEFORE :id to avoid being matched as an id
      GoRoute(
        path: AppRoutes.activeDeliveries,
        builder: (context, state) => const ActiveDeliveriesScreen(),
      ),
      GoRoute(
        path: AppRoutes.deliveryDetail,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          return DeliveryDetailScreen(deliveryId: id);
        },
      ),
      GoRoute(
        path: AppRoutes.pickup,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          return PickupScreen(deliveryId: id);
        },
      ),
      GoRoute(
        path: AppRoutes.dropoff,
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          return DropoffScreen(deliveryId: id);
        },
      ),
      GoRoute(
        path: AppRoutes.earnings,
        builder: (context, state) => const EarningsScreen(),
      ),
      GoRoute(
        path: AppRoutes.badges,
        builder: (context, state) => const BadgesScreen(),
      ),
      GoRoute(
        path: AppRoutes.leaderboard,
        builder: (context, state) => const LeaderboardScreen(),
      ),
      GoRoute(
        path: AppRoutes.history,
        builder: (context, state) => const HistoryScreen(),
      ),
      GoRoute(
        path: AppRoutes.support,
        builder: (context, state) => const SupportScreen(),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Text('Page non trouvée: ${state.error}'),
      ),
    ),
  );
});
