#!/usr/bin/env python3
"""
McDade Insurance — Risk Management Division
Custom Proposal Generator
Dallas Downey / Risk Advisors of Iowa x McDade Insurance
"""

import io
import os
import re
import streamlit as st
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, PageBreak, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfWriter

W, H = letter

# ── Brand Colors ──────────────────────────────────────────────────────────────
NB  = colors.HexColor("#2D1B69")   # Dark Purple (McDade primary)
RD  = colors.HexColor("#4B2D9E")   # Medium Purple accent
GD  = colors.HexColor("#C8A951")   # Gold
LB  = colors.HexColor("#F3F0FF")   # Light purple bg
GR  = colors.HexColor("#6B7280")   # Gray
DG  = colors.HexColor("#1F2937")   # Dark gray
MG  = colors.HexColor("#374151")
LG  = colors.HexColor("#F3F4F6")
BG  = colors.HexColor("#E5E7EB")
WY  = colors.HexColor("#FFFBEB")
WB  = colors.HexColor("#C8A951")   # Gold warning border
WH  = colors.white
BK  = colors.black

# ─────────────────────────────────────────────────────────────────────────────
# PDF TEXT EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

def extract_pdf_text(uploaded_file) -> str:
    reader = PdfReader(io.BytesIO(uploaded_file.read()))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def parse_carrier_pdf(text: str) -> dict:
    """Best-effort regex extraction from carrier quote PDFs."""
    def find(patterns, default=""):
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return default

    data = {
        "carrier":    find([r"(?:carrier|company)[:\s]+([A-Z][\w\s&,\.]+?)(?:\n|\r|$)",
                            r"^([A-Z][\w\s&]+(?:Insurance|Mutual|Indemnity|Casualty|National)[\w\s,\.]*)",
                            r"insured by[:\s]+([\w\s&,\.]+?)(?:\n|$)"]),
        "quote_num":  find([r"quote\s*(?:number|#|no\.?)[:\s]+([\w\-]+)",
                            r"ref(?:erence)?[:\s#]+([\w\-]+)"]),
        "policy_period": find([r"policy\s*period[:\s]+([\d/\-]+\s*(?:to|--|through)?\s*[\d/\-]+)",
                               r"effective[:\s]+([\d/\-]+)"]),
        "total_premium": find([r"total\s*(?:annual\s*)?premium[:\s\$]+([\d,\.]+)",
                               r"(?:amount due|total payable)[:\s\$]+([\d,\.]+)",
                               r"premium[:\s\$]+([\d,]+\.\d{2})"]),
        "deductible":  find([r"deductible[:\s\$]+([\d,\.]+(?:\s*per\s*\w+)?)",
                             r"\$([\d,]+)\s+per\s+occurrence"]),
        "each_occurrence": find([r"each\s+occurrence[:\s\$]+([\d,]+(?:,\d{3})*)",
                                 r"per\s+occurrence\s+limit[:\s\$]+([\d,]+)"]),
        "general_aggregate": find([r"general\s+aggregate[:\s\$]+([\d,]+(?:,\d{3})*)",
                                   r"aggregate\s+limit[:\s\$]+([\d,]+)"]),
        "insured_name": find([r"(?:named\s+insured|insured)[:\s]+([A-Z][\w\s,\.&]+?)(?:\n|$)",
                              r"(?:applicant|account)[:\s]+([A-Z][\w\s,\.&]+?)(?:\n|$)"]),
        "coverage_type": find([r"(commercial\s+general\s+liability|workers.{0,5}comp(?:ensation)?|"
                                r"commercial\s+property|business\s+auto|umbrella|excess|professional\s+liability|"
                                r"cyber\s+liability|directors\s+and\s+officers|employment\s+practices)",]),
        "raw_text": text[:3000],
    }
    return data

# ─────────────────────────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────────────────────────

def build_styles():
    s = getSampleStyleSheet()
    defs = [
        ("SL",  dict(fontName="Helvetica-Bold", fontSize=7.5, textColor=GD,  spaceAfter=4, leading=10)),
        ("ET",  dict(fontName="Helvetica",      fontSize=10.5,textColor=MG,  leading=16,   spaceAfter=8)),
        ("IL",  dict(fontName="Helvetica-Bold", fontSize=7.5, textColor=GR,  leading=10,   spaceAfter=2)),
        ("IV",  dict(fontName="Helvetica-Bold", fontSize=11,  textColor=DG,  leading=14,   spaceAfter=6)),
        ("RT",  dict(fontName="Helvetica-Bold", fontSize=10,  textColor=NB,  leading=14,   spaceAfter=3)),
        ("RBs", dict(fontName="Helvetica",      fontSize=9.5, textColor=MG,  leading=14,   spaceAfter=2)),
        ("XT",  dict(fontName="Helvetica-Bold", fontSize=10,  textColor=DG,  leading=13,   spaceAfter=2)),
        ("XK",  dict(fontName="Helvetica-Oblique",fontSize=8.5,textColor=GR, leading=12,   spaceAfter=4)),
        ("XP",  dict(fontName="Helvetica",      fontSize=9.5, textColor=MG,  leading=14)),
        ("TH",  dict(fontName="Helvetica-Bold", fontSize=8,   textColor=WH,  leading=11)),
        ("SG",  dict(fontName="Helvetica",      fontSize=8,   textColor=GR,  leading=11)),
        ("PL",  dict(fontName="Helvetica-Bold", fontSize=8,   textColor=GR,  leading=10,   spaceAfter=2)),
        ("PB",  dict(fontName="Helvetica-Bold", fontSize=20,  textColor=NB,  leading=24)),
        ("WRN", dict(fontName="Helvetica",      fontSize=9.5, textColor=colors.HexColor("#92400E"), leading=14)),
        ("SIG", dict(fontName="Helvetica",      fontSize=9.5, textColor=MG,  leading=15)),
    ]
    for name, kw in defs:
        if name not in s:
            s.add(ParagraphStyle(name=name, **kw))
    return s

