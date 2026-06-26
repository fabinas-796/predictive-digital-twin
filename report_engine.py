# report_engine.py — PDF + CSV Report Generation for InfraGuard AI

import os
import csv
import json
from datetime import datetime
from io import BytesIO, StringIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from config import Config
from database import (
    get_all_servers, get_active_alerts, get_all_alerts,
    get_metric_history, get_latest_metric, get_latest_prediction
)


# ══════════════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE
# ══════════════════════════════════════════════════════════════════════════════

DARK_BG    = colors.HexColor('#1a1a2e')
ACCENT     = colors.HexColor('#00d4ff')
CARD_BG    = colors.HexColor('#16213e')
GREEN      = colors.HexColor('#00ff88')
YELLOW     = colors.HexColor('#ffd700')
ORANGE     = colors.HexColor('#ff8c00')
RED        = colors.HexColor('#ff4757')
WHITE      = colors.white
LIGHT_GRAY = colors.HexColor('#e0e0e0')
MID_GRAY   = colors.HexColor('#888888')


def risk_color(risk):
    return {
        'CRITICAL': RED,
        'HIGH':     ORANGE,
        'MEDIUM':   YELLOW,
        'WARNING':  YELLOW,
        'LOW':      GREEN,
        'OK':       GREEN,
    }.get(risk, MID_GRAY)


