import 'package:flutter/material.dart';
import '../services/api_service.dart';

/// Modal bottom sheet allowing users to view, add, and manage BYOK (Bring-Your-Own-Key)
/// LLM credentials for multi-provider routing (Step 4 & Design Doc §12).
class ByokSettingsSheet extends StatefulWidget {
  final ApiService? apiService;

  const ByokSettingsSheet({super.key, this.apiService});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => const ByokSettingsSheet(),
    );
  }

  @override
  State<ByokSettingsSheet> createState() => _ByokSettingsSheetState();
}

class _ByokSettingsSheetState extends State<ByokSettingsSheet> {
  late final ApiService _apiService;
  bool _isLoading = true;
  List<Map<String, dynamic>> _credentials = [];
  Map<String, dynamic> _quota = {
    'has_byok': false,
    'used': 0,
    'limit': 5,
    'remaining': 5,
    'is_capped': false,
  };

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    final creds = await _apiService.fetchCredentials();
    final quota = await _apiService.fetchQuotaStatus();
    if (mounted) {
      setState(() {
        _credentials = creds;
        _quota = quota;
        _isLoading = false;
      });
    }
  }

  Future<void> _showAddKeyDialog({String initialProvider = 'gemini'}) async {
    String selectedProvider = initialProvider;
    final keyController = TextEditingController();
    bool obscure = true;

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            return AlertDialog(
              backgroundColor: const Color(0xFF1E1E1E),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Add BYOK Provider Key',
                  style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Provider:', style: TextStyle(color: Colors.white70, fontSize: 13)),
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      decoration: BoxDecoration(
                        color: Colors.black26,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.white24),
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<String>(
                          value: selectedProvider,
                          dropdownColor: const Color(0xFF2A2A2A),
                          isExpanded: true,
                          style: const TextStyle(color: Colors.white),
                          items: const [
                            DropdownMenuItem(
                                value: 'gemini', child: Text('Google Gemini (Recommended)')),
                            DropdownMenuItem(
                                value: 'groq', child: Text('Groq (OpenAI GPT-OSS 20B/120B)')),
                            DropdownMenuItem(
                                value: 'zai', child: Text('Z.AI (Free GLM-4.7/4.5 Flash)')),
                          ],
                          onChanged: (val) {
                            if (val != null) setDialogState(() => selectedProvider = val);
                          },
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text('API Key:', style: TextStyle(color: Colors.white70, fontSize: 13)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: keyController,
                      obscureText: obscure,
                      style: const TextStyle(color: Colors.white, fontSize: 14),
                      decoration: InputDecoration(
                        hintText: 'Paste provider API key...',
                        hintStyle: const TextStyle(color: Colors.white38),
                        filled: true,
                        fillColor: Colors.black26,
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                            borderSide: const BorderSide(color: Colors.white24)),
                        suffixIcon: IconButton(
                          icon: Icon(
                              obscure ? Icons.visibility_off_rounded : Icons.visibility_rounded,
                              color: Colors.white54),
                          onPressed: () => setDialogState(() => obscure = !obscure),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'Your API key is encrypted at rest (AES-128 via Fernet) and scoped strictly to your account.',
                      style: TextStyle(color: Colors.white38, fontSize: 11),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Cancel', style: TextStyle(color: Colors.white60)),
                ),
                FilledButton(
                  style: FilledButton.styleFrom(
                      backgroundColor: Colors.white, foregroundColor: Colors.black),
                  onPressed: () async {
                    final key = keyController.text.trim();
                    if (key.isNotEmpty) {
                      Navigator.pop(ctx, true);
                      await _apiService.saveCredential(selectedProvider, key);
                      await _loadData();
                    }
                  },
                  child: const Text('Save Key', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ],
            );
          },
        );
      },
    );

    if (result == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('BYOK credential saved and encrypted successfully!')),
      );
    }
  }

  Future<void> _deleteKey(int id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E1E1E),
        title: const Text('Remove Credential?', style: TextStyle(color: Colors.white)),
        content: const Text('Are you sure you want to delete this custom API key?',
            style: TextStyle(color: Colors.white70)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel', style: TextStyle(color: Colors.white60))),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await _apiService.deleteCredential(id);
      await _loadData();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.75,
      decoration: const BoxDecoration(
        color: Color(0xFF121212),
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Drag handle
          Container(
            margin: const EdgeInsets.only(top: 12, bottom: 8),
            width: 40,
            height: 4,
            decoration:
                BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(2)),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10)),
                  child: const Icon(Icons.vpn_key_rounded, color: Colors.white, size: 22),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('LLM Providers & BYOK',
                          style: TextStyle(
                              color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold)),
                      SizedBox(height: 2),
                      Text('Bring your own API key for unlimited deep-dives & chat',
                          style: TextStyle(color: Colors.white54, fontSize: 12)),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded, color: Colors.white60),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          const Divider(color: Colors.white12, height: 1),

          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator.adaptive())
                : ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      // Quota & Cost Split Card
                      _buildQuotaCard(),

                      const SizedBox(height: 24),

                      // Configured Keys Section
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('YOUR ACTIVE KEYS',
                              style: TextStyle(
                                  color: Colors.white54,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 0.8)),
                          TextButton.icon(
                            style: TextButton.styleFrom(foregroundColor: Colors.white),
                            onPressed: () => _showAddKeyDialog(),
                            icon: const Icon(Icons.add_rounded, size: 18),
                            label: const Text('Add Key',
                                style: TextStyle(fontWeight: FontWeight.bold)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),

                      if (_credentials.isEmpty)
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.03),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.white10),
                          ),
                          child: Column(
                            children: [
                              const Icon(Icons.key_off_rounded, color: Colors.white38, size: 36),
                              const SizedBox(height: 10),
                              const Text('No custom keys added yet',
                                  style: TextStyle(
                                      color: Colors.white70, fontWeight: FontWeight.w600)),
                              const SizedBox(height: 4),
                              const Text(
                                'Add a Google Gemini, Groq, or OpenAI key to unlock unlimited personalized deep-dive variants.',
                                textAlign: TextAlign.center,
                                style: TextStyle(color: Colors.white38, fontSize: 12),
                              ),
                              const SizedBox(height: 14),
                              OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(
                                    foregroundColor: Colors.white,
                                    side: const BorderSide(color: Colors.white24)),
                                onPressed: () => _showAddKeyDialog(),
                                icon: const Icon(Icons.add_rounded, size: 16),
                                label: const Text('Add First Key'),
                              ),
                            ],
                          ),
                        )
                      else
                        ..._credentials.map(_buildCredentialTile),

                      const SizedBox(height: 28),

                      // Supported Providers Info
                      const Text('SUPPORTED MULTI-PROVIDER TIERS',
                          style: TextStyle(
                              color: Colors.white54,
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.8)),
                      const SizedBox(height: 10),
                      _buildProviderTierTile('Google Gemini',
                          'Large context & multi-token synthesis (1M+ context)', 'gemini'),
                      _buildProviderTierTile(
                          'Groq', 'Fast inference with OpenAI GPT-OSS (20B / 120B) on LPU', 'groq'),
                      _buildProviderTierTile('Z.AI (BigModel GLM)',
                          '100% Free GLM-4.7-Flash & GLM-4.5-Flash text models', 'zai'),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuotaCard() {
    final bool hasByok = _quota['has_byok'] == true;
    final int limit = _quota['limit'] as int? ?? 5;
    final int remaining = _quota['remaining'] as int? ?? 5;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color:
            hasByok ? Colors.green.withValues(alpha: 0.1) : Colors.blueGrey.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(16),
        border:
            Border.all(color: hasByok ? Colors.greenAccent.withValues(alpha: 0.3) : Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                hasByok ? Icons.verified_rounded : Icons.pie_chart_outline_rounded,
                color: hasByok ? Colors.greenAccent : Colors.amberAccent,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                hasByok ? 'BYOK Status: Active (Unlimited)' : 'Shared Fallback Quota',
                style: TextStyle(
                  color: hasByok ? Colors.greenAccent : Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            hasByok
                ? 'Your personalized deep-dives and chat requests run directly on your own BYOK keys with zero shared rate limits.'
                : '$remaining of $limit free daily personalized deep-dives remaining on shared quota. Add a custom key to remove daily caps.',
            style: const TextStyle(color: Colors.white70, fontSize: 12.5, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _buildCredentialTile(Map<String, dynamic> cred) {
    final id = cred['id'] as int;
    final provider = (cred['provider'] as String? ?? 'gemini').toUpperCase();
    final masked = cred['masked_key'] as String? ?? '••••';
    final isDefault = cred['is_default'] == true;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1C1C1E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDefault ? Colors.white30 : Colors.white10),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration:
                BoxDecoration(color: Colors.white.withValues(alpha: 0.08), shape: BoxShape.circle),
            child: const Icon(Icons.key_rounded, color: Colors.white, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(provider,
                        style: const TextStyle(
                            color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13.5)),
                    if (isDefault) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                            color: Colors.white24, borderRadius: BorderRadius.circular(4)),
                        child: const Text('DEFAULT',
                            style: TextStyle(
                                color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(masked,
                    style: const TextStyle(
                        color: Colors.white54, fontSize: 12, fontFamily: 'monospace')),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline_rounded, color: Colors.white38, size: 20),
            onPressed: () => _deleteKey(id),
          ),
        ],
      ),
    );
  }

  Widget _buildProviderTierTile(String name, String description, String providerKey) {
    final alreadyAdded =
        _credentials.any((c) => (c['provider'] as String?).toString().toLowerCase() == providerKey);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: const TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13)),
                const SizedBox(height: 2),
                Text(description, style: const TextStyle(color: Colors.white38, fontSize: 11)),
              ],
            ),
          ),
          if (alreadyAdded)
            const Text('Added',
                style:
                    TextStyle(color: Colors.greenAccent, fontSize: 11, fontWeight: FontWeight.bold))
          else
            TextButton(
              style:
                  TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(50, 30)),
              onPressed: () => _showAddKeyDialog(initialProvider: providerKey),
              child: const Text('Add Key', style: TextStyle(color: Colors.white70, fontSize: 12)),
            ),
        ],
      ),
    );
  }
}
