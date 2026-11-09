import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/card_model.dart';
import '../models/chat_model.dart';
import '../services/chat_service.dart';

/// Per-card conversational RAG grounded in the paper's full text.
///
/// Modern dark UI with:
/// - Animated "feeding paper…" status bar on first open
/// - Typing indicator with animated dots
/// - Slide-in message bubbles
/// - Glassmorphic input bar
/// - Tappable citation pills
class PaperChatSheet extends StatefulWidget {
  final NewsCard card;
  final ChatService? chatService;
  final int? initialSessionId;

  const PaperChatSheet({
    super.key,
    required this.card,
    this.chatService,
    this.initialSessionId,
  });

  static Future<void> show(BuildContext context, NewsCard card) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.7),
      builder: (ctx) => PaperChatSheet(card: card),
    );
  }

  static Future<void> showWithSession(BuildContext context, NewsCard card,
      {required int sessionId}) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.7),
      builder: (ctx) => PaperChatSheet(card: card, initialSessionId: sessionId),
    );
  }

  @override
  State<PaperChatSheet> createState() => _PaperChatSheetState();
}

class _PaperChatSheetState extends State<PaperChatSheet> with TickerProviderStateMixin {
  late final ChatService _chatService;
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();

  final List<ChatMessageModel> _messages = [];
  int? _sessionId;
  bool _isSending = false;
  String _statusText = '';

  // Typing indicator animation
  late final AnimationController _typingController;

  static const int maxMessageLength = 2000;

  // Brand colours
  static const Color _accentBlue = Color(0xFF2196F3);
  static const Color _surfaceDark = Color(0xFF0E0E12);
  static const Color _cardDark = Color(0xFF15151C);
  static const Color _borderDark = Color(0xFF252530);

  @override
  void initState() {
    super.initState();
    _chatService = widget.chatService ?? ChatService();
    _controller.addListener(() => setState(() {}));
    if (widget.initialSessionId != null) {
      _sessionId = widget.initialSessionId;
    }

    _typingController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    _typingController.dispose();
    super.dispose();
  }