# ─────────────────────────────────────────────────────────────────────────────
# PAGE DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def make_page_deco(D, logo_path=None):
    def page_deco(c, doc):
        c.saveState()
        # Header bar
        c.setFillColor(WH); c.rect(0, H-44, W, 44, fill=1, stroke=0)
        c.setFillColor(RD); c.rect(0, H-47, W, 3, fill=1, stroke=0)
        if logo_path and os.path.exists(logo_path):
            try:
                img = ImageReader(logo_path)
                c.drawImage(img, 0.55*inch, H-40, width=120, height=32,
                            preserveAspectRatio=True, mask="auto")
            except:
                pass
        else:
            c.setFillColor(NB); c.setFont("Helvetica-Bold", 13)
            c.drawString(0.6*inch, H-28, "McDade Insurance")
            c.setFillColor(RD); c.setFont("Helvetica-Bold", 7)
            c.drawString(0.6*inch, H-40, "RISK MANAGEMENT DIVISION")
        c.setFillColor(GR); c.setFont("Helvetica", 9)
        c.drawRightString(W-0.6*inch, H-22, f"{D['cn']} | {D.get('coverage_type','Insurance')} Proposal")
        c.setFillColor(GR); c.setFont("Helvetica", 8)
        ref_str = f"{D.get('ca','Carrier')} | Ref: {D.get('ref','N/A')} | Expires {D.get('qe','N/A')}"
        c.drawRightString(W-0.6*inch, H-36, ref_str)
        # Footer
        c.setFillColor(LG); c.rect(0, 0, W, 34, fill=1, stroke=0)
        c.setFillColor(RD); c.rect(0, 34, W, 1.5, fill=1, stroke=0)
        c.setFillColor(GR); c.setFont("Helvetica", 7.5)
        c.drawString(0.6*inch, 12, "McDade Insurance • Risk Management Division • Houston, TX | Des Moines, IA • Confidential")
        c.drawRightString(W-0.6*inch, 12, f"Page {doc.page}")
        c.restoreState()
    return page_deco

# ─────────────────────────────────────────────────────────────────────────────
# COVER PAGE
# ─────────────────────────────────────────────────────────────────────────────

