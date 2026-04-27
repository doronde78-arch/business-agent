"""
Business assistant agent powered by Claude.
Supports: calendar invitations, price quotes, tax invoices.
"""

import json
import os
import sys
from anthropic import Anthropic
from dotenv import load_dotenv

from . import tools as biz_tools

load_dotenv()

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """אתה סוכן עסקי חכם ומקצועי. אתה עוזר לנהל עסק ויכול:

1. **זימונים ביומן** – לקבוע פגישות עם לקוחות ולשלוח להם זימון ביומן (קובץ iCal)
2. **הצעות מחיר** – ליצור ולשלוח הצעות מחיר מפורטות בפורמט HTML מקצועי
3. **חשבוניות מס** – ליצור ולשלוח חשבוניות מס מקצועיות הכוללות מע"מ

**הנחיות:**
- תמיד אסוף את כל המידע הנדרש לפני ביצוע פעולה. אם חסר מידע – שאל.
- לגבי תאריכים ושעות – בקש מהמשתמש לאשר לפני שליחה.
- כאשר הפעולה הושלמה, הודע בבירור מה נעשה ואיפה נשמר הקובץ.
- אם SMTP לא מוגדר, הסבר שהקובץ נשמר מקומית בתיקיית output/ ויש להגדיר SMTP לשליחה.
- היה תמיד מנומס, ענייני ומקצועי.
- ענה תמיד בעברית אלא אם המשתמש מדבר אנגלית.

**פורמט תאריכים לפגישות:** ISO 8601 – YYYY-MM-DDTHH:MM:SS
**פורמט תאריכים לחשבוניות/הצעות:** DD/MM/YYYY"""

TOOLS = [
    {
        "name": "schedule_meeting",
        "description": "יוצר זימון ביומן (קובץ iCal) לפגישה עם לקוח ושולח אותו אליו באימייל. השתמש בכלי זה כאשר המשתמש רוצה לקבוע פגישה.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {
                    "type": "string",
                    "description": "כתובת האימייל של הלקוח"
                },
                "client_name": {
                    "type": "string",
                    "description": "שם מלא של הלקוח"
                },
                "title": {
                    "type": "string",
                    "description": "כותרת/נושא הפגישה"
                },
                "description": {
                    "type": "string",
                    "description": "תיאור מפורט של הפגישה ומטרתה"
                },
                "start_datetime": {
                    "type": "string",
                    "description": "תאריך ושעת התחלה בפורמט ISO 8601, למשל: 2024-06-15T10:00:00"
                },
                "end_datetime": {
                    "type": "string",
                    "description": "תאריך ושעת סיום בפורמט ISO 8601, למשל: 2024-06-15T11:00:00"
                },
                "location": {
                    "type": "string",
                    "description": "מיקום הפגישה – כתובת פיזית, קישור Zoom, וכו' (אופציונלי)"
                }
            },
            "required": ["client_email", "client_name", "title", "description",
                         "start_datetime", "end_datetime"]
        }
    },
    {
        "name": "create_quote",
        "description": "יוצר הצעת מחיר מקצועית בפורמט HTML ושולח אותה ללקוח באימייל. השתמש כאשר המשתמש רוצה לשלוח הצעת מחיר.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {
                    "type": "string",
                    "description": "כתובת האימייל של הלקוח"
                },
                "client_name": {
                    "type": "string",
                    "description": "שם הלקוח או שם החברה"
                },
                "items": {
                    "type": "array",
                    "description": "רשימת הפריטים/שירותים בהצעה",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "תיאור הפריט או השירות"
                            },
                            "quantity": {
                                "type": "number",
                                "description": "כמות"
                            },
                            "unit_price": {
                                "type": "number",
                                "description": "מחיר ליחידה (לפני מע\"מ)"
                            }
                        },
                        "required": ["description", "quantity", "unit_price"]
                    }
                },
                "valid_until": {
                    "type": "string",
                    "description": "תאריך תפוגת ההצעה בפורמט DD/MM/YYYY"
                },
                "quote_number": {
                    "type": "string",
                    "description": "מספר הצעה ידני (אופציונלי, נוצר אוטומטית אם לא מסופק)"
                },
                "notes": {
                    "type": "string",
                    "description": "הערות, תנאי תשלום, או מידע נוסף (אופציונלי)"
                }
            },
            "required": ["client_email", "client_name", "items", "valid_until"]
        }
    },
    {
        "name": "create_invoice",
        "description": "יוצר חשבונית מס (כולל מע\"מ) בפורמט HTML ושולח אותה ללקוח באימייל. השתמש כאשר המשתמש רוצה להוציא חשבונית.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {
                    "type": "string",
                    "description": "כתובת האימייל של הלקוח"
                },
                "client_name": {
                    "type": "string",
                    "description": "שם הלקוח או שם החברה"
                },
                "items": {
                    "type": "array",
                    "description": "רשימת השירותים/המוצרים בחשבונית",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "תיאור השירות או המוצר"
                            },
                            "quantity": {
                                "type": "number",
                                "description": "כמות"
                            },
                            "unit_price": {
                                "type": "number",
                                "description": "מחיר ליחידה (לפני מע\"מ)"
                            }
                        },
                        "required": ["description", "quantity", "unit_price"]
                    }
                },
                "due_date": {
                    "type": "string",
                    "description": "תאריך לתשלום בפורמט DD/MM/YYYY"
                },
                "invoice_number": {
                    "type": "string",
                    "description": "מספר חשבונית ידני (אופציונלי, נוצר אוטומטית אם לא מסופק)"
                },
                "notes": {
                    "type": "string",
                    "description": "הערות, פרטי חשבון בנק לתשלום, וכו' (אופציונלי)"
                }
            },
            "required": ["client_email", "client_name", "items", "due_date"]
        }
    }
]

