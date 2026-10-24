"""Print the LaTeX templates a user owns in the local SQLite database.

Usage:
    uv run python scripts/get_user_templates.py <email> [path/to/latex_agent.db]
"""

import sqlite3
import sys

if len(sys.argv) not in (2, 3):
    sys.exit("usage: get_user_templates.py <email> [db_path]")

email = sys.argv[1]
db_path = sys.argv[2] if len(sys.argv) == 3 else "latex_agent.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, email, name FROM users WHERE email = ?", (email,))
user = cursor.fetchone()
print(f"User: {user}")

if user:
    user_id = user[0]
    cursor.execute(
        "SELECT id, name, description, latex_content, is_system FROM templates WHERE user_id = ?",
        (user_id,),
    )
    templates = cursor.fetchall()
    print(f"\nFound {len(templates)} template(s)")

    for template in templates:
        print(f"\nTemplate ID: {template[0]}")
        print(f"Name: {template[1]}")
        print(f"Description: {template[2]}")
        print(f"Is System: {template[4]}")
        print(f"LaTeX Content Length: {len(template[3])} characters")
        print("\n--- LaTeX Content Preview (first 500 chars) ---")
        print(template[3][:500])

conn.close()
