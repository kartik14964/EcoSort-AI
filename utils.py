
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[0]  # ecosort/ root

class Settings(BaseSettings):
    APP_NAME: str = "EcoSort AI"
    MONGO_URI: str = "mongodb://localhost:27017" # Default fallback
    DB_NAME: str = "ecosort"
    # `best.pt` in older project copies was saved from the unpublished
    # `ultralytics_bower` fork and cannot be loaded by official Ultralytics.
    YOLO_MODEL_PATH: str = str(BASE_DIR / "model" / "best_int8.onnx")
    DETECTION_THRESHOLD: float = 0.25
    REPORTS_DIR: str = str(BASE_DIR / "reports")
    GROQ_API_KEY: str = ""
    
    # Standard emission factors (kg CO2 saved per kg of recycled material)
    # Source: EPA WARM model and carbon offset estimation figures
    CO2_SAVINGS_FACTORS: dict = {
        "Plastic":      2.5,
        "Paper":        1.5,
        "Metal":        5.0,
        "Brown-glass":  0.8,
        "Green-glass":  0.8,
        "White-glass":  0.8,
        "Biological":   0.5,
        "Battery":      8.0,
        "Cardboard":    1.5,
        "Clothes":      3.0,
        "Shoes":        3.0,
        "E-Waste":      4.0,   # ADD
        "Trash":        0.1,
    }

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Create necessary directories
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.YOLO_MODEL_PATH), exist_ok=True)


import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger


import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from utils import settings

