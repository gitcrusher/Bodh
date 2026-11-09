import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'tokens.dart';

class AppTheme {
  static ThemeData buildTheme({
    required AppThemeFamily family,
    required bool isDark,
  }) {
    final tokens = AppColorTokens.resolve(family: family, isDark: isDark);
    final brightness = isDark ? Brightness.dark : Brightness.light;

    // Humanist serif for headlines (design.md §7b)
    final headlineFont = GoogleFonts.sourceSerif4(
      color: tokens.textPrimary,
      fontWeight: FontWeight.w600,
    ).copyWith(
      fontFamilyFallback: const ['Georgia', 'Cambria', 'serif'],
    );

    // Clean sans for body and UI (Inter, line-height 1.5-1.6)
    final bodyFont = GoogleFonts.inter(
      color: tokens.textPrimary,
      height: 1.55,
    ).copyWith(
      fontFamilyFallback: const [
        'Inter',
        '-apple-system',
        'BlinkMacSystemFont',
        'Segoe UI',
        'Roboto',
        'Helvetica',
        'Arial',
        'sans-serif',
      ],
    );

    return ThemeData(
      brightness: brightness,
      scaffoldBackgroundColor: tokens.background,
      cardColor: tokens.surface,
      dividerColor: tokens.divider,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: tokens.primaryAccent,
        onPrimary: tokens.surface,
        secondary: tokens.secondaryAccent,
        onSecondary: tokens.surface,
        error: Colors.redAccent,
        onError: Colors.white,
        surface: tokens.surface,
        onSurface: tokens.textPrimary,
      ),
      textTheme: TextTheme(
        headlineLarge: headlineFont.copyWith(fontSize: 24, letterSpacing: -0.3),
        headlineMedium: headlineFont.copyWith(fontSize: 20, letterSpacing: -0.2),
        headlineSmall: headlineFont.copyWith(fontSize: 18),
        titleMedium: bodyFont.copyWith(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: tokens.textPrimary,
        ),
        bodyLarge: bodyFont.copyWith(fontSize: 16),
        bodyMedium: bodyFont.copyWith(fontSize: 14),
        bodySmall: bodyFont.copyWith(fontSize: 12, color: tokens.textSecondary),
        labelSmall: bodyFont.copyWith(
          fontSize: 11,
          letterSpacing: 0.5,
          fontWeight: FontWeight.w500,
          color: tokens.textSecondary,
        ),
      ),
      cardTheme: CardThemeData(
        color: tokens.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: tokens.divider, width: 1),
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: tokens.background,
        elevation: 0,
        scrolledUnderElevation: 0,
        iconTheme: IconThemeData(color: tokens.textPrimary),
        titleTextStyle: headlineFont.copyWith(
          fontSize: 18,
          color: tokens.textPrimary,
        ),
      ),
    );
  }
}
