#!/usr/bin/env python3
"""
McDade Insurance — Risk Management Division
Multi-Line Proposal Generator
Dallas Downey / Risk Advisors of Iowa x McDade Insurance
"""

import io, os, re
import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, PageBreak, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader

W, H = letter

# ── Brand Colors ──────────────────────────────────────────────────────────────
NB  = colors.HexColor("#2D1B69")   # Dark Purple
AC  = colors.HexColor("#4B2D9E")   # Medium Purple accent
GD  = colors.HexColor("#C8A951")   # Gold
LB  = colors.HexColor("#F3F0FF")   # Light purple bg
GR  = colors.HexColor("#6B7280")
DG  = colors.HexColor("#1F2937")
MG  = colors.HexColor("#374151")
LG  = colors.HexColor("#F3F4F6")
BG  = colors.HexColor("#E5E7EB")
WY  = colors.HexColor("#FFFBEB")
WB  = colors.HexColor("#C8A951")
WH  = colors.white
BK  = colors.black

# LOB color accents (one per line of business)
LOB_COLORS = {
    "General Liability":      colors.HexColor("#2D1B69"),
    "Workers Compensation":   colors.HexColor("#065f46"),
    "Umbrella / Excess":      colors.HexColor("#1e3a5f"),
    "Cyber Liability":        colors.HexColor("#7c2d12"),
    "Commercial Auto":        colors.HexColor("#1a3a1a"),
    "Commercial Property":    colors.HexColor("#3b1f00"),
    "Professional Liability": colors.HexColor("#4a1a4a"),
}

LOB_ICONS = {
    "General Liability":      "GL",
    "Workers Compensation":   "WC",
    "Umbrella / Excess":      "UMB",
    "Cyber Liability":        "CYB",
    "Commercial Auto":        "CA",
    "Commercial Property":    "CP",
    "Professional Liability": "PL",
}

DEFAULT_COVS = {
    "General Liability": "General Aggregate|$2,000,000|N/A\nEach Occurrence|$1,000,000|Per Deductible\nProducts & Completed Operations|$2,000,000|Per Deductible\nPersonal & Advertising Injury|$1,000,000|Per Deductible\nDamage to Rented Premises|$100,000|Per Deductible\nMedical Payments|$5,000|None",
    "Workers Compensation": "Workers Compensation|Statutory|N/A\nEmployers Liability - Each Accident|$1,000,000|N/A\nEmployers Liability - Disease (Policy)|$1,000,000|N/A\nEmployers Liability - Disease (Employee)|$1,000,000|N/A",
    "Umbrella / Excess": "Each Occurrence|$5,000,000|$10,000\nGeneral Aggregate|$5,000,000|$10,000\nProducts & Completed Operations Aggregate|$5,000,000|$10,000\nSelf-Insured Retention|$10,000|N/A",
    "Cyber Liability": "Network Security & Privacy Liability|$1,000,000|$10,000\nFirst Party Data Breach Response|$1,000,000|$10,000\nCyber Extortion / Ransomware|$1,000,000|$10,000\nBusiness Interruption|$500,000|$10,000\nRegulatory Defense & Penalties|$250,000|$10,000",
    "Commercial Auto": "Combined Single Limit (CSL)|$1,000,000|$1,000\nUninsured/Underinsured Motorist|$1,000,000|N/A\nMedical Payments|$5,000|N/A\nComprehensive|Actual Cash Value|$500\nCollision|Actual Cash Value|$1,000",
    "Commercial Property": "Building Replacement Cost|Per Schedule|$5,000\nBusiness Personal Property|Per Schedule|$5,000\nBusiness Income / Extra Expense|12 Months|$5,000\nEquipment Breakdown|Included|$5,000\nOutdoor Property|$25,000|$5,000",
    "Professional Liability": "Each Claim|$1,000,000|$5,000\nAggregate|$2,000,000|$5,000\nPersonal Injury|$1,000,000|$5,000\nDefense Costs|Outside Limits|N/A",
}

# ─────────────────────────────────────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_pdf_text(uploaded_file) -> str:
    try:
        uploaded_file.seek(0)
        reader = PdfReader(io.BytesIO(uploaded_file.read()))
        return "".join(p.extract_text() or "" for p in reader.pages)
    except:
        return ""

def parse_carrier_pdf(text: str) -> dict:
    def find(patterns, default=""):
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return default
    return {
        "carrier":       find([r"(?:carrier|company)[:\s]+([A-Z][\w\s&,\.]+?)(?:\n|$)",
                               r"([A-Z][\w\s]+(?:Insurance|Mutual|Indemnity|Casualty|National)[\w\s,\.]*)"]),
        "quote_num":     find([r"quote\s*(?:number|#|no\.?)[:\s]+([\w\-]+)",
                               r"ref(?:erence)?[:\s#]+([\w\-]+)"]),
        "policy_period": find([r"policy\s*period[:\s]+([\d/\-]+\s*(?:to|--|through)?\s*[\d/\-]+)",
                               r"effective[:\s]+([\d/\-]+)"]),
        "total_premium": find([r"total\s*(?:annual\s*)?premium[:\s\$]+([\d,\.]+)",
                               r"(?:amount due|total payable)[:\s\$]+([\d,]+\.\d{2})",
                               r"premium[:\s\$]+([\d,]+\.\d{2})"]),
        "deductible":    find([r"deductible[:\s\$]+([\d,\.]+(?:\s*per\s*\w+)?)"]),
        "each_occurrence": find([r"each\s+occurrence[:\s\$]+([\d,]+(?:,\d{3})*)"]),
        "general_aggregate": find([r"general\s+aggregate[:\s\$]+([\d,]+(?:,\d{3})*)"]),
        "insured_name":  find([r"(?:named\s+insured|insured)[:\s]+([A-Z][\w\s,\.&]+?)(?:\n|$)",
                               r"(?:applicant|account)[:\s]+([A-Z][\w\s,\.&]+?)(?:\n|$)"]),
        "underwriter":   find([r"underwriter[:\s]+([A-Z][\w\s\.]+?)(?:\n|$)"]),
        "quote_exp":     find([r"(?:quote|expir\w+)\s*(?:date|exp)[:\s]+([\d/\-]+)"]),
    }

# ─────────────────────────────────────────────────────────────────────────────
# REPORTLAB STYLES
# ─────────────────────────────────────────────────────────────────────────────

def build_styles():
    s = getSampleStyleSheet()
    defs = [
        ("SL",  dict(fontName="Helvetica-Bold", fontSize=7.5, textColor=GD,  spaceAfter=4,  leading=10)),
        ("ET",  dict(fontName="Helvetica",      fontSize=10.5,textColor=MG,  leading=16,    spaceAfter=8)),
        ("IL",  dict(fontName="Helvetica-Bold", fontSize=7.5, textColor=GR,  leading=10,    spaceAfter=2)),
        ("IV",  dict(fontName="Helvetica-Bold", fontSize=11,  textColor=DG,  leading=14,    spaceAfter=6)),
        ("RT",  dict(fontName="Helvetica-Bold", fontSize=10,  textColor=NB,  leading=14,    spaceAfter=3)),
        ("RBs", dict(fontName="Helvetica",      fontSize=9.5, textColor=MG,  leading=14,    spaceAfter=2)),
        ("XT",  dict(fontName="Helvetica-Bold", fontSize=10,  textColor=DG,  leading=13,    spaceAfter=2)),
        ("XK",  dict(fontName="Helvetica-Oblique",fontSize=8.5,textColor=GR, leading=12,    spaceAfter=4)),
        ("XP",  dict(fontName="Helvetica",      fontSize=9.5, textColor=MG,  leading=14)),
        ("TH",  dict(fontName="Helvetica-Bold", fontSize=8,   textColor=WH,  leading=11)),
        ("WRN", dict(fontName="Helvetica",      fontSize=9.5, textColor=colors.HexColor("#92400E"), leading=14)),
        ("SIG", dict(fontName="Helvetica",      fontSize=9.5, textColor=MG,  leading=15)),
        ("LOBT",dict(fontName="Helvetica-Bold", fontSize=16,  textColor=WH,  leading=20)),
        ("LOBS",dict(fontName="Helvetica",      fontSize=10,  textColor=colors.HexColor("#CBD5E1"), leading=14)),
    ]
    for name, kw in defs:
        if name not in s:
            s.add(ParagraphStyle(name=name, **kw))
    return s

# ─────────────────────────────────────────────────────────────────────────────
# PAGE DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def make_page_deco(client_name, logo_path=None):
    def page_deco(c, doc):
        c.saveState()
        c.setFillColor(WH); c.rect(0, H-44, W, 44, fill=1, stroke=0)
        c.setFillColor(GD); c.rect(0, H-47, W, 3, fill=1, stroke=0)
        if logo_path and os.path.exists(logo_path):
            try:
                c.drawImage(ImageReader(logo_path), 0.55*inch, H-40, width=120, height=32,
                            preserveAspectRatio=True, mask="auto")
            except: pass
        else:
            c.setFillColor(NB); c.setFont("Helvetica-Bold", 13)
            c.drawString(0.6*inch, H-28, "McDade Insurance")
            c.setFillColor(AC); c.setFont("Helvetica-Bold", 7)
            c.drawString(0.6*inch, H-40, "RISK MANAGEMENT DIVISION")
        c.setFillColor(GR); c.setFont("Helvetica", 9)
        c.drawRightString(W-0.6*inch, H-22, f"{client_name}  |  Commercial Insurance Program Proposal")
        c.setFillColor(LG); c.rect(0, 0, W, 34, fill=1, stroke=0)
        c.setFillColor(GD); c.rect(0, 34, W, 1.5, fill=1, stroke=0)
        c.setFillColor(GR); c.setFont("Helvetica", 7.5)
        c.drawString(0.6*inch, 12, "McDade Insurance  •  Risk Management Division  •  Houston, TX  |  Des Moines, IA  •  Confidential")
        c.drawRightString(W-0.6*inch, 12, f"Page {doc.page}")
        c.restoreState()
    return page_deco

# ─────────────────────────────────────────────────────────────────────────────
# COVER PAGE
# ─────────────────────────────────────────────────────────────────────────────

