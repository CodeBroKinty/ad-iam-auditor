# report.py — PDF and HTML report generator

import os
from datetime import datetime
from jinja2 import Template
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from config import REPORT_DIR
from utils import setup_logger, get_filename_timestamp, severity_color

logger = setup_logger()


# ─── HTML REPORT ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AD IAM Audit Report</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4f4; color: #222; margin: 0; padding: 0; }
        .container { max-width: 960px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 48px; }
        h1 { color: #1a1a2e; font-size: 2em; margin-bottom: 4px; }
        h2 { color: #1a1a2e; font-size: 1.2em; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; margin-top: 40px; }
        .meta { color: #666; font-size: 0.95em; margin-bottom: 32px; }
        .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 24px 0; }
        .summary-card { background: #f8f8f8; border-radius: 6px; padding: 20px; text-align: center; border-top: 4px solid #1a1a2e; }
        .summary-card .number { font-size: 2em; font-weight: bold; color: #1a1a2e; }
        .summary-card .label { font-size: 0.85em; color: #666; margin-top: 4px; }
        .check-block { margin-bottom: 32px; }
        .severity-badge { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 0.8em; font-weight: bold; color: #fff; margin-left: 12px; vertical-align: middle; }
        .finding { background: #fafafa; border-left: 4px solid #e0e0e0; padding: 12px 16px; margin: 8px 0; border-radius: 0 4px 4px 0; font-size: 0.95em; }
        .no-findings { color: #2d862d; font-style: italic; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th { background: #1a1a2e; color: #fff; padding: 10px 14px; text-align: left; font-size: 0.9em; }
        td { padding: 10px 14px; border-bottom: 1px solid #e0e0e0; font-size: 0.9em; }
        tr:nth-child(even) { background: #f8f8f8; }
        .footer { margin-top: 48px; color: #aaa; font-size: 0.85em; text-align: center; border-top: 1px solid #e0e0e0; padding-top: 24px; }
    </style>
</head>
<body>
<div class="container">
    <h1>Active Directory IAM Audit Report</h1>
    <div class="meta">
        Domain: <strong>{{ domain }}</strong> &nbsp;|&nbsp;
        Generated: <strong>{{ timestamp }}</strong> &nbsp;|&nbsp;
        Total Users Scanned: <strong>{{ total_users }}</strong>
    </div>

    <div class="summary-grid">
        {% for key, check in checks.items() %}
        <div class="summary-card">
            <div class="number">{{ check.findings | length }}</div>
            <div class="label">{{ check.title }}</div>
        </div>
        {% endfor %}
    </div>

    {% for key, check in checks.items() %}
    <div class="check-block">
        <h2>
            {{ check.title }}
            <span class="severity-badge" style="background: {{ severity_color(check.severity) }};">{{ check.severity }}</span>
        </h2>
        {% if check.findings %}
            <table>
                <tr>
                    <th>User</th>
                    <th>Display Name</th>
                    <th>OU</th>
                    <th>Detail</th>
                </tr>
                {% for f in check.findings %}
                <tr>
                    <td>{{ f.user }}</td>
                    <td>{{ f.display_name }}</td>
                    <td>{{ f.ou }}</td>
                    <td>{{ f.detail }}</td>
                </tr>
                {% endfor %}
            </table>
        {% else %}
            <p class="no-findings">✓ No findings for this check.</p>
        {% endif %}
    </div>
    {% endfor %}

    <div class="footer">
        AD IAM Auditor &nbsp;|&nbsp; Generated {{ timestamp }} &nbsp;|&nbsp; corp.local
    </div>
</div>
</body>
</html>
"""


def generate_html_report(results):
    logger.info("Generating HTML report...")
    template = Template(HTML_TEMPLATE)
    html = template.render(
        domain=results["domain"],
        timestamp=results["timestamp"],
        total_users=results["total_users"],
        checks=results["checks"],
        severity_color=severity_color
    )
    filename = os.path.join(REPORT_DIR, f"audit_report_{get_filename_timestamp()}.html")
    with open(filename, "w") as f:
        f.write(html)
    logger.info(f"HTML report saved: {filename}")
    return filename


# ─── PDF REPORT ─────────────────────────────────────────────────────────────

def generate_pdf_report(results):
    logger.info("Generating PDF report...")
    filename = os.path.join(REPORT_DIR, f"audit_report_{get_filename_timestamp()}.pdf")
    doc = SimpleDocTemplate(filename, pagesize=letter,
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle("title", fontSize=22, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1a1a2e"), spaceAfter=6)
    sub_style = ParagraphStyle("sub", fontSize=10, textColor=colors.grey, spaceAfter=20)
    body_style = ParagraphStyle("body", fontSize=9, leading=14, spaceAfter=6)
    finding_style = ParagraphStyle("finding", fontSize=9, leading=13,
                                    leftIndent=12, textColor=colors.HexColor("#333"))

    story.append(Paragraph("Active Directory IAM Audit Report", title_style))
    story.append(Paragraph(
        f"Domain: {results['domain']}  |  Generated: {results['timestamp']}  |  Users Scanned: {results['total_users']}",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0")))
    story.append(Spacer(1, 16))

    # Summary table
    summary_data = [["Check", "Severity", "Findings"]]
    for key, check in results["checks"].items():
        summary_data.append([
            check["title"],
            check["severity"],
            str(len(check["findings"]))
        ])

    summary_table = Table(summary_data, colWidths=[3.8*inch, 1.2*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 24))

    # Findings sections
    for key, check in results["checks"].items():
        sev_color = colors.HexColor(severity_color(check["severity"]))

        section_style = ParagraphStyle("section", fontSize=12, fontName="Helvetica-Bold",
                                        textColor=colors.HexColor("#1a1a2e"), spaceAfter=4, spaceBefore=16)
        story.append(Paragraph(check["title"], section_style))
        story.append(Paragraph(f"Severity: {check['severity']}", ParagraphStyle(
            "sev", fontSize=9, textColor=sev_color, spaceAfter=8
        )))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0e0e0")))
        story.append(Spacer(1, 6))

        if check["findings"]:
            for f in check["findings"]:
                story.append(Paragraph(f"• {f['detail']}", finding_style))
        else:
            story.append(Paragraph("✓ No findings for this check.", ParagraphStyle(
                "ok", fontSize=9, textColor=colors.HexColor("#2d862d")
            )))

        story.append(Spacer(1, 8))

    # Footer
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0e0e0")))
    story.append(Paragraph(
        f"AD IAM Auditor  |  Generated {results['timestamp']}  |  corp.local",
        ParagraphStyle("footer", fontSize=8, textColor=colors.grey, spaceBefore=8)
    ))

    doc.build(story)
    logger.info(f"PDF report saved: {filename}")
    return filename


# ─── GENERATE BOTH ──────────────────────────────────────────────────────────

def generate_reports(results):
    from utils import ensure_report_dir
    ensure_report_dir()
    html_file = generate_html_report(results)
    pdf_file = generate_pdf_report(results)
    return html_file, pdf_file