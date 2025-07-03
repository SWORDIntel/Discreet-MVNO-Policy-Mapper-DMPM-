#!/usr/bin/env python3
"""Natural Language Processing layer for GHOST MCP Server"""
import re
import json
from typing import Dict, Any, Tuple, List
from datetime import datetime

class GhostNLPProcessor:
    """Convert natural language queries to MCP commands"""

    def __init__(self):
        # Pattern matching for common queries
        self.patterns = [
            # Top MVNOs queries
            (r"(top|best|most)\s+(anonymous|lenient|private)\s+(carriers?|mvnos?|providers?)",
             "get_top_mvnos", {"n": 10}),

            (r"(which|what)\s+(carriers?|mvnos?|providers?)\s+(don'?t|do not)\s+(require|need|check)\s+(id|identification)",
             "get_top_mvnos", {"n": 10}),

            (r"(show|list|give)\s*(me)?\s*(the)?\s*(anonymous|no.?id|cash.?only)\s*(carriers?|mvnos?|options?)",
             "get_top_mvnos", {"n": 10}),

            # Specific MVNO queries
            (r"(check|search|find|lookup|what about|how about)\s+([A-Za-z][A-Za-z\s&-]+?)\s*(mobile|wireless)?\s*(policy|policies|requirements?|verification)?",
             "search_mvno", "extract_mvno"),

            (r"(tell me about|information on|details for)\s+([A-Za-z][A-Za-z\s&-]+?)\s*(mobile|wireless)?",
             "search_mvno", "extract_mvno"),

            # Recent changes
            (r"(recent|latest|new)\s+(changes?|updates?|alerts?|policies)",
             "get_recent_alerts", {"days": 7}),

            (r"(what|which)\s+(changed|updated)\s+(recently|this week|today|yesterday)",
             "get_recent_alerts", {"days": 7}),

            (r"(any|show|list)\s*(policy)?\s*(changes?|updates?)\s*(in the)?\s*(last|past)\s*(\d+)?\s*(days?|weeks?)",
             "get_recent_alerts", "extract_timeframe"),

            # Trend queries
            (r"(trend|history|changes?)\s+(?:for|of)\s+([A-Za-z][A-Za-z\s&-]+?)\s*(?:over)?\s*(?:the)?\s*(?:last|past)?\s*(\d+)?\s*(days?|weeks?|months?)?",
             "get_mvno_trend", "extract_mvno_timeframe"),

            # System status
            (r"(system|server)\s+(status|health|check)",
             "get_system_status", {}),

            (r"(is|are)\s+(everything|system|server)\s+(working|operational|online|okay|up)",
             "get_system_status", {}),

            # Help queries
            (r"(help|what can you do|commands|usage)",
             "help", {})
        ]

        # Common MVNO name variations
        self.mvno_aliases = {
            "mint": "Mint Mobile",
            "cricket": "Cricket Wireless",
            "metro": "Metro by T-Mobile",
            "metro pcs": "Metro by T-Mobile",
            "visible": "Visible",
            "us mobile": "US Mobile",
            "google fi": "Google Fi",
            "fi": "Google Fi",
            "boost": "Boost Mobile",
            "virgin": "Virgin Mobile",
            "straight talk": "Straight Talk",
            "simple mobile": "Simple Mobile",
            "tracfone": "TracFone",
            "total": "Total Wireless",
            "red pocket": "Red Pocket",
            "ting": "Ting",
            "republic": "Republic Wireless"
        }

    def parse_query(self, natural_query: str) -> Tuple[str, Dict[str, Any]]:
        """Parse natural language query into MCP method and params"""
        query_lower = natural_query.lower().strip()

        # Check each pattern
        for pattern, method, params in self.patterns:
            match = re.search(pattern, query_lower)
            if match:
                # Handle parameter extraction
                if params == "extract_mvno":
                    mvno_name = self._extract_mvno_name(match.group(2))
                    return method, {"mvno_name": mvno_name}

                elif params == "extract_mvno_timeframe":
                    mvno_name = self._extract_mvno_name(match.group(2))
                    days = self._extract_days(
                        match.group(3) if len(match.groups()) >= 3 else None,
                        match.group(4) if len(match.groups()) >= 4 else None
                    )
                    return method, {"mvno_name": mvno_name, "days": days}

                elif params == "extract_timeframe":
                    days = self._extract_days(
                        match.group(5) if len(match.groups()) >= 5 else None,
                        match.group(6) if len(match.groups()) >= 6 else None
                    )
                    return method, {"days": days}

                else:
                    return method, params

        # Default fallback - assume they want top MVNOs
        return "get_top_mvnos", {"n": 5}

    def _extract_mvno_name(self, raw_name: str) -> str:
        """Clean and normalize MVNO name"""
        name = raw_name.strip().lower()

        # Check aliases
        for alias, full_name in self.mvno_aliases.items():
            if alias in name:
                return full_name

        # Title case for unrecognized names
        return raw_name.strip().title()

    def _extract_days(self, time_value: str, time_unit: str) -> int:
        """Extract number of days from time expression"""
        if not time_value:
            # Default based on unit
            if time_unit and "month" in time_unit:
                return 30
            elif time_unit and "week" in time_unit:
                return 7
            else:
                return 7  # Default to 1 week

        try:
            days = int(time_value)

            if time_unit:
                if "week" in time_unit:
                    days *= 7
                elif "month" in time_unit:
                    days *= 30

            return days
        except:
            return 7  # Default to 1 week

    def format_response(self, method: str, result: Dict[str, Any], query: str = "") -> str:
        """Format MCP response for human readability"""
        if "error" in result:
            return f"❌ Error: {result['error']}"

        if method == "get_top_mvnos":
            return self._format_top_mvnos(result)
        elif method == "search_mvno":
            return self._format_mvno_search(result)
        elif method == "get_recent_alerts":
            return self._format_alerts(result)
        elif method == "get_mvno_trend":
            return self._format_trend(result)
        elif method == "get_system_status":
            return self._format_status(result)
        elif method == "help":
            return self._format_help()
        else:
            return f"📊 Result: {json.dumps(result, indent=2)}"

    def _format_top_mvnos(self, result: Dict) -> str:
        """Format top MVNOs response"""
        mvnos = result.get("mvnos", [])
        if not mvnos:
            return "No MVNO data available. The system may need to run a crawl first."

        lines = ["🏆 **Most Anonymous Carriers:**\n"]

        for mvno in mvnos[:10]:  # Limit to top 10
            # Create visual score bar
            score = mvno.get("score", 0)
            filled = int(score)
            empty = 5 - filled
            score_bar = "🟢" * filled + "⚪" * empty

            lines.append(f"{mvno['rank']}. **{mvno['name']}** {score_bar}")
            lines.append(f"   Score: {score:.1f}/5.0 - {mvno.get('assessment', 'No assessment')}")

            # Add warning for low scores
            if score < 2.0:
                lines.append("   ⚠️  *Requires significant verification*")

            lines.append("")

        if len(mvnos) > 10:
            lines.append(f"... and {len(mvnos) - 10} more carriers tracked")

        lines.append(f"\n_Last updated: {result.get('generated_at', 'Unknown')}_")
        return "\n".join(lines)

    def _format_mvno_search(self, result: Dict) -> str:
        """Format MVNO search result"""
        mvno = result.get("mvno", {})
        if not mvno:
            return "❌ MVNO not found in database. Try checking the exact name or running a fresh crawl."

        score = mvno.get("leniency_score", 0)

        lines = [f"📱 **{mvno['name']} Policy Analysis:**\n"]

        # Visual score
        filled = int(score)
        empty = 5 - filled
        score_bar = "🟢" * filled + "⚪" * empty

        lines.append(f"**Anonymity Score**: {score_bar} ({score:.1f}/5.0)")
        lines.append(f"**Assessment**: {mvno.get('assessment', 'No assessment available')}")
        lines.append(f"**Last Updated**: {mvno.get('last_updated', 'Unknown')}")

        # Add recommendations based on score
        if score >= 4.0:
            lines.append("\n✅ **Recommendation**: Excellent choice for anonymous activation")
        elif score >= 3.0:
            lines.append("\n⚠️  **Recommendation**: Good option, minimal verification required")
        else:
            lines.append("\n❌ **Recommendation**: Not recommended for anonymous use")

        # Recent changes if available
        if mvno.get("recent_changes"):
            lines.append("\n**Recent Policy Changes**:")
            for change in mvno["recent_changes"]:
                lines.append(f"  • {change}")

        return "\n".join(lines)

    def _format_alerts(self, result: Dict) -> str:
        """Format recent alerts"""
        alerts = result.get("alerts", [])

        if not alerts:
            return "✅ No policy changes detected in the specified timeframe. All carriers maintaining current policies."

        # Group by alert type
        tightened = [a for a in alerts if a.get("type") == "POLICY_TIGHTENED"]
        relaxed = [a for a in alerts if a.get("type") == "POLICY_RELAXED"]
        new_mvnos = [a for a in alerts if a.get("type") == "NEW_MVNO"]

        lines = ["🔔 **Recent Policy Changes:**\n"]

        if tightened:
            lines.append("🔴 **Tightened Policies** (Less Anonymous):")
            for alert in tightened:
                lines.append(f"  • **{alert['mvno']}**: {alert['old_score']} → {alert['new_score']}")
                lines.append(f"    Impact: {alert.get('impact', 'Reduced anonymity')}")
            lines.append("")

        if relaxed:
            lines.append("🟢 **Relaxed Policies** (More Anonymous):")
            for alert in relaxed:
                lines.append(f"  • **{alert['mvno']}**: {alert['old_score']} → {alert['new_score']}")
                lines.append(f"    Impact: {alert.get('impact', 'Improved anonymity')}")
            lines.append("")

        if new_mvnos:
            lines.append("🆕 **New Carriers Detected**:")
            for alert in new_mvnos:
                lines.append(f"  • **{alert['mvno']}**: Initial score {alert['new_score']}")
            lines.append("")

        lines.append(f"_Total changes: {result.get('total_changes', len(alerts))}_")

        return "\n".join(lines)

    def _format_trend(self, result: Dict) -> str:
        """Format trend analysis"""
        trend = result.get("trend", {})
        mvno_name = result.get("mvno_name", "Unknown")

        if not trend or not trend.get("data_points"):
            return f"📊 No historical data available for {mvno_name}. This MVNO may be newly tracked."

        lines = [f"📈 **{mvno_name} Historical Trend:**\n"]

        # Get recent data points
        data_points = trend.get("data_points", [])
        if len(data_points) > 10:
            data_points = data_points[-10:]  # Last 10 points
            lines.append("*Showing last 10 data points*\n")

        # Create ASCII chart
        max_score = 5.0
        for point in data_points:
            score = point.get("score", 0)
            date = point.get("date", "Unknown")

            # Create bar
            bar_length = int((score / max_score) * 20)
            bar = "█" * bar_length + "░" * (20 - bar_length)

            lines.append(f"{date}: [{bar}] {score:.1f}")

        # Add analysis
        analysis = trend.get("analysis", {})
        if analysis:
            lines.append(f"\n**Trend Analysis**:")

            direction = analysis.get("direction", "stable")
            if direction == "improving":
                lines.append("📈 Becoming more anonymous over time")
            elif direction == "declining":
                lines.append("📉 Becoming less anonymous over time")
            else:
                lines.append("➡️  Relatively stable policies")

            if analysis.get("volatility", 0) > 0.5:
                lines.append("⚠️  High volatility - policies change frequently")

        return "\n".join(lines)

    def _format_status(self, result: Dict) -> str:
        """Format system status"""
        status = result.get("status", {})

        # Overall health indicator
        overall = status.get("overall", "unknown").lower()
        if overall == "operational":
            emoji = "✅"
        elif overall == "degraded":
            emoji = "⚠️"
        else:
            emoji = "❌"

        lines = [f"{emoji} **GHOST DMPM System Status**\n"]

        lines.append(f"**Overall Status**: {status.get('overall', 'Unknown')}")
        lines.append(f"**Last Data Collection**: {status.get('last_crawl', 'Never')}")

        # Database stats
        db_stats = status.get("database", {})
        if db_stats:
            lines.append(f"\n**Database Statistics**:")
            lines.append(f"  • MVNOs Tracked: {db_stats.get('mvno_count', 0)}")
            lines.append(f"  • Total Policies: {db_stats.get('policy_count', 0)}")
            lines.append(f"  • Recent Changes: {db_stats.get('recent_changes', 0)}")

        # API status
        api_status = status.get("api_status", {})
        if api_status:
            lines.append(f"\n**API Configuration**:")
            mode = api_status.get("mode", "unknown")
            if mode == "real":
                lines.append("  • Mode: Live Google Search API")
            else:
                lines.append("  • Mode: Mock data (testing mode)")

        # System alerts
        if status.get("alerts"):
            lines.append(f"\n⚠️  **System Alerts**:")
            for alert in status.get("alerts", []):
                lines.append(f"  • {alert}")

        return "\n".join(lines)

    def _format_help(self) -> str:
        """Format help message"""
        return """🤖 **GHOST DMPM Natural Language Interface**

I understand questions about anonymous phone carriers and MVNOs. Try asking:

**Finding Anonymous Carriers:**
• "Which carriers don't require ID?"
• "Show me the most anonymous MVNOs"
• "Best carriers for cash payment"

**Checking Specific Carriers:**
• "Check Mint Mobile policy"
• "Tell me about Cricket Wireless"
• "Search US Mobile requirements"

**Monitoring Changes:**
• "What changed recently?"
• "Any policy updates this week?"
• "Show alerts from last 30 days"

**Trend Analysis:**
• "Show Cricket trends"
• "Mint Mobile history over 3 months"
• "Track Visible changes"

**System Status:**
• "Is the system working?"
• "System health check"
• "Server status"

💡 **Tips:**
- Carrier names are flexible (e.g., "Metro" = "Metro by T-Mobile")
- Time periods default to 7 days if not specified
- Results are based on automated web crawling
"""

    def get_suggested_followups(self, method: str, result: Dict[str, Any]) -> List[str]:
        """Suggest follow-up queries based on current result"""
        suggestions = []

        if method == "get_top_mvnos":
            mvnos = result.get("mvnos", [])
            if mvnos:
                top_mvno = mvnos[0]["name"]
                suggestions.extend([
                    f"Tell me more about {top_mvno}",
                    "What changed recently?",
                    "Show me carriers with score above 4"
                ])

        elif method == "search_mvno":
            mvno = result.get("mvno", {})
            if mvno:
                name = mvno["name"]
                suggestions.extend([
                    f"Show {name} trends",
                    "Compare with other carriers",
                    "Find similar MVNOs"
                ])

        elif method == "get_recent_alerts":
            if result.get("alerts"):
                suggestions.extend([
                    "Show me the top carriers now",
                    "Which carriers got better?",
                    "Explain these changes"
                ])

        return suggestions