# ══════════════════════════════════════════════════════════════════════════════
#  PDF REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class PDFReportGenerator:

    def __init__(self):
        self.styles  = getSampleStyleSheet()
        self._setup_styles()


    def _setup_styles(self):
        """Define custom paragraph styles."""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent    = self.styles['Title'],
            fontSize  = 28,
            textColor = WHITE,
            alignment = TA_CENTER,
            spaceAfter= 6,
        )
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent    = self.styles['Normal'],
            fontSize  = 12,
            textColor = ACCENT,
            alignment = TA_CENTER,
            spaceAfter= 4,
        )
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent    = self.styles['Heading1'],
            fontSize  = 14,
            textColor = ACCENT,
            spaceBefore=16,
            spaceAfter= 8,
        )
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent    = self.styles['Normal'],
            fontSize  = 10,
            textColor = LIGHT_GRAY,
            spaceAfter= 4,
        )
        self.small_style = ParagraphStyle(
            'CustomSmall',
            parent    = self.styles['Normal'],
            fontSize  = 8,
            textColor = MID_GRAY,
        )


    def generate(self, latest_data=None):
        """
        Generate a complete PDF health report.
        Returns bytes that can be sent as a file download.
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize    = A4,
            leftMargin  = 1.5 * cm,
            rightMargin = 1.5 * cm,
            topMargin   = 1.5 * cm,
            bottomMargin= 1.5 * cm,
        )

        story = []

        # ── Cover section ─────────────────────────────────────────────────────
        story += self._build_header()
        story += self._build_executive_summary(latest_data)
        story += self._build_server_status_table(latest_data)
        story += self._build_alert_summary()
        story += self._build_predictions_table()
        story += self._build_footer()

        # Build PDF with dark background
        doc.build(
            story,
            onFirstPage = self._draw_background,
            onLaterPages= self._draw_background,
        )

        buffer.seek(0)
        return buffer.read()


    def _draw_background(self, canvas, doc):
        """Draw dark background on every page."""
        canvas.saveState()
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()


    def _build_header(self):
        """Report title and metadata."""
        elements = []

        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph("🛡 InfraGuard AI", self.title_style))
        elements.append(Paragraph(
            "Infrastructure Health Report",
            self.subtitle_style
        ))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}",
            self.small_style
        ))
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(HRFlowable(
            width="100%", thickness=1,
            color=ACCENT, spaceAfter=12
        ))

        return elements


    def _build_executive_summary(self, latest_data):
        """High level system health numbers."""
        elements = []
        elements.append(Paragraph("Executive Summary", self.heading_style))

        servers = get_all_servers()
        alerts  = get_active_alerts()

        # Count risk levels
        risk_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for s in servers:
            pred = get_latest_prediction(s['id'])
            risk = pred.get('risk_level', 'LOW') if pred else 'LOW'
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        critical_alerts = sum(1 for a in alerts if a['severity'] == 'CRITICAL')
        high_alerts     = sum(1 for a in alerts if a['severity'] == 'HIGH')
        health_score    = max(0, 100 - (risk_counts['CRITICAL'] * 25) -
                             (risk_counts['HIGH'] * 10))

        # Summary table
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Servers Monitored', str(len(servers)),       '✅ Online'],
            ['Overall Health Score',   f"{health_score}%",
             '✅ Good' if health_score >= 80 else '⚠️ Degraded'],
            ['Active Alerts',          str(len(alerts)),
             '✅ None' if len(alerts) == 0 else f'⚠️ {len(alerts)} Active'],
            ['Critical Alerts',        str(critical_alerts),
             '✅ None' if critical_alerts == 0 else '🔴 Action Required'],
            ['High Risk Servers',      str(risk_counts['HIGH'] + risk_counts['CRITICAL']),
             '✅ None' if risk_counts['HIGH'] + risk_counts['CRITICAL'] == 0 else '⚠️ Monitor'],
        ]

        t = Table(summary_data, colWidths=[7*cm, 4*cm, 6*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND',  (0,0), (-1,0),  CARD_BG),
            ('TEXTCOLOR',   (0,0), (-1,0),  ACCENT),
            ('FONTSIZE',    (0,0), (-1,0),  10),
            ('FONTNAME',    (0,0), (-1,0),  'Helvetica-Bold'),
            ('BACKGROUND',  (0,1), (-1,-1), DARK_BG),
            ('TEXTCOLOR',   (0,1), (-1,-1), LIGHT_GRAY),
            ('FONTSIZE',    (0,1), (-1,-1), 9),
            ('GRID',        (0,0), (-1,-1), 0.5, CARD_BG),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [DARK_BG, CARD_BG]),
            ('ALIGN',       (1,0), (-1,-1), 'CENTER'),
            ('TOPPADDING',  (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ]))

        elements.append(t)
        elements.append(Spacer(1, 0.5 * cm))
        return elements


    def _build_server_status_table(self, latest_data):
        """Detailed per-server metrics table."""
        elements = []
        elements.append(Paragraph("Server Status Overview", self.heading_style))

        servers = get_all_servers()
        latest  = latest_data or {}

        headers = ['Server', 'Type', 'CPU%', 'RAM%', 'Disk%', 'Temp°C', 'Risk']
        rows    = [headers]

        for s in servers:
            sid     = s['id']
            metrics = latest.get(sid, get_latest_metric(sid) or {})
            pred    = get_latest_prediction(sid)
            risk    = pred.get('risk_level', 'LOW') if pred else 'LOW'

            rows.append([
                s['name'],
                s['type'].capitalize(),
                f"{metrics.get('cpu',  0):.1f}",
                f"{metrics.get('ram',  0):.1f}",
                f"{metrics.get('disk', 0):.1f}",
                f"{metrics.get('temperature', 0):.1f}",
                risk,
            ])

        col_widths = [5*cm, 3.5*cm, 2*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm]
        t = Table(rows, colWidths=col_widths)

        # Build style
        style = [
            ('BACKGROUND',   (0,0), (-1,0),  CARD_BG),
            ('TEXTCOLOR',    (0,0), (-1,0),  ACCENT),
            ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 9),
            ('BACKGROUND',   (0,1), (-1,-1), DARK_BG),
            ('TEXTCOLOR',    (0,1), (-1,-1), LIGHT_GRAY),
            ('GRID',         (0,0), (-1,-1), 0.5, CARD_BG),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [DARK_BG, CARD_BG]),
            ('ALIGN',        (2,0), (-1,-1), 'CENTER'),
            ('TOPPADDING',   (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ]

        # Colour code the risk column
        for i, row in enumerate(rows[1:], start=1):
            risk  = row[-1]
            color = risk_color(risk)
            style.append(('TEXTCOLOR', (6, i), (6, i), color))
            style.append(('FONTNAME',  (6, i), (6, i), 'Helvetica-Bold'))

        t.setStyle(TableStyle(style))
        elements.append(t)
        elements.append(Spacer(1, 0.5 * cm))
        return elements


    def _build_alert_summary(self):
        """Recent alerts table."""
        elements = []
        elements.append(Paragraph("Recent Alerts", self.heading_style))

        alerts = get_all_alerts(limit=15)

        if not alerts:
            elements.append(Paragraph(
                "✅ No alerts recorded in this period.",
                self.body_style
            ))
            return elements

        headers = ['Time', 'Server', 'Severity', 'Metric', 'Message', 'Status']
        rows    = [headers]

        for a in alerts:
            rows.append([
                a['created_at'][11:16],   # just HH:MM
                a['server_name'][:15],
                a['severity'],
                a['metric'],
                a['message'][:35] + '...' if len(a['message']) > 35 else a['message'],
                a['status'].capitalize(),
            ])

        col_widths = [1.8*cm, 3.5*cm, 2.2*cm, 2.5*cm, 6*cm, 2*cm]
        t = Table(rows, colWidths=col_widths)

        style = [
            ('BACKGROUND',    (0,0), (-1,0),  CARD_BG),
            ('TEXTCOLOR',     (0,0), (-1,0),  ACCENT),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('BACKGROUND',    (0,1), (-1,-1), DARK_BG),
            ('TEXTCOLOR',     (0,1), (-1,-1), LIGHT_GRAY),
            ('GRID',          (0,0), (-1,-1), 0.5, CARD_BG),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [DARK_BG, CARD_BG]),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]

        # Colour code severity
        severity_col = 2
        for i, row in enumerate(rows[1:], start=1):
            color = risk_color(row[severity_col])
            style.append(('TEXTCOLOR', (severity_col, i), (severity_col, i), color))
            style.append(('FONTNAME',  (severity_col, i), (severity_col, i), 'Helvetica-Bold'))

        t.setStyle(TableStyle(style))
        elements.append(t)
        elements.append(Spacer(1, 0.5 * cm))
        return elements


    def _build_predictions_table(self):
        """AI prediction summary table."""
        elements = []
        elements.append(Paragraph("AI Prediction Summary", self.heading_style))

        servers = get_all_servers()
        headers = ['Server', 'Risk Level', 'Failure Prob%', 'Time to Failure']
        rows    = [headers]

        for s in servers:
            pred = get_latest_prediction(s['id'])
            if pred:
                rows.append([
                    s['name'],
                    pred.get('risk_level', 'LOW'),
                    f"{pred.get('failure_probability', 0):.1f}%",
                    str(pred.get('time_to_failure', 'N/A'))[:40],
                ])
            else:
                rows.append([s['name'], 'LOW', '0.0%', 'No data yet'])

        col_widths = [5*cm, 3*cm, 3.5*cm, 8*cm]
        t = Table(rows, colWidths=col_widths)

        style = [
            ('BACKGROUND',    (0,0), (-1,0),  CARD_BG),
            ('TEXTCOLOR',     (0,0), (-1,0),  ACCENT),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('BACKGROUND',    (0,1), (-1,-1), DARK_BG),
            ('TEXTCOLOR',     (0,1), (-1,-1), LIGHT_GRAY),
            ('GRID',          (0,0), (-1,-1), 0.5, CARD_BG),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [DARK_BG, CARD_BG]),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]

        for i, row in enumerate(rows[1:], start=1):
            color = risk_color(row[1])
            style.append(('TEXTCOLOR', (1, i), (1, i), color))
            style.append(('FONTNAME',  (1, i), (1, i), 'Helvetica-Bold'))

        t.setStyle(TableStyle(style))
        elements.append(t)
        elements.append(Spacer(1, 0.5*cm))
        return elements


    def _build_footer(self):
        """Report footer."""
        elements = []
        elements.append(HRFlowable(
            width="100%", thickness=1,
            color=ACCENT, spaceBefore=12
        ))
        elements.append(Paragraph(
            "Generated by InfraGuard AI — AI-Powered Infrastructure Monitoring Platform",
            self.small_style
        ))
        elements.append(Paragraph(
            f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
            f"Confidential",
            self.small_style
        ))
        return elements


# ══════════════════════════════════════════════════════════════════════════════
#  CSV EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_csv(server_id=None, limit=100):
    """
    Export metric history as CSV string.
    If server_id given — export that server only.
    Otherwise export all servers.
    """
    output  = StringIO()
    writer  = csv.writer(output)

    # Header row
    writer.writerow([
        'server_id', 'server_name', 'timestamp',
        'cpu', 'ram', 'disk', 'network_in', 'network_out',
        'temperature', 'processes', 'response_time', 'error_rate'
    ])

    servers = get_all_servers()

    if server_id:
        servers = [s for s in servers if s['id'] == server_id]

    server_names = {s['id']: s['name'] for s in servers}

    for s in servers:
        history = get_metric_history(s['id'], limit=limit)
        for row in history:
            writer.writerow([
                row.get('server_id'),
                server_names.get(row.get('server_id'), ''),
                row.get('timestamp'),
                row.get('cpu'),
                row.get('ram'),
                row.get('disk'),
                row.get('network_in'),
                row.get('network_out'),
                row.get('temperature'),
                row.get('processes'),
                row.get('response_time'),
                row.get('error_rate'),
            ])

    return output.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  ADD ROUTES TO APP — Call this from app.py
# ══════════════════════════════════════════════════════════════════════════════

def register_report_routes(app, get_login_required, get_collector):
    """Register PDF and CSV download routes with the Flask app."""
    from flask import send_file, Response

    @app.route('/api/reports/pdf')
    @get_login_required()
    def download_pdf():
        generator  = PDFReportGenerator()
        collector  = get_collector()
        latest     = collector.get_latest() if collector else {}
        pdf_bytes  = generator.generate(latest_data=latest)

        return send_file(
            BytesIO(pdf_bytes),
            mimetype            = 'application/pdf',
            as_attachment       = True,
            download_name       = f'infraguard_report_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        )

    @app.route('/api/reports/csv')
    @get_login_required()
    def download_csv():
        server_id = None
        csv_data  = generate_csv(server_id=server_id, limit=200)

        return Response(
            csv_data,
            mimetype    = 'text/csv',
            headers     = {
                'Content-Disposition':
                    f'attachment; filename=infraguard_metrics_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
            }
        )


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test report generation
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    from database import init_db
    print("=== InfraGuard AI — Report Engine Test ===\n")
    init_db()

    # ── Test 1: Generate PDF ──────────────────────────────────────────────────
    print("Test 1: Generating PDF report...")
    generator = PDFReportGenerator()
    pdf_bytes = generator.generate()

    output_path = 'docs/infraguard_test_report.pdf'
    os.makedirs('docs', exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f"  ✅ PDF saved to {output_path} ({len(pdf_bytes):,} bytes)\n")

    # ── Test 2: Generate CSV ──────────────────────────────────────────────────
    print("Test 2: Generating CSV export...")
    csv_data = generate_csv(limit=20)
    lines    = csv_data.strip().split('\n')
    print(f"  ✅ CSV generated — {len(lines)} rows")
    print(f"  First row : {lines[0]}")
    if len(lines) > 1:
        print(f"  Sample row: {lines[1]}\n")

    # ── Test 3: CSV for one server ────────────────────────────────────────────
    print("Test 3: CSV for pc_local only...")
    csv_single = generate_csv(server_id='pc_local', limit=5)
    lines      = csv_single.strip().split('\n')
    print(f"  ✅ {len(lines)} rows for pc_local")

    print("\n✅ Report engine test complete!")
    print(f"   Open docs/infraguard_test_report.pdf to see your report!")