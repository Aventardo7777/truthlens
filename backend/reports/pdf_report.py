"""PDF audit report generator (fpdf2, with system CJK font support)."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def _find_font() -> Path | None:
    for p in _FONT_CANDIDATES:
        path = Path(p)
        if path.exists():
            return path
    return None


def generate_pdf_report(result: dict) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)

    font = _find_font()
    if font is not None:
        try:
            pdf.add_font("cjk", "", str(font))
            fam = "cjk"
        except Exception:
            fam = "helvetica"
    else:
        fam = "helvetica"

    W = 190  # usable width

    pdf.add_page()
    pdf.set_text_color(20, 20, 20)
    pdf.set_font(fam, "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(W, 6, "TRUTHLENS - STATISTICAL INTEGRITY REPORT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(10, 10, 10)
    pdf.set_font(fam, "", 20)
    pdf.cell(W, 12, result["case_number"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(fam, "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(W, 6, f"File: {result['filename']}  |  {result['n_rows']} rows x {result['n_cols']} cols"
                   f"  |  {len(result['findings'])} findings", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    integ = result["integrity"]
    pdf.set_font(fam, "", 44)
    pdf.set_text_color(230, 179, 57) if integ["total"] >= 70 else pdf.set_text_color(229, 72, 77)
    pdf.cell(W, 26, str(integ["total"]) + " / 100", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)
    pdf.set_font(fam, "", 13)
    pdf.cell(W, 8, integ["verdict"] + " - " + integ["explanation"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # dimensions
    pdf.set_font(fam, "", 11)
    pdf.set_text_color(232, 179, 57)
    pdf.cell(W, 8, "SCORE BREAKDOWN", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)
    pdf.set_font(fam, "", 9)
    for k, v in integ["dimensions"].items():
        pdf.cell(60, 6, k, border=0)
        filled = int(v / 2)
        pdf.set_font(fam, "", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(50, 6, "[" + "#" * filled + "." * (50 - filled) + "] " + str(v),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
    pdf.ln(6)

    # findings
    pdf.set_font(fam, "", 11)
    pdf.set_text_color(232, 179, 57)
    pdf.cell(W, 8, f"FINDINGS ({len(result['findings'])})", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)

    for f in result["findings"]:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font(fam, "", 10)
        pdf.set_text_color(229, 72, 77) if f["severity"] == "high" else pdf.set_text_color(120, 120, 120)
        pdf.cell(W, 6, f"[{f['severity'].upper()}] {f['id']}  {f['title']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
        pdf.set_font(fam, "", 9)
        pdf.multi_cell(W, 5, f"Summary: {f['stat_summary']}")
        pdf.multi_cell(W, 5, f"Why it matters: {f['why_it_matters']}")
        pdf.multi_cell(W, 5, "Possible causes: " + "; ".join(f["possible_causes"]))
        pdf.multi_cell(W, 5, f"Not proof of: {f['what_it_does_not_prove']}")
        pdf.multi_cell(W, 5, "Next steps: " + "; ".join(f["next_steps"]))
        pdf.ln(3)

    pdf.ln(4)
    pdf.set_font(fam, "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(W, 5,
                   "Limitations: TruthLens is a screening tool. Findings describe statistical "
                   "observations, not intent, and are grounds for investigation - never proof of fraud.")
    return bytes(pdf.output())