def draw_cover(D, logo_path=None) -> bytes:
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=letter)
    # Background
    c.setFillColor(WH); c.rect(0, 0, W, H, fill=1, stroke=0)
    # Left accent bar — navy
    c.setFillColor(NB); c.rect(0, 0, 6, H, fill=1, stroke=0)
    # Top right red accent
    c.setFillColor(RD); c.rect(0, H-6, W, 6, fill=1, stroke=0)

    # Logo / Agency name
    if logo_path and os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            c.drawImage(img, 52, H-115, width=270, height=90,
                        preserveAspectRatio=True, mask="auto")
        except:
            logo_path = None
    if not logo_path or not os.path.exists(logo_path or ""):
        c.setFillColor(NB); c.setFont("Helvetica-Bold", 30)
        c.drawString(52, H-80, "McDade Insurance")
        c.setFillColor(RD); c.setFont("Helvetica-Bold", 11)
        c.drawString(52, H-98, "RISK MANAGEMENT DIVISION")

    # Top-right tagline
    c.setFillColor(GR); c.setFont("Helvetica", 8)
    c.drawRightString(W-52, H-52, f"{D.get('coverage_type','Commercial Insurance').upper()} PROPOSAL")
    c.setFillColor(GD); c.setFont("Helvetica-Bold", 8)
    c.drawRightString(W-52, H-66, "Prepared by McDade Insurance — Risk Management Division")

    # Gold rule
    c.setStrokeColor(GD); c.setLineWidth(2); c.line(52, H-115, W-52, H-115)

    # Client name (large)
    c.setFillColor(NB); c.setFont("Helvetica-Bold", 38)
    # Wrap long names
    cn = D["cn"]
    c.drawString(52, H-165, cn[:40])
    if len(cn) > 40:
        c.setFont("Helvetica-Bold", 28)
        c.drawString(52, H-195, cn[40:80])

    c.setFillColor(GR); c.setFont("Helvetica", 11)
    c.drawString(52, H-185, D.get("addr", ""))
    c.setFillColor(GR); c.setFont("Helvetica", 13)
    c.drawString(52, H-207, f"{D.get('coverage_type','Insurance')} Proposal — Prepared Exclusively for You")

    # Gold rule
    c.setStrokeColor(GD); c.setLineWidth(2); c.line(52, H-221, W-52, H-221)

    # Info boxes
    boxes = [
        ("CARRIER", D.get("ca", "TBD")),
        ("QUOTE #",  D.get("ref", "TBD")),
        ("POLICY PERIOD", D.get("pp", "TBD")),
        ("TOTAL PAYABLE",  D.get("tot", "TBD")),
    ]
    bx = 52; bw = (W-104-18)/4; by = H-360
    for idx, (label, val) in enumerate(boxes):
        is_total = idx == 3
        c.setFillColor(NB if is_total else colors.HexColor("#F8F9FC"))
        c.roundRect(bx, by, bw-6, 85, 5, fill=1, stroke=0)
        c.setFillColor(RD if is_total else GD)
        c.rect(bx, by+81, bw-6, 4, fill=1, stroke=0)
        if not is_total:
            c.setStrokeColor(BG); c.setLineWidth(0.5)
            c.roundRect(bx, by, bw-6, 85, 5, fill=0, stroke=1)
        c.setFillColor(WH if is_total else GR)
        c.setFont("Helvetica-Bold", 7); c.drawString(bx+10, by+66, label)
        c.setFillColor(WH if is_total else NB)
        lines = str(val).split("\n")
        fs = 13 if is_total else 10
        c.setFont("Helvetica-Bold", fs)
        yv = by+48
        for ln in lines:
            c.drawString(bx+10, yv, ln); yv -= 15
        bx += bw+6

    # Coverage highlights
    highlights = [
        (D.get("each_occurrence","$1,000,000"), "Each Occurrence"),
        (D.get("general_aggregate","$2,000,000"), "General Aggregate"),
        (D.get("deductible","TBD"), "Deductible"),
        (D.get("tot","TBD"), "Total Premium"),
    ]
    hx = 52; hw = (W-104-18)/4; hy = H-500
    for stat, label in highlights:
        c.setFillColor(colors.HexColor("#F8F9FC"))
        c.roundRect(hx, hy, hw-6, 75, 5, fill=1, stroke=0)
        c.setStrokeColor(BG); c.setLineWidth(0.5)
        c.roundRect(hx, hy, hw-6, 75, 5, fill=0, stroke=1)
        c.setFillColor(NB); c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(hx+(hw-6)/2, hy+42, str(stat)[:14])
        c.setFillColor(GR); c.setFont("Helvetica", 8)
        c.drawCentredString(hx+(hw-6)/2, hy+26, label)
        hx += hw+6

    # Footer bar
    c.setFillColor(NB); c.rect(0, 0, W, 56, fill=1, stroke=0)
    c.setFillColor(RD); c.rect(0, 56, W, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#8B9CC8")); c.setFont("Helvetica", 8.5)
    c.drawString(52, 22, "McDade Insurance • Risk Management Division • Houston, TX  |  Des Moines, IA via Risk Advisors of Iowa")
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawRightString(W-52, 22, f"This proposal is confidential and prepared exclusively for {D['cn']}")

    c.save()
    return buf.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# BODY BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_body(D, logo_path=None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.75*inch, bottomMargin=0.6*inch)
    s = build_styles()
    story = []
    uw = W - 1.2*inch

    def sec_hdr(num, title):
        nc = Table([[Paragraph(str(num), ParagraphStyle("SN", fontName="Helvetica-Bold",
                    fontSize=14, textColor=WH, alignment=TA_CENTER, leading=18))]],
                   colWidths=[30], rowHeights=[30],
                   style=TableStyle([("BACKGROUND",(0,0),(-1,-1),NB),
                                     ("TOPPADDING",(0,0),(-1,-1),5),
                                     ("LEFTPADDING",(0,0),(-1,-1),0)]))
        t = Table([[nc, Paragraph(title.upper(), ParagraphStyle("SHT",
                   fontName="Helvetica-Bold", fontSize=13, textColor=NB, leading=18))]],
                  colWidths=[40, uw-40])
        t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                               ("LEFTPADDING",(0,0),(-1,-1),0),
                               ("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("TOPPADDING",(0,0),(-1,-1),0),
                               ("BOTTOMPADDING",(0,0),(-1,-1),0),
                               ("LINEBELOW",(0,0),(-1,-1),2,GD)]))
        return t

    def blue_box(para):
        t = Table([[para]], colWidths=[uw])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LB),
                               ("BOX",(0,0),(-1,-1),1,BG),
                               ("LINEBEFORE",(0,0),(0,-1),4,NB),
                               ("LEFTPADDING",(0,0),(-1,-1),14),
                               ("RIGHTPADDING",(0,0),(-1,-1),14),
                               ("TOPPADDING",(0,0),(-1,-1),12),
                               ("BOTTOMPADDING",(0,0),(-1,-1),12)]))
        return t

    def gold_box(para):
        t = Table([[para]], colWidths=[uw])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LB),
                               ("BOX",(0,0),(-1,-1),1,BG),
                               ("LINEBEFORE",(0,0),(0,-1),4,GD),
                               ("LEFTPADDING",(0,0),(-1,-1),14),
                               ("RIGHTPADDING",(0,0),(-1,-1),14),
                               ("TOPPADDING",(0,0),(-1,-1),12),
                               ("BOTTOMPADDING",(0,0),(-1,-1),12)]))
        return t

    # ── SECTION 1: Client & Risk Summary ─────────────────────────────────────
    story.append(sec_hdr(1, "Client & Risk Summary")); story.append(Spacer(1,14))
    pairs = [
        ("INSURED BUSINESS",  D.get("cn","N/A")),
        ("BUSINESS TYPE",     D.get("bt","N/A")),
        ("ADDRESS",           D.get("addr","N/A")),
        ("CARRIER / MGA",     D.get("ca","N/A")),
        ("QUOTE NUMBER",      D.get("ref","N/A")),
        ("UNDERWRITER",       D.get("uw","N/A")),
        ("COVERAGE TYPE",     D.get("coverage_type","N/A")),
        ("DEDUCTIBLE",        D.get("ded","N/A")),
        ("POLICY PERIOD",     D.get("pp","N/A")),
        ("QUOTE EXPIRATION",  D.get("qe","N/A")),
        ("EXPOSURE BASIS",    D.get("exp","N/A")),
        ("TERRITORY",         D.get("ter","N/A")),
    ]
    cs = [(uw-8)/2, 8, (uw-8)/2]
    grid_rows = []
    for i in range(0, len(pairs), 2):
        l, r = pairs[i], pairs[i+1]
        even = i//2 % 2 == 0
        bg = LB if even else colors.HexColor("#FAFBFF")
        lt = Table([[Paragraph(l[0], s["IL"])], [Paragraph(str(l[1]), s["IV"])]], colWidths=[(uw-8)/2])
        rt = Table([[Paragraph(r[0], s["IL"])], [Paragraph(str(r[1]), s["IV"])]], colWidths=[(uw-8)/2])
        for t2 in [lt, rt]:
            t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),
                                    ("LINEBEFORE",(0,0),(0,-1),3,NB),
                                    ("LEFTPADDING",(0,0),(-1,-1),10),
                                    ("RIGHTPADDING",(0,0),(-1,-1),8),
                                    ("TOPPADDING",(0,0),(-1,-1),6),
                                    ("BOTTOMPADDING",(0,0),(-1,-1),6),
                                    ("BOX",(0,0),(-1,-1),0.5,BG)]))
        grid_rows.append([lt, Spacer(8,1), rt])
    grid = Table(grid_rows, colWidths=cs)
    grid.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),
                               ("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("TOPPADDING",(0,0),(-1,-1),3),
                               ("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(grid); story.append(Spacer(1,12))

    story.append(Paragraph("RISK PROFILE", s["SL"]))
    story.append(blue_box(Paragraph(D.get("rs","Risk profile not provided."), s["ET"])))
    story.append(PageBreak())

    # ── SECTION 2: Executive Summary ─────────────────────────────────────────
    story.append(sec_hdr(2, "Executive Summary & Recommendations")); story.append(Spacer(1,14))
    story.append(Paragraph("OVERVIEW", s["SL"]))
    story.append(gold_box(Paragraph(D.get("es","Executive summary not provided."), s["ET"])))
    story.append(Spacer(1,16))

    recs = D.get("recs", [])
    if recs:
        story.append(Paragraph(f"KEY RECOMMENDATIONS FOR {D.get('cn','CLIENT').upper()}", s["SL"]))
        story.append(Spacer(1,8))
        for i, (title, body) in enumerate(recs, 1):
            nc = Table([[Paragraph(str(i), ParagraphStyle("RN", fontName="Helvetica-Bold",
                         fontSize=12, textColor=BK, alignment=TA_CENTER, leading=16))]],
                       colWidths=[26], rowHeights=[26],
                       style=TableStyle([("BACKGROUND",(0,0),(-1,-1),GD),
                                         ("TOPPADDING",(0,0),(-1,-1),4),
                                         ("LEFTPADDING",(0,0),(-1,-1),0)]))
            row = Table([[nc, [Paragraph(title, s["RT"]), Paragraph(body, s["RBs"])]]],
                        colWidths=[36, uw-36])
            row.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                     ("LEFTPADDING",(0,0),(-1,-1),0),
                                     ("RIGHTPADDING",(0,0),(-1,-1),0),
                                     ("TOPPADDING",(0,0),(-1,-1),6),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),6),
                                     ("LINEBELOW",(0,0),(-1,-1),0.5,BG)]))
            story.append(row)
    story.append(PageBreak())

    # ── SECTION 3: Coverage Details ───────────────────────────────────────────
    story.append(sec_hdr(3, "Coverage Details")); story.append(Spacer(1,14))
    covs = D.get("covs", [])
    if covs:
        story.append(Paragraph("SCHEDULE OF COVERAGE LIMITS", s["SL"])); story.append(Spacer(1,6))
        chdr = [Paragraph(t, s["TH"]) for t in ["COVERAGE LINE", "LIMIT", "DEDUCTIBLE"]]
        crow = [chdr]
        for name, limit, ded in covs:
            ns = ParagraphStyle("cn", fontName="Helvetica-Bold", fontSize=9, textColor=DG, leading=12)
            ls = ParagraphStyle("cl", fontName="Helvetica-Bold", fontSize=9, textColor=NB, leading=12)
            ds = ParagraphStyle("cd", fontName="Helvetica", fontSize=8.5, textColor=GR, leading=12)
            crow.append([Paragraph(name,ns), Paragraph(limit,ls), Paragraph(ded,ds)])
        ct = Table(crow, colWidths=[uw*0.50, uw*0.28, uw*0.22])
        rs2 = [("BACKGROUND",(0,0),(-1,0),NB),
               ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
               ("LEFTPADDING",(0,0),(-1,-1),10), ("RIGHTPADDING",(0,0),(-1,-1),10),
               ("LINEBELOW",(0,0),(-1,-2),0.5,BG), ("BOX",(0,0),(-1,-1),1,BG),
               ("VALIGN",(0,0),(-1,-1),"TOP")]
        for i in range(1, len(crow), 2):
            rs2.append(("BACKGROUND",(0,i),(-1,i),LG))
        ct.setStyle(TableStyle(rs2)); story.append(ct); story.append(Spacer(1,16))

    # Audit / pricing note
    if D.get("audit_note"):
        at = Table([[Paragraph(D["audit_note"], ParagraphStyle("AN", fontName="Helvetica",
                    fontSize=9.5, textColor=colors.HexColor("#92400E"), leading=14))]],
                   colWidths=[uw])
        at.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WY),
                                ("BOX",(0,0),(-1,-1),1,WB),
                                ("LINEBEFORE",(0,0),(0,-1),4,WB),
                                ("LEFTPADDING",(0,0),(-1,-1),14),
                                ("RIGHTPADDING",(0,0),(-1,-1),14),
                                ("TOPPADDING",(0,0),(-1,-1),10),
                                ("BOTTOMPADDING",(0,0),(-1,-1),10)]))
        story.append(at)
    story.append(PageBreak())

    # ── SECTION 4: Exclusions ─────────────────────────────────────────────────
    excls = D.get("excls", [])
    if excls:
        story.append(sec_hdr(4, "Policy Exclusions — Read & Acknowledge")); story.append(Spacer(1,12))
        wt = Table([[Paragraph("<b>IMPORTANT:</b> The following are conditions and situations this policy will "
                               "<b>NOT cover</b>. Read each carefully. Your signature at the bottom confirms "
                               "you have reviewed and understood all exclusions. Questions? Ask your McDade "
                               "Insurance advisor before binding.", s["WRN"])]], colWidths=[uw])
        wt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WY),
                                ("BOX",(0,0),(-1,-1),1.5,WB),
                                ("LEFTPADDING",(0,0),(-1,-1),14),
                                ("RIGHTPADDING",(0,0),(-1,-1),14),
                                ("TOPPADDING",(0,0),(-1,-1),10),
                                ("BOTTOMPADDING",(0,0),(-1,-1),10)]))
        story.append(wt); story.append(Spacer(1,12))

        for i, (title, tech, plain) in enumerate(excls, 1):
            badge = Table([[Paragraph("EXCLUDED", ParagraphStyle("B", fontName="Helvetica-Bold",
                           fontSize=7, textColor=BK, leading=9))]],
                          colWidths=[54], rowHeights=[16],
                          style=TableStyle([("BACKGROUND",(0,0),(-1,-1),RD),
                                            ("TOPPADDING",(0,0),(-1,-1),3),
                                            ("BOTTOMPADDING",(0,0),(-1,-1),3),
                                            ("LEFTPADDING",(0,0),(-1,-1),6),
                                            ("RIGHTPADDING",(0,0),(-1,-1),6)]))
            hdr = Table([[badge, Paragraph(f"{i}. {title}", s["XT"])]], colWidths=[64, uw-64])
            hdr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LG),
                                     ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                     ("LEFTPADDING",(0,0),(-1,-1),10),
                                     ("RIGHTPADDING",(0,0),(-1,-1),10),
                                     ("TOPPADDING",(0,0),(-1,-1),8),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
            tech_t = Table([[Paragraph(f"Policy language: {tech}", s["XK"])]], colWidths=[uw])
            tech_t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),14),
                                         ("RIGHTPADDING",(0,0),(-1,-1),14),
                                         ("TOPPADDING",(0,0),(-1,-1),6),
                                         ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            pe_lbl = Paragraph("PLAIN ENGLISH — What This Means For You:",
                               ParagraphStyle("PE", fontName="Helvetica-Bold", fontSize=7.5, textColor=GD, leading=10))
            pe_txt = Paragraph(plain, s["XP"])
            pe_in  = Table([[pe_lbl],[pe_txt]], colWidths=[uw-28])
            pe_in.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),10),
                                        ("RIGHTPADDING",(0,0),(-1,-1),10),
                                        ("TOPPADDING",(0,0),(-1,-1),4),
                                        ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
            pe_out = Table([[pe_in]], colWidths=[uw])
            pe_out.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WY),
                                         ("LINEBEFORE",(0,0),(0,-1),3,GD),
                                         ("LEFTPADDING",(0,0),(-1,-1),4),
                                         ("RIGHTPADDING",(0,0),(-1,-1),4),
                                         ("TOPPADDING",(0,0),(-1,-1),4),
                                         ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            sep = Table([[" "]], colWidths=[uw], rowHeights=[8],
                        style=TableStyle([("LINEBELOW",(0,0),(-1,-1),1,BG)]))
            story.append(KeepTogether([hdr, tech_t, pe_out, sep, Spacer(1,6)]))

        # Signature block
        story.append(Spacer(1,14))
        sh = Table([[Paragraph("EXCLUSION ACKNOWLEDGMENT & SIGNATURE",
                    ParagraphStyle("SH2", fontName="Helvetica-Bold", fontSize=11, textColor=NB, leading=14))]],
                   colWidths=[uw])
        sh.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LB),
                                ("BOX",(0,0),(-1,-1),2,NB),
                                ("LINEBEFORE",(0,0),(0,-1),5,NB),
                                ("LEFTPADDING",(0,0),(-1,-1),14),
                                ("TOPPADDING",(0,0),(-1,-1),12),
                                ("BOTTOMPADDING",(0,0),(-1,-1),12)]))
        story.append(sh); story.append(Spacer(1,10))
        story.append(Paragraph(
            "By signing below, I confirm that I have <b>read, understood, and received</b> a copy of all policy "
            "exclusions listed above. I acknowledge these situations are <b>NOT covered</b> by this policy, "
            "and I have had the opportunity to ask questions of my McDade Insurance advisor prior to signing.",
            s["SIG"]))
        story.append(Spacer(1,22))
        cw = [uw*0.38, uw*0.04, uw*0.35, uw*0.04, uw*0.19]
        def sig_col(label, w):
            t = Table([[Paragraph(label, s["IL"])], [Spacer(1,26)],
                       [HRFlowable(width=w, thickness=1.5, color=NB)]], colWidths=[w])
            t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),
                                   ("RIGHTPADDING",(0,0),(-1,-1),0),
                                   ("TOPPADDING",(0,0),(-1,-1),0),
                                   ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
            return t
        for labels in [["INSURED SIGNATURE","PRINTED NAME","DATE"],
                       ["BROKER / ADVISOR SIGNATURE","PRINTED NAME & LICENSE #","DATE"]]:
            row = Table([[sig_col(labels[0],cw[0]), Spacer(cw[1],1),
                          sig_col(labels[1],cw[2]), Spacer(cw[3],1),
                          sig_col(labels[2],cw[4])]], colWidths=cw)
            row.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),
                                     ("LEFTPADDING",(0,0),(-1,-1),0),
                                     ("RIGHTPADDING",(0,0),(-1,-1),0),
                                     ("TOPPADDING",(0,0),(-1,-1),0),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
            story.append(row); story.append(Spacer(1,22))

    # ── CONFIDENTIALITY PAGE ──────────────────────────────────────────────────
    story.append(PageBreak())
    conf_hdr = Table([[Paragraph("CONFIDENTIALITY NOTICE",
                       ParagraphStyle("CHT", fontName="Helvetica-Bold", fontSize=13, textColor=NB, leading=18))]],
                     colWidths=[uw])
    conf_hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                   ("LEFTPADDING",(0,0),(-1,-1),0),
                                   ("TOPPADDING",(0,0),(-1,-1),0),
                                   ("BOTTOMPADDING",(0,0),(-1,-1),0),
                                   ("LINEBELOW",(0,0),(-1,-1),2,GD)]))
    story.append(conf_hdr); story.append(Spacer(1,14))
    notice_text = (
        f"This proposal has been prepared exclusively by <b>McDade Insurance — Risk Management Division</b> "
        f"for the sole use of <b>{D.get('cn','the named insured')}</b>. It contains proprietary methodologies, "
        "coverage analysis, market placement strategies, pricing structures, and intellectual work product "
        "that are the exclusive property of McDade Insurance."
    )
    nb2 = Table([[Paragraph(notice_text, ParagraphStyle("NT", fontName="Helvetica", fontSize=10.5,
                 textColor=MG, leading=16))]], colWidths=[uw])
    nb2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LB),
                              ("BOX",(0,0),(-1,-1),1,BG),
                              ("LINEBEFORE",(0,0),(0,-1),4,NB),
                              ("LEFTPADDING",(0,0),(-1,-1),14),
                              ("RIGHTPADDING",(0,0),(-1,-1),14),
                              ("TOPPADDING",(0,0),(-1,-1),12),
                              ("BOTTOMPADDING",(0,0),(-1,-1),12)]))
    story.append(nb2); story.append(Spacer(1,16))

    terms = [
        ("Prohibited Use",
         "This proposal may not be shared with, forwarded to, or reproduced for any competing insurance "
         "agency, broker, carrier, MGA, or third party without the prior written consent of McDade Insurance."),
        ("Prohibited Disclosure",
         "The recipient may not use the contents of this proposal to solicit competing quotes by sharing its "
         "structure, pricing benchmarks, or coverage terms with any other agency or broker."),
        ("$10,000 Penalty for Breach",
         "Any unauthorized sharing, distribution, or use of this proposal — in whole or in part — with a "
         "competitor of McDade Insurance will result in a minimum liquidated damages claim of "
         "<b>$10,000 (ten thousand dollars)</b> per occurrence."),
        ("Permitted Use",
         f"This document is provided solely for the internal review and decision-making of "
         f"{D.get('cn','the named insured')}'s authorized representatives."),
    ]
    for i, (title, body) in enumerate(terms):
        is_penalty = "Penalty" in title
        bg = colors.HexColor("#FFF8E1") if is_penalty else colors.HexColor("#F8F9FC")
        border = GD if is_penalty else BG
        left_bar = GD if is_penalty else NB
        title_color = colors.HexColor("#92400E") if is_penalty else NB
        tp = Paragraph(title, ParagraphStyle("TT", fontName="Helvetica-Bold", fontSize=10,
                        textColor=title_color, leading=14, spaceAfter=4))
        bp = Paragraph(body, ParagraphStyle("TB", fontName="Helvetica", fontSize=9.5,
                        textColor=MG, leading=14))
        t = Table([[tp],[bp]], colWidths=[uw])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),
                               ("BOX",(0,0),(-1,-1),1,border),
                               ("LINEBEFORE",(0,0),(0,-1),4,left_bar),
                               ("LEFTPADDING",(0,0),(-1,-1),14),
                               ("RIGHTPADDING",(0,0),(-1,-1),14),
                               ("TOPPADDING",(0,0),(-1,-1),10),
                               ("BOTTOMPADDING",(0,0),(-1,-1),10)]))
        story.append(t); story.append(Spacer(1,8))

    page_deco = make_page_deco(D, logo_path)
    doc.build(story, onFirstPage=page_deco, onLaterPages=page_deco)
    return buf.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLE FINAL PDF
