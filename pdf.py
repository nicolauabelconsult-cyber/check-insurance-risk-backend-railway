from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

def generate_analysis_pdf(a):
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)

    c.drawString(40, 800, "CHECK INSURANCE RISK – TECHNICAL REPORT")
    c.drawString(40, 770, f"Reference: {a.reference}")
    c.drawString(40, 740, f"Subject: {a.subject_name}")
    c.drawString(40, 710, f"Risk Score: {a.risk_score}")
    c.drawString(40, 680, f"Risk Level: {a.risk_level}")
    c.drawString(40, 650, f"PEP: {'YES' if a.pep else 'NO'}")
    if a.pep_reason:
        c.drawString(40, 620, f"PEP Reason: {a.pep_reason}")

    c.showPage()
    c.save()
    b.seek(0)
    return b
