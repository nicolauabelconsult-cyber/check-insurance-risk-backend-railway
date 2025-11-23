"""
Módulo de relatórios - versão sem pandas
"""

import json
from typing import Dict, Any, List
from datetime import datetime
import io
import base64

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

import matplotlib.pyplot as plt
from openpyxl import Workbook


def generate_risk_report(risk_record: Dict[str, Any]) -> Dict[str, Any]:
    """Gerar relatório detalhado de análise de risco em formato JSON estruturado."""
    try:
        matches = json.loads(risk_record.get("matches", "[]"))
        risk_factors = json.loads(risk_record.get("risk_factors", "[]"))

        report = {
            "id": risk_record["id"],
            "timestamp": datetime.now().isoformat(),
            "subject": {
                "full_name": risk_record.get("full_name"),
                "nif": risk_record.get("nif"),
                "passport": risk_record.get("passport"),
                "resident_card": risk_record.get("resident_card"),
            },
            "risk_assessment": {
                "score": risk_record.get("risk_score", 0),
                "level": risk_record.get("risk_level", "UNKNOWN"),
                "factors": risk_factors,
                "recommendation": get_risk_recommendation(
                    risk_record.get("risk_level", "UNKNOWN"),
                    risk_record.get("risk_score", 0),
                ),
            },
            "matches_found": len(matches),
            "detailed_matches": matches,
            "analysis_metadata": {
                "analyzed_at": risk_record.get("analyzed_at"),
                "analyzed_by": risk_record.get("analyzed_by"),
                "decision": risk_record.get("decision"),
                "analyst_notes": risk_record.get("analyst_notes"),
            },
        }

        # Análise das fontes
        source_analysis = analyze_sources(matches)
        report["source_analysis"] = source_analysis

        return report

    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return {"error": str(e)}


def get_risk_recommendation(risk_level: str, score: int) -> str:
    """Obter recomendação baseada no nível de risco."""
    recommendations = {
        "LOW": "Risco baixo. Processar normalmente com monitoramento padrão.",
        "MEDIUM": "Risco médio. Revisar documentação adicional antes de aprovar.",
        "HIGH": "Risco alto. Análise manual detalhada necessária. Considerar recusa.",
        "CRITICAL": "Risco crítico. Recomenda-se recusa imediata. Alertar compliance.",
    }

    base_recommendation = recommendations.get(
        risk_level, "Nível de risco desconhecido."
    )

    if score > 80:
        base_recommendation += (
            " Score muito alto indica necessidade de investigação adicional."
        )
    elif score > 60:
        base_recommendation += " Score elevado requer atenção especial."

    return base_recommendation