# ─────────────────────────────────────────────────────────────────────────────

def assemble_pdf(D, logo_path=None, carrier_pdfs=None) -> bytes:
    writer = PdfWriter()
    for section_bytes in [draw_cover(D, logo_path), build_body(D, logo_path)]:
        r = PdfReader(io.BytesIO(section_bytes))
        for pg in r.pages:
            writer.add_page(pg)
    # Append raw carrier quotes if uploaded
    if carrier_pdfs:
        for cpdf_bytes in carrier_pdfs:
            r = PdfReader(io.BytesIO(cpdf_bytes))
            for pg in r.pages:
                writer.add_page(pg)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="McDade Insurance — Proposal Generator",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── CSS ───────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2D1B69 0%, #4B2D9E 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        border-left: 6px solid #C8A951;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p  { color: #C8A951; margin: 0.3rem 0 0 0; font-size: 0.95rem; }
    .section-card {
        background: #f8f9fc;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #2D1B69;
    }
    .parsed-badge {
        background: #d1fae5;
        color: #065f46;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .stButton>button {
        background: #2D1B69;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 700;
        padding: 0.5rem 2rem;
        font-size: 1rem;
    }
    .stButton>button:hover { background: #C8A951; color: #2D1B69; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>📋 McDade Insurance — Risk Management Division</h1>
        <p>Custom Proposal Generator | Houston, TX · Des Moines, IA via Risk Advisors of Iowa</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.image("https://via.placeholder.com/240x80/2D1B69/C8A951?text=McDade+Insurance",
                 use_column_width=True)
        st.markdown("---")
        st.markdown("### 📤 Upload Carrier Quote(s)")
        carrier_files = st.file_uploader(
            "Upload carrier PDFs to auto-populate fields",
            type=["pdf"],
            accept_multiple_files=True,
            help="Upload one or more carrier quote PDFs. The app will extract key data automatically."
        )
        st.markdown("---")
        st.markdown("### 🖼️ Agency Logo")
        logo_file = st.file_uploader("Upload your agency logo (PNG/JPG)", type=["png","jpg","jpeg"])
        st.markdown("---")
        st.markdown("### 📎 Append Carrier PDFs")
        append_carrier = st.checkbox("Append raw carrier quotes to proposal", value=False,
                                     help="Appends the uploaded carrier PDFs as supporting exhibits.")
        st.markdown("---")
        st.markdown("""
        <small style='color:#6B7280'>
        McDade Insurance · Risk Management<br>
        Houston TX · Des Moines IA<br>
        <em>Dallas Downey | Risk Advisors of Iowa</em>
        </small>
        """, unsafe_allow_html=True)

    # ── Parse uploaded carrier PDFs ───────────────────────────────────────────
    parsed = {}
    carrier_pdf_bytes_list = []

    if carrier_files:
        all_text = ""
        for cf in carrier_files:
            try:
                text = extract_pdf_text(cf)
                all_text += text
                cf.seek(0)
                carrier_pdf_bytes_list.append(cf.read())
            except Exception as e:
                st.warning(f"Could not parse {cf.name}: {e}")
        parsed = parse_carrier_pdf(all_text)
        st.success(f"✅ Parsed {len(carrier_files)} carrier PDF(s). Review and edit fields below.")

    # ── Save logo ─────────────────────────────────────────────────────────────
    logo_path = None
    if logo_file:
        logo_path = f"/tmp/mcdade_logo_{logo_file.name}"
        with open(logo_path, "wb") as f:
            f.write(logo_file.read())

    # ── Main Form ─────────────────────────────────────────────────────────────
    st.markdown("## 📝 Proposal Details")
    st.caption("Fields auto-populated from carrier PDFs where possible. Edit anything before generating.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### 🏢 Client Information")
        cn   = st.text_input("Client / Insured Name *", value=parsed.get("insured_name",""))
        addr = st.text_input("Business Address", value="")
        bt   = st.text_input("Business Type / Industry", value="")
        ter  = st.text_input("Territory / State(s)", value="Texas" if not parsed.get("ter") else parsed.get("ter",""))
        exp  = st.text_input("Exposure Basis (e.g. $5M Gross Sales)", value=parsed.get("exp",""))
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### 📄 Quote & Policy Info")
        ca   = st.text_input("Carrier / MGA", value=parsed.get("carrier",""))
        ref  = st.text_input("Quote / Reference Number", value=parsed.get("quote_num",""))
        uw   = st.text_input("Underwriter", value="")
        pp   = st.text_input("Policy Period", value=parsed.get("policy_period",""))
        qe   = st.text_input("Quote Expiration Date", value="")
        cov_type = st.text_input("Coverage Type",
                                  value=parsed.get("coverage_type","Commercial General Liability"))
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### 💰 Premium & Limits")
        tot  = st.text_input("Total Annual Premium *", value=parsed.get("total_premium",""))
        ded  = st.text_input("Deductible", value=parsed.get("deductible",""))
        each_occ = st.text_input("Each Occurrence Limit", value=parsed.get("each_occurrence","$1,000,000"))
        gen_agg  = st.text_input("General Aggregate Limit", value=parsed.get("general_aggregate","$2,000,000"))
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### 📊 Coverage Schedule")
        st.caption("Enter coverage lines (one per row: Coverage, Limit, Deductible)")
        covs_raw = st.text_area(
            "Coverage Lines (pipe-separated: Coverage|Limit|Deductible)",
            value="General Aggregate|$2,000,000|N/A\nEach Occurrence|$1,000,000|Per Deductible\nPersonal & Advertising Injury|$1,000,000|Per Deductible\nMedical Payments|$5,000|None",
            height=120
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    col5, col6 = st.columns(2)
    with col5:
        st.markdown("#### 📋 Risk Profile")
        rs = st.text_area("Risk Summary (auto-write or paste in)",
            value=f"{cn if cn else '[Client Name]'} is a business operating in {ter if ter else 'Texas/Iowa'}. " +
                  "This placement addresses the key liability and risk exposures specific to their operations.",
            height=120)

    with col6:
        st.markdown("#### 📌 Executive Summary")
        es = st.text_area("Executive Summary / Overview",
            value=f"McDade Insurance — Risk Management Division is pleased to present this {cov_type if cov_type else 'insurance'} proposal "
                  f"for {cn if cn else '[Client Name]'}. This coverage has been carefully selected to address "
                  "the specific risk exposures of your business at a competitive premium.",
            height=120)

    st.markdown("---")
    st.markdown("#### 💡 Key Recommendations")
    st.caption("Enter recommendations (one per row: Title | Body text)")
    recs_raw = st.text_area(
        "Recommendations (pipe-separated: Title|Body)",
        value="Review Your Deductible Strategy|Higher deductibles can reduce premium but increase out-of-pocket exposure. Work with your advisor to align deductibles with your cash flow capacity.\nUnderstand Your Audit Obligations|This policy may be subject to annual audit. Keep clean financial records and notify McDade Insurance of material revenue changes throughout the year.\nAdditional Insured Compliance|Ensure all contracts are reviewed for AI requirements. Blanket AI endorsements protect you without needing individual certificates for every relationship.",
        height=100
    )

    st.markdown("#### ⛔ Policy Exclusions")
    st.caption("Enter exclusions (pipe-separated: Title|Policy Language|Plain English Explanation)")
    excls_raw = st.text_area(
        "Exclusions",
        value="Intentional Acts|Standard CGL exclusion for expected or intended injury|Coverage does not apply to damage or injury you intentionally cause. This is standard across all GL policies.\nProfessional Services|Professional services exclusion endorsement|If you provide professional advice or consulting and a claim arises from that advice, this GL policy will not respond. A separate E&O policy may be needed.",
        height=100
    )

    st.markdown("#### 📝 Audit / Pricing Note (optional)")
    audit_note = st.text_input("Audit or Pricing Note",
        value="This policy may be subject to annual audit. Final premium is subject to adjustment based on actual exposure at policy expiration.")

    # ── Generate ──────────────────────────────────────────────────────────────
    st.markdown("---")
    col_gen1, col_gen2, col_gen3 = st.columns([1,2,1])
    with col_gen2:
        generate = st.button("🚀 Generate Proposal PDF", use_container_width=True)

    if generate:
        if not cn:
            st.error("⚠️ Client / Insured Name is required.")
        elif not tot:
            st.error("⚠️ Total Annual Premium is required.")
        else:
            # Parse coverage lines
            covs = []
            for line in covs_raw.strip().split("\n"):
                parts = line.split("|")
                if len(parts) == 3:
                    covs.append(tuple(p.strip() for p in parts))

            # Parse recommendations
            recs = []
            for line in recs_raw.strip().split("\n"):
                parts = line.split("|")
                if len(parts) == 2:
                    recs.append((parts[0].strip(), parts[1].strip()))

            # Parse exclusions
            excls = []
            for line in excls_raw.strip().split("\n"):
                parts = line.split("|")
                if len(parts) == 3:
                    excls.append(tuple(p.strip() for p in parts))

            D = {
                "cn":            cn,
                "addr":          addr,
                "bt":            bt,
                "pp":            pp,
                "qe":            qe,
                "ca":            ca,
                "ref":           ref,
                "uw":            uw,
                "ded":           ded,
                "ter":           ter,
                "coverage_type": cov_type,
                "exp":           exp,
                "tot":           f"${tot}" if tot and not tot.startswith("$") else tot,
                "each_occurrence": each_occ,
                "general_aggregate": gen_agg,
                "rs":            rs,
                "es":            es,
                "recs":          recs,
                "covs":          covs,
                "excls":         excls,
                "audit_note":    audit_note,
            }

            with st.spinner("Building your proposal..."):
                try:
                    carrier_bytes = carrier_pdf_bytes_list if append_carrier else None
                    pdf_bytes = assemble_pdf(D, logo_path=logo_path, carrier_pdfs=carrier_bytes)
                    filename = f"McDade_Proposal_{cn.replace(' ','_')[:40]}.pdf"
                    st.success("✅ Proposal generated successfully!")
                    st.download_button(
                        label="📥 Download Proposal PDF",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {e}")
                    import traceback; st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