class NumberedCanvas(canvas.Canvas):
    """Canvas that computes total pages dynamically for footer page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#4B5563"))
        
        # Header (suppressed on page 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "EcoSort AI - Sustainability Analytics & Performance Report")
            self.setStrokeColor(colors.HexColor("#E5E7EB"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 40, footer_text)
        self.drawString(54, 40, "Confidential - EcoSort AI Platform Analytics")
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(54, 52, 558, 52)
        
        self.restoreState()


class ReportGenerator:
    @staticmethod
    def generate_pdf(timeframe_days: int = 30) -> str:
        # 1. ADD THE IMPORT HERE, INSIDE THE FUNCTION
        from database import Repository
        
        filename = f"ecosort_report_last_{timeframe_days}_days.pdf"
        filepath = os.path.join(settings.REPORTS_DIR, filename)
        
        # Pull data
        start_date = datetime.utcnow() - timedelta(days=timeframe_days)
        
        # 2. Now these lines will work without red errors!
        detections = Repository.get_detections(filters={"start_date": start_date}, limit=10000)
        summary = Repository.get_analytics_summary(days=timeframe_days)
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=72
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=26,
            leading=30,
            textColor=colors.HexColor('#1E3A8A'), # Deep Indigo
            spaceAfter=6
        )
        
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#4B5563'),
            spaceAfter=20
        )
        
        h1_style = ParagraphStyle(
            'SectionH1',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#111827'),
            spaceBefore=14,
            spaceAfter=10,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=10
        )
        
        bold_body_style = ParagraphStyle(
            'ReportBodyBold',
            parent=body_style,
            fontName='Helvetica-Bold'
        )

        story = []
        
        # --- COVER / TITLE ---
        story.append(Paragraph("EcoSort AI Analytics Report", title_style))
        story.append(Paragraph(
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Scope: Past {timeframe_days} Days Analytics",
            subtitle_style
        ))
        
        # Accent bar
        d_bar = Table([[""]], colWidths=[504], rowHeights=[4])
        d_bar.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#10B981')), # Emerald Accent
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(d_bar)
        story.append(Spacer(1, 15))
        
        # --- EXECUTIVE SUMMARY ---
        story.append(Paragraph("Executive Summary", h1_style))
        story.append(Paragraph(
            "This document presents a comprehensive summary of material detection, categorization, and environmental carbon offsets "
            "recorded by the EcoSort AI platform. By leveraging Computer Vision object detection, the platform tracks municipal waste stream "
            "components in real time to calculate active carbon reductions and monitor recycling efficiency metrics.",
            body_style
        ))
        
        # --- KPI TABLE ---
        story.append(Spacer(1, 10))
        kpi_data = [
            [
                Paragraph("<b>Total Scanned Items</b>", body_style),
                Paragraph("<b>Recycling Rate</b>", body_style),
                Paragraph("<b>Total Carbon Saved</b>", body_style),
                Paragraph("<b>Avg Confidence</b>", body_style)
            ],
            [
                Paragraph(f"<font size=14 color='#1E3A8A'><b>{summary['total_detections']}</b></font>", bold_body_style),
                Paragraph(f"<font size=14 color='#10B981'><b>{summary['recycling_rate_percent']}%</b></font>", bold_body_style),
                Paragraph(f"<font size=14 color='#D97706'><b>{summary['carbon_saved_kg']} kg CO₂</b></font>", bold_body_style),
                Paragraph(f"<font size=14 color='#4B5563'><b>{summary['average_confidence'] * 100:.1f}%</b></font>", bold_body_style)
            ]
        ]
        
        kpi_table = Table(kpi_data, colWidths=[126, 126, 126, 126])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 20))
        
        # --- CATEGORY DISTRIBUTION ---
        story.append(Paragraph("Material Composition Breakdown", h1_style))
        story.append(Paragraph(
            "Below is the breakdown of items identified and registered by the platform, organized by waste category.",
            body_style
        ))
        
        # Count by category
        cat_counts = {}
        cat_co2 = {}
        for det in detections:
            cat = det.get("category", "Other")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            cat_co2[cat] = cat_co2.get(cat, 0.0) + det.get("carbon_saved_kg", 0.0)
            
        dist_data = [
            [
                Paragraph("<b>Category</b>", bold_body_style),
                Paragraph("<b>Items Detected</b>", bold_body_style),
                Paragraph("<b>Share (%)</b>", bold_body_style),
                Paragraph("<b>Carbon Savings (kg CO₂)</b>", bold_body_style)
            ]
        ]
        
        total_items = max(1, len(detections))
        sorted_categories = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        for cat, count in sorted_categories:
            pct = (count / total_items) * 100
            dist_data.append([
                Paragraph(cat, body_style),
                Paragraph(str(count), body_style),
                Paragraph(f"{pct:.1f}%", body_style),
                Paragraph(f"{cat_co2.get(cat, 0):.2f}", body_style)
            ])
            
        dist_table = Table(dist_data, colWidths=[140, 100, 100, 164])
        dist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E5E7EB')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
        ]))
        story.append(dist_table)
        story.append(Spacer(1, 20))
        
        # --- CARBON FOOTPRINT PROJECTIONS ---
        story.append(Paragraph("Carbon Offsets Projections", h1_style))
        story.append(Paragraph(
            "Using standard material carbon coefficients, we project future carbon savings based on current sorting rates:",
            body_style
        ))
        
        daily_avg_co2 = summary['carbon_saved_kg'] / timeframe_days if timeframe_days > 0 else 0
        projection_data = [
            [Paragraph("<b>Timeframe</b>", bold_body_style), Paragraph("<b>Projected Carbon Reduction (kg CO₂)</b>", bold_body_style)],
            [Paragraph("Daily Average Offset", body_style), Paragraph(f"{daily_avg_co2:.2f} kg", body_style)],
            [Paragraph("Weekly Projected Offset", body_style), Paragraph(f"{daily_avg_co2 * 7:.2f} kg", body_style)],
            [Paragraph("Monthly Projected Offset", body_style), Paragraph(f"{daily_avg_co2 * 30:.2f} kg", body_style)],
            [Paragraph("Annual Projected Offset", body_style), Paragraph(f"{daily_avg_co2 * 365:.2f} kg", body_style)],
        ]
        proj_table = Table(projection_data, colWidths=[200, 304])
        proj_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(proj_table)
        story.append(Spacer(1, 20))
        
        # --- ACTIONABLE RECOMMENDATIONS ---
        story.append(Paragraph("Sustainability Action Plan", h1_style))
        story.append(Paragraph(
            "1. <b>Target High-Volume Materials:</b> Enhance staff training on packaging separation to capture more paper and plastic from general waste.<br/>"
            "2. <b>Expand E-waste Collection:</b> Implement designated pickup schedules for discarded chargers and laptops to recycle heavy metals safely.<br/>"
            "3. <b>Promote Organic Composting:</b> Food waste is compostable but organic material must be kept separated from plastic bags to prevent contamination.",
            body_style
        ))
        
        # Build PDF
        doc.build(story, canvasmaker=NumberedCanvas)
        return filepath
