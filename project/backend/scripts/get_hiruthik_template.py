import sqlite3

conn = sqlite3.connect('latex_agent.db')
cursor = conn.cursor()

# Find user
cursor.execute('SELECT id, email, name FROM users WHERE email = "xmyhiruthik2020@gmail.com"')
user = cursor.fetchone()
print(f"User: {user}")

if user:
    user_id = user[0]
    # Get templates for this user
    cursor.execute('SELECT id, name, description, latex_content, is_system FROM templates WHERE user_id = ?', (user_id,))
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
