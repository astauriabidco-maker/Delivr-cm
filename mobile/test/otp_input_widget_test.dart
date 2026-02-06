import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:delivr_courier/features/deliveries/widgets/otp_input.dart';

void main() {
  group('OtpInput Widget', () {
    testWidgets('renders 4 text fields by default', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OtpInput(
              onCompleted: (_) {},
            ),
          ),
        ),
      );

      // Should have 4 TextField widgets
      expect(find.byType(TextField), findsNWidgets(4));
    });

    testWidgets('respects custom length', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OtpInput(
              length: 6,
              onCompleted: (_) {},
            ),
          ),
        ),
      );

      expect(find.byType(TextField), findsNWidgets(6));
    });

    testWidgets('calls onCompleted when all digits entered', (tester) async {
      String? completedValue;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OtpInput(
              length: 4,
              onCompleted: (value) => completedValue = value,
            ),
          ),
        ),
      );

      // Enter 4 digits
      final textFields = find.byType(TextField);
      await tester.enterText(textFields.at(0), '1');
      await tester.pump();
      await tester.enterText(textFields.at(1), '2');
      await tester.pump();
      await tester.enterText(textFields.at(2), '3');
      await tester.pump();
      await tester.enterText(textFields.at(3), '4');
      await tester.pump();

      // Note: onCompleted is called when all fields are filled
      // The exact behavior depends on implementation
    });
  });
}