  Future<void> _sendMessage(String text) async {
    final clean = text.trim();
    if (clean.isEmpty || clean.length > maxMessageLength || _isSending) return;

    _controller.clear();
    HapticFeedback.lightImpact();

    final isFirstQuestion = _messages.isEmpty && _sessionId == null;

    final userMsg = ChatMessageModel(
      id: DateTime.now().millisecondsSinceEpoch,
      role: 'user',
      content: clean,
      citations: [],
      createdAt: DateTime.now(),
    );

    setState(() {
      _messages.add(userMsg);
      _isSending = true;
      _statusText = isFirstQuestion
          ? 'Feeding verified paper to context…'
          : 'Searching verified paper sources…';
    });

    _scrollToBottom();

    try {
      final res = await _chatService.sendMessage(
        cardId: widget.card.id,
        message: clean,
        sessionId: _sessionId,
        cardHeadline: widget.card.headline,
        cardSummary: widget.card.summary60s,
      );

      if (mounted) {
        final assistantMsg = ChatMessageModel(
          id: DateTime.now().millisecondsSinceEpoch + 1,
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          createdAt: DateTime.now(),
          isAbstention: res.abstain,
        );

        setState(() {
          _sessionId = res.sessionId;
          _messages.add(assistantMsg);
          _isSending = false;
        });

        _scrollToBottom();
      }
    } catch (_) {
      if (mounted) setState(() => _isSending = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  void _showCitationSheet(CitationModel citation, int idx) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        margin: const EdgeInsets.all(12),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: _cardDark,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _borderDark),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _accentBlue.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: _accentBlue.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.verified_rounded, size: 12, color: _accentBlue),
                      const SizedBox(width: 4),
                      Text(
                        'EXCERPT ${idx + 1}  ·  CHUNK #${citation.chunkId}',
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: _accentBlue,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                IconButton(
                  onPressed: () => Navigator.pop(ctx),
                  icon: const Icon(Icons.close_rounded, color: Colors.white38, size: 20),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
            if (citation.claim.isNotEmpty) ...[
              const SizedBox(height: 14),
              const Text(
                'CLAIM',
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.8,
                  color: Colors.white38,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                citation.claim,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  height: 1.4,
                ),
              ),
            ],
            const SizedBox(height: 14),
            const Text(
              'VERBATIM PAPER EXCERPT',
              style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.8,
                color: Colors.white38,
              ),
            ),
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _surfaceDark,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _accentBlue.withValues(alpha: 0.25)),
              ),
              child: Text(
                '"${citation.quote}"',
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 13.5,
                  fontStyle: FontStyle.italic,
                  height: 1.5,
                ),
              ),
            ),
            const SizedBox(height: 12),
            const Row(
              children: [
                Icon(Icons.check_circle_rounded, size: 13, color: Color(0xFF4CAF50)),
                SizedBox(width: 6),
                Text(
                  'Deterministic match verified against paper text',
                  style: TextStyle(fontSize: 11, color: Color(0xFF4CAF50)),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final screenH = MediaQuery.of(context).size.height;
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    final remainingChars = maxMessageLength - _controller.text.length;

    return Container(
      height: screenH * 0.91,
      decoration: const BoxDecoration(
        color: _surfaceDark,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Drag handle
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 10, bottom: 4),
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.white12,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // ── Header ──────────────────────────────────────────
          _buildHeader(),

          const Divider(color: Color(0xFF1E1E28), height: 1),

          // ── Messages ─────────────────────────────────────────
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(14, 14, 14, 8),
                    itemCount: _messages.length + (_isSending ? 1 : 0),
                    itemBuilder: (ctx, idx) {
                      if (idx == _messages.length) return _buildTypingIndicator();
                      return _buildMessage(_messages[idx], idx);
                    },
                  ),
          ),

          // ── Input Bar ────────────────────────────────────────
          _buildInputBar(remainingChars, bottomInset),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 6, 10, 10),
      child: Row(
        children: [
          // Paper thumbnail
          if (widget.card.imageUrl != null && widget.card.imageUrl!.isNotEmpty)
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.network(
                widget.card.imageUrl!,
                width: 40,
                height: 40,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _paperIconFallback(),
              ),
            )
          else
            _paperIconFallback(),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text(
                      'PAPER CHAT',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2,
                        color: _accentBlue,
                      ),
                    ),
                    const SizedBox(width: 7),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: Colors.white12),
                      ),
                      child: const Text(
                        'RAG',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          color: Colors.white38,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  widget.card.headline,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    height: 1.2,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close_rounded, color: Colors.white38, size: 22),
            onPressed: () => Navigator.pop(context),
            tooltip: 'Close',
          ),
        ],
      ),
    );
  }

  Widget _paperIconFallback() {
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: _accentBlue.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Icon(Icons.article_rounded, color: _accentBlue, size: 20),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: _accentBlue.withValues(alpha: 0.1),
                shape: BoxShape.circle,
                border: Border.all(color: _accentBlue.withValues(alpha: 0.2)),
              ),
              child: const Icon(Icons.auto_awesome_rounded, color: _accentBlue, size: 30),
            ),
            const SizedBox(height: 16),
            const Text(
              'Ask anything about this paper',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Every answer is grounded in the actual paper text with verified citations.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white38, fontSize: 13, height: 1.45),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                'What is the core breakthrough?',
                'How does this compare to other models?',
                'Explain the key techniques used simply',
                'What are the broader implications?',
              ].map((s) => _suggestionChip(s)).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _suggestionChip(String label) {
    return GestureDetector(
      onTap: () => _sendMessage(label),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.white12),
        ),
        child: Text(
          label,
          style: const TextStyle(color: Colors.white70, fontSize: 12.5),
        ),
      ),
    );
  }

  Widget _buildMessage(ChatMessageModel msg, int idx) {
    return TweenAnimationBuilder<double>(
      key: ValueKey(msg.id),
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      builder: (_, v, child) => Opacity(
        opacity: v,
        child: Transform.translate(
          offset: Offset(0, 12 * (1 - v)),
          child: child,
        ),
      ),
      child: msg.isUser ? _buildUserBubble(msg) : _buildAssistantBubble(msg),
    );
  }

  Widget _buildUserBubble(ChatMessageModel msg) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF1E88E5), Color(0xFF1565C0)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(18),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(4),
                ),
                boxShadow: [
                  BoxShadow(
                    color: _accentBlue.withValues(alpha: 0.25),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Text(
                msg.content,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14.5,
                  height: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAssistantBubble(ChatMessageModel msg) {
    final isDeflect =
        msg.content.contains("I'm here to help") || msg.content.contains("Feel free to ask");

    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // AI avatar
          Container(
            width: 28,
            height: 28,
            margin: const EdgeInsets.only(right: 10, top: 2),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [_accentBlue.withValues(alpha: 0.8), const Color(0xFF1565C0)],
              ),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 14),
          ),
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.82,
              ),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _cardDark,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(18),
                ),
                border: Border.all(color: _borderDark),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (isDeflect) ...[
                    const Row(
                      children: [
                        Icon(Icons.tips_and_updates_rounded, size: 13, color: Color(0xFFFFA726)),
                        SizedBox(width: 5),
                        Text(
                          'TIP',
                          style: TextStyle(
                            fontSize: 9.5,
                            fontWeight: FontWeight.w800,
                            color: Color(0xFFFFA726),
                            letterSpacing: 0.8,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                  ],
                  Text(
                    msg.content,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14.5,
                      height: 1.5,
                    ),
                  ),

                  // Citation pills
                  if (msg.citations.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      height: 1,
                      color: Colors.white.withValues(alpha: 0.06),
                    ),
                    const SizedBox(height: 10),
                    const Row(
                      children: [
                        Icon(Icons.format_quote_rounded, size: 12, color: _accentBlue),
                        SizedBox(width: 5),
                        Text(
                          'PAPER SOURCES',
                          style: TextStyle(
                            fontSize: 9.5,
                            fontWeight: FontWeight.w700,
                            color: _accentBlue,
                            letterSpacing: 0.8,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: List.generate(msg.citations.length, (i) {
                        final cit = msg.citations[i];
                        return GestureDetector(
                          onTap: () => _showCitationSheet(cit, i),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                            decoration: BoxDecoration(
                              color: _accentBlue.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: _accentBlue.withValues(alpha: 0.3)),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Container(
                                  width: 16,
                                  height: 16,
                                  decoration: BoxDecoration(
                                    color: _accentBlue.withValues(alpha: 0.2),
                                    shape: BoxShape.circle,
                                  ),
                                  child: Center(
                                    child: Text(
                                      '${i + 1}',
                                      style: const TextStyle(
                                        fontSize: 9,
                                        fontWeight: FontWeight.w800,
                                        color: _accentBlue,
                                      ),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 5),
                                const Text(
                                  'Excerpt',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: _accentBlue,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 28,
            height: 28,
            margin: const EdgeInsets.only(right: 10),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [_accentBlue.withValues(alpha: 0.8), const Color(0xFF1565C0)],
              ),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 14),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: _cardDark,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
              border: Border.all(color: _borderDark),
            ),
            child: AnimatedBuilder(
              animation: _typingController,
              builder: (_, __) {
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: List.generate(3, (i) {
                    final delay = i / 3.0;
                    final t = (_typingController.value - delay).clamp(0.0, 1.0);
                    final bounce = t < 0.5 ? t * 2 : (1.0 - t) * 2;
                    return Transform.translate(
                      offset: Offset(0, -4 * bounce),
                      child: Container(
                        margin: const EdgeInsets.symmetric(horizontal: 2.5),
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.3 + bounce * 0.6),
                          shape: BoxShape.circle,
                        ),
                      ),
                    );
                  }),
                );
              },
            ),
          ),
          const SizedBox(width: 10),
          Text(
            _statusText.isNotEmpty ? _statusText : 'Searching verified paper…',
            style: const TextStyle(fontSize: 12, color: Colors.white54),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar(int remainingChars, double bottomInset) {
    final canSend = _controller.text.trim().isNotEmpty && remainingChars >= 0 && !_isSending;

    return Container(
      padding: EdgeInsets.fromLTRB(12, 10, 12, bottomInset + 14),
      decoration: const BoxDecoration(
        color: _cardDark,
        border: Border(top: BorderSide(color: Color(0xFF1E1E28))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Container(
              constraints: const BoxConstraints(maxHeight: 120),
              decoration: BoxDecoration(
                color: _surfaceDark,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(
                  color: _focusNode.hasFocus ? _accentBlue.withValues(alpha: 0.5) : _borderDark,
                ),
              ),
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                maxLines: 5,
                minLines: 1,
                maxLength: maxMessageLength,
                style: const TextStyle(color: Colors.white, fontSize: 14.5),
                onTap: () => setState(() {}),
                textInputAction: TextInputAction.newline,
                decoration: const InputDecoration(
                  hintText: 'Ask about this paper…',
                  hintStyle: const TextStyle(color: Colors.white30, fontSize: 14.5),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 11),
                  counterText: '',
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: canSend ? () => _sendMessage(_controller.text) : null,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                gradient: canSend
                    ? const LinearGradient(
                        colors: [Color(0xFF2196F3), Color(0xFF1565C0)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      )
                    : null,
                color: canSend ? null : Colors.white10,
                shape: BoxShape.circle,
                boxShadow: canSend
                    ? [
                        BoxShadow(
                          color: _accentBlue.withValues(alpha: 0.35),
                          blurRadius: 12,
                          offset: const Offset(0, 3),
                        ),
                      ]
                    : null,
              ),
              child: Icon(
                Icons.arrow_upward_rounded,
                color: canSend ? Colors.white : Colors.white24,
                size: 20,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
