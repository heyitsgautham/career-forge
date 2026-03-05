"""
Run database migration for experience and education arrays.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import async_engine, get_db
from app.core.config import settings


async def run_migration():
    """Run the migration to add experience and education columns."""
    print("Starting migration: add experience and education arrays...")
    
    migration_sql = """
    -- Add experience column (JSON array)
    ALTER TABLE users ADD COLUMN IF NOT EXISTS experience JSONB;
    
    -- Add education column (JSON array)
    ALTER TABLE users ADD COLUMN IF NOT EXISTS education JSONB;
    
    -- Add comments for documentation
    COMMENT ON COLUMN users.experience IS 'Array of work experience entries: [{company, title, dates, location, highlights}]';
    COMMENT ON COLUMN users.education IS 'Array of education entries: [{school, degree, field, dates, location, gpa}]';
    """
    
    try:
        async with async_engine.begin() as conn:
            # Execute migration
            await conn.execute(text(migration_sql))
            print("✅ Migration completed successfully!")
            print("   - Added 'experience' column (JSONB)")
            print("   - Added 'education' column (JSONB)")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_migration())
