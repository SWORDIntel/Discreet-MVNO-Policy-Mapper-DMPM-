# GHOST DMPM - AI Assistant Quick Reference

## Connection Info
```python
URL: ws://localhost:8765
Token: ghost-mcp-2024 # Replace with actual token if different
```

## Natural Language Queries

### Finding Anonymous Carriers
- "Which carriers don't require ID?"
- "Show me anonymous phone options"
- "Best MVNOs for cash payment"
- "Top carriers for privacy"
- "What are the most lenient providers?"

### Checking Specific Carriers
- "Check [Carrier Name] policy" (e.g., "Check Mint Mobile policy")
- "Tell me about [Carrier]" (e.g., "Tell me about US Mobile")
- "Is [Carrier] anonymous?"
- "Search [Carrier] requirements"
- "What about Google Fi?"

### Monitoring Changes
- "What changed recently?"
- "Any policy updates this week?"
- "Show alerts from last [N] days" (e.g., "Show alerts from last 30 days")
- "Which carriers got stricter?"
- "List new policies"

### Trend Analysis
- "Show [Carrier] trends" (e.g., "Show Cricket trends")
- "[Carrier] history over [N] days/weeks/months" (e.g., "Mint Mobile history over 3 months")
- "Is [Carrier] getting better or worse?"
- "Track Visible changes over the past 60 days"

### System Status
- "Is the system working?"
- "System health"
- "When was the last update?"
- "Server status"
- "Are you okay?"

### Help
- "Help"
- "What can you do?"
- "Show commands"

## Understanding Scores

The anonymity score ranges from 0.0 to 5.0. Higher is better for anonymity.

| Score Range | Meaning                 | Example Requirements                               |
|-------------|-------------------------|----------------------------------------------------|
| 5.0         | No ID Required          | Cash payment accepted, no personal info asked.     |
| 4.0 - 4.9   | Minimal Verification    | Name/ZIP may be asked, but no formal ID check.     |
| 3.0 - 3.9   | Basic Verification      | May look at ID but not copy/scan it.               |
| 2.0 - 2.9   | Standard Verification   | ID copy/scan required, basic personal details.     |
| 1.0 - 1.9   | Enhanced Verification   | ID copy + address proof, possibly SSN last 4.      |
| 0.0 - 0.9   | Strict Requirements     | Full SSN, credit check, extensive personal data.   |

## Response Emojis & Indicators
- 🏆 **Most Anonymous Carriers:** - Indicates a list of top-ranked MVNOs.
- 🟢 (filled circle) / ⚪ (empty circle) - Visual score representation (e.g., 🟢🟢🟢🟢⚪ for a score of 4/5).
- ✅ **Recommendation**: Excellent choice...
- ⚠️ **Recommendation**: Good option... / *Requires significant verification* / High volatility...
- ❌ **Recommendation**: Not recommended... / MVNO not found... / Error...
- 📱 **[MVNO Name] Policy Analysis:** - Detailed report for a specific MVNO.
- 🔔 **Recent Policy Changes:** - Summary of recent alerts.
- 🔴 **Tightened Policies** (Less Anonymous)
- 🟢 **Relaxed Policies** (More Anonymous)
- 🆕 **New Carriers Detected**
- 📈 **[MVNO Name] Historical Trend:** - Trend data for an MVNO.
-   `[████░░░░]` - ASCII bar chart for trends.
- 📈 Becoming more anonymous...
- 📉 Becoming less anonymous...
- ➡️ Relatively stable policies...
- ✅ **GHOST DMPM System Status** (Operational)
- ⚠️ **GHOST DMPM System Status** (Degraded)
- ❌ **GHOST DMPM System Status** (Error/Unknown)

## Example Conversation Flow
```
User: I need an anonymous phone quickly. What are my best options?
AI:   (Internally, I will query GHOST DMPM: "top anonymous carriers")
      Based on the latest GHOST DMPM data, here are some top options:
      1. US Mobile 🟢🟢🟢🟢⚪ (Score: 4.5/5.0) - Assessment: Minimal verification.
      2. Mint Mobile 🟢🟢🟢🟢⚪ (Score: 4.2/5.0) - Assessment: Accepts cash payments.
      3. Visible 🟢🟢🟢⚪⚪ (Score: 3.8/5.0) - Assessment: Basic verification.

      US Mobile appears to be a strong candidate for quick anonymous activation.

User: Tell me more about US Mobile's policy.
AI:   (Internally, I will query GHOST DMPM: "tell me about US Mobile")
      📱 **US Mobile Policy Analysis:**
      **Anonymity Score**: 🟢🟢🟢🟢⚪ (4.5/5.0)
      **Assessment**: Minimal verification, often just name and email. Prepaid cards accepted.
      **Last Updated**: [Date from response]
      ✅ **Recommendation**: Excellent choice for anonymous activation

User: Has US Mobile's policy changed recently?
AI:   (Internally, I will query GHOST DMPM: "US Mobile recent changes")
      Let me check... According to GHOST DMPM, US Mobile's policy has been stable.
      No significant changes reported in the last 30 days for US Mobile.

User: What about recent changes for any carrier?
AI:   (Internally, I will query GHOST DMPM: "recent changes")
      🔔 **Recent Policy Changes:**
      🔴 **Tightened Policies**:
        • SomeCarrierX: 3.5 → 2.5 (Impact: Now requires ID scan)
      🟢 **Relaxed Policies**:
        • AnotherCarrierY: 2.0 → 3.0 (Impact: No longer requires address proof)

      It seems SomeCarrierX has become less anonymous.
```

**Note:** Always rely on the most current data from GHOST DMPM as policies can change. The token "ghost-mcp-2024" is an example; use the correct operational token.