def draw_cover(D, lobs, logo_path=None) -> bytes:
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=letter)
    c.setFillColor(WH); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NB); c.rect(0, 0, 6, H, fill=1, stroke=0)
    c.setFillColor(GD); c.rect(0, H-6, W, 6, fill=1, stroke=0)

    if logo_path and os.path.exists(logo_path):
        try:
            c.drawImage(ImageReader(logo_path), 52, H-115, width=270, height=90,
                        preserveAspectRatio=True, mask="auto")
        except: logo_path = None
    if not (logo_path and os.path.exists(logo_path or "")):
        c.setFillColor(NB); c.setFont("Helvetica-Bold", 30); c.drawString(52, H-80, "McDade Insurance")
        c.setFillColor(AC); c.setFont("Helvetica-Bold", 11); c.drawString(52, H-98, "RISK MANAGEMENT DIVISION")

    c.setFillColor(GR); c.setFont("Helvetica", 8)
    c.drawRightString(W-52, H-52, "COMMERCIAL INSURANCE PROGRAM PROPOSAL")
    c.setFillColor(GD); c.setFont("Helvetica-Bold", 8)
    c.drawRightString(W-52, H-66, "Prepared by McDade Insurance — Risk Management Division")
    c.setStrokeColor(GD); c.setLineWidth(2); c.line(52, H-115, W-52, H-115)

    # Client name
    c.setFillColor(NB); c.setFont("Helvetica-Bold", 36)
    cn = D["cn"]
    c.drawString(52, H-163, cn[:42])
    if len(cn) > 42:
        c.setFont("Helvetica-Bold", 26); c.drawString(52, H-193, cn[42:84])
    c.setFillColor(GR); c.setFont("Helvetica", 11); c.drawString(52, H-183, D.get("addr",""))
    c.setFillColor(GR); c.setFont("Helvetica", 12)
    c.drawString(52, H-200, "Commercial Insurance Program — Prepared Exclusively for You")
    c.setStrokeColor(GD); c.setLineWidth(2); c.line(52, H-214, W-52, H-214)

    # Top info boxes: total premium + quote expiration
    boxes = [
        ("POLICY PERIOD",  D.get("pp", "See Schedule")),
        ("QUOTE EXPIRES",  D.get("qe", "See Schedule")),
        ("LINES OF BUSINESS", str(len(lobs))),
        ("TOTAL PROGRAM PREMIUM", "$" + D.get("total_program_premium","See Schedule")),
    ]
    bx = 52; bw = (W-104-18)/4; by = H-345
    for idx, (label, val) in enumerate(boxes):
        is_total = idx == 3
        c.setFillColor(NB if is_total else colors.HexColor("#F8F9FC"))
        c.roundRect(bx, by, bw-6, 80, 5, fill=1, stroke=0)
        c.setFillColor(GD); c.rect(bx, by+76, bw-6, 4, fill=1, stroke=0)
        if not is_total:
            c.setStrokeColor(BG); c.setLineWidth(0.5)
            c.roundRect(bx, by, bw-6, 80, 5, fill=0, stroke=1)
        c.setFillColor(WH if is_total else GR)
        c.setFont("Helvetica-Bold", 7); c.drawString(bx+10, by+62, label)
        c.setFillColor(WH if is_total else NB)
        c.setFont("Helvetica-Bold", 11 if is_total else 10)
        c.drawString(bx+10, by+40, str(val)[:22])
        bx += bw+6

    # LOB chips
    chip_x = 52; chip_y = H-370; chip_h = 24
    for lob_name in lobs:
        lob_color = LOB_COLORS.get(lob_name, NB)
        badge = LOB_ICONS.get(lob_name, "INS")
        chip_w = len(lob_name)*6.2 + 40
        if chip_x + chip_w > W - 52:
            chip_x = 52; chip_y -= chip_h + 8
        c.setFillColor(lob_color)
        c.roundRect(chip_x, chip_y, chip_w, chip_h, 4, fill=1, stroke=0)
        c.setFillColor(GD); c.setFont("Helvetica-Bold", 7)
        c.drawString(chip_x+8, chip_y+17, badge)
        c.setFillColor(WH); c.setFont("Helvetica", 9)
        c.drawString(chip_x+8+len(badge)*5.5+4, chip_y+17, lob_name)
        chip_x += chip_w + 8

    # Premium summary table by LOB
    summary_y = chip_y - 36
    c.setFillColor(DG); c.setFont("Helvetica-Bold", 9)
    c.drawString(52, summary_y+14, "PREMIUM SUMMARY BY LINE:")
    summary_y -= 18
    c.setFillColor(NB); c.rect(52, summary_y-4, W-104, 18, fill=1, stroke=0)
    c.setFillColor(WH); c.setFont("Helvetica-Bold", 8)
    c.drawString(58, summary_y+2, "LINE OF BUSINESS")
    c.drawString(320, summary_y+2, "CARRIER")
    c.drawRightString(W-58, summary_y+2, "ANNUAL PREMIUM")
    row_y = summary_y - 20
    total_p = 0
    for i, lob in enumerate(D.get("lob_data",[])):
        bg = colors.HexColor("#F3F0FF") if i%2==0 else WH
        c.setFillColor(bg); c.rect(52, row_y-4, W-104, 18, fill=1, stroke=0)
        lob_color = LOB_COLORS.get(lob["lob_name"], NB)
        c.setFillColor(lob_color); c.rect(52, row_y-4, 4, 18, fill=1, stroke=0)
        c.setFillColor(DG); c.setFont("Helvetica-Bold", 8)
        c.drawString(62, row_y+2, lob["lob_name"])
        c.setFillColor(GR); c.setFont("Helvetica", 8)
        c.drawString(320, row_y+2, lob.get("carrier","")[:30])
        prem = lob.get("premium","").replace("$","").replace(",","")
        try: total_p += float(prem)
        except: pass
        c.setFillColor(NB); c.setFont("Helvetica-Bold", 8)
        c.drawRightString(W-58, row_y+2, f"${lob.get('premium','TBD')}")
        row_y -= 20
        if row_y < 100: break
    # Total row
    c.setFillColor(NB); c.rect(52, row_y-4, W-104, 20, fill=1, stroke=0)
    c.setFillColor(GD); c.setFont("Helvetica-Bold", 9)
    c.drawString(62, row_y+2, "TOTAL ANNUAL PROGRAM PREMIUM")
    c.setFillColor(WH); c.setFont("Helvetica-Bold", 10)
    total_str = f"${total_p:,.2f}" if total_p > 0 else f"${D.get('total_program_premium','TBD')}"
    c.drawRightString(W-58, row_y+2, total_str)

    # Footer
    c.setFillColor(NB); c.rect(0, 0, W, 52, fill=1, stroke=0)
    c.setFillColor(GD); c.rect(0, 52, W, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#8B9CC8")); c.setFont("Helvetica", 8.5)
    c.drawString(52, 18, "McDade Insurance  •  Risk Management Division  •  Houston, TX  |  Des Moines, IA via Risk Advisors of Iowa")
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawRightString(W-52, 18, f"Confidential — Prepared exclusively for {D['cn']}")
    c.save()
    return buf.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# LOB SECTION BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_lob_section(lob, section_num, s, story, uw):
    lob_name = lob["lob_name"]
    lob_color = LOB_COLORS.get(lob_name, NB)
    badge = LOB_ICONS.get(lob_name, "INS")

    # LOB divider banner
    banner = Table([[
        Paragraph(badge, ParagraphStyle("BDG", fontName="Helvetica-Bold", fontSize=18,
                  textColor=GD, alignment=TA_CENTER, leading=22)),
        [Paragraph(lob_name.upper(), ParagraphStyle("LOBT2", fontName="Helvetica-Bold",
                   fontSize=14, textColor=WH, leading=18)),
         Paragraph(f"Section {section_num}  |  {lob.get('carrier','')}", ParagraphStyle("LOBS2",
                   fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#CBD5E1"), leading=12))]
    ]], colWidths=[60, uw-60])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), lob_color),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING", (0,0),(-1,-1), 12),
        ("BOTTOMPADDING", (0,0),(-1,-1), 12),
        ("LINEBELOW", (0,0),(-1,-1), 3, GD),
    ]))
    story.append(banner); story.append(Spacer(1, 14))

    # Quote info grid
    pairs = [
        ("CARRIER / MGA",    lob.get("carrier","")),
        ("QUOTE NUMBER",     lob.get("quote_num","")),
        ("POLICY PERIOD",    lob.get("policy_period","")),
        ("QUOTE EXPIRATION", lob.get("quote_exp","")),
        ("ANNUAL PREMIUM",   f"${lob.get('premium','')}"),
        ("DEDUCTIBLE",       lob.get("deductible","")),
    ]
    cs = [(uw-8)/2, 8, (uw-8)/2]
    grid_rows = []
    for i in range(0, len(pairs), 2):
        l, r = pairs[i], pairs[i+1]
        bg = LB if i//2 % 2 == 0 else colors.HexColor("#FAFBFF")
        for item in [l, r]:
            pass
        lt = Table([[Paragraph(l[0], s["IL"])],[Paragraph(str(l[1]), s["IV"])]], colWidths=[(uw-8)/2])
        rt = Table([[Paragraph(r[0], s["IL"])],[Paragraph(str(r[1]), s["IV"])]], colWidths=[(uw-8)/2])
        for t2 in [lt, rt]:
            t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),
                                    ("LINEBEFORE",(0,0),(0,-1),3,lob_color),
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

    # Coverage table
    covs = lob.get("covs", [])
    if covs:
        story.append(Paragraph("SCHEDULE OF COVERAGE LIMITS", s["SL"])); story.append(Spacer(1,6))
        chdr = [Paragraph(t, s["TH"]) for t in ["COVERAGE LINE","LIMIT","DEDUCTIBLE"]]
        crow = [chdr]
        for name, limit, ded in covs:
            ns = ParagraphStyle("cn2", fontName="Helvetica-Bold", fontSize=9, textColor=DG, leading=12)
            ls = ParagraphStyle("cl2", fontName="Helvetica-Bold", fontSize=9, textColor=lob_color, leading=12)
            ds = ParagraphStyle("cd2", fontName="Helvetica", fontSize=8.5, textColor=GR, leading=12)
            crow.append([Paragraph(name,ns), Paragraph(limit,ls), Paragraph(ded,ds)])
        ct = Table(crow, colWidths=[uw*0.50, uw*0.28, uw*0.22])
        rs2 = [("BACKGROUND",(0,0),(-1,0),lob_color),
               ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
               ("LEFTPADDING",(0,0),(-1,-1),10), ("RIGHTPADDING",(0,0),(-1,-1),10),
               ("LINEBELOW",(0,0),(-1,-2),0.5,BG), ("BOX",(0,0),(-1,-1),1,BG),
               ("VALIGN",(0,0),(-1,-1),"TOP")]
        for i in range(1, len(crow), 2):
            rs2.append(("BACKGROUND",(0,i),(-1,i),LG))
        ct.setStyle(TableStyle(rs2)); story.append(ct); story.append(Spacer(1,12))

    # Notes
    if lob.get("notes"):
        nt = Table([[Paragraph(f"<b>NOTE:</b> {lob['notes']}",
                    ParagraphStyle("AN2", fontName="Helvetica", fontSize=9.5,
                    textColor=colors.HexColor("#92400E"), leading=14))]],
                   colWidths=[uw])
        nt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WY),
                                ("BOX",(0,0),(-1,-1),1,WB),
                                ("LINEBEFORE",(0,0),(0,-1),4,WB),
                                ("LEFTPADDING",(0,0),(-1,-1),14),
                                ("RIGHTPADDING",(0,0),(-1,-1),14),
                                ("TOPPADDING",(0,0),(-1,-1),10),
                                ("BOTTOMPADDING",(0,0),(-1,-1),10)]))
        story.append(nt); story.append(Spacer(1,10))

    # Exclusions
    excls = lob.get("excls", [])
    if excls:
        story.append(Paragraph(f"KEY EXCLUSIONS — {lob_name.upper()}", s["SL"])); story.append(Spacer(1,8))
        for i, (title, tech, plain) in enumerate(excls, 1):
            badge_t = Table([[Paragraph("EXCLUDED", ParagraphStyle("B2", fontName="Helvetica-Bold",
                             fontSize=7, textColor=WH, leading=9))]],
                            colWidths=[54], rowHeights=[16],
                            style=TableStyle([("BACKGROUND",(0,0),(-1,-1),lob_color),
                                              ("TOPPADDING",(0,0),(-1,-1),3),
                                              ("BOTTOMPADDING",(0,0),(-1,-1),3),
                                              ("LEFTPADDING",(0,0),(-1,-1),6),
                                              ("RIGHTPADDING",(0,0),(-1,-1),6)]))
            hdr = Table([[badge_t, Paragraph(f"{i}. {title}", s["XT"])]], colWidths=[64, uw-64])
            hdr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LG),
                                     ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                     ("LEFTPADDING",(0,0),(-1,-1),10),
                                     ("RIGHTPADDING",(0,0),(-1,-1),10),
                                     ("TOPPADDING",(0,0),(-1,-1),8),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
            tech_t = Table([[Paragraph(f"Policy language: {tech}", s["XK"])]], colWidths=[uw])
            tech_t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),14),
                                         ("TOPPADDING",(0,0),(-1,-1),6),
                                         ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            pe_lbl = Paragraph("PLAIN ENGLISH — What This Means For You:",
                               ParagraphStyle("PE2", fontName="Helvetica-Bold", fontSize=7.5, textColor=GD, leading=10))
            pe_txt = Paragraph(plain, s["XP"])
            pe_in  = Table([[pe_lbl],[pe_txt]], colWidths=[uw-28])
            pe_in.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),10),
                                        ("TOPPADDING",(0,0),(-1,-1),4),
                                        ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
            pe_out = Table([[pe_in]], colWidths=[uw])
            pe_out.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WY),
                                         ("LINEBEFORE",(0,0),(0,-1),3,lob_color),
                                         ("LEFTPADDING",(0,0),(-1,-1),4),
                                         ("TOPPADDING",(0,0),(-1,-1),4),
                                         ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            sep = Table([[" "]], colWidths=[uw], rowHeights=[8],
                        style=TableStyle([("LINEBELOW",(0,0),(-1,-1),1,BG)]))
            story.append(KeepTogether([hdr, tech_t, pe_out, sep, Spacer(1,6)]))

    story.append(PageBreak())

