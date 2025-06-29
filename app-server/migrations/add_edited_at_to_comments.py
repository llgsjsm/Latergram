#!/usr/bin/env python3
"""
Migration script to add edited_at column to comment table
This allows tracking when comments are edited to display "Edited" timestamp
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from models.database import db
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MySQL Database Configuration
DB_USER = os.environ.get('DB_USER', '') 
DB_PASSWORD = os.environ.get('DB_PASSWORD', '') 
DB_HOST = os.environ.get('DB_HOST', '')
DB_PORT = os.environ.get('DB_PORT', '')
DB_NAME = os.environ.get('DB_NAME', '')

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def add_edited_at_column():
    """Add edited_at column to comment table"""
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = :schema 
                AND TABLE_NAME = 'comment' 
                AND COLUMN_NAME = 'edited_at'
            """), {'schema': DB_NAME})
            
            column_exists = result.fetchone()[0] > 0
            
            if column_exists:
                print("Column 'edited_at' already exists in comment table.")
                return
            
            # Add the edited_at column
            db.session.execute(text("""
                ALTER TABLE comment 
                ADD COLUMN edited_at DATETIME NULL 
                COMMENT 'Timestamp when comment was last edited'
            """))
            
            db.session.commit()
            print("Successfully added 'edited_at' column to comment table.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error adding edited_at column: {e}")
            raise

def rollback_migration():
    """Remove edited_at column from comment table"""
    with app.app_context():
        try:
            # Check if column exists
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = :schema 
                AND TABLE_NAME = 'comment' 
                AND COLUMN_NAME = 'edited_at'
            """), {'schema': DB_NAME})
            
            column_exists = result.fetchone()[0] > 0
            
            if not column_exists:
                print("Column 'edited_at' does not exist in comment table.")
                return
            
            # Remove the edited_at column
            db.session.execute(text("""
                ALTER TABLE comment 
                DROP COLUMN edited_at
            """))
            
            db.session.commit()
            print("Successfully removed 'edited_at' column from comment table.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error removing edited_at column: {e}")
            raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Add edited_at column to comment table')
    parser.add_argument('--rollback', action='store_true', 
                       help='Rollback the migration (remove the column)')
    
    args = parser.parse_args()
    
    if args.rollback:
        print("Rolling back migration...")
        rollback_migration()
    else:
        print("Running migration...")
        add_edited_at_column()
    
    print("Migration completed.")
