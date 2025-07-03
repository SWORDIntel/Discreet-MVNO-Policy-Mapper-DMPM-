#!/usr/bin/env python3
"""GHOST Protocol Intelligence Reporter - Per Document #2, Section 4.4"""
import json
from datetime import datetime
from pathlib import Path
from ghost_db import GhostDatabase

class GhostReporter:
    def __init__(self, config):
        self.config = config
        self.logger = config.get_logger("GhostReporter")
        self.db = GhostDatabase(config)
        self.output_dir = Path("reports")
        self.output_dir.mkdir(exist_ok=True)

    def generate_intelligence_brief(self):
        """Generate comprehensive intelligence brief"""
        self.logger.info("Generating intelligence brief")

        # Gather intelligence
        top_mvnos = self.db.get_top_mvnos(20)
        recent_changes = self.db.get_recent_changes(7)

        # Build report
        report = {
            "classification": "SENSITIVE - INTERNAL USE ONLY",
            "generated": datetime.now().isoformat(),
            "executive_summary": self._generate_executive_summary(top_mvnos, recent_changes),
            "top_lenient_mvnos": self._format_mvno_list(top_mvnos),
            "recent_changes": self._format_changes(recent_changes),
            "operational_recommendations": self._generate_recommendations(top_mvnos)
        }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON format
        json_file = self.output_dir / f"intel_brief_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Human-readable format
        text_file = self.output_dir / f"intel_brief_{timestamp}.txt"
        with open(text_file, 'w') as f:
            f.write(self._format_text_report(report))

        self.logger.info(f"Intelligence brief saved: {json_file} and {text_file}")
        return report

    def _generate_executive_summary(self, top_mvnos, changes):
        """Generate executive summary"""
        if not top_mvnos:
            return "No MVNO data available. Initial crawl required."

        top_carrier = top_mvnos[0] if top_mvnos else None
        change_count = len(changes)

        summary = f"BLUF: {top_carrier['mvno_name']} currently offers the most lenient "
        summary += f"verification policies (score: {top_carrier['leniency_score']}/5.0). "
        summary += f"{change_count} policy changes detected in past 7 days. "

        if any(c['change_type'] == 'POLICY_TIGHTENED' for c in changes):
            summary += "WARNING: Multiple carriers tightening verification requirements."

        return summary

    def _format_mvno_list(self, mvnos):
        """Format MVNO list for report"""
        formatted = []
        for rank, mvno in enumerate(mvnos, 1):
            formatted.append({
                "rank": rank,
                "name": mvno['mvno_name'],
                "leniency_score": mvno['leniency_score'],
                "last_updated": mvno['crawl_timestamp'],
                "assessment": self._assess_leniency(mvno['leniency_score'])
            })
        return formatted

    def _assess_leniency(self, score):
        """Provide qualitative assessment of leniency score"""
        if score >= 4.0:
            return "HIGHLY LENIENT - Minimal/no verification"
        elif score >= 3.0:
            return "LENIENT - Basic verification only"
        elif score >= 2.0:
            return "MODERATE - Standard verification"
        elif score >= 1.0:
            return "STRINGENT - Enhanced verification"
        else:
            return "HIGHLY STRINGENT - Comprehensive verification"

    def _format_changes(self, changes):
        """Format policy changes for report"""
        formatted = []
        for change in changes:
            formatted.append({
                "mvno": change['mvno_name'],
                "type": change['change_type'],
                "previous_score": change['old_value'],
                "new_score": change['new_value'],
                "detected": change['detected_timestamp'],
                "impact": self._assess_change_impact(change)
            })
        return formatted

    def _assess_change_impact(self, change):
        """Assess operational impact of policy change"""
        if change['change_type'] == 'NEW_MVNO':
            return "NEW OPTION - Evaluate for operational use"
        elif change['change_type'] == 'POLICY_RELAXED':
            return "OPPORTUNITY - Improved acquisition potential"
        elif change['change_type'] == 'POLICY_TIGHTENED':
            return "RISK - Reduced operational viability"
        return "MONITOR - No immediate action required"

    def _generate_recommendations(self, top_mvnos):
        """Generate operational recommendations"""
        recommendations = []

        if top_mvnos:
            # Primary recommendation
            top = top_mvnos[0]
            if top['leniency_score'] >= 4.0:
                recommendations.append({
                    "priority": "HIGH",
                    "action": f"Prioritize {top['mvno_name']} for immediate acquisition",
                    "rationale": "Highest leniency score with minimal verification"
                })

            # Backup options
            backups = [m for m in top_mvnos[1:4] if m['leniency_score'] >= 3.0]
            if backups:
                recommendations.append({
                    "priority": "MEDIUM",
                    "action": f"Maintain capability with: {', '.join(m['mvno_name'] for m in backups)}",
                    "rationale": "Viable alternatives if primary option compromised"
                })

        # Monitoring recommendation
        recommendations.append({
            "priority": "ONGOING",
            "action": "Continue daily monitoring for policy shifts",
            "rationale": "Regulatory landscape remains dynamic"
        })

        return recommendations

    def _format_text_report(self, report):
        """Format report as human-readable text"""
        lines = [
            "=" * 70,
            "GHOST PROTOCOL - MVNO INTELLIGENCE BRIEF",
            "=" * 70,
            f"Classification: {report['classification']}",
            f"Generated: {report['generated']}",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 70,
            report['executive_summary'],
            "",
            "TOP LENIENT MVNOs",
            "-" * 70
        ]

        for mvno in report['top_lenient_mvnos'][:10]:
            lines.append(
                f"{mvno['rank']:2d}. {mvno['name']:20s} "
                f"Score: {mvno['leniency_score']:3.1f} - {mvno['assessment']}"
            )

        lines.extend([
            "",
            "RECENT POLICY CHANGES",
            "-" * 70
        ])

        for change in report['recent_changes']:
            lines.append(
                f"• {change['mvno']:15s} {change['type']:20s} "
                f"{change['previous_score']} → {change['new_score']}"
            )

        lines.extend([
            "",
            "OPERATIONAL RECOMMENDATIONS",
            "-" * 70
        ])

        for rec in report['operational_recommendations']:
            lines.append(f"[{rec['priority']}] {rec['action']}")
            lines.append(f"        Rationale: {rec['rationale']}")

        lines.append("=" * 70)

        return "\n".join(lines)
