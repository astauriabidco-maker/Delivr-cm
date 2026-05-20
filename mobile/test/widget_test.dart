// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package.

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:delivr_courier/app/app.dart';
import 'package:delivr_courier/core/auth/auth_provider.dart';

void main() {
  testWidgets('App loads successfully', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authStateProvider.overrideWith(
            (ref) => AuthStateNotifier(
              ref,
              initialState: const AuthState(
                isAuthenticated: false,
                isLoading: false,
              ),
              checkOnInit: false,
            ),
          ),
        ],
        child: const DelivrCourierApp(),
      ),
    );

    // Verify that the app renders
    expect(find.byType(DelivrCourierApp), findsOneWidget);
  });
}
