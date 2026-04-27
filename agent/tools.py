"""
Business tools: calendar invitations, price quotes, invoices, and email sending.
"""

import os
import json
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from dotenv import load_dotenv
from icalendar import Calendar, Event, vCalAddress, vText
from jinja2 import Environment, FileSystemLoader

load_dotenv()

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "העסק שלי")
BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "")
BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "")
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "")
BUSINESS_TAX_ID = os.getenv("BUSINESS_TAX_ID", "")
VAT_RATE = float(os.getenv("VAT_RATE", "0.18"))
CURRENCY = os.getenv("CURRENCY", "₪")

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

def _fmt(value: float) -> str:
    """Format number with thousands separator and 2 decimal places."""
    return f"{value:,.2f}"


_jinja = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
_jinja.filters["fmt"] = _fmt


def _next_number(prefix: str, directory: Path) -> str:
    """Generate a sequential document number."""
    existing = list(directory.glob(f"{prefix}*.html"))
    return f"{prefix}{len(existing) + 1:04d}"


def create_calendar_invite(
    client_email: str,
    client_name: str,
    title: str,
    description: str,
    start_datetime: str,
    end_datetime: str,
    location: str = "",
) -> dict:
    """
    Creates an iCal (.ics) calendar invitation and sends it by email.

    start_datetime / end_datetime must be ISO 8601, e.g. '2024-06-15T10:00:00'.
    Returns a dict with keys: success, file, message, email.
    """
    cal = Calendar()
    cal.add("prodid", f"-//{BUSINESS_NAME}//Business Agent//HE")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")

    event = Event()
    event.add("summary", title)
    event.add("description", description)
    event.add("dtstart", datetime.fromisoformat(start_datetime))
    event.add("dtend", datetime.fromisoformat(end_datetime))
    event.add("uid", str(uuid.uuid4()))

    if location:
        event.add("location", location)

    organizer_email = BUSINESS_EMAIL or os.getenv("SENDER_EMAIL", "")
    if organizer_email:
        organizer = vCalAddress(f"MAILTO:{organizer_email}")
        organizer.params["cn"] = vText(BUSINESS_NAME)
        event["organizer"] = organizer

    attendee = vCalAddress(f"MAILTO:{client_email}")
    attendee.params["cn"] = vText(client_name)
    attendee.params["ROLE"] = vText("REQ-PARTICIPANT")
    event.add("attendee", attendee, encode=0)

    cal.add_component(event)

    out_dir = OUTPUT_DIR / "calendar"
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"invite_{client_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ics"
    filepath = out_dir / filename

    with open(filepath, "wb") as f:
        f.write(cal.to_ical())

    start_fmt = datetime.fromisoformat(start_datetime).strftime("%d/%m/%Y %H:%M")
    body = (
        f"שלום {client_name},\n\n"
        f"הנך מוזמן/ת לפגישה: {title}\n"
        f"תאריך ושעה: {start_fmt}\n"
        f"מיקום: {location or 'יישלח בנפרד'}\n\n"
        f"{description}\n\n"
        f"אנא פתח/י את הקובץ המצורף כדי להוסיף את הפגישה ליומן שלך.\n\n"
        f"בברכה,\n{BUSINESS_NAME}"
    )

    email_result = _send_email(
        to_email=client_email,
        to_name=client_name,
        subject=f"זימון לפגישה: {title}",
        body=body,
        attachment_path=str(filepath),
        attachment_name=filename,
    )

    return {
        "success": True,
        "file": str(filepath),
        "message": f"זימון נוצר עבור {client_name} – {title} ב-{start_fmt}",
        "email": email_result,
    }


def create_quote(
    client_email: str,
    client_name: str,
    items: list,
    valid_until: str,
    quote_number: str = None,
    notes: str = "",
) -> dict:
    """
    Creates an HTML price quote, saves it, and sends it by email.

    items: list of {"description": str, "quantity": number, "unit_price": number}
    valid_until: date string, e.g. '30/06/2024'
    Returns a dict with keys: success, file, quote_number, total, message, email.
    """
    out_dir = OUTPUT_DIR / "quotes"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not quote_number:
        quote_number = _next_number("Q", out_dir)

    subtotal, vat, grand_total, enriched_items = _calculate_totals(items)

    context = {
        "doc_type": "הצעת מחיר",
        "doc_number": quote_number,
        "doc_date": datetime.now().strftime("%d/%m/%Y"),
        "valid_until": valid_until,
        "client_name": client_name,
        "client_email": client_email,
        "items": enriched_items,
        "subtotal": subtotal,
        "vat_rate_pct": int(VAT_RATE * 100),
        "vat": vat,
        "grand_total": grand_total,
        "notes": notes,
        "currency": CURRENCY,
        "business_name": BUSINESS_NAME,
        "business_address": BUSINESS_ADDRESS,
        "business_phone": BUSINESS_PHONE,
        "business_email": BUSINESS_EMAIL,
        "business_tax_id": BUSINESS_TAX_ID,
    }

    html = _jinja.get_template("quote.html").render(**context)
    filename = f"quote_{quote_number}_{client_name.replace(' ', '_')}.html"
    filepath = out_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    body = (
        f"שלום {client_name},\n\n"
        f"מצורפת הצעת המחיר שלנו עבורך.\n\n"
        f"מספר הצעה: {quote_number}\n"
        f"סה\"כ כולל מע\"מ: {CURRENCY}{grand_total:,.2f}\n"
        f"בתוקף עד: {valid_until}\n\n"
        f"{notes}\n\n"
        f"לשאלות נוספות אנחנו כאן.\n\nבברכה,\n{BUSINESS_NAME}"
    )

    email_result = _send_email(
        to_email=client_email,
        to_name=client_name,
        subject=f"הצעת מחיר {quote_number} – {BUSINESS_NAME}",
        body=body,
        attachment_path=str(filepath),
        attachment_name=filename,
    )

    return {
        "success": True,
        "file": str(filepath),
        "quote_number": quote_number,
        "total": grand_total,
        "message": f"הצעת מחיר {quote_number} נוצרה עבור {client_name} – סה\"כ {CURRENCY}{grand_total:,.2f}",
        "email": email_result,
    }


