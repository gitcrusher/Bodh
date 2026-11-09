// learning_service.dart — Flutter API client for /api/v1/learning/ (Step 2)
//
// Provides typed methods for topics, learner profile, quiz sessions,
// and level-adaptive deep-dive. Falls back to offline mock data when the
// server is unreachable so the UI always renders.

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'app_config.dart';

// ---------------------------------------------------------------------------
// Data models
// ---------------------------------------------------------------------------

class QuizTopic {
  final int id;
  final String slug;
  final String displayName;
  final String description;

  const QuizTopic({
    required this.id,
    required this.slug,
    required this.displayName,
    this.description = '',
  });

  factory QuizTopic.fromJson(Map<String, dynamic> j) => QuizTopic(
        id: j['id'] as int,
        slug: j['slug'] as String,
        displayName: j['display_name'] as String,
        description: j['description'] as String? ?? '',
      );
}

class QuizQuestion {
  final int id;
  final String stem;
  final List<String> optionsRandomised;
  final List<int> optionOrder; // display → original index mapping
  final String difficulty;

  const QuizQuestion({
    required this.id,
    required this.stem,
    required this.optionsRandomised,
    required this.optionOrder,
    required this.difficulty,
  });

  factory QuizQuestion.fromJson(Map<String, dynamic> j) => QuizQuestion(
        id: j['id'] as int,
        stem: j['stem'] as String,
        optionsRandomised:
            (j['options_randomised'] as List<dynamic>).cast<String>(),
        optionOrder:
            (j['option_order'] as List<dynamic>).cast<int>(),
        difficulty: j['difficulty'] as String? ?? 'medium',
      );
}

class QuizSession {
  final int id;
  final String topicSlug;
  final String topicName;
  final String state;
  final int currentIndex;
  final int totalQuestions;
  final int progressPct;
  final double? finalScore;
  final String? assignedLevel;
  final QuizQuestion? currentQuestion;

  const QuizSession({
    required this.id,
    required this.topicSlug,
    required this.topicName,
    required this.state,
    required this.currentIndex,
    required this.totalQuestions,
    required this.progressPct,
    this.finalScore,
    this.assignedLevel,
    this.currentQuestion,
  });

  factory QuizSession.fromJson(Map<String, dynamic> j) {
    final qJson = j['current_question'] as Map<String, dynamic>?;
    return QuizSession(
      id: j['id'] as int,
      topicSlug: j['topic_slug'] as String,
      topicName: j['topic_name'] as String,
      state: j['state'] as String,
      currentIndex: j['current_index'] as int,
      totalQuestions: j['total_questions'] as int,
      progressPct: j['progress_pct'] as int,
      finalScore: (j['final_score'] as num?)?.toDouble(),
      assignedLevel: j['assigned_level'] as String?,
      currentQuestion:
          qJson != null ? QuizQuestion.fromJson(qJson) : null,
    );
  }

  bool get isCompleted => state == 'completed';
}

class AnswerResult {
  final bool isCorrect;
  final int correctIndex;
  final String explanation;
  final bool sessionEnded;
  final QuizQuestion? nextQuestion;
  final QuizSession? session;
  final double currentAccuracy;

  const AnswerResult({
    required this.isCorrect,
    required this.correctIndex,
    required this.explanation,
    required this.sessionEnded,
    required this.currentAccuracy,
    this.nextQuestion,
    this.session,
  });

  factory AnswerResult.fromJson(Map<String, dynamic> j) {
    final nqJson = j['next_question'] as Map<String, dynamic>?;
    final sessionJson = j['session'] as Map<String, dynamic>?;
    return AnswerResult(
      isCorrect: j['is_correct'] as bool,
      correctIndex: j['correct_index'] as int,
      explanation: j['explanation'] as String? ?? '',
      sessionEnded: j['session_ended'] as bool,
      currentAccuracy: (j['current_accuracy'] as num?)?.toDouble() ?? 0.0,
      nextQuestion:
          nqJson != null ? QuizQuestion.fromJson(nqJson) : null,
      session:
          sessionJson != null ? QuizSession.fromJson(sessionJson) : null,
    );
  }
}

class LearnerProfile {
  final int id;
  final String topicSlug;
  final String topicName;
  final String level;
  final double? lastQuizScore;
  final double? accuracy;
  final int streakDays;

  const LearnerProfile({
    required this.id,
    required this.topicSlug,
    required this.topicName,
    required this.level,
    this.lastQuizScore,
    this.accuracy,
    this.streakDays = 0,
  });

  factory LearnerProfile.fromJson(Map<String, dynamic> j) => LearnerProfile(
        id: j['id'] as int,
        topicSlug: j['topic_slug'] as String,
        topicName: j['topic_name'] as String,
        level: j['level'] as String,
        lastQuizScore: (j['last_quiz_score'] as num?)?.toDouble(),
        accuracy: (j['accuracy'] as num?)?.toDouble(),
        streakDays: j['streak_days'] as int? ?? 0,
      );

  String get levelLabel {
    switch (level) {
      case 'fluent':
        return 'Fluent';
      case 'familiar':
        return 'Familiar';
      default:
        return 'New';
    }
  }

  double get levelProgress {
    switch (level) {
      case 'fluent':
        return 1.0;
      case 'familiar':
        return 0.6;
      default:
        return 0.2;
    }
  }
}

class DeepDiveResult {
  final String level;
  final String paperExplanation;
  final String backgroundContext;
  final String keyTakeaway;
  final bool fromCache;

  const DeepDiveResult({
    required this.level,
    required this.paperExplanation,
    required this.backgroundContext,
    required this.keyTakeaway,
    required this.fromCache,
  });