# ─────────────────────────────────────────────────────────────────────────────
# FULL BODY BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_body(D, logo_path=None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.75*inch, bottomMargin=0.6*inch)
    s = build_styles(); story = []; uw = W - 1.2*inch

    def sec_hdr(num, title):
        nc = Table([[Paragraph(str(num), ParagraphStyle("SN", fontName="Helvetica-Bold",
                    fontSize=14, textColor=WH, alignment=TA_CENTER, leading=18))]],
                   colWidths=[30], rowHeights=[30],
                   style=TableStyle([("BACKGROUND",(0,0),(-1,-1),NB),
                                     ("TOPPADDING",(0,0),(-1,-1),5),
                                     ("LEFTPADDING",(0,0),(-1,-1),0)]))
        t = Table([[nc, Paragraph(title.upper(), ParagraphStyle("SHT", fontName="Helvetica-Bold",
                   fontSize=13, textColor=NB, leading=18))]], colWidths=[40, uw-40])
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
        ("INSURED BUSINESS",  D.get("cn","")),      ("BUSINESS TYPE",    D.get("bt","")),
        ("ADDRESS",           D.get("addr","")),     ("TERRITORY",        D.get("ter","")),
        ("POLICY PERIOD",     D.get("pp","")),       ("QUOTE EXPIRATION", D.get("qe","")),
        ("LINES OF BUSINESS", str(len(D.get("lob_data",[])))), ("TOTAL PROGRAM PREMIUM", f"${D.get('total_program_premium','')}"),
    ]
    cs = [(uw-8)/2, 8, (uw-8)/2]; grid_rows = []
    for i in range(0, len(pairs), 2):
        l, r = pairs[i], pairs[i+1]
        bg = LB if i//2 % 2 == 0 else colors.HexColor("#FAFBFF")
        lt = Table([[Paragraph(l[0],s["IL"])],[Paragraph(str(l[1]),s["IV"])]], colWidths=[(uw-8)/2])
        rt = Table([[Paragraph(r[0],s["IL"])],[Paragraph(str(r[1]),s["IV"])]], colWidths=[(uw-8)/2])
        for t2 in [lt,rt]:
            t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),
                                    ("LINEBEFORE",(0,0),(0,-1),3,NB),
                                    ("LEFTPADDING",(0,0),(-1,-1),10),
                                    ("TOPPADDING",(0,0),(-1,-1),6),
                                    ("BOTTOMPADDING",(0,0),(-1,-1),6),
                                    ("BOX",(0,0),(-1,-1),0.5,BG)]))
        grid_rows.append([lt,Spacer(8,1),rt])
    grid = Table(grid_rows, colWidths=cs)
    grid.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(grid); story.append(Spacer(1,12))
    story.append(Paragraph("RISK PROFILE", s["SL"]))
    story.append(blue_box(Paragraph(D.get("rs",""), s["ET"])))
    story.append(PageBreak())

    # ── SECTION 2: Executive Summary ─────────────────────────────────────────
    story.append(sec_hdr(2, "Executive Summary & Program Overview")); story.append(Spacer(1,14))
    story.append(Paragraph("OVERVIEW", s["SL"]))
    story.append(gold_box(Paragraph(D.get("es",""), s["ET"]))); story.append(Spacer(1,16))

    # Program-level recommendations
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
            row = Table([[nc,[Paragraph(title,s["RT"]),Paragraph(body,s["RBs"])]]],
                        colWidths=[36,uw-36])
            row.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                     ("LEFTPADDING",(0,0),(-1,-1),0),
                                     ("TOPPADDING",(0,0),(-1,-1),6),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),6),
                                     ("LINEBELOW",(0,0),(-1,-1),0.5,BG)]))
            story.append(row)
    story.append(PageBreak())

    # ── SECTIONS 3+: One per LOB ──────────────────────────────────────────────
    for i, lob in enumerate(D.get("lob_data",[]), 3):
        build_lob_section(lob, i, s, story, uw)

    # ── SIGNATURE / EXCLUSION ACK ─────────────────────────────────────────────
    story.append(sec_hdr("✎", "Program Acknowledgment & Signature")); story.append(Spacer(1,12))
    wt = Table([[Paragraph(
        "<b>IMPORTANT:</b> By signing below, you confirm that you have reviewed all coverage details, "
        "exclusions, and policy terms for each line of business in this proposal. You acknowledge "
        "the situations listed as exclusions are <b>NOT covered</b> by the respective policies, and "
        "you have had the opportunity to ask questions of your McDade Insurance advisor prior to signing.",
        s["WRN"])]], colWidths=[uw])
    wt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WY),("BOX",(0,0),(-1,-1),1.5,WB),
                            ("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),14),
                            ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10)]))
    story.append(wt); story.append(Spacer(1,22))
    cw = [uw*0.38, uw*0.04, uw*0.35, uw*0.04, uw*0.19]
    def sig_col(label, w):
        t = Table([[Paragraph(label, s["IL"])],[Spacer(1,26)],
                   [HRFlowable(width=w, thickness=1.5, color=NB)]], colWidths=[w])
        t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
        return t
    for labels in [["INSURED SIGNATURE","PRINTED NAME","DATE"],
                   ["BROKER / ADVISOR SIGNATURE","PRINTED NAME & LICENSE #","DATE"]]:
        row = Table([[sig_col(labels[0],cw[0]),Spacer(cw[1],1),
                      sig_col(labels[1],cw[2]),Spacer(cw[3],1),
                      sig_col(labels[2],cw[4])]], colWidths=cw)
        row.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),
                                 ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                                 ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
        story.append(row); story.append(Spacer(1,22))

    # ── CONFIDENTIALITY ───────────────────────────────────────────────────────
    story.append(PageBreak())
    conf_hdr = Table([[Paragraph("CONFIDENTIALITY NOTICE",
                       ParagraphStyle("CHT",fontName="Helvetica-Bold",fontSize=13,textColor=NB,leading=18))]],
                     colWidths=[uw])
    conf_hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                   ("LEFTPADDING",(0,0),(-1,-1),0),
                                   ("TOPPADDING",(0,0),(-1,-1),0),
                                   ("BOTTOMPADDING",(0,0),(-1,-1),0),
                                   ("LINEBELOW",(0,0),(-1,-1),2,GD)]))
    story.append(conf_hdr); story.append(Spacer(1,14))
    notice_text = (f"This proposal has been prepared exclusively by <b>McDade Insurance — Risk Management Division</b> "
                   f"for the sole use of <b>{D.get('cn','the named insured')}</b>. It contains proprietary methodologies, "
                   "coverage analysis, market placement strategies, pricing structures, and intellectual work product.")
    nb2 = Table([[Paragraph(notice_text, ParagraphStyle("NT",fontName="Helvetica",fontSize=10.5,textColor=MG,leading=16))]],
                colWidths=[uw])
    nb2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LB),("BOX",(0,0),(-1,-1),1,BG),
                              ("LINEBEFORE",(0,0),(0,-1),4,NB),("LEFTPADDING",(0,0),(-1,-1),14),
                              ("RIGHTPADDING",(0,0),(-1,-1),14),("TOPPADDING",(0,0),(-1,-1),12),
                              ("BOTTOMPADDING",(0,0),(-1,-1),12)]))
    story.append(nb2); story.append(Spacer(1,16))
    terms = [
        ("Prohibited Use", "This proposal may not be shared with any competing insurance agency, broker, carrier, MGA, or third party without prior written consent of McDade Insurance."),
        ("Permitted Use", f"This document is provided solely for the internal review and decision-making of {D.get('cn','')}'s authorized representatives."),
    ]
    for title, body in terms:
        is_penalty = "Penalty" in title
        bg = colors.HexColor("#FFF8E1") if is_penalty else colors.HexColor("#F8F9FC")
        lb2 = GD if is_penalty else NB
        tp = Paragraph(title, ParagraphStyle("TT",fontName="Helvetica-Bold",fontSize=10,
                        textColor=colors.HexColor("#92400E") if is_penalty else NB,leading=14,spaceAfter=4))
        bp = Paragraph(body, ParagraphStyle("TB",fontName="Helvetica",fontSize=9.5,textColor=MG,leading=14))
        t = Table([[tp],[bp]], colWidths=[uw])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),
                               ("BOX",(0,0),(-1,-1),1,GD if is_penalty else BG),
                               ("LINEBEFORE",(0,0),(0,-1),4,lb2),
                               ("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),14),
                               ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10)]))
        story.append(t); story.append(Spacer(1,8))

    page_deco = make_page_deco(D.get("cn","Client"), logo_path)
    doc.build(story, onFirstPage=page_deco, onLaterPages=page_deco)
    return buf.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLE PDF
