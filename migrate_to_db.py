#!/usr/bin/env python3
"""
Migration script to convert ticker_list.json to SQLite database
"""

import json
import sys
from database import init_db, create_user

def migrate_from_json(json_file="ticker_list.json"):
    print("="*60)
    print("TradeAdvisor Data Migration")
    print("="*60)
    print()
    
    # Initialize database
    print("1. Initializing database...")
    init_db()
    print("   ✓ Database schema created")
    print()
    
    # Load JSON data
    print(f"2. Loading data from {json_file}...")
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"   ✗ Error: {json_file} not found")
        print(f"   Make sure ticker_list.json is in the same folder")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"   ✗ Error: Invalid JSON format: {e}")
        sys.exit(1)
    
    users = data.get('users', [])
    print(f"   ✓ Found {len(users)} users")
    print()
    
    # Migrate users
    print("3. Migrating users to database...")
    migrated = 0
    skipped = 0
    
    for i, user in enumerate(users, 1):
        name = user.get('name', '').strip()
        email = user.get('email', '').strip()
        tickers = user.get('tickers', [])
        
        if not name or not email:
            print(f"   ⚠ User {i}: Missing name or email, skipping...")
            skipped += 1
            continue
        
        try:
            user_id = create_user(name, email, tickers)
            if user_id:
                print(f"   ✓ User {i}: {name} ({email}) - {len(tickers)} tickers")
                migrated += 1
            else:
                print(f"   ⚠ User {i}: {email} already exists, skipping...")
                skipped += 1
        except Exception as e:
            print(f"   ✗ User {i}: Error: {e}")
            skipped += 1
    
    print()
    print("="*60)
    print("Migration Complete!")
    print("="*60)
    print(f"✓ Successfully migrated: {migrated} users")
    if skipped > 0:
        print(f"⚠ Skipped: {skipped} users")
    print()
    print("Next steps:")
    print("1. Start your app: python app.py")
    print("2. Go to http://127.0.0.1:5000")
    print("3. Login with one of your migrated email addresses")
    print()

if __name__ == "__main__":
    migrate_from_json()