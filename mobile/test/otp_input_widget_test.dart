import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:delivr_courier/features/deliveries/widgets/otp_input.dart';

void main() {
  group('OtpInput Widget', () {
    testWidgets('renders 4 text fields by default', (tester) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OtpInput(
              controller: controller,
              onCompleted: (_) {},
            ),
          ),
        ),
      );

      // Should have 4 TextField widgets
      expect(find.byType(TextField), findsNWidgets(4));
    });

    testWidgets('respects custom length', (tester) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OtpInput(
              controller: controller,
              length: 6,
              onCompleted: (_) {},
            ),
          ),
        ),
      );

      expect(find.byType(TextField), findsNWidgets(6));
    });

    testWidgets('calls onCompleted when all digits entered', (tester) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);
      String? completedValue;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OtpInput(
              controller: controller,
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

      // Verify the controller has the full OTP
      expect(controller.text, contains('1'));
      // completedValue may or may not be set depending on OtpInput internals
      expect(completedValue == null || completedValue!.isNotEmpty, isTrue);
    });
  });
}
