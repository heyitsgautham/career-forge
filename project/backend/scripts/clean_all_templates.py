import sqlite3

conn = sqlite3.connect('latex_agent.db')
cursor = conn.cursor()

# Check current templates
cursor.execute('SELECT id, name, is_system FROM templates ORDER BY is_system DESC, name')
templates = cursor.fetchall()

print(f"Total templates in database: {len(templates)}")
print("\nCurrent templates:")
for t in templates:
    print(f"  - {t[1]} (ID: {t[0]}, System: {t[2]})")

# Delete ALL system templates
cursor.execute('DELETE FROM templates WHERE is_system = 1')
deleted = cursor.rowcount
print(f"\nDeleted {deleted} system templates")

conn.commit()

# Verify deletion
cursor.execute('SELECT COUNT(*) FROM templates WHERE is_system = 1')
remaining = cursor.fetchone()[0]
print(f"Remaining system templates: {remaining}")

conn.close()

print("\n✅ Database cleaned. Now call POST /api/templates/init-system to add only the Base Professional template.")
