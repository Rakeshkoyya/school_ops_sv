"""Check and fix enum values in database."""
from sqlalchemy import text
from app.core.database import engine

with engine.connect() as conn:
    # Check current enum values
    result = conn.execute(text(
        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = 'evoreductiontype'"
    ))
    values = [row[0] for row in result]
    print(f"Current enum values: {values}")
    
    if 'none' in values:
        print("Found lowercase values, updating to uppercase...")
        
        # Add new uppercase values
        conn.execute(text("ALTER TYPE evoreductiontype ADD VALUE IF NOT EXISTS 'NONE'"))
        conn.execute(text("ALTER TYPE evoreductiontype ADD VALUE IF NOT EXISTS 'GRADUAL'"))
        conn.execute(text("ALTER TYPE evoreductiontype ADD VALUE IF NOT EXISTS 'FIXED'"))
        conn.commit()
        
        # Update existing rows to use uppercase
        conn.execute(text("UPDATE tasks SET evo_reduction_type = 'NONE' WHERE evo_reduction_type = 'none'"))
        conn.execute(text("UPDATE tasks SET evo_reduction_type = 'GRADUAL' WHERE evo_reduction_type = 'gradual'"))
        conn.execute(text("UPDATE tasks SET evo_reduction_type = 'FIXED' WHERE evo_reduction_type = 'fixed'"))
        conn.commit()
        
        # Update the default
        conn.execute(text("ALTER TABLE tasks ALTER COLUMN evo_reduction_type SET DEFAULT 'NONE'"))
        conn.commit()
        
        print("Updated enum values to uppercase!")
        
    elif 'NONE' in values:
        print("Enum values are already uppercase - good!")
