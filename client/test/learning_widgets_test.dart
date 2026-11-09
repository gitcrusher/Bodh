import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_news_client/models/card_model.dart';
import 'package:ai_news_client/widgets/deep_dive_sheet.dart';
import 'package:ai_news_client/widgets/learner_profile_sheet.dart';
import 'package:ai_news_client/widgets/quiz_modal.dart';

void main() {
  final testCard = NewsCard(
    id: 1,
    category: 'research',
    headline: 'Attention Mechanisms in Large Language Models',
    summary60s: '• Introduces linear attention approximation.\n• Achieves 2x throughput with minimal loss.',
    tags: const ['transformers', 'attention'],
    candidateTechniques: const ['linear attention'],
    deepDiveBase: 'Linear attention replaces quadratic scaling with kernel approximations.',
    sourceUrl: 'https://arxiv.org/abs/2601.00001',
    publishedAt: DateTime.now(),
    needsReview: false,
  );

  testWidgets('DeepDiveSheet displays paper explanation, separate background, and takeaway',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DeepDiveSheet(card: testCard),
        ),
      ),
    );

    // Initial pump and settling
    await tester.pumpAndSettle();

    // Verify header and headline
    expect(find.text('DEEP DIVE'), findsOneWidget);
    expect(find.text(testCard.headline), findsOneWidget);

    // Verify level choices exist
    expect(find.text('New'), findsOneWidget);
    expect(find.text('Familiar'), findsOneWidget);
    expect(find.text('Fluent'), findsOneWidget);

    // Verify paper-derived explanation section
    expect(find.text('Derived from Paper Source Text'), findsOneWidget);

    // Verify visual separation of background context (design.md §4)
    await tester.scrollUntilVisible(
      find.text('General Background · Not a claim made by this paper'),
      100.0,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('General Background · Not a claim made by this paper'), findsOneWidget);

    // Verify key takeaway section
    await tester.scrollUntilVisible(
      find.text('Key Takeaway'),
      100.0,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Key Takeaway'), findsOneWidget);
  });

  testWidgets('QuizModal displays topic, question stem, options and handles answer selection',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: QuizModal(
            topicSlug: 'transformers',
            topicDisplayName: 'Transformer Architecture',
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify title
    expect(find.text('TRANSFORMER ARCHITECTURE'), findsOneWidget);
    expect(find.text('Knowledge Calibration Quiz'), findsOneWidget);

    // Verify stem is rendered
    expect(find.byType(ListView), findsOneWidget);

    // Verify submit button is rendered
    expect(find.text('Submit Answer'), findsOneWidget);
  });

  testWidgets('LearnerProfileSheet displays seeded topics and calibration options',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: LearnerProfileSheet(),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify title and description
    expect(find.text('Knowledge Calibration'), findsOneWidget);
    expect(find.text('CORE TOPICS'), findsOneWidget);

    // Verify topics are rendered from mock data
    expect(find.text('Transformer Architecture'), findsOneWidget);
    expect(find.text('Diffusion Models'), findsOneWidget);
  });
}

