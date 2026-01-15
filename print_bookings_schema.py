import sqlite3
conn = sqlite3.connect('nexuzy_hotel.db')
cur = conn.cursor()
cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'")
row = cur.fetchone()
print('CREATE TABLE SQL:\n')
print(row[0] if row and row[0] else '<not found>')
print('\nPRAGMA index_list(\'bookings\'):\n')
cur.execute("PRAGMA index_list('bookings')")
for idx in cur.fetchall():
    print(idx)
    try:
        name = idx[1]
        cur.execute(f"PRAGMA index_info('{name}')")
        print('  index_info:', cur.fetchall())
    except Exception as e:
        print('  index_info failed:', e)
conn.close()