# Enhanced MCP Server Integration
class NLPEnhancedMCPServer:
    """MCP Server with Natural Language Processing"""

    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.nlp = GhostNLPProcessor()

    async def handle_natural_language(self, query: str) -> Dict[str, Any]:
        """Handle natural language query"""
        # Parse to MCP command
        method, params = self.nlp.parse_query(query)

        # Log the translation
        self.mcp_server.logger.info(f"NLP: '{query}' -> {method}({params})")

        # Execute via MCP
        result = await self.mcp_server.execute_method(method, params)

        # Format response
        formatted = self.nlp.format_response(method, result, query)

        # Get suggestions
        suggestions = self.nlp.get_suggested_followups(method, result)

        return {
            "query": query,
            "method": method,
            "params": params,
            "formatted_response": formatted,
            "raw_result": result,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat()
        }

    async def execute_method(self, method: str, params: Dict[str, Any]) -> Any:
        """Pass-through to underlying MCP server"""
        return await self.mcp_server.execute_method(method, params)

if __name__ == "__main__":
    # Test the NLP processor
    nlp = GhostNLPProcessor()

    test_queries = [
        "Which carriers don't require ID?",
        "Check Mint Mobile",
        "What changed recently?",
        "Show me Cricket wireless trends for 2 weeks",
        "Is everything working?",
        "Help"
    ]

    print("=== NLP Query Parser Test ===\n")

    for query in test_queries:
        method, params = nlp.parse_query(query)
        print(f"Query: '{query}'")
        print(f"  → Method: {method}")
        print(f"  → Params: {params}")
        print()
