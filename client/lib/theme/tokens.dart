import 'package:flutter/material.dart';

/// Design tokens matching Agent/design.md §7b.
/// Dusk is the default brand theme (muted slate + soft teal).
/// Overcast is a cooler, neutral-corporate switchable theme.
enum AppThemeFamily { dusk, overcast }

class AppColorTokens {
  final Color background;
  final Color surface;
  final Color primaryAccent;
  final Color secondaryAccent;
  final Color textPrimary;
  final Color textSecondary;
  final Color divider;
  final Color success;

  const AppColorTokens({
    required this.background,
    required this.surface,
    required this.primaryAccent,
    required this.secondaryAccent,
    required this.textPrimary,
    required this.textSecondary,
    required this.divider,
    required this.success,
  });

  // --- Dusk: Default Palette ---
  static const duskLight = AppColorTokens(
    background: Color(0xFFF6F5F1),
    surface: Color(0xFFFFFFFF),
    primaryAccent: Color(0xFF3B6E71),
    secondaryAccent: Color(0xFF8B7E74),
    textPrimary: Color(0xFF2A2E33),
    textSecondary: Color(0xFF6B6F73),
    divider: Color(0xFFE4E1DA),
    success: Color(0xFF5B8C6E),
  );

  static const duskDark = AppColorTokens(
    background: Color(0xFF15181C),
    surface: Color(0xFF1E2227),
    primaryAccent: Color(0xFF5FA3A6),
    secondaryAccent: Color(0xFFA79C91),
    textPrimary: Color(0xFFE8E6E1),
    textSecondary: Color(0xFF9A9D9F),
    divider: Color(0xFF2B2F34),
    success: Color(0xFF7FAF8E),
  );

  // --- Overcast: Alternative Cooler Palette ---
  static const overcastLight = AppColorTokens(
    background: Color(0xFFF4F5F7),
    surface: Color(0xFFFFFFFF),
    primaryAccent: Color(0xFF4A5B7C),
    secondaryAccent: Color(0xFF8B7E74), // fallback to Dusk
    textPrimary: Color(0xFF22252B),
    textSecondary: Color(0xFF6C7280),
    divider: Color(0xFFE3E5E9),
    success: Color(0xFF5B8C6E),
  );

  static const overcastDark = AppColorTokens(
    background: Color(0xFF14161A),
    surface: Color(0xFF1D2024),
    primaryAccent: Color(0xFF7C8FB0),
    secondaryAccent: Color(0xFFA79C91), // fallback to Dusk
    textPrimary: Color(0xFFE6E7EA),
    textSecondary: Color(0xFF9BA0AC),
    divider: Color(0xFF2A2D32),
    success: Color(0xFF7FAF8E),
  );

  static AppColorTokens resolve({
    required AppThemeFamily family,
    required bool isDark,
  }) {
    if (family == AppThemeFamily.dusk) {
      return isDark ? duskDark : duskLight;
    } else {
      return isDark ? overcastDark : overcastLight;
    }
  }
}
