import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/card_model.dart';
import 'app_config.dart';

/// Manages User Authentication and Rule 65 (OKF) 15-day comprehension cycle.
class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  String? _token;
  String? _username;
  int? _userId;

  String? get token => _token;
  String? get username => _username;
  int? get userId => _userId;
  bool get isAuthenticated => _token != null;

  Map<String, String> get authHeaders => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Token $_token',
      };

  /// Registers a new user and initializes their 15-day knowledge cycle
  Future<bool> register({
    required String username,
    required String email,
    required String password,
  }) async {
    try {
      final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/core/auth/register/');
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': username,
          'email': email,
          'password': password,
        }),
      );

      if (response.statusCode == 201) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _token = data['token'] as String?;
        final user = data['user'] as Map<String, dynamic>?;
        _username = user?['username'] as String?;
        _userId = user?['id'] as int?;
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// Logs in an existing user
  Future<bool> login({
    required String username,
    required String password,
  }) async {
    try {
      final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/core/auth/login/');
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': username,
          'password': password,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _token = data['token'] as String?;
        final user = data['user'] as Map<String, dynamic>?;
        _username = user?['username'] as String?;
        _userId = user?['id'] as int?;
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// Logs out and revokes auth token
  Future<void> logout() async {
    if (_token != null) {
      try {
        final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/core/auth/logout/');
        await http.post(url, headers: authHeaders);
      } catch (_) {}
    }
    _token = null;
    _username = null;
    _userId = null;
  }

  /// Checks the user's 15-day comprehension cadence and gating status (Rule 65)
  Future<Map<String, dynamic>?> checkCycleStatus() async {
    if (!isAuthenticated) return null;
    try {
      final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/learning/cycle/status/');
      final response = await http.get(url, headers: authHeaders);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  /// Records that the user scrolled and read a card for 15-day evaluation
  Future<void> recordScrolledCard(NewsCard card) async {
    if (!isAuthenticated) return;
    try {
      final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/learning/cards/scrolled/');
      await http.post(
        url,
        headers: authHeaders,
        body: jsonEncode({
          'card_id': card.id,
          'headline': card.headline,
          'candidate_techniques': card.candidateTechniques,
          'summary_60s': card.summary60s,
        }),
      );
    } catch (_) {}
  }

  /// Starts the 10-minute maximum, medium-to-hard retention quiz based on scrolled cards
  Future<Map<String, dynamic>?> startRetentionQuiz({bool force = false}) async {
    if (!isAuthenticated) return null;
    try {
      final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/learning/cycle/start-quiz/');
      final response = await http.post(
        url,
        headers: authHeaders,
        body: jsonEncode({'force': force}),
      );
      if (response.statusCode == 201) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  /// Submits an answer to the active retention quiz
  Future<Map<String, dynamic>?> submitQuizAnswer({
    required int sessionId,
    required int questionId,
    required int chosenDisplayIndex,
    required List<int> optionOrder,
  }) async {
    if (!isAuthenticated) return null;
    try {
      final url = Uri.parse('${AppConfig.backendBaseUrl}/api/v1/learning/quiz/$sessionId/answer/');
      final response = await http.post(
        url,
        headers: authHeaders,
        body: jsonEncode({
          'question_id': questionId,
          'chosen_display_index': chosenDisplayIndex,
          'option_order': optionOrder,
        }),
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }
}

