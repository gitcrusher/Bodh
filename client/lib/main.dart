import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'theme/tokens.dart';
import 'widgets/feed_view.dart';

void main() {
  runApp(const AiNewsApp());
}

class AiNewsApp extends StatefulWidget {
  const AiNewsApp({super.key});

  @override
  State<AiNewsApp> createState() => _AiNewsAppState();
}

class _AiNewsAppState extends State<AiNewsApp> {
  AppThemeFamily _themeFamily = AppThemeFamily.dusk; // Dusk is default (design.md §7b)
  bool _isDark = false;

  void _updateThemeFamily(AppThemeFamily family) {
    setState(() => _themeFamily = family);
  }

  void _toggleDarkMode(bool isDark) {
    setState(() => _isDark = isDark);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI News Feed',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.buildTheme(family: _themeFamily, isDark: _isDark),
      home: FeedView(
        themeFamily: _themeFamily,
        isDark: _isDark,
        onThemeFamilyChanged: _updateThemeFamily,
        onDarkThemeToggled: _toggleDarkMode,
      ),
    );
  }
}
