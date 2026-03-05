"""Check the last resume's LaTeX for syntax errors."""
import sqlite3
import sys

def check_latex():
    conn = sqlite3.connect('latex_agent.db')
    cursor = conn.cursor()
    
    # Get the latest resume
    cursor.execute('''
        SELECT id, name, latex_content, status, error_message, compilation_log
        FROM resumes 
        ORDER BY updated_at DESC 
        LIMIT 1
    ''')
    
    result = cursor.fetchone()
    if not result:
        print("No resumes found")
        conn.close()
        return
    
    resume_id, name, latex_content, status, error_message, compilation_log = result
    
    print(f"Resume ID: {resume_id}")
    print(f"Name: {name}")
    print(f"Status: {status}")
    print(f"Error: {error_message}")
    print(f"Log: {compilation_log}")
    print("\n" + "="*80)
    print("LaTeX Content:")
    print("="*80)
    
    if latex_content:
        print(latex_content)
        
        # Check for common issues
        print("\n" + "="*80)
        print("Syntax Checks:")
        print("="*80)
        
        open_braces = latex_content.count('{')
        close_braces = latex_content.count('}')
        print(f"Open braces: {open_braces}")
        print(f"Close braces: {close_braces}")
        print(f"Balanced: {open_braces == close_braces}")
        
        # Check for common problematic patterns
        if r'\\' in latex_content and latex_content.count(r'\\') > 100:
            print("WARNING: Many \\\\ found - may have line break issues")
        
        # Check for unescaped special chars
        special_chars = ['&', '%', '$', '#', '_']
        for char in special_chars:
            count = latex_content.count(char)
            escaped_count = latex_content.count('\\' + char)
            if count > escaped_count:
                print(f"WARNING: Unescaped '{char}' found ({count - escaped_count} times)")
    else:
        print("No LaTeX content")
    
    conn.close()

if __name__ == "__main__":
    check_latex()
