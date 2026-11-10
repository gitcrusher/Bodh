import 'package:flutter/material.dart';

/// Reusable user avatar that renders the user's Gravatar photo derived from email,
/// deterministic identicon, or colored monogram fallback.
class UserAvatar extends StatelessWidget {
  final String avatarUrl;
  final String? username;
  final double radius;
  final Color backgroundColor;

  const UserAvatar({
    super.key,
    required this.avatarUrl,
    this.username,
    this.radius = 16,
    this.backgroundColor = const Color(0xFF238636),
  });

  @override
  Widget build(BuildContext context) {
    final initial = (username != null && username!.isNotEmpty) ? username![0].toUpperCase() : 'U';

    return CircleAvatar(
      radius: radius,
      backgroundColor: backgroundColor,
      child: ClipOval(
        child: Image.network(
          avatarUrl,
          width: radius * 2,
          height: radius * 2,
          fit: BoxFit.cover,
          errorBuilder: (ctx, err, stack) => Center(
            child: Text(
              initial,
              style: TextStyle(
                fontSize: radius * 0.85,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ),
          loadingBuilder: (ctx, child, progress) {
            if (progress == null) return child;
            return Center(
              child: Text(
                initial,
                style: TextStyle(
                  fontSize: radius * 0.85,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

