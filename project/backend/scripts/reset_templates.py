import sqlite3

conn = sqlite3.connect('latex_agent.db')
cursor = conn.cursor()

# Delete all system templates
cursor.execute('DELETE FROM templates WHERE is_system = 1')
deleted = cursor.rowcount
print(f"Deleted {deleted} system templates")

conn.commit()
conn.close()

print("System templates cleared. Now call POST /api/templates/init-system to reinitialize.")