  factory DeepDiveResult.fromJson(Map<String, dynamic> j) => DeepDiveResult(
        level: j['level'] as String,
        paperExplanation: j['paper_explanation'] as String,
        backgroundContext: j['background_context'] as String,
        keyTakeaway: j['key_takeaway'] as String,
        fromCache: j['from_cache'] as bool? ?? false,
      );
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

class LearningService {
  final String baseUrl;

  // Shared auth token — set after login. For now uses Django session or
  // anonymous (endpoints require auth; mock fallback handles offline).
  String? _authToken;

  LearningService({String? baseUrl}) : baseUrl = baseUrl ?? AppConfig.learningBaseUrl;

  void setAuthToken(String token) => _authToken = token;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_authToken != null) 'Authorization': 'Token $_authToken',
      };

  // ── Topics ──────────────────────────────────────────────────────────────

  Future<List<QuizTopic>> fetchTopics() async {
    try {
      final resp = await http
          .get(Uri.parse('$baseUrl/topics/'), headers: _headers)
          .timeout(const Duration(seconds: 4));
      if (resp.statusCode == 200) {
        final list = json.decode(utf8.decode(resp.bodyBytes)) as List<dynamic>;
        return list
            .map((e) => QuizTopic.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {}
    return _mockTopics;
  }

  // ── Learner profiles ─────────────────────────────────────────────────────

  Future<List<LearnerProfile>> fetchProfile() async {
    try {
      final resp = await http
          .get(Uri.parse('$baseUrl/profile/'), headers: _headers)
          .timeout(const Duration(seconds: 4));
      if (resp.statusCode == 200) {
        final list = json.decode(utf8.decode(resp.bodyBytes)) as List<dynamic>;
        return list
            .map((e) => LearnerProfile.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {}
    return [];
  }

  // ── Quiz session ─────────────────────────────────────────────────────────

  Future<QuizSession?> startQuiz(String topicSlug) async {
    try {
      final resp = await http
          .post(
            Uri.parse('$baseUrl/quiz/start/'),
            headers: _headers,
            body: json.encode({'topic_slug': topicSlug}),
          )
          .timeout(const Duration(seconds: 6));
      if (resp.statusCode == 201) {
        return QuizSession.fromJson(
            json.decode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>);
      }
    } catch (_) {}
    return _mockSession(topicSlug);
  }

  Future<AnswerResult?> submitAnswer({
    required int sessionId,
    required int questionId,
    required int chosenDisplayIndex,
    required List<int> optionOrder,
  }) async {
    try {
      final resp = await http
          .post(
            Uri.parse('$baseUrl/quiz/$sessionId/answer/'),
            headers: _headers,
            body: json.encode({
              'question_id': questionId,
              'chosen_display_index': chosenDisplayIndex,
              'option_order': optionOrder,
            }),
          )
          .timeout(const Duration(seconds: 6));
      if (resp.statusCode == 200) {
        return AnswerResult.fromJson(
            json.decode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>);
      }
    } catch (_) {}
    return null;
  }

  Future<QuizSession?> swapQuestions(int sessionId) async {
    try {
      final resp = await http
          .post(Uri.parse('$baseUrl/quiz/$sessionId/swap/'), headers: _headers)
          .timeout(const Duration(seconds: 6));
      if (resp.statusCode == 200) {
        return QuizSession.fromJson(
            json.decode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>);
      }
    } catch (_) {}
    return null;
  }

  // ── Deep-dive ────────────────────────────────────────────────────────────

  Future<DeepDiveResult?> fetchDeepDive({
    required int cardId,
    required String topicSlug,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/deep-dive/$cardId/').replace(
          queryParameters: {'topic': topicSlug});
      final resp = await http
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 10));
      if (resp.statusCode == 200) {
        return DeepDiveResult.fromJson(
            json.decode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>);
      }
    } catch (_) {}
    return null;
  }

  // ── Offline mock data ────────────────────────────────────────────────────

  static final List<QuizTopic> _mockTopics = [
    const QuizTopic(
        id: 1,
        slug: 'transformers',
        displayName: 'Transformer Architecture',
        description: 'Self-attention, multi-head attention, positional encoding.'),
    const QuizTopic(
        id: 2,
        slug: 'diffusion_models',
        displayName: 'Diffusion Models',
        description: 'Denoising diffusion, DDPMs, DDIMs, classifier-free guidance.'),
    const QuizTopic(
        id: 3,
        slug: 'rag',
        displayName: 'Retrieval-Augmented Generation',
        description: 'Dense retrieval, RAG pipelines, citation grounding.'),
    const QuizTopic(
        id: 4,
        slug: 'fine_tuning',
        displayName: 'Fine-Tuning & Alignment',
        description: 'LoRA, RLHF, DPO, instruction tuning.'),
  ];

  static QuizSession _mockSession(String topicSlug) => QuizSession(
        id: 0,
        topicSlug: topicSlug,
        topicName: 'Mock Topic',
        state: 'active',
        currentIndex: 0,
        totalQuestions: 4,
        progressPct: 0,
        currentQuestion: const QuizQuestion(
          id: 1,
          stem:
              'What is the primary role of the attention mechanism in a Transformer?',
          optionsRandomised: [
            'To apply convolutions across the sequence',
            'To allow the model to focus on relevant parts of the input',
            'To compress the input into a fixed-size vector',
            'To enforce positional ordering by masking future tokens',
          ],
          optionOrder: [2, 1, 0, 3],
          difficulty: 'easy',
        ),
      );
}