# ─────────────────────────────────────────────────────────────────────────────

def assemble_pdf(D, lobs, logo_path=None, carrier_pdfs=None) -> bytes:
    writer = PdfWriter()
    for section_bytes in [draw_cover(D, lobs, logo_path), build_body(D, logo_path)]:
        r = PdfReader(io.BytesIO(section_bytes))
        for pg in r.pages: writer.add_page(pg)
    if carrier_pdfs:
        for cpdf_bytes in carrier_pdfs:
            try:
                r = PdfReader(io.BytesIO(cpdf_bytes))
                for pg in r.pages: writer.add_page(pg)
            except: pass
    out = io.BytesIO(); writer.write(out); return out.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT APP
# ─────────────────────────────────────────────────────────────────────────────

ALL_LOBS = list(LOB_COLORS.keys())

def lob_form(lob_name, parsed=None, key_prefix=""):
    p = parsed or {}
    st.markdown(f"**Carrier & Quote Info**")
    c1, c2, c3 = st.columns(3)
    carrier   = c1.text_input("Carrier / MGA",     value=p.get("carrier",""),       key=f"{key_prefix}_carrier")
    quote_num = c2.text_input("Quote Number",       value=p.get("quote_num",""),     key=f"{key_prefix}_quote_num")
    uw        = c3.text_input("Underwriter",        value=p.get("underwriter",""),   key=f"{key_prefix}_uw")
    c4, c5, c6 = st.columns(3)
    policy_period = c4.text_input("Policy Period",  value=p.get("policy_period",""), key=f"{key_prefix}_pp")
    quote_exp     = c5.text_input("Quote Expires",  value=p.get("quote_exp",""),     key=f"{key_prefix}_qe")
    premium       = c6.text_input("Annual Premium ($)", value=p.get("total_premium",""), key=f"{key_prefix}_prem")
    deductible    = st.text_input("Deductible",     value=p.get("deductible",""),    key=f"{key_prefix}_ded")

    st.markdown("**Coverage Schedule** *(Coverage|Limit|Deductible — one per line)*")
    default_covs = DEFAULT_COVS.get(lob_name, "Coverage Line|Limit|Deductible")
    covs_raw = st.text_area("Coverage Lines", value=default_covs, height=130, key=f"{key_prefix}_covs")

    st.markdown("**Exclusions** *(Title|Policy Language|Plain English — one per line)*")
    excls_raw = st.text_area("Exclusions", value="", height=90, key=f"{key_prefix}_excls",
                              placeholder="Intentional Acts|Standard CGL exclusion|Coverage does not apply to intentional injury...")

    notes = st.text_input("Audit / Pricing Note (optional)", key=f"{key_prefix}_notes")

    # Parse
    covs = []
    for line in covs_raw.strip().split("\n"):
        parts = [x.strip() for x in line.split("|")]
        if len(parts) == 3: covs.append(tuple(parts))
    excls = []
    for line in excls_raw.strip().split("\n"):
        parts = [x.strip() for x in line.split("|")]
        if len(parts) == 3: excls.append(tuple(parts))

    return {
        "lob_name":      lob_name,
        "carrier":       carrier,
        "quote_num":     quote_num,
        "underwriter":   uw,
        "policy_period": policy_period,
        "quote_exp":     quote_exp,
        "premium":       premium,
        "deductible":    deductible,
        "covs":          covs,
        "excls":         excls,
        "notes":         notes,
    }


