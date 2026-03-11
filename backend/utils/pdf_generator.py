from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import cm
import io
from datetime import datetime


def generate_pdf(job_id: str, products: list[dict]) -> bytes:
    """Called by routes.py — generate_pdf(job_id, products) -> bytes"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("CarbonLens Carbon Footprint Report", styles["Title"]))
    story.append(Paragraph(f"Job ID: {job_id}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Per-Product Carbon Estimates", styles["Heading2"]))

    table_data = [["Product", "Qty", "CO2e Min (kg)", "CO2e Est. (kg)", "CO2e Max (kg)", "Conf."]]
    for p in products:
        table_data.append([
            str(p.get("description", ""))[:30],
            str(p.get("quantity_units", "")),
            str(p.get("co2e_min", "")),
            str(p.get("co2e_estimate", "")),
            str(p.get("co2e_max", "")),
            f"{p.get('confidence_pct', '')}%"
        ])

    table = Table(table_data, colWidths=[5*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Methodology", styles["Heading2"]))
    story.append(Paragraph(
        "Estimates generated using physics-informed Bayesian disaggregation. "
        "Energy attribution uses BEE India SEC benchmarks. Material attribution uses process yield coefficients. "
        "Confidence intervals derived from Monte Carlo simulation (N=1000) with 15% SEC uncertainty.",
        styles["Normal"]
    ))

    doc.build(story)
    return buffer.getvalue()


def generate_pdf_report(factory: dict, reporting_period: dict, products: list[dict], factory_totals: dict) -> bytes:
    """Original signature — kept for backward compatibility."""
    return generate_pdf("N/A", products)