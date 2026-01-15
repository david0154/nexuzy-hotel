import sqlite3
import sys

DB='nexuzy_hotel.db'

required_tables = {
    'bookings': ['id','booking_ref','guest_id','room_id','check_in','check_out','status','total_amount','advance_payment'],
    'guests': ['id','name','phone','email','address'],
    'booking_persons': ['id','booking_ref','person_name','is_primary'],
    'rooms': ['id','room_number','room_type','bed_type','rate','status'],
    'daily_income': ['date','total','last_updated'],
    'daily_expenses': ['id','date','name','amount','note','created_at'],
    'settings': ['id','hotel_name','address','address_line1','address_line2','gst_number','contact_number','hotel_rules','cgst_rate','sgst_rate','igst_rate','enable_cgst_sgst','enable_igst']
}

print('Opening DB:', DB)
try:
    conn = sqlite3.connect(DB)
except Exception as e:
    print('Could not open DB:', e)
    sys.exit(1)

cursor = conn.cursor()

# list tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
all_tables = set(r[0] for r in cursor.fetchall())
print('\nFound tables:')
for t in sorted(all_tables):
    print(' -', t)

print('\nChecking required tables and columns...')
errors = []
for table, cols in required_tables.items():
    if table not in all_tables:
        errors.append(f"Missing table: {table}")
        continue
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [r[1] for r in cursor.fetchall()]
    missing = [c for c in cols if c not in existing]
    if missing:
        errors.append(f"Table {table} missing columns: {missing}")
    else:
        print(f"Table {table}: OK")

if errors:
    print('\nIssues detected:')
    for e in errors:
        print(' *', e)
    sys.exit(2)
else:
    print('\nSchema check OK. No missing tables/columns detected.')
    sys.exit(0)
