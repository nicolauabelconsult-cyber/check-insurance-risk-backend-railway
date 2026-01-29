from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def build_risk_pdf(title: str, data: dict) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 60
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    y -= 30

    c.setFont("Helvetica", 10)
    for k, v in data.items():
        line = f"{k}: {v}"
        c.drawString(50, y, line[:120])
        y -= 14
        if y < 80:
            c.showPage()
            y = h - 60
            c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    return buf.getvalue()
