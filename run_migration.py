import sqlite3
import re
import sys

DB = 'nexuzy_hotel.db'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    unique_index_name = None
    try:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'")
        row = cur.fetchone()
        create_sql = row[0] if row and row[0] else ''
        found_unique_decl = False
        if create_sql and re.search(r"booking_ref\s+TEXT\s+UNIQUE", create_sql, re.IGNORECASE):
            found_unique_decl = True

        if not found_unique_decl:
            cur.execute("PRAGMA index_list('bookings')")
            indexes = cur.fetchall()
            for idx in indexes:
                idx_name = idx[1]
                is_unique = idx[2]
                if is_unique:
                    try:
                        cur.execute(f"PRAGMA index_info('{idx_name}')")
                        cols = [c[2] for c in cur.fetchall()]
                        if 'booking_ref' in cols:
                            unique_index_name = idx_name
                            found_unique_decl = True
                            break
                    except Exception:
                        continue

        if not found_unique_decl:
            print('No UNIQUE constraint or index on bookings.booking_ref detected. Nothing to do.')
            return 0

        print('UNIQUE constraint detected on bookings.booking_ref. Proceeding with safe migration...')
        cur.execute('BEGIN')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bookings_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_ref TEXT NOT NULL,
                guest_id INTEGER,
                room_id INTEGER,
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Reserved', 'Checked-In', 'Checked-Out', 'Cancelled')),
                total_amount REAL,
                advance_payment REAL DEFAULT 0.0,
                FOREIGN KEY(guest_id) REFERENCES guests(id),
                FOREIGN KEY(room_id) REFERENCES rooms(id)
            )
        ''')
        cur.execute("INSERT OR REPLACE INTO bookings_new (id, booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, advance_payment) SELECT id, booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, advance_payment FROM bookings")
        cur.execute("DROP TABLE IF EXISTS bookings")
        cur.execute("ALTER TABLE bookings_new RENAME TO bookings")
        if unique_index_name:
            try:
                cur.execute(f"DROP INDEX IF EXISTS {unique_index_name}")
            except Exception:
                pass
        conn.commit()
        print('Migration completed successfully.')
        return 0
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print('Migration failed:', e)
        return 2
    finally:
        conn.close()

if __name__ == '__main__':
    sys.exit(main())