def main():
    st.set_page_config(
        page_title="McDade Insurance — Proposal Generator",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2D1B69 0%, #4B2D9E 100%);
        padding: 1.5rem 2rem; border-radius: 10px; margin-bottom: 1.5rem;
        border-left: 6px solid #C8A951;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p  { color: #C8A951; margin: 0.3rem 0 0 0; font-size: 0.95rem; }
    .lob-header {
        padding: 0.6rem 1rem; border-radius: 6px; margin-bottom: 0.5rem;
        font-weight: 700; color: white; font-size: 1rem;
    }
    .stButton>button { background: #2D1B69; color: white; border: none;
        border-radius: 6px; font-weight: 700; padding: 0.5rem 2rem; font-size: 1rem; }
    .stButton>button:hover { background: #C8A951; color: #2D1B69; }
    div[data-testid="stTabs"] button { font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="main-header">
        <h1>📋 McDade Insurance — Risk Management Division</h1>
        <p>Multi-Line Commercial Insurance Proposal Generator  |  Houston, TX  ·  Des Moines, IA via Risk Advisors of Iowa</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🏢 Lines of Business")
        st.caption("Select which lines to include in this proposal")
        selected_lobs = []
        for lob in ALL_LOBS:
            icon = LOB_ICONS[lob]
            if st.checkbox(f"{icon} — {lob}", value=(lob=="General Liability"), key=f"lob_check_{lob}"):
                selected_lobs.append(lob)
        st.markdown("---")
        st.markdown("### 📤 Upload Carrier PDFs")
        carrier_files = st.file_uploader("Upload carrier quotes (PDF)", type=["pdf"],
                                          accept_multiple_files=True)
        st.markdown("---")
        st.markdown("### 🖼️ Agency Logo")
        logo_file = st.file_uploader("Upload logo (PNG/JPG)", type=["png","jpg","jpeg"])
        st.markdown("---")
        append_carrier = st.checkbox("Append raw carrier PDFs to proposal", value=False)

    # Save logo
    logo_path = None
    if logo_file:
        logo_path = f"/tmp/mcdade_logo_{logo_file.name}"
        with open(logo_path, "wb") as f:
            f.write(logo_file.read())

    # Parse uploaded PDFs
    parsed_data = {}
    carrier_pdf_bytes_list = []
    if carrier_files:
        for cf in carrier_files:
            try:
                text = extract_pdf_text(cf)
                parsed = parse_carrier_pdf(text)
                # Try to match to a LOB
                for lob in ALL_LOBS:
                    kw = lob.lower().replace(" ","")
                    if any(k in text.lower() for k in kw.split("/")):
                        parsed_data[lob] = parsed
                        break
                else:
                    parsed_data["General Liability"] = parsed
                cf.seek(0)
                carrier_pdf_bytes_list.append(cf.read())
            except Exception as e:
                st.sidebar.warning(f"Could not parse {cf.name}: {e}")
        st.sidebar.success(f"✅ Parsed {len(carrier_files)} PDF(s)")

    if not selected_lobs:
        st.warning("⬅️ Select at least one line of business in the sidebar to get started.")
        return

    # ── Client Info ───────────────────────────────────────────────────────────
    st.markdown("## 🏢 Client Information")
    col1, col2 = st.columns(2)
    with col1:
        cn   = st.text_input("Client / Insured Name *", value=list(parsed_data.values())[0].get("insured_name","") if parsed_data else "")
        addr = st.text_input("Business Address")
        bt   = st.text_input("Business Type / Industry")
    with col2:
        ter  = st.text_input("Territory / State(s)", value="Texas")
        pp   = st.text_input("Overall Policy Period (e.g. 05/01/2026 – 05/01/2027)")
        qe   = st.text_input("Quote Expiration Date")
        total_prog_prem = st.text_input("Total Program Premium (leave blank to auto-sum)")

    st.markdown("---")
    col3, col4 = st.columns(2)
    with col3:
        rs = st.text_area("Risk Profile", height=110,
            value=f"{cn if cn else '[Client Name]'} is a business operating in {ter if ter else 'Texas/Iowa'} presenting the following multi-line insurance program.")
    with col4:
        es = st.text_area("Executive Summary", height=110,
            value=f"McDade Insurance — Risk Management Division is pleased to present this comprehensive commercial insurance program for {cn if cn else '[Client Name]'}.")

    st.markdown("#### 💡 Program-Level Recommendations *(Title|Body — one per line)*")
    recs_raw = st.text_area("Recommendations", height=80,
        value="Review Your Total Cost of Risk|Beyond premium, consider deductibles, uninsured exposures, and claim costs. McDade will work with you annually to optimize the total program cost.\nCoordinate Certificate of Insurance Requests|With multiple lines, ensure your COI requests capture all required coverages and additional insured statuses across every line.")

    # ── LOB Tabs ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 📄 Coverage Details by Line of Business")
    tabs = st.tabs([f"{LOB_ICONS[l]} {l}" for l in selected_lobs])
    lob_data = []
    for tab, lob_name in zip(tabs, selected_lobs):
        with tab:
            st.markdown(f"### {LOB_ICONS[lob_name]} {lob_name}")
            parsed = parsed_data.get(lob_name, {})
            data = lob_form(lob_name, parsed=parsed, key_prefix=lob_name.replace(" ","_").replace("/","_"))
            lob_data.append(data)

    # ── Generate ──────────────────────────────────────────────────────────────
    st.markdown("---")
    col_g1, col_g2, col_g3 = st.columns([1,2,1])
    with col_g2:
        generate = st.button("🚀 Generate Multi-Line Proposal PDF", use_container_width=True)

    if generate:
        if not cn:
            st.error("⚠️ Client / Insured Name is required.")
        else:
            recs = []
            for line in recs_raw.strip().split("\n"):
                parts = [x.strip() for x in line.split("|")]
                if len(parts) == 2: recs.append(tuple(parts))

            D = {
                "cn": cn, "addr": addr, "bt": bt, "ter": ter,
                "pp": pp, "qe": qe,
                "total_program_premium": total_prog_prem,
                "rs": rs, "es": es, "recs": recs,
                "lob_data": lob_data,
            }

            with st.spinner("Building your multi-line proposal..."):
                try:
                    carrier_bytes = carrier_pdf_bytes_list if append_carrier else None
                    pdf_bytes = assemble_pdf(D, selected_lobs, logo_path=logo_path, carrier_pdfs=carrier_bytes)
                    filename = f"McDade_Proposal_{cn.replace(' ','_')[:40]}.pdf"
                    st.success(f"✅ Proposal generated — {len(selected_lobs)} line(s) of business included!")
                    st.download_button("📥 Download Proposal PDF", data=pdf_bytes,
                                       file_name=filename, mime="application/pdf",
                                       use_container_width=True)
                except Exception as e:
                    st.error(f"Error generating PDF: {e}")
                    import traceback; st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