def analyze_sources(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analisar fontes dos matches."""
    source_count: Dict[str, int] = {}
    source_types: Dict[str, int] = {}
    highest_risk_match = None
    highest_risk_score = 0

    for match in matches:
        source = match.get("source", "Unknown")
        source_type = match.get("source_type", "OTHER")

        source_count[source] = source_count.get(source, 0) + 1
        source_types[source_type] = source_types.get(source_type, 0) + 1

        risk_score = get_match_risk_score(
            source_type, match.get("similarity", 0.0)
        )
        if risk_score > highest_risk_score:
            highest_risk_score = risk_score
            highest_risk_match = match

    return {
        "total_sources": len(source_count),
        "source_breakdown": source_count,
        "source_type_breakdown": source_types,
        "highest_risk_match": highest_risk_match,
        "risk_distribution": source_types,
    }


def get_match_risk_score(source_type: str, similarity: float) -> int:
    """Calcular score de risco para um match específico."""
    base_scores = {
        "PEP": 40,
        "SANCTIONS": 50,
        "FRAUD": 60,
        "CLAIMS": 30,
        "OTHER": 20,
    }

    base_score = base_scores.get(source_type, 20)
    similarity_bonus = similarity * 20  # Max 20 pontos por similaridade

    return int(base_score + similarity_bonus)


def export_to_excel(data: List[Dict[str, Any]], filename: str | None = None) -> Dict[str, Any]:
    """
    Exportar dados para Excel SEM pandas, usando apenas openpyxl.
    Mantém a mesma assinatura e formato de retorno da versão anterior.
    """
    try:
        if filename is None:
            filename = (
                f"risk_analysis_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )

        wb = Workbook()
        ws = wb.active
        ws.title = "Risk Analysis"

        if not data:
            # Nenhum dado – criar apenas cabeçalho vazio
            wb.save(io.BytesIO())
        else:
            # Cabeçalhos = chaves do primeiro registo
            headers = list(data[0].keys())
            ws.append(headers)

            # Linhas
            for row in data:
                ws.append([row.get(h, "") for h in headers])

            # Ajustar largura das colunas
            for column_cells in ws.columns:
                length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                adjusted_width = min(length + 2, 50)
                ws.column_dimensions[column_cells[0].column_letter].width = adjusted_width

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_data = buffer.read()

        excel_base64 = base64.b64encode(excel_data).decode("utf-8")

        return {
            "filename": filename,
            "data": excel_base64,
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        return {"error": str(e)}


def generate_pdf_report(risk_record: Dict[str, Any]) -> Dict[str, Any]:
    """Gerar relatório PDF a partir de um registo de risco."""
    try:
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story: List[Any] = []

        # Título
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=30,
            textColor=colors.HexColor("#2563EB"),
        )
        story.append(Paragraph("Relatório de Análise de Risco", title_style))
        story.append(Spacer(1, 12))

        # Dados do analisado
        story.append(Paragraph("Dados do Analisado", styles["Heading2"]))
        subject_data = [
            ["Nome Completo:", risk_record.get("full_name", "N/A")],
            ["NIF:", risk_record.get("nif", "N/A")],
            ["Passaporte:", risk_record.get("passport", "N/A")],
            ["Cartão Residente:", risk_record.get("resident_card", "N/A")],
        ]

        subject_table = Table(subject_data, colWidths=[2 * inch, 4 * inch])
        subject_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.grey),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (1, 0), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(subject_table)
        story.append(Spacer(1, 12))

        # Resultado da análise
        story.append(Paragraph("Resultado da Análise", styles["Heading2"]))

        risk_level = risk_record.get("risk_level", "UNKNOWN")
        risk_score = risk_record.get("risk_score", 0)

        level_colors = {
            "LOW": colors.green,
            "MEDIUM": colors.orange,
            "HIGH": colors.red,
            "CRITICAL": colors.darkred,
        }
        level_color = level_colors.get(risk_level, colors.grey)

        result_data = [
            ["Nível de Risco:", risk_level],
            ["Score de Risco:", str(risk_score)],
            ["Data da Análise:", risk_record.get("analyzed_at", "N/A")],
        ]

        result_table = Table(result_data, colWidths=[2 * inch, 4 * inch])
        result_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.grey),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (1, 1), (1, 1), level_color),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(result_table)
        story.append(Spacer(1, 12))

        doc.build(story)

        buffer.seek(0)
        pdf_data = buffer.read()
        pdf_base64 = base64.b64encode(pdf_data).decode("utf-8")

        return {
            "filename": f"risk_report_{risk_record['id']}.pdf",
            "data": pdf_base64,
            "content_type": "application/pdf",
        }

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return {"error": str(e)}


def generate_dashboard_charts() -> Dict[str, str]:
    """Gerar gráfico simples para o dashboard (distribuição de risco + análises por mês)."""
    try:
        from database import execute_query

        # Distribuição de risco
        risk_distribution = execute_query(
            """
            SELECT risk_level, COUNT(*) as count
            FROM risk_records
            WHERE risk_level IS NOT NULL
            GROUP BY risk_level
            """
        )

        # Dados mensais
        monthly_data = execute_query(
            """
            SELECT
                DATE_TRUNC('month', analyzed_at) as month,
                COUNT(*) as count
            FROM risk_records
            WHERE analyzed_at >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', analyzed_at)
            ORDER BY month
            """
        )

        plt.clf()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Gráfico 1: Distribuição de Níveis de Risco
        if risk_distribution:
            levels = [item["risk_level"] for item in risk_distribution]
            counts = [item["count"] for item in risk_distribution]

            ax1.pie(counts, labels=levels, autopct="%1.1f%%")
            ax1.set_title("Distribuição de Níveis de Risco")
        else:
            ax1.text(0.5, 0.5, "Sem dados", ha="center", va="center")
            ax1.set_axis_off()

        # Gráfico 2: análises por mês
        if monthly_data:
            months = [item["month"].strftime("%Y-%m") for item in monthly_data]
            counts = [item["count"] for item in monthly_data]

            ax2.bar(months, counts)
            ax2.set_title("Análises por Mês")
            ax2.set_xlabel("Mês")
            ax2.set_ylabel("Número de Análises")
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")
        else:
            ax2.text(0.5, 0.5, "Sem dados", ha="center", va="center")
            ax2.set_axis_off()

        buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
        buffer.seek(0)
        chart_data = base64.b64encode(buffer.read()).decode("utf-8")
        plt.close(fig)

        return {
            "chart": chart_data,
            "content_type": "image/png",
        }

    except Exception as e:
        print(f"Erro ao gerar gráficos: {e}")
        return {"error": str(e)}
