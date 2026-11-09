import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_news_client/models/card_model.dart';
import 'package:ai_news_client/widgets/paper_chat_sheet.dart';

void main() {
  final testCard = NewsCard(
    id: 42,
    category: 'research',
    headline: 'Attention Is All You Need',
    summary60s: '• Introduces the Transformer architecture.\n• Dispenses with recurrence and convolutions.',
    tags: const ['transformers', 'nlp'],
    candidateTechniques: const ['self-attention'],
    deepDiveBase: 'The Transformer replaces recurrent layers with multi-head attention.',
    sourceUrl: 'https://arxiv.org/abs/1706.03762',
    publishedAt: DateTime.now(),
    needsReview: false,
  );

  testWidgets('PaperChatSheet renders header, suggestions, and input bar',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PaperChatSheet(card: testCard),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify header and RAG tag
    expect(find.text('PAPER CHAT'), findsOneWidget);
    expect(find.text('GROUNDED RAG'), findsOneWidget);
    expect(find.text('Attention Is All You Need'), findsOneWidget);

    // Verify empty state suggestions
    expect(find.text('SUGGESTED QUESTIONS'), findsOneWidget);
    expect(find.text('What is the core contribution?'), findsOneWidget);

    // Verify input field and counter
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('2000 / 2000 chars'), findsOneWidget);
  });

  testWidgets('PaperChatSheet sending question adds messages and shows citation chips',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PaperChatSheet(card: testCard),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Enter a question in the text field
    final textField = find.byType(TextField);
    await tester.enterText(textField, 'What is the core contribution of this work?');
    await tester.pump();

    // Verify counter updated
    expect(find.textContaining('/ 2000 chars'), findsOneWidget);

    // Tap send button
    final sendButton = find.byIcon(Icons.send_rounded);
    await tester.tap(sendButton);
    await tester.pumpAndSettle();

    // Verify user message appears in list
    expect(find.text('What is the core contribution of this work?'), findsOneWidget);

    // Verify assistant answer appears
    expect(find.textContaining('The core contribution'), findsOneWidget);

    // Verify citation chips are rendered
    expect(find.text('Excerpt 1'), findsOneWidget);

    // Tap on the citation chip to open modal
    await tester.tap(find.text('Excerpt 1'));
    await tester.pumpAndSettle();

    // Verify citation dialog content
    expect(find.text('Verified Paper Citation'), findsOneWidget);
    expect(find.textContaining('VERBATIM EXCERPT'), findsOneWidget);
    expect(find.textContaining('Deterministic non-LLM match'), findsOneWidget);

    // Close dialog
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();
    expect(find.text('Verified Paper Citation'), findsNothing);
  });
}

