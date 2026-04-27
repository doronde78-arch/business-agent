#!/usr/bin/env python3
"""
Business Assistant Agent
Usage: python main.py [--verbose]
"""

import argparse
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from agent.agent import run


def main():
    parser = argparse.ArgumentParser(
        description="סוכן עסקי – שולח זימונים, הצעות מחיר וחשבוניות",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
דוגמאות לפקודות:
  "קבע לי פגישה עם דוד כהן דוד@example.com ביום שני ה-15/6 בשעה 10:00 למשך שעה"
  "שלח הצעת מחיר לחברת ABC עם 5 ימי עבודה ב-1500 ש"ח ליום"
  "הוצא חשבונית לרחל לוי עבור עיצוב לוגו 3500 ש"ח לתשלום עד סוף החודש"
        """,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="הצג פרטי כלים ותוצאות גולמיות"
    )
    args = parser.parse_args()

    run(verbose=args.verbose)


if __name__ == "__main__":
    main()
