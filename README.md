# Business Assistant Agent – סוכן עסקי

סוכן AI מבוסס Claude המסייע לניהול עסק:

- 📅 **זימונים ביומן** – יוצר קובץ iCal ושולח אותו ללקוח
- 💼 **הצעות מחיר** – מייצר מסמך HTML מקצועי עם מע"מ ושולח למייל
- 🧾 **חשבוניות מס** – מייצר חשבונית HTML הכוללת מע"מ ושולח למייל

---

## מבנה הפרויקט

```
business-agent/
├── main.py                 # נקודת כניסה
├── requirements.txt
├── .env.example            # תבנית קובץ הגדרות
├── agent/
│   ├── agent.py            # לוגיקת הסוכן (Claude + tool use)
│   └── tools.py            # כלים: יומן, הצעה, חשבונית, מייל
├── templates/
│   ├── quote.html          # תבנית הצעת מחיר (RTL, עברית)
│   └── invoice.html        # תבנית חשבונית מס (RTL, עברית)
└── output/
    ├── calendar/           # קבצי iCal שנוצרו
    ├── quotes/             # הצעות מחיר שנוצרו
    └── invoices/           # חשבוניות שנוצרו
```

---

## התקנה

```bash
# שכפול / כניסה לתיקייה
cd business-agent

# התקנת תלויות
pip install -r requirements.txt

# הגדרת משתני סביבה
cp .env.example .env
# ערוך את .env עם פרטי העסק ומפתח ה-API
```

### קובץ `.env` נדרש

| משתנה | תיאור | חובה |
|---|---|---|
| `ANTHROPIC_API_KEY` | מפתח API של Anthropic | ✅ |
| `BUSINESS_NAME` | שם העסק | מומלץ |
| `BUSINESS_ADDRESS` | כתובת | אופציונלי |
| `BUSINESS_PHONE` | טלפון | אופציונלי |
| `BUSINESS_EMAIL` | אימייל | אופציונלי |
| `BUSINESS_TAX_ID` | מספר עוסק מורשה | אופציונלי |
| `VAT_RATE` | שיעור מע"מ (ברירת מחדל: `0.18`) | אופציונלי |
| `SMTP_HOST` | שרת דואר (למשל: `smtp.gmail.com`) | לשליחת מייל |
| `SMTP_PORT` | פורט (ברירת מחדל: `587`) | לשליחת מייל |
| `SMTP_USER` | שם משתמש SMTP | לשליחת מייל |
| `SMTP_PASSWORD` | סיסמת SMTP / App Password | לשליחת מייל |
| `SENDER_EMAIL` | כתובת השולח | לשליחת מייל |
| `SENDER_NAME` | שם השולח | לשליחת מייל |

> **שליחת מייל**: אם SMTP לא מוגדר, הקבצים נשמרים ב-`output/` בלבד.  
> עם Gmail: הפעל [App Passwords](https://myaccount.google.com/apppasswords) והגדר `SMTP_PASSWORD=<app-password>`.

---

## הפעלה

```bash
python main.py
```

מצב verbose (מציג פרטי כלים):
```bash
python main.py --verbose
```

---

## דוגמאות שיחה

```
אתה: קבע לי פגישה עם יוסי לוי yossi@example.com ביום שני ה-16/06 בשעה 10:00 למשך שעה
סוכן: קובץ הזימון נוצר ונשמר בתיקיית output/calendar/

אתה: שלח הצעת מחיר לחברת ABC abc@company.com עם:
      - פיתוח אתר: 1 יחידה, 8000 ש"ח
      - תחזוקה חודשית: 3 חודשים, 500 ש"ח לחודש
      הצעה בתוקף עד 30/06/2025
סוכן: הצעת מחיר Q0001 נוצרה – סה"כ ₪10,030.00 (כולל מע"מ)

אתה: הוצא חשבונית לדנה ברק dana@startup.io עבור ייעוץ עסקי 5 שעות ב-400 ש"ח לשעה
      לתשלום עד 15/05/2025
סוכן: חשבונית INV0001 נוצרה – סה"כ ₪2,360.00 (כולל מע"מ)
```

---

## הערות טכניות

- **מסמכי HTML** ניתן לפתוח בדפדפן ולהדפיס כ-PDF (Ctrl+P → Save as PDF)
- **קבצי iCal** נפתחים ב-Google Calendar, Outlook, Apple Calendar
- **מע"מ**: ברירת המחדל היא 18%. ניתן לשנות ב-`.env` עם `VAT_RATE=0.17`
- **מספור אוטומטי**: מספרי הצעות/חשבוניות נוצרים אוטומטית (Q0001, INV0001...)
