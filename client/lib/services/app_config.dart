import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

/// Centralized API configuration that adapts automatically across Web, Android Emulator,
/// physical Android devices, and production.
class AppConfig {
  static const String _envHost = String.fromEnvironment('API_HOST');

  /// Resolves the backend host:
  /// - Environment flag if provided: `--dart-define=API_HOST=192.168.1.x:8000`
  /// - Web browser: `127.0.0.1:8000`
  /// - Android emulator: `10.0.2.2:8000` (maps to host machine localhost)
  /// - Other platforms: `127.0.0.1:8000`
  static String get defaultHost {
    if (_envHost.isNotEmpty) return _envHost;
    if (kIsWeb) return '127.0.0.1:8000';
    try {
      if (Platform.isAndroid) return '10.0.2.2:8000';
    } catch (_) {}
    return '127.0.0.1:8000';
  }

  static String get backendBaseUrl => 'http://$defaultHost';
  static String get researchBaseUrl => 'http://$defaultHost/api/v1/research';
  static String get coreBaseUrl => 'http://$defaultHost/api/v1/core';
  static String get learningBaseUrl => 'http://$defaultHost/api/v1/learning';
}