def create_invoice(
    client_email: str,
    client_name: str,
    items: list,
    due_date: str,
    invoice_number: str = None,
    notes: str = "",
) -> dict:
    """
    Creates an HTML tax invoice (חשבונית מס), saves it, and sends it by email.

    items: list of {"description": str, "quantity": number, "unit_price": number}
    due_date: payment due date string, e.g. '30/06/2024'
    Returns a dict with keys: success, file, invoice_number, total, message, email.
    """
    out_dir = OUTPUT_DIR / "invoices"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not invoice_number:
        invoice_number = _next_number("INV", out_dir)

    subtotal, vat, grand_total, enriched_items = _calculate_totals(items)

    context = {
        "doc_type": "חשבונית מס",
        "doc_number": invoice_number,
        "doc_date": datetime.now().strftime("%d/%m/%Y"),
        "due_date": due_date,
        "client_name": client_name,
        "client_email": client_email,
        "items": enriched_items,
        "subtotal": subtotal,
        "vat_rate_pct": int(VAT_RATE * 100),
        "vat": vat,
        "grand_total": grand_total,
        "notes": notes,
        "currency": CURRENCY,
        "business_name": BUSINESS_NAME,
        "business_address": BUSINESS_ADDRESS,
        "business_phone": BUSINESS_PHONE,
        "business_email": BUSINESS_EMAIL,
        "business_tax_id": BUSINESS_TAX_ID,
    }

    html = _jinja.get_template("invoice.html").render(**context)
    filename = f"invoice_{invoice_number}_{client_name.replace(' ', '_')}.html"
    filepath = out_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    body = (
        f"שלום {client_name},\n\n"
        f"מצורפת חשבונית המס עבור השירותים שניתנו.\n\n"
        f"מספר חשבונית: {invoice_number}\n"
        f"סה\"כ לתשלום: {CURRENCY}{grand_total:,.2f}\n"
        f"תאריך לתשלום: {due_date}\n\n"
        f"{notes}\n\n"
        f"תודה על שיתוף הפעולה.\n\nבברכה,\n{BUSINESS_NAME}"
    )

    email_result = _send_email(
        to_email=client_email,
        to_name=client_name,
        subject=f"חשבונית מס {invoice_number} – {BUSINESS_NAME}",
        body=body,
        attachment_path=str(filepath),
        attachment_name=filename,
    )

    return {
        "success": True,
        "file": str(filepath),
        "invoice_number": invoice_number,
        "total": grand_total,
        "message": f"חשבונית {invoice_number} נוצרה עבור {client_name} – סה\"כ {CURRENCY}{grand_total:,.2f}",
        "email": email_result,
    }


def _calculate_totals(items: list) -> tuple:
    enriched = []
    subtotal = 0.0
    for item in items:
        qty = float(item.get("quantity", 1))
        price = float(item.get("unit_price", 0))
        line_total = qty * price
        subtotal += line_total
        enriched.append({
            "description": item.get("description", ""),
            "quantity": qty,
            "unit_price": price,
            "line_total": line_total,
        })
    vat = subtotal * VAT_RATE
    grand_total = subtotal + vat
    return subtotal, vat, grand_total, enriched


def _send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    attachment_path: str = None,
    attachment_name: str = None,
) -> dict:
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    sender_email = os.getenv("SENDER_EMAIL", smtp_user)
    sender_name = os.getenv("SENDER_NAME", BUSINESS_NAME)

    if not all([smtp_host, smtp_user, smtp_password]):
        return {
            "sent": False,
            "message": "SMTP לא מוגדר – הקובץ נשמר בתיקיית output/ בלבד.",
        }

    msg = MIMEMultipart()
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path:
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        name = attachment_name or Path(attachment_path).name
        part.add_header("Content-Disposition", f'attachment; filename="{name}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return {"sent": True, "message": f"אימייל נשלח בהצלחה אל {to_email}"}
    except Exception as exc:
        return {"sent": False, "message": f"שליחת האימייל נכשלה: {exc}"}
