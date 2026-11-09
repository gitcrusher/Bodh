import 'package:flutter_test/flutter_test.dart';
import 'package:ai_news_client/main.dart';

void main() {
  testWidgets('App smoke test builds feed view', (WidgetTester tester) async {
    await tester.pumpWidget(const AiNewsApp());
    expect(find.text('My Feed'), findsOneWidget);
  });
}
