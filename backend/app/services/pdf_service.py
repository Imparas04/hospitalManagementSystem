"""PDF generation with ReportLab (invoice, payment receipt, discharge summary).

Notes for viva:
  * Built with ReportLab "Platypus": we describe the page as a list of blocks
    (headings, paragraphs, tables) and ReportLab lays them out and adds pages.
  * Every piece of text typed by a user is passed through escape(), because
    ReportLab paragraphs read <b>, <i>, & etc. as markup and would crash on raw input.
  * The built-in fonts cannot print the rupee symbol, so amounts are written as "Rs. 1,234.50".
"""
from io import BytesIO
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_styles = getSampleStyleSheet()
NORMAL = ParagraphStyle("n", parent=_styles["Normal"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("s", parent=NORMAL, fontSize=8.5, textColor=colors.HexColor("#555555"))
H_HOSPITAL = ParagraphStyle("hh", parent=_styles["Title"], fontSize=18, spaceAfter=2, textColor=colors.HexColor("#0b5394"))
H_TITLE = ParagraphStyle("ht", parent=_styles["Heading2"], fontSize=13, spaceBefore=4, spaceAfter=6)
H_SECTION = ParagraphStyle("hs", parent=_styles["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4,
                           textColor=colors.HexColor("#0b5394"))
HEAD_FILL = colors.HexColor("#e8eef7")


def P(text, style=NORMAL):
    """Paragraph from plain text (escaped, line breaks kept)."""
    return Paragraph(escape("" if text is None else str(text)).replace("\n", "<br/>"), style)


def rs(amount):
    return f"Rs. {float(amount):,.2f}"


def _table(rows, col_widths, header=True, align_right_cols=()):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b7b7b7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), HEAD_FILL), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    for c in align_right_cols:
        style.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def _kv_table(pairs, widths=(45 * mm, 125 * mm)):
    t = Table([[P(k, SMALL), P(v)] for k, v in pairs], colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def _build(story, title, pagesize=A4):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=12 * mm,
                            bottomMargin=12 * mm, title=title, author=current_app.config["HOSPITAL_NAME"])
    doc.build(story)
    return buf.getvalue()


def _header(title):
    return [P(current_app.config["HOSPITAL_NAME"], H_HOSPITAL), P(title, H_TITLE)]


def _date(iso):
    return iso[:10] if iso else "-"


# ----------------------------------------------------------------------------
def invoice_pdf(bill):
    d = bill.to_dict(include_details=True)
    story = _header("INVOICE")
    story.append(_kv_table([
        ("Bill number", d["bill_number"]), ("Date", _date(d["created_at"])),
        ("Patient", f'{d["patient_name"]} ({d["patient_code"]})'), ("Status", d["status"].replace("_", " ").upper()),
    ]))
    story.append(Spacer(1, 8))

    rows = [["#", "Description", "Qty", "Unit price", "Amount"]]
    for n, i in enumerate(d["items"], 1):
        rows.append([str(n), P(i["description"]), str(i["quantity"]), rs(i["unit_price"]), rs(i["amount"])])
    story.append(_table(rows, [10 * mm, 90 * mm, 15 * mm, 28 * mm, 31 * mm], align_right_cols=(2, 3, 4)))
    story.append(Spacer(1, 8))

    totals = [["Subtotal", rs(d["subtotal"])],
              [f'Discount ({d["discount_percent"]:g}%)', "- " + rs(d["discount_amount"])],
              [f'Tax ({d["tax_percent"]:g}%)', "+ " + rs(d["tax_amount"])],
              ["TOTAL", rs(d["total_amount"])],
              ["Paid", rs(d["amount_paid"])],
              ["Outstanding", rs(d["outstanding_amount"])]]
    t = Table(totals, colWidths=[50 * mm, 40 * mm], hAlign="RIGHT")
    t.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                           ("LINEABOVE", (0, 3), (-1, 3), 0.8, colors.black), ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold")]))
    story.append(t)

    if d["payments"]:
        story.append(P("Payments received", H_SECTION))
        prow = [["Receipt", "Date", "Method", "Reference", "Amount"]]
        for p in d["payments"]:
            prow.append([p["receipt_number"], _date(p["paid_at"]), p["method"].replace("_", " "),
                         P(p["reference"] or "-"), rs(p["amount"])])
        story.append(_table(prow, [30 * mm, 28 * mm, 30 * mm, 50 * mm, 36 * mm], align_right_cols=(4,)))
    story.append(Spacer(1, 14))
    story.append(P("This is a computer generated invoice.", SMALL))
    return _build(story, f'Invoice {d["bill_number"]}')


def receipt_pdf(payment):
    from app.services.billing_service import balance_after
    bill, p = payment.bill, payment.to_dict()
    story = _header("PAYMENT RECEIPT")
    story.append(_kv_table([
        ("Receipt number", p["receipt_number"]), ("Date", _date(p["paid_at"])),
        ("Patient", f"{bill.patient.full_name} ({bill.patient.patient_code})"),
        ("Against bill", bill.bill_number),
        ("Payment method", p["method"].replace("_", " ").title()),
        ("Reference", p["reference"] or "-"), ("Received by", p["received_by"]),
    ]))
    story.append(Spacer(1, 10))
    t = Table([["Amount received", rs(p["amount"])], ["Bill total", rs(bill.total_amount)],
               ["Balance after this payment", rs(balance_after(payment))]], colWidths=[70 * mm, 45 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b7b7b7")),
                           ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(t)
    story.append(Spacer(1, 14))
    story.append(P("Thank you. This is a computer generated receipt.", SMALL))
    return _build(story, f'Receipt {p["receipt_number"]}')


def discharge_pdf(d):
    """d = discharge_service.build_summary_data(...)"""
    pt, dr, adm = d["patient"], d["doctor"], d["admission"]
    story = _header("DISCHARGE SUMMARY")

    story.append(P("Patient details", H_SECTION))
    story.append(_kv_table([
        ("Name", f'{pt["full_name"]} ({pt["patient_code"]})'),
        ("Age / Gender", f'{pt["age"]} years / {pt["gender"]}'),
        ("Blood group", pt["blood_group"]), ("Phone", pt["phone"]),
        ("Ward / Bed", f'{adm["ward"]} / {adm["bed_number"]}'),
        ("Admitted", _date(adm["admission_date"])), ("Discharged", _date(adm["discharge_date"])),
        ("Reason for admission", adm["reason"]),
    ]))

    story.append(P("Treating doctor", H_SECTION))
    story.append(_kv_table([("Doctor", f'Dr. {dr["full_name"]}'), ("Specialization", dr["specialization"]),
                            ("Department", dr["department"])]))

    story.append(P("Diagnosis", H_SECTION))
    story.append(P(d["diagnosis"]))
    story.append(P("Treatment summary", H_SECTION))
    story.append(P(d["treatment_summary"]))

    story.append(P("Laboratory reports", H_SECTION))
    if d["lab_reports"]:
        rows = [["Test", "Result", "Doctor's note"]]
        for r in d["lab_reports"]:
            result = (r["result"] or "pending") + (" (ABNORMAL)" if r["is_abnormal"] else "")
            rows.append([P(f'{r["test"]} ({r["code"]})'), P(result), P(r["reviewer_notes"] or "-")])
        story.append(_table(rows, [55 * mm, 65 * mm, 50 * mm]))
    else:
        story.append(P("No laboratory tests during this stay.", SMALL))

    story.append(P("Medicines", H_SECTION))
    if d["medicines"]:
        rows = [["Medicine", "Dosage", "Prescribed", "Issued"]]
        for m in d["medicines"]:
            rows.append([P(f'{m["medicine"]} ({m["unit"]})'), P(m["dosage"]), str(m["quantity_prescribed"]),
                         str(m["quantity_issued"])])
        story.append(_table(rows, [60 * mm, 60 * mm, 25 * mm, 25 * mm], align_right_cols=(2, 3)))
    else:
        story.append(P("No medicines prescribed during this stay.", SMALL))

    story.append(P("Doctor's instructions", H_SECTION))
    story.append(P(d["doctor_instructions"] or "None"))
    story.append(P("Follow-up", H_SECTION))
    story.append(P(d["follow_up_date"] or "No follow-up date set"))

    story.append(P("Final bill", H_SECTION))
    b = d["final_bill"]
    if b:
        story.append(_kv_table([("Bill number", b["bill_number"]), ("Subtotal", rs(b["subtotal"])),
                                ("Discount", rs(b["discount_amount"])), ("Tax", rs(b["tax_amount"])),
                                ("Total", rs(b["total_amount"])), ("Paid", rs(b["amount_paid"])),
                                ("Outstanding", rs(b["outstanding_amount"])),
                                ("Payment status", b["status"].replace("_", " ").upper())]))
    else:
        story.append(P("No bill has been generated for this admission yet.", SMALL))
    story.append(Spacer(1, 6))
    story.append(P("This is a computer generated document.", SMALL))
    return _build(story, f'Discharge summary - {pt["patient_code"]}')


def _column_widths(table, usable):
    """Column widths in points, MEASURED with ReportLab's own font metrics.
    Every column gets at least the width of its longest header WORD (so headers never break
    mid-word); spare page width is shared in proportion to how long the column's content is."""
    pad = 14                                                            # cell padding (6pt each side) + a little slack
    minimum, preferred = [], []
    for i, name in enumerate(table["columns"]):
        header_need = max(stringWidth(word, "Helvetica", 8.5) for word in name.split()) + pad
        content = max((stringWidth(str(row[i]), "Helvetica", 9.5) for row in table["rows"] if row[i] is not None), default=0)
        minimum.append(header_need)
        preferred.append(max(header_need, min(content + pad, 60 * mm)))
    if sum(preferred) <= usable:
        return [p * usable / sum(preferred) for p in preferred]         # spread the spare room
    extra = [p - m for p, m in zip(preferred, minimum)]
    room = max(usable - sum(minimum), 0)
    return [m + (e * room / sum(extra) if sum(extra) else 0) for m, e in zip(minimum, extra)]


def report_pdf(report):
    """Any report from services/report_service.py -> PDF. Pages turn landscape when a table is wide."""
    wide = any(len(t["columns"]) > 6 for t in report["tables"])
    page = landscape(A4) if wide else A4
    usable = page[0] - 36 * mm

    story = _header(report["title"].upper())
    story.append(P(f'Period: {report["period"]["from"]} to {report["period"]["to"]}    |    Generated: {report["generated_at"]} UTC', SMALL))
    story.append(P("Summary", H_SECTION))
    story.append(_kv_table([(s["label"], s["value"]) for s in report["summary"]], widths=(70 * mm, usable - 70 * mm)))

    def cell(value):
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, int) and not isinstance(value, bool):
            return f"{value:,}"
        return P(value)

    for table in report["tables"]:
        story.append(P(table["title"], H_SECTION))
        if not table["rows"]:
            story.append(P("No data for this period.", SMALL))
            continue
        rows = [[P(c, SMALL) for c in table["columns"]]] + [[cell(v) for v in row] for row in table["rows"]]
        numeric = [i for i in range(len(table["columns"]))
                   if all(isinstance(r[i], (int, float)) and not isinstance(r[i], bool) for r in table["rows"] if r[i] is not None)]
        story.append(_table(rows, _column_widths(table, usable), align_right_cols=numeric))
    story.append(Spacer(1, 8))
    story.append(P("This is a computer generated report.", SMALL))
    return _build(story, report["title"], pagesize=page)