TOOL_HANDLERS = {
    "schedule_meeting": biz_tools.create_calendar_invite,
    "create_quote": biz_tools.create_quote,
    "create_invoice": biz_tools.create_invoice,
}


def _run_tool(tool_name: str, tool_input: dict) -> str:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"כלי לא מוכר: {tool_name}"}, ensure_ascii=False)
    try:
        result = handler(**tool_input)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def run(verbose: bool = False) -> None:
    """Start the interactive business assistant agent."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("שגיאה: ANTHROPIC_API_KEY לא מוגדר. אנא הגדר אותו בקובץ .env")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    messages: list[dict] = []

    print()
    print("━" * 56)
    print("  סוכן עסקי  |  Business Assistant Agent")
    print("━" * 56)
    print("  פקודות: 'יציאה' / 'exit' / Ctrl+C להפסקה")
    print("━" * 56)
    print()

    while True:
        try:
            user_input = input("אתה: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nתודה ושלום!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "יציאה", "יצא"}:
            print("תודה ושלום!")
            break

        messages.append({"role": "user", "content": user_input})

        # Agentic loop: keep going until Claude stops using tools
        while True:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                # Final text reply
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        print(f"\nסוכן: {block.text}\n")
                break

            # Execute all tool calls
            tool_results = []
            for tool_use in tool_uses:
                if verbose:
                    print(f"\n[כלי: {tool_use.name}]")
                    print(f"[קלט: {json.dumps(tool_use.input, ensure_ascii=False)}]")

                result_str = _run_tool(tool_use.name, tool_use.input)

                if verbose:
                    print(f"[תוצאה: {result_str}]")
                else:
                    try:
                        r = json.loads(result_str)
                        msg = r.get("message", "")
                        email = r.get("email", {})
                        email_msg = email.get("message", "") if isinstance(email, dict) else ""
                        if msg:
                            print(f"\n  ✓ {msg}")
                        if email_msg:
                            print(f"  ✉ {email_msg}")
                    except Exception:
                        pass

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})
