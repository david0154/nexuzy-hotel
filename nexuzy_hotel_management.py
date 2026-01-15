import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from datetime import datetime, timedelta
import os
import sys
import platform
import subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import time
import random
from PIL import Image, ImageTk
import shutil
import webbrowser
import textwrap
import re
import logging
from pathlib import Path

# --- Simple file logger for diagnostics ---
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'app.log'),
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger('nexuzy')

# --- Software Details ---
SOFTWARE_NAME = "Nexuzy Hotel Management by Monoj"
SOFTWARE_VERSION = "2.4.1"  # <-- UPDATED: Fixes & History/Guest Detail Enhancement
DB_NAME = 'nexuzy_hotel.db'

# --- UI Colors ---
COLOR_PRIMARY = "#0052cc"  # Nexuzy Blue
COLOR_PRIMARY_LIGHT = "#e6f0ff"
COLOR_LIGHT_BG = "#ffffff"
COLOR_DARK_TEXT = "#222222"
COLOR_HEADER_FG = "#ffffff"
COLOR_SUCCESS = "#006400"  # Dark Green
COLOR_SUCCESS_LIGHT = "#d4edda"
COLOR_DANGER = "#a30000"  # Dark Red
COLOR_DANGER_LIGHT = "#f8d7da"
COLOR_WARNING = "#856404"
COLOR_WARNING_LIGHT = "#fff3cd"
COLOR_MAINTENANCE = "#383d41"
COLOR_MAINTENANCE_LIGHT = "#d6d8d9"
COLOR_ODD_ROW = "#f8f9fa"  # Light grey for treeview
COLOR_EVEN_ROW = "#ffffff"


# --- Database Helper ---
def _add_column_if_not_exists(conn, table_name, column_name, column_type, default_value=None):
    """Robustly adds a column to a table if it doesn't already exist."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]

    if column_name not in columns:
        try:
            query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            if default_value is not None:
                if isinstance(default_value, str):
                    query += f" DEFAULT '{default_value}'"
                else:
                    query += f" DEFAULT {default_value}"

            cursor.execute(query)
            conn.commit()
            print(f"Added column '{column_name}' to table '{table_name}'.")
        except sqlite3.OperationalError as e:
            print(f"Could not add column {column_name} to {table_name}: {e}")


def resource_path(relative_path: str) -> str:
    """Return the absolute path to a resource, working for dev and for PyInstaller onefile.

    When running as a bundled exe, files added with --add-data are extracted to sys._MEIPASS.
    """
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_user_pdfs_dir(subfolder: str = None) -> str:
    """Return a path inside the user's Documents folder suitable for storing generated PDFs.

    Creates the folder on first call. If subfolder is provided, it will be created under the base PDFs folder.
    """
    """Create and return a folder on the user's Desktop to store PDFs.

    Folder layout (Windows/macOS/Linux):
      <HOME>/Desktop/Nexuzy hotel bill name/<subfolder>

    Falls back to Documents/NexuzyHotelPDFs or the current working directory if Desktop
    isn't writable.
    """
    try:
        home = str(Path.home())
    except Exception:
        home = os.path.expanduser('~')

    # Preferred: Desktop under home (user-requested folder name)
    desktop_base = os.path.join(home, 'Desktop', 'Nexuzy hotel bill')
    fallback_docs = os.path.join(home, 'Documents', 'NexuzyHotelPDFs')

    base = desktop_base
    if subfolder:
        base = os.path.join(base, subfolder)

    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        # Try fallback to Documents
        try:
            base = fallback_docs
            if subfolder:
                base = os.path.join(base, subfolder)
            os.makedirs(base, exist_ok=True)
        except Exception:
            # last-resort fallback to current directory if Documents/Desktop is not writable
            base = os.path.abspath('.')

    return base


def cleanup_old_pdfs(root_dir: str, days: int = 30):
    """Remove files under root_dir older than `days` days. Only removes files with .pdf extension.

    This is safe to call repeatedly; errors are logged but do not raise.
    """
    try:
        cutoff = time.time() - (days * 24 * 3600)
        if not root_dir:
            return
        # If root_dir is a subfolder (e.g., Desktop/Nexuzy hotel bill name/Invoices), move up one
        base = root_dir
        # If path contains known subfolder names, normalize to top-level Nexuzy folder
        try:
            p = Path(root_dir)
            # if last part looks like a bill-type folder, use parent
            if p.name.lower() in ('invoices', 'advancereceipts', 'advanceReceipts'.lower(), 'advanceReceipts') and p.parent:
                base = str(p.parent)
        except Exception:
            base = root_dir

        for root, dirs, files in os.walk(base):
            for fname in files:
                if not fname.lower().endswith('.pdf'):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    if mtime < cutoff:
                        try:
                            os.remove(fpath)
                            logger.info('Removed old PDF: %s', fpath)
                        except Exception as e:
                            logger.warning('Failed to remove old PDF %s: %s', fpath, e)
                except Exception:
                    continue
    except Exception as e:
        logger.exception('cleanup_old_pdfs failed: %s', e)

# --- Utility to enable Copy/Paste on Windows/Linux ---
def enable_copy_paste(widget):
    """Binds standard copy/paste/cut shortcuts to a widget."""
    if platform.system() == "Darwin": # macOS bindings
        widget.bind('<Command-c>', lambda e: widget.event_generate('<<Copy>>'))
        widget.bind('<Command-v>', lambda e: widget.event_generate('<<Paste>>'))
        widget.bind('<Command-x>', lambda e: widget.event_generate('<<Cut>>'))
    else: # Windows/Linux bindings (Ctrl)
        widget.bind('<Control-c>', lambda e: widget.event_generate('<<Copy>>'))
        widget.bind('<Control-v>', lambda e: widget.event_generate('<<Paste>>'))
        widget.bind('<Control-x>', lambda e: widget.event_generate('<<Cut>>'))
        
# --- Main Application Class ---


class HotelManagementApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{SOFTWARE_NAME} - {SOFTWARE_VERSION}")
        self.geometry("1366x768")
        self.state('zoomed')
        self.set_app_icon('logo.ico')  # Set app icon
        self.configure(background=COLOR_LIGHT_BG)

        # Database Initialization
        self.db_conn = self.init_database()
        # Cleanup old PDFs from user's Desktop Nexuzy folder (keep last 30 days)
        try:
            base = get_user_pdfs_dir()
            cleanup_old_pdfs(base, days=30)
        except Exception:
            # Do not block startup on cleanup errors
            logger.exception('PDF cleanup at startup failed')

        # User Role (Default to None until login)
        self.user_role = None
        self.clock_label = None  # For the live clock
        self.login_logo_image = None # For login screen logo
        self.header_logo_image = None # For main dashboard logo (NEW)

        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.configure_styles()
        
        # --- NEW: Enable global copy/paste for all widgets ---
        self.bind_class("Entry", "<Control-c>", self.copy_event)
        self.bind_class("Entry", "<Control-v>", self.paste_event)
        self.bind_class("Entry", "<Control-x>", self.cut_event)
        self.bind_class("TEntry", "<Control-c>", self.copy_event)
        self.bind_class("TEntry", "<Control-v>", self.paste_event)
        self.bind_class("TEntry", "<Control-x>", self.cut_event)
        self.bind_class("Text", "<Control-c>", self.copy_event)
        self.bind_class("Text", "<Control-v>", self.paste_event)
        self.bind_class("Text", "<Control-x>", self.cut_event)
        # --- END NEW ---

        self.create_login_screen()

    # --- NEW: Copy/Paste handlers (needed because ttk.Entry often overrides default bindings) ---
    def copy_event(self, event):
        event.widget.event_generate('<<Copy>>')
        # FIX: Added copy functionality for text selections 
        if event.widget.winfo_class() == 'Treeview':
            # Handle Treeview copy (Copying Booking Ref #)
            selected_item = event.widget.focus()
            if selected_item:
                if 'bookings_tree' in str(event.widget):
                    # In bookings_tree, the booking ref is at index 0
                    booking_ref = event.widget.item(selected_item)['values'][0]
                elif 'history_tree' in str(event.widget):
                     # In history_tree, the booking ref is at index 0
                     booking_ref = event.widget.item(selected_item)['values'][0]
                else:
                    return "break"
                
                self.clipboard_clear()
                self.clipboard_append(str(booking_ref))
                messagebox.showinfo("Copied", f"Booking Ref # {booking_ref} copied to clipboard.", parent=self)
            return "break"
        
        # If not a Treeview, let the default Tcl copy happen but still break
        try:
             event.widget.selection_get()
        except:
             pass # No selection
             
        return "break"
    
    def paste_event(self, event):
        event.widget.event_generate('<<Paste>>')
        return "break"
        
    def cut_event(self, event):
        event.widget.event_generate('<<Cut>>')
        return "break"
    # --- END NEW ---
    
    def set_app_icon(self, icon_path):
        """Sets the application icon."""
        try:
            # self.iconbitmap is the correct method for .ico files
            ico = resource_path(icon_path)
            self.iconbitmap(ico)
            # Load icon for main dashboard header (logo.png next to icon)
            png = resource_path(icon_path.replace(".ico", ".png"))
            img = Image.open(png)
            img = img.resize((30, 30), Image.LANCZOS)
            self.header_logo_image = ImageTk.PhotoImage(img)

        except tk.TclError:
            print(f"Warning: Could not find icon file at {icon_path}. Using default icon.")
        except Exception as e:
            print(f"An error occurred while setting the icon/loading logo: {e}")

    def configure_styles(self):
        """Configure custom styles for ttk widgets."""

        # General Frame
        self.style.configure("TFrame", background=COLOR_LIGHT_BG)
        self.style.configure("TLabel", background=COLOR_LIGHT_BG, foreground=COLOR_DARK_TEXT, font=('Helvetica', 10))
        self.style.configure("TButton", font=('Helvetica', 10, 'bold'), padding=5)
        self.style.configure("TLabelframe", background=COLOR_LIGHT_BG, bordercolor=COLOR_PRIMARY, relief="solid", borderwidth=1)
        self.style.configure("TLabelframe.Label", background=COLOR_LIGHT_BG, foreground=COLOR_PRIMARY, font=('Helvetica', 11, 'bold'))

        # --- Notebook (Tabs) ---
        self.style.configure("TNotebook", background=COLOR_LIGHT_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab",
                             background="#f0f0f0",
                             padding=[12, 6],
                             font=('Helvetica', 10, 'bold'),
                             foreground="#555"
                             )
        self.style.map("TNotebook.Tab",
                       background=[("selected", COLOR_LIGHT_BG)],
                       foreground=[("selected", COLOR_PRIMARY)],
                       expand=[("selected", [0, 0, 0, 2])]  # Adds underline effect
                       )

        # --- Header Frame & Label (Updated) ---
        self.style.configure("Header.TFrame", background=COLOR_PRIMARY, padding=(15, 0))
        self.style.configure("Header.TLabel",
                             background=COLOR_PRIMARY,
                             foreground=COLOR_HEADER_FG,
                             font=('Helvetica', 16, 'bold'),
                             padding=(0, 10)  # No side padding, just top/bottom
                             )
        
        # --- NEW: Login Screen Footer ---
        self.style.configure("Footer.TLabel", background=COLOR_LIGHT_BG, foreground="#777", font=('Helvetica', 9))

        # --- Button Styles ---
        self.style.configure("Accent.TButton", foreground=COLOR_HEADER_FG, background=COLOR_PRIMARY, font=('Helvetica', 12, 'bold'))
        self.style.map("Accent.TButton", background=[('active', '#0041a3')])

        self.style.configure("Success.TButton", foreground=COLOR_HEADER_FG, background=COLOR_SUCCESS, font=('Helvetica', 10, 'bold'))
        self.style.map("Success.TButton", background=[('active', '#004a00')])

        self.style.configure("Danger.TButton", foreground=COLOR_HEADER_FG, background=COLOR_DANGER, font=('Helvetica', 10, 'bold'))
        self.style.map("Danger.TButton", background=[('active', '#7c0000')])

        # --- Room Status Labels (Dashboard) ---
        self.style.configure("Room.TFrame", background=COLOR_ODD_ROW, relief="solid", borderwidth=1, bordercolor="#e0e0e0")

        self.style.configure("Available.TLabel", background=COLOR_SUCCESS_LIGHT, foreground=COLOR_SUCCESS, font=('Helvetica', 10, 'bold'), padding=6, anchor='center')
        self.style.configure("Occupied.TLabel", background=COLOR_DANGER_LIGHT, foreground=COLOR_DANGER, font=('Helvetica', 10, 'bold'), padding=6, anchor='center')
        self.style.configure("Reserved.TLabel", background=COLOR_WARNING_LIGHT, foreground=COLOR_WARNING, font=('Helvetica', 10, 'bold'), padding=6, anchor='center')
        self.style.configure("Maintenance.TLabel", background=COLOR_MAINTENANCE_LIGHT, foreground=COLOR_MAINTENANCE, font=('Helvetica', 10, 'bold'), padding=6, anchor='center')

        # --- Treeview ---
        self.style.configure("Treeview",
                             rowheight=28,
                             fieldbackground=COLOR_LIGHT_BG,
                             background=COLOR_LIGHT_BG,
                             font=('Helvetica', 10)
                             )
        self.style.configure("Treeview.Heading", font=('Helvetica', 11, 'bold'), padding=8, background="#e9ecef", foreground=COLOR_DARK_TEXT)
        self.style.map("Treeview.Heading", background=[('active', '#d6dbe0')])

        # Alternating row colors
        self.style.configure("Treeview", font=('Helvetica', 10))
        self.style.map('Treeview', background=[('selected', COLOR_PRIMARY_LIGHT)], foreground=[('selected', COLOR_PRIMARY)])
        self.style.configure('Treeview.Odd', background=COLOR_ODD_ROW)
        self.style.configure('Treeview.Even', background=COLOR_EVEN_ROW)
        
        # --- NEW: Prominent Balance Due Label ---
        self.style.configure("Balance.TLabel", 
                             background=COLOR_LIGHT_BG, 
                             foreground=COLOR_PRIMARY, 
                             font=('Helvetica', 16, 'bold'))

    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist.

        If running as a PyInstaller onefile bundle, the bundled files are extracted
        to a temporary directory (sys._MEIPASS). The bundled DB must be copied to
        a persistent, writable location (the executable directory) so that data
        persists between runs. This logic copies the bundled DB if necessary and
        ensures we always connect to a writable DB path.
        """
        # Determine DB path. If running frozen, prefer a DB next to the executable.
        try:
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                target_db = os.path.join(exe_dir, DB_NAME)

                # If the target DB doesn't exist, try to copy the bundled DB out of _MEIPASS
                if not os.path.exists(target_db):
                    bundled_db = resource_path(DB_NAME)
                    try:
                        shutil.copyfile(bundled_db, target_db)
                        print(f"Copied bundled DB from {bundled_db} to {target_db}")
                    except Exception as e:
                        print(f"Warning: failed to copy bundled DB: {e}")

                conn = sqlite3.connect(target_db)
            else:
                conn = sqlite3.connect(DB_NAME)
        except Exception:
            # Fallback to local DB name if any of the above fails
            conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Users table (Admin/Employee)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('SuperAdmin', 'Admin', 'Employee', 'Receptionist'))
            )
        ''')

        # Ensure existing users table allows SuperAdmin; if not, migrate table safely.
        try:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            row = cursor.fetchone()
            create_sql = row[0] if row and row[0] else ''
            # If existing users table lacks SuperAdmin or Receptionist in its CHECK constraint, migrate table
            if 'SuperAdmin' not in create_sql or 'Receptionist' not in create_sql:
                # Migrate table to allow SuperAdmin role
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('SuperAdmin', 'Admin', 'Employee', 'Receptionist'))
                    )
                ''')
                # Copy existing users into new table (role will be copied as-is)
                cursor.execute("INSERT OR IGNORE INTO users_new (id, username, password, role) SELECT id, username, password, role FROM users")
                cursor.execute("DROP TABLE IF EXISTS users")
                cursor.execute("ALTER TABLE users_new RENAME TO users")
                self.db_conn.commit()
                cursor = conn.cursor()
        except Exception:
            # If anything goes wrong, continue without breaking startup.
            pass

        # Create default users if they don't exist
        cursor.execute("SELECT * FROM users WHERE username='admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'Admin')")

        cursor.execute("SELECT * FROM users WHERE username='emp'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, role) VALUES ('emp', 'emp123', 'Employee')")

        # Ensure SuperAdmin user exists (username: david)
        cursor.execute("SELECT * FROM users WHERE username='david'")
        if not cursor.fetchone():
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES ('david', 'david7845', 'SuperAdmin')")
            except Exception:
                # If insert fails due to schema constraint, ignore; migration above should have handled it.
                pass

        # Settings table for hotel details (extended to store address lines, tax rates and hotel rules)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                hotel_name TEXT,
                address TEXT,
                address_line1 TEXT,
                address_line2 TEXT,
                gst_number TEXT,
                contact_number TEXT,
                cgst_rate REAL DEFAULT 0.0,
                sgst_rate REAL DEFAULT 0.0,
                igst_rate REAL DEFAULT 0.0,
                enable_cgst_sgst TEXT DEFAULT 'false',
                enable_igst TEXT DEFAULT 'false',
                hotel_rules TEXT
            )
        ''')
        cursor.execute("SELECT * FROM settings WHERE id=1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO settings (id, hotel_name, address, address_line1, address_line2, gst_number, contact_number, cgst_rate, sgst_rate, igst_rate, enable_cgst_sgst, enable_igst, hotel_rules) VALUES (1, 'My Hotel', '123, Main Street, City', '', '', 'GSTIN12345', '9876543210', 0.0, 0.0, 0.0, 'false', 'false', '')")

        # Rooms table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT UNIQUE NOT NULL,
                room_type TEXT NOT NULL,
                bed_type TEXT NOT NULL,
                rate REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance'))
            )
        ''')

        # Guests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                address TEXT
            )
        ''')

        # Bookings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_ref TEXT UNIQUE NOT NULL,
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
        
        # --- NEW: booking_persons table for multi-guest info ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS booking_persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_ref TEXT NOT NULL,
                person_name TEXT NOT NULL,
                is_primary TEXT NOT NULL CHECK(is_primary IN ('true', 'false'))
            )
        ''')

        # Restaurant Menu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL
            )
        ''')

        # Restaurant Orders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                item_id INTEGER,
                quantity INTEGER,
                price_at_order REAL,
                order_date TEXT,
                FOREIGN KEY(booking_id) REFERENCES bookings(id),
                FOREIGN KEY(item_id) REFERENCES restaurant_menu(id)
            )
        ''')

        # --- NEW: local_charges table ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_charges (
                id INTEGER PRIMARY KEY,
                enabled TEXT NOT NULL DEFAULT 'false',
                charge_name TEXT,
                amount REAL NOT NULL DEFAULT 0.0,
                calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Per Day', 'Per Person'))
            )
        ''')
        # Ensure default row exists
        cursor.execute("SELECT * FROM local_charges WHERE id=1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO local_charges (id, charge_name, amount, calculation_type) VALUES (1, 'Local Dev Fee', 50.0, 'Per Person')")
        # --- END NEW ---

        conn.commit()

        # --- MIGRATION: Ensure bookings.booking_ref is not UNIQUE so group bookings can share one ref ---
        try:
            # First, inspect the CREATE TABLE SQL to see if booking_ref was declared UNIQUE at column level.
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'")
            row = cursor.fetchone()
            create_sql = row[0] if row and row[0] else ''
            found_unique_decl = False
            try:
                if create_sql and re.search(r"booking_ref\s+TEXT\s+UNIQUE", create_sql, re.IGNORECASE):
                    found_unique_decl = True
            except Exception:
                found_unique_decl = False

            # If not found via CREATE SQL, fall back to checking indexes (implicit unique index may exist)
            unique_index_on_booking_ref = None
            if not found_unique_decl:
                cursor.execute("PRAGMA index_list('bookings')")
                indexes = cursor.fetchall()
                for idx in indexes:
                    # PRAGMA index_list returns: seq, name, unique, origin, partial
                    idx_name = idx[1]
                    is_unique = idx[2]
                    if is_unique:
                        try:
                            cursor.execute(f"PRAGMA index_info('{idx_name}')")
                            cols = cursor.fetchall()
                            for col in cols:
                                # index_info returns seqno, cid, name
                                if col and len(col) >= 3 and col[2] == 'booking_ref':
                                    unique_index_on_booking_ref = idx_name
                                    found_unique_decl = True
                                    break
                            if found_unique_decl:
                                break
                        except Exception:
                            continue

            if found_unique_decl:
                # Recreate bookings table without UNIQUE constraint on booking_ref
                cursor.execute('BEGIN')
                cursor.execute('''
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
                cursor.execute("INSERT OR REPLACE INTO bookings_new (id, booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, advance_payment) SELECT id, booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, advance_payment FROM bookings")
                cursor.execute("DROP TABLE IF EXISTS bookings")
                cursor.execute("ALTER TABLE bookings_new RENAME TO bookings")
                # Remove the old unique index if it still exists
                try:
                    if unique_index_on_booking_ref:
                        cursor.execute(f"DROP INDEX IF EXISTS {unique_index_on_booking_ref}")
                except Exception:
                    pass
                conn.commit()
                logger.info("Migrated bookings table to remove UNIQUE constraint on booking_ref (index %s)", unique_index_on_booking_ref)
        except Exception as e:
            # Do not stop startup on migration failure; log and continue
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("Bookings migration check failed: %s", e)

        # --- NEW: Daily finance tables (income + expenses) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_income (
                date TEXT PRIMARY KEY,
                total REAL NOT NULL DEFAULT 0.0,
                last_updated TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()

        # --- VERSION 2.2: Add new columns robustly ---
        _add_column_if_not_exists(conn, 'bookings', 'num_adults', 'INTEGER', 1)
        _add_column_if_not_exists(conn, 'bookings', 'num_children', 'INTEGER', 0)
        _add_column_if_not_exists(conn, 'bookings', 'num_rooms', 'INTEGER', 1)
        _add_column_if_not_exists(conn, 'settings', 'enable_tax', 'TEXT', 'true')  # Kept for legacy
        _add_column_if_not_exists(conn, 'settings', 'cgst_rate', 'REAL', 9.0)
        _add_column_if_not_exists(conn, 'settings', 'sgst_rate', 'REAL', 9.0)
        _add_column_if_not_exists(conn, 'settings', 'igst_rate', 'REAL', 18.0)
        _add_column_if_not_exists(conn, 'bookings', 'actual_check_in', 'TEXT', None)
        _add_column_if_not_exists(conn, 'bookings', 'actual_check_out', 'TEXT', None)
        # --- V2.2: New independent tax columns ---
        _add_column_if_not_exists(conn, 'settings', 'enable_cgst_sgst', 'TEXT', 'true')
        _add_column_if_not_exists(conn, 'settings', 'enable_igst', 'TEXT', 'true')
        # Add separate address lines to avoid overlap in long addresses and for better PDF rendering
        _add_column_if_not_exists(conn, 'settings', 'address_line1', 'TEXT', '')
        _add_column_if_not_exists(conn, 'settings', 'address_line2', 'TEXT', '')

        return conn

    def create_login_screen(self):
        """Creates the initial login screen."""
        if hasattr(self, 'main_frame'):
            self.main_frame.destroy()

        self.login_frame = ttk.Frame(self, style="TFrame", padding=40)
        self.login_frame.place(relx=0.5, rely=0.5, anchor='center')

        # --- NEW: Load and display logo.png ---
        try:
            img_path = resource_path("logo.png")
            img = Image.open(img_path)
            img = img.resize((100, 100), Image.LANCZOS) # Resize to 100x100
            self.login_logo_image = ImageTk.PhotoImage(img)
            
            logo_label = ttk.Label(self.login_frame, image=self.login_logo_image, background=COLOR_LIGHT_BG)
            logo_label.pack(pady=(0, 15))
        except Exception as e:
            print(f"Error loading logo.png: {e}")
            # Fallback text if logo fails
            logo_frame = tk.Frame(self.login_frame, bg=COLOR_PRIMARY, width=80, height=80)
            logo_frame.pack(pady=10)
            ttk.Label(logo_frame, text="N", font=('Helvetica', 40, 'bold'), background=COLOR_PRIMARY, foreground="white").place(relx=0.5, rely=0.5, anchor='center')
        # --- END NEW ---

        ttk.Label(self.login_frame, text=SOFTWARE_NAME, font=('Helvetica', 24, 'bold'), background="white", foreground=COLOR_PRIMARY).pack(pady=(0, 20))

        ttk.Label(self.login_frame, text="Username", background="white", font=('Helvetica', 12)).pack(pady=(10, 2), anchor='w', padx=40)
        self.username_entry = ttk.Entry(self.login_frame, width=30, font=('Helvetica', 12))
        self.username_entry.pack(ipady=5, padx=40)

        ttk.Label(self.login_frame, text="Password", background="white", font=('Helvetica', 12)).pack(pady=(10, 2), anchor='w', padx=40)
        self.password_entry = ttk.Entry(self.login_frame, show="*", width=30, font=('Helvetica', 12))
        self.password_entry.pack(ipady=5, padx=40)

        login_button = ttk.Button(self.login_frame, text="Login", command=self.handle_login, style="Accent.TButton")
        login_button.pack(pady=30, ipadx=20, ipady=8, fill='x', padx=40)

        # --- MODIFIED: Footer Text ---
        footer_text = (
            "Developed by Nexuzy Tech Pvt Ltd\n"
            "For Enquiry: support@nexuzy.in | For Customization: manoj@nexuzy.in | Other: david@nexuzy.in"
        )
        ttk.Label(self.login_frame, text=footer_text, style="Footer.TLabel", justify=tk.CENTER).pack(pady=(10, 0))
        # --- END MODIFIED ---

        self.username_entry.focus()
        self.bind('<Return>', lambda event: self.handle_login())

        # Center the login frame in a more robust way
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.login_frame.grid(row=0, column=0)
        # Apply style to the login frame itself for rounded corners (theme-dependent)
        self.style.configure("Login.TFrame", background=COLOR_LIGHT_BG, relief="solid", borderwidth=1, bordercolor="#e0e0e0")
        self.login_frame.configure(style="Login.TFrame")

    def handle_login(self):
        """Validates user credentials."""
        username = self.username_entry.get()
        password = self.password_entry.get()

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        result = cursor.fetchone()

        if result:
            self.user_role = result[0]
            self.login_frame.destroy()  # Destroy frame
            self.unbind('<Return>')
            # Reset grid configuration
            self.rowconfigure(0, weight=0)
            self.columnconfigure(0, weight=0)
            self.create_main_widgets()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def update_clock(self):
        """Updates the clock label every second."""
        # e.g., 10/22/2025  11:50:30 AM (MM/DD/YYYY + 12-hour)
        now = datetime.now().strftime('%m/%d/%Y  %I:%M:%S %p')
        try:
            if self.clock_label:
                self.clock_label.config(text=now)
                # Schedule the next update
                self.after(1000, self.update_clock)
        except tk.TclError:
            # This happens if the widget is destroyed (e.g., logout)
            pass

    def create_main_widgets(self):
        """Create the main application interface after successful login."""
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create the "Help > About" menu
        self.create_main_menu()

        # --- V2.1: New Header with Clock ---
        header_frame = ttk.Frame(self.main_frame, style="Header.TFrame")
        header_frame.pack(fill="x")

        # Left: Software Name with Logo (NEW)
        if self.header_logo_image:
            ttk.Label(header_frame, image=self.header_logo_image, background=COLOR_PRIMARY).pack(side='left', padx=(5, 5))

        ttk.Label(header_frame, text=f"{SOFTWARE_NAME}", style="Header.TLabel").pack(side='left')

        # Center: User Role
        ttk.Label(header_frame, text=f"Logged in as: {self.user_role}", style="Header.TLabel", font=('Helvetica', 11, 'normal')).pack(side='left', padx=30)

        # Right: Clock
        self.clock_label = ttk.Label(header_frame, text="", style="Header.TLabel", font=('Helvetica', 11, 'bold'))
        self.clock_label.pack(side='right')

        # Far Right: Logout Button
        logout_button = ttk.Button(header_frame, text="Logout", command=self.create_login_screen, style="TButton")
        logout_button.pack(side='right', padx=(0, 10))

        # Start the clock
        self.update_clock()
        # --- End V2.1 Header ---

        # --- Toolbar: critical quick actions visible on all tabs ---
        toolbar = ttk.Frame(self.main_frame, padding=(6,4))
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text="New Advance Booking", command=lambda: self.open_new_booking_window(booking_type="Advance"), style="Accent.TButton").pack(side='left', padx=4)
        ttk.Button(toolbar, text="New Quick Booking", command=lambda: self.open_new_booking_window(booking_type="Quick"), style="TButton").pack(side='left', padx=4)
        ttk.Button(toolbar, text="Check-In", command=self.check_in_guest, style="Success.TButton").pack(side='left', padx=4)
        ttk.Button(toolbar, text="Check-Out & Bill", command=self.check_out_guest).pack(side='left', padx=4)
        ttk.Button(toolbar, text="Add Restaurant Order", command=self.add_restaurant_order).pack(side='left', padx=4)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_dashboard).pack(side='left', padx=4)
        # --- End Toolbar ---

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Add tabs based on user role
        self.dashboard_tab = ttk.Frame(self.notebook, style="TFrame")
        self.bookings_tab = ttk.Frame(self.notebook, style="TFrame")
        self.history_tab = ttk.Frame(self.notebook, style="TFrame")  # V2.0 New Tab

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.bookings_tab, text="Bookings & Guests")
        self.notebook.add(self.history_tab, text="Booking History")  # V2.0 New Tab
        # Finance tab (separate from dashboard to avoid layout overlap)
        self.finance_tab = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.finance_tab, text="Finance")

        # Admin & SuperAdmin tabs
        if self.user_role in ('Admin', 'SuperAdmin'):
            self.rooms_tab = ttk.Frame(self.notebook, style="TFrame")
            self.restaurant_tab = ttk.Frame(self.notebook, style="TFrame")
            self.settings_tab = ttk.Frame(self.notebook, style="TFrame")
            self.backup_tab = ttk.Frame(self.notebook, style="TFrame") # <-- NEW: Backup/Restore

            self.notebook.add(self.rooms_tab, text="Room Management")
            self.notebook.add(self.restaurant_tab, text="Restaurant Menu")
            self.notebook.add(self.settings_tab, text="Settings")
            self.notebook.add(self.backup_tab, text="Backup & Restore") # <-- NEW

            # User Management is only visible to SuperAdmin
            if self.user_role == 'SuperAdmin':
                self.users_tab = ttk.Frame(self.notebook, style="TFrame") # <-- NEW: User Mgmt
                self.notebook.add(self.users_tab, text="User Management")

            self.setup_rooms_tab()
            self.setup_restaurant_tab()
            self.setup_settings_tab()
            if self.user_role == 'SuperAdmin':
                self.setup_users_tab()
            self.setup_backup_tab() # <-- NEW

        # Populate tabs
        self.setup_dashboard_tab()
        self.setup_bookings_tab()
        self.setup_history_tab()  # V2.0 New Tab
        self.setup_finance_tab()

    def create_main_menu(self):
        """Creates the main menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.open_about_window)

    def open_about_window(self):
        """Opens the About Toplevel window."""
        AboutWindow(self)

    def setup_dashboard_tab(self):
        """Setup the dashboard with room status."""
        # Debounce rebuilds: avoid rebuilding too frequently which can freeze UI
        now_ts = time.time()
        if hasattr(self, '_last_dashboard_build_time'):
            if now_ts - self._last_dashboard_build_time < 0.8:
                # schedule a refresh slightly later and skip current heavy rebuild
                try:
                    self.after(800, self.setup_dashboard_tab)
                except Exception:
                    pass
                return
        self._last_dashboard_build_time = now_ts

        # Avoid rebuilding the dashboard when it's not the active tab (prevents blinking when switching tabs)
        try:
            if hasattr(self, 'notebook'):
                current = self.notebook.tab(self.notebook.select(), 'text')
                if str(current).lower() != 'dashboard':
                    return
        except Exception:
            # on any issue determining tab, continue with build
            pass

        for widget in self.dashboard_tab.winfo_children():
            widget.destroy()

        controls_frame = ttk.Frame(self.dashboard_tab, padding=(10, 10))
        controls_frame.pack(fill='x')

        # Quick actions are available in the global toolbar above the tabs.
        # Avoid duplicating the same buttons here to prevent them appearing twice.

        # Legend
        legend_frame = ttk.Frame(controls_frame)
        legend_frame.pack(side='right', padx=20)
        ttk.Label(legend_frame, text="Legend:", font=('Helvetica', 10, 'bold')).pack(side='left', padx=5, anchor='s')
        ttk.Label(legend_frame, text="", style="Available.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Available").pack(side='left', padx=(0, 10))
        ttk.Label(legend_frame, text="", style="Occupied.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Occupied").pack(side='left', padx=(0, 10))
        ttk.Label(legend_frame, text="", style="Reserved.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Reserved (Today)").pack(side='left', padx=(0, 10))
        ttk.Label(legend_frame, text="", style="Maintenance.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Maintenance").pack(side='left', padx=(0, 10))

        # Room display area (wrap into a top frame so the bottom matrix cannot overlap)
        cards_frame = ttk.Frame(self.dashboard_tab)
        cards_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Buttons to show/hide the 30-day matrix (Show will auto-hide after a timeout)
        try:
              # Button to toggle the 30-day matrix (click to show/hide)
              # Keep a constant user-facing label as requested: do not switch to "Hide".
              self._matrix_toggle_text = tk.StringVar(value="Show 30 Day Booking Status")
              btn = ttk.Button(controls_frame, textvariable=self._matrix_toggle_text, command=self._toggle_dashboard_matrix)
              btn.pack(side='left', padx=(0,10))
              self._matrix_toggle_btn = btn
        except Exception:
            pass

        canvas = tk.Canvas(cards_frame, bg=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(cards_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Forward enter/leave from the inner frame to the canvas so _make_scrollable can bind/unbind correctly
        try:
            scrollable_frame.bind('<Enter>', lambda e: canvas.event_generate('<Enter>'))
            scrollable_frame.bind('<Leave>', lambda e: canvas.event_generate('<Leave>'))
            # Enable smooth scrolling (mouse + keyboard) for the main dashboard cards area
            try:
                self._make_scrollable(canvas)
            except Exception:
                pass
        except Exception:
            pass

        # Finance UI moved to a dedicated Finance tab to avoid dashboard overlap

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, room_number, room_type, bed_type, status, rate FROM rooms ORDER BY room_number")
        rooms = cursor.fetchall()

        available_rooms_count = 0
        today = datetime.now().strftime('%Y-%m-%d')

        row, col = 0, 0
        for room in rooms:
            room_id, room_number, room_type, bed_type, status, rate = room

            # BUGFIX: New logic to determine status for display
            display_status = status
            if status == 'Available':
                # Check if it's reserved for today using an overlap range so we catch datetime-stored values
                date_start = datetime.combine(datetime.now().date(), datetime.min.time()).strftime('%Y-%m-%d %H:%M')
                date_end = (datetime.combine(datetime.now().date(), datetime.min.time()) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
                cursor.execute("SELECT 1 FROM bookings WHERE room_id=? AND status='Reserved' AND check_in <= ? AND check_out >= ? LIMIT 1", (room_id, date_end, date_start))
                if cursor.fetchone():
                    display_status = 'Reserved'
                else:
                    available_rooms_count += 1

            frame = ttk.Frame(scrollable_frame, style="Room.TFrame")
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            ttk.Label(frame, text=f"Room {room_number}", font=('Helvetica', 14, 'bold'), background=COLOR_ODD_ROW).pack(pady=(10, 5))
            ttk.Label(frame, text=f"{room_type} - {bed_type}", background=COLOR_ODD_ROW).pack(pady=2)
            ttk.Label(frame, text=f"Rate: Rs.{rate:.2f}/day", background=COLOR_ODD_ROW).pack(pady=(2, 10))

            status_label = ttk.Label(frame, text=display_status.upper(), style=f"{display_status}.TLabel")
            status_label.pack(fill='x', side='bottom', ipady=5)

            col += 1
            if col > 5:  # Adjust number of columns as needed
                col = 0
                row += 1

        # Display Available Rooms Count
        status_bar = ttk.Frame(self.dashboard_tab, style="TFrame")
        status_bar.pack(fill='x', side='bottom', pady=5, padx=10)
        ttk.Label(status_bar, text=f"Total Rooms Available (Now): {available_rooms_count}", font=('Helvetica', 12, 'bold')).pack(side='right')

        # (Removed) Next 30 Days Room Status Summary - not required by user to reduce clutter

        # --- NEW: Per-Room 30-Day Status Matrix (colored cells) ---
        try:
            # Insert a visual separator to prevent the matrix from overlapping the room cards
            ttk.Separator(self.dashboard_tab, orient='horizontal').pack(fill='x', padx=10, pady=(6,4))
            matrix_frame = ttk.Labelframe(self.dashboard_tab, text="Room Status Matrix (Next 30 Days)", padding=6)
            # Keep a reference so toggle/hide helpers can operate on the latest matrix
            try:
                self._last_matrix_frame_ref = matrix_frame
            except Exception:
                pass
            # NOTE: keep the matrix hidden by default to avoid overlap; it will be packed when the user
            # requests it via the Show button (self._temp_show_matrix). This prevents the matrix from
            # appearing automatically and overlapping the room cards area.

            # Optimize: prefetch bookings for next 30 days and compute statuses in-memory
            today = datetime.now().date()
            date_list = [(today + timedelta(days=i)) for i in range(0, 30)]
            # Show all 30 days in one horizontal row (single-line display)
            chunk = 30
            date_rows = [date_list]

            # Create inner frame to hold the matrix (compact, no horizontal scroll)
            mat_inner = ttk.Frame(matrix_frame)
            mat_inner.pack(fill='both', padx=4, pady=4)

            # Header row (header on left, status label on right) so status aligns in one line with headers
            top_row = ttk.Frame(mat_inner)
            top_row.pack(fill='x')
            header = ttk.Frame(top_row)
            header.pack(side='left', fill='x', expand=True)
            # Status info label (shows last clicked cell date/status) aligned to the right of headers
            self.dashboard_matrix_status = ttk.Label(top_row, text="", font=('Helvetica', 9))
            self.dashboard_matrix_status.pack(side='right', padx=6)

            # Fetch rooms and bookings overlapping the 30-day window
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, room_number, status FROM rooms ORDER BY room_number")
            rooms = cursor.fetchall()

            # Draw header: left 'Room' label, then dates split into rows
            ttk.Label(header, text='Room', width=10).grid(row=0, column=0, rowspan=len(date_rows), padx=2, pady=2)
            for r_idx, dlist in enumerate(date_rows):
                for col_idx, d in enumerate(dlist, start=1):
                    # Compact header: show only the day number (single-line) in a smaller font
                    # This keeps the 30-day matrix narrow without changing other views.
                    lbl = ttk.Label(header, text=d.strftime('%d'), width=3, anchor='center', font=('Helvetica', 8))
                    lbl.grid(row=r_idx, column=col_idx, padx=1, pady=0)

            # Use date-only bounds so check-out date is treated as non-inclusive
            start_range = date_list[0].strftime('%Y-%m-%d')
            end_range = (date_list[-1] + timedelta(days=1)).strftime('%Y-%m-%d')
            # Fetch bookings overlapping the 30-day window (inclusive of check-out)
            cursor.execute(
                "SELECT room_id, status, check_in, check_out FROM bookings WHERE DATE(check_out) >= ? AND DATE(check_in) <= ?",
                (start_range, end_range)
            )
            raw = cursor.fetchall()

            # Build bookings_by_room to avoid DB queries per cell
            from collections import defaultdict
            bookings_by_room = defaultdict(list)
            for row in raw:
                room_id_b, b_status, b_ci, b_co = row
                # Normalize check-in/check-out to date objects so check-out day is non-inclusive
                ci_dt = None
                co_dt = None
                try:
                    if b_ci:
                        try:
                            ci_parsed = datetime.strptime(str(b_ci)[:16], '%Y-%m-%d %H:%M')
                        except Exception:
                            ci_parsed = datetime.strptime(str(b_ci)[:10], '%Y-%m-%d')
                        ci_dt = ci_parsed.date()
                except Exception:
                    ci_dt = None
                try:
                    if b_co:
                        try:
                            co_parsed = datetime.strptime(str(b_co)[:16], '%Y-%m-%d %H:%M')
                        except Exception:
                            co_parsed = datetime.strptime(str(b_co)[:10], '%Y-%m-%d')
                        co_dt = co_parsed.date()
                except Exception:
                    co_dt = None
                bookings_by_room[room_id_b].append({'status': b_status, 'check_in': ci_dt, 'check_out': co_dt})

            # Color legend mapping
            status_color = {
                'Available': "#b8f0b8",
                'Occupied': "#eb9797",
                'Reserved': "#f0dda5",
                'Maintenance': "#e4dcdc"
            }

            # Decide render mode: if number of widgets (cells) large, render on Canvas for speed
            total_cells = len(rooms) * len(date_list)
            use_canvas = total_cells > 500

            # Map room id -> display number for quick access
            room_number_by_id = {r[0]: r[1] for r in rooms}

            if use_canvas:
                # Canvas-based grid rendering (fewer Tk widgets, much faster)
                pad = 4
                left_margin = 90
                rows_count = len(rooms)
                cols_count = len(date_rows[0]) if date_rows else 0

                mat_canvas = tk.Canvas(mat_inner, background=COLOR_LIGHT_BG, height=min(700, rows_count * (len(date_rows) * 24) + 60))
                vscroll = ttk.Scrollbar(mat_inner, orient='vertical', command=mat_canvas.yview)
                mat_canvas.configure(yscrollcommand=vscroll.set)
                mat_canvas.pack(side='left', fill='both', expand=True)
                vscroll.pack(side='right', fill='y')

                # Forward enter/leave from the inner mat_inner frame to the matrix canvas
                try:
                    mat_inner.bind('<Enter>', lambda e: mat_canvas.event_generate('<Enter>'))
                    mat_inner.bind('<Leave>', lambda e: mat_canvas.event_generate('<Leave>'))
                    # Enable smooth scrolling for the matrix canvas as well
                    try:
                        self._make_scrollable(mat_canvas)
                    except Exception:
                        pass
                except Exception:
                    pass

                # Allow the canvas to compute a sensible width before sizing cells
                mat_canvas.update_idletasks()
                try:
                    avail_w = mat_canvas.winfo_width() or mat_canvas.winfo_reqwidth() or 800
                    # leave some padding on the right
                    usable_w = max(200, avail_w - left_margin - 60)
                    cell_w = max(22, min(48, int(usable_w / max(1, cols_count))))
                except Exception:
                    cell_w = 28
                # cell height slightly larger so we can draw a status glyph
                cell_h = max(18, int(cell_w * 0.75))

                # create a single inner canvas group and compute content size
                content_width = left_margin + (cols_count) * (cell_w + pad) + 40
                content_height = rows_count * (len(date_rows) * (cell_h + pad)) + 40
                mat_canvas.configure(scrollregion=(0,0,content_width,content_height))

                # Draw compact date headers (single-line day numbers) and compute header height
                header_font = ('Helvetica', 8)
                header_height = int(cell_h + pad)
                for col_idx, d in enumerate(date_list):
                    x = left_margin + col_idx * (cell_w + pad)
                    # center header above column (single-line day number)
                    mat_canvas.create_text(x + cell_w/2, header_height/2, text=d.strftime('%d'), font=header_font, tags=(f"hdr_{d.strftime('%Y%m%d')}",))

                # Draw grid cells and room labels: each room occupies one row; each date occupies one column
                room_label_font = ('Helvetica', 10, 'bold')
                status_glyph_font = ('Helvetica', 8, 'bold')
                for i, room in enumerate(rooms):
                    room_id, room_number, room_status = room
                    row_y_top = header_height + 6 + i * (cell_h + pad)
                    # room label (left margin)
                    mat_canvas.create_text(8, row_y_top + cell_h/2, anchor='w', text=str(room_number), font=room_label_font)
                    for col_idx, d in enumerate(date_list):
                        # work with date objects: dt_start is the date 'd', dt_end is next date
                        dt_start = d
                        dt_end = d + timedelta(days=1)

                        # determine status (maintenance > occupied > reserved > available)
                        if room_status == 'Maintenance':
                            st = 'Maintenance'
                        else:
                            st = 'Available'
                            for b in bookings_by_room.get(room_id, []):
                                b_ci = b.get('check_in')
                                b_co = b.get('check_out')
                                if not b_ci or not b_co:
                                    continue
                                # b_ci and b_co are date objects; treat check_out as inclusive so checkout day is occupied
                                if b.get('status') == 'Checked-In' and (b_ci <= dt_end and b_co >= dt_start):
                                    st = 'Occupied'
                                    break
                            else:
                                for b in bookings_by_room.get(room_id, []):
                                    b_ci = b.get('check_in')
                                    b_co = b.get('check_out')
                                    if not b_ci or not b_co:
                                        continue
                                    if b.get('status') == 'Reserved' and (b_ci <= dt_end and b_co >= dt_start):
                                        st = 'Reserved'
                                        break

                        if st not in status_color:
                            st = 'Available'
                        color = status_color.get(st, '#ffffff')

                        x = left_margin + col_idx * (cell_w + pad)
                        y = row_y_top
                        rect_id = mat_canvas.create_rectangle(x, y, x + cell_w, y + cell_h, fill=color, outline='#cccccc')
                        tag = f"cell_{room_id}_{d.strftime('%Y%m%d')}"
                        mat_canvas.addtag_withtag(tag, rect_id)

                        # Draw a short status glyph/text centered in the cell to make status more visible
                        glyph = 'A' if st == 'Available' else ('O' if st == 'Occupied' else ('R' if st == 'Reserved' else 'M'))
                        mat_canvas.create_text(x + cell_w/2, y + cell_h/2, text=glyph, font=status_glyph_font, fill='#333333', tags=(tag,))

                # (Removed) the vertical 'Today' marker to keep the header compact and avoid the long bar

                # Click handler for canvas: find the cell tag and act on it
                def _on_canvas_click(ev, canvas_widget=mat_canvas):
                    try:
                        x = canvas_widget.canvasx(ev.x)
                        y = canvas_widget.canvasy(ev.y)
                        items = canvas_widget.find_overlapping(x, y, x, y)
                        if not items:
                            return
                        # Pick top-most item
                        item = items[-1]
                        tags = canvas_widget.gettags(item)
                        cell_tag = next((t for t in tags if t.startswith('cell_')), None)
                        if not cell_tag:
                            return
                        parts = cell_tag.split('_')
                        if len(parts) < 3:
                            return
                        rid = int(parts[1])
                        date_s = parts[2]
                        dt = datetime.strptime(date_s, '%Y%m%d').date()
                        # determine status and update status label in single-line format
                        try:
                            st = self._get_room_status_for_room_on_date(rid, dt)
                        except Exception:
                            st = ''
                        status_text = f"Room {room_number_by_id.get(rid,'?')} — {dt.strftime('%d/%m/%Y')} — {st}"
                        try:
                            self.dashboard_matrix_status.config(text=status_text)
                        except Exception:
                            pass
                        self._show_bookings_for_room_on_date(rid, dt)
                    except Exception:
                        pass

                mat_canvas.bind('<Button-1>', _on_canvas_click)
            else:
                # Fallback to previous Label-based grid for small numbers (keeps existing behavior)
                for i, room in enumerate(rooms, start=1):
                    rowf = ttk.Frame(mat_inner)
                    rowf.pack(fill='x', pady=2)
                    room_id, room_number, room_status = room
                    ttk.Label(rowf, text=str(room_number), width=10).grid(row=0, column=0, rowspan=len(date_rows)*1, padx=2, pady=1)

                    # For each date-row (top/bottom)
                    for r_idx, dlist in enumerate(date_rows):
                        for j, d in enumerate(dlist, start=1 + r_idx*chunk):
                            dt_start = datetime.combine(d, datetime.min.time())
                            dt_end = dt_start + timedelta(days=1)

                            if room_status == 'Maintenance':
                                st = 'Maintenance'
                            else:
                                st = 'Available'
                                for b in bookings_by_room.get(room_id, []):
                                    b_ci = b.get('check_in')
                                    b_co = b.get('check_out')
                                    if not b_ci or not b_co:
                                        continue
                                    if b.get('status') == 'Checked-In' and (b_ci <= dt_end and b_co >= dt_start):
                                        st = 'Occupied'
                                        break
                                else:
                                    for b in bookings_by_room.get(room_id, []):
                                        b_ci = b.get('check_in')
                                        b_co = b.get('check_out')
                                        if not b_ci or not b_co:
                                            continue
                                        if b.get('status') == 'Reserved' and (b_ci <= dt_end and b_co >= dt_start):
                                            st = 'Reserved'
                                            break

                            if st not in status_color:
                                st = 'Available'
                            color = status_color.get(st, '#ffffff')

                            cell = tk.Label(rowf, text='', bg=color, width=2, relief='ridge', bd=1)
                            cell.grid(row= r_idx, column=(j - (r_idx*chunk)), padx=1, pady=1)
                            def _on_click(ev, rid=room_id, dt=d, st=st):
                                try:
                                    # show MM/DD/YYYY in status
                                    self.dashboard_matrix_status.config(text=f"Room {room_number} — {dt.strftime('%d/%m/%Y')} — {st}")
                                except Exception:
                                    pass
                                self._show_bookings_for_room_on_date(rid, dt)
                            cell.bind('<Button-1>', _on_click)
        except Exception:
            pass

        # Dashboard auto-refresh will be started once during main widget creation

    def refresh_dashboard(self):
        """Refreshes the dashboard view."""
        self.setup_dashboard_tab()

    def _temp_show_matrix(self, timeout_ms=8000):
        """Temporarily show the last-created dashboard matrix for `timeout_ms` milliseconds.

        The matrix is created each time `setup_dashboard_tab` runs; that function sets
        `self._last_matrix_frame_ref` to the most recent `matrix_frame` so this method
        can operate on it. The matrix will auto-hide after `timeout_ms` unless
        another show request resets the timer.
        """
        # Show matrix temporarily as a toplevel, then auto-hide after timeout_ms.
        try:
            # cancel prior auto-hide if any
            try:
                if hasattr(self, '_matrix_hide_after_id') and self._matrix_hide_after_id:
                    self.after_cancel(self._matrix_hide_after_id)
            except Exception:
                pass

            # open or lift the compact matrix Toplevel
            try:
                if not (hasattr(self, '_matrix_toplevel') and self._matrix_toplevel and tk.Toplevel.winfo_exists(self._matrix_toplevel)):
                    self._open_matrix_window()
                else:
                    try:
                        self._matrix_toplevel.lift()
                    except Exception:
                        pass
            except Exception:
                return

            # schedule hide
            try:
                self._matrix_hide_after_id = self.after(int(timeout_ms), lambda: self._hide_dashboard_matrix())
            except Exception:
                self._matrix_hide_after_id = None
        except Exception:
            pass

    def _toggle_dashboard_matrix(self):
        """Toggle visibility of the embedded matrix labelframe (or destroy the toplevel).

        Click once to show (no auto-hide). Click again to hide. If matrix Toplevel is open,
        it will be raised/destroyed appropriately.
        """
        # Toggle behavior: open a clean Toplevel sized to current application window, or close it.
        try:
            # If a toplevel exists, close it and reset toggle text
            if hasattr(self, '_matrix_toplevel') and self._matrix_toplevel and tk.Toplevel.winfo_exists(self._matrix_toplevel):
                try:
                    self._matrix_toplevel.destroy()
                except Exception:
                    pass
                self._matrix_toplevel = None
                try:
                    if hasattr(self, '_matrix_toggle_text'):
                        self._matrix_toggle_text.set("Show 30 Day Booking Status")
                except Exception:
                    pass
                return

            # Not open: ensure embedded matrix (if any) is hidden so Toplevel won't overlap
            try:
                mf = getattr(self, '_last_matrix_frame_ref', None)
                if mf and mf.winfo_ismapped():
                    try:
                        mf.pack_forget()
                    except Exception:
                        pass
            except Exception:
                pass

            # Open a fresh toplevel sized to current application window so 30 columns fit
            try:
                self._open_matrix_window()
                try:
                    if hasattr(self, '_matrix_toggle_text'):
                        # Keep the button label constant per user preference
                        self._matrix_toggle_text.set("Show 30 Day Booking Status")
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def _open_matrix_window(self):
        """Open a Toplevel window with the 30-day room×date matrix.

        This creates an independent window so the matrix cannot overlap the main
        dashboard content. It reuses the database queries and draws a compact
        canvas grid with one cell per room×date.
        """
        # If already open, do nothing
        if hasattr(self, '_matrix_toplevel') and self._matrix_toplevel and tk.Toplevel.winfo_exists(self._matrix_toplevel):
            return

        # Size the toplevel relative to the current main window so the 30 columns can fit
        try:
            main_w = self.winfo_width() or self.winfo_screenwidth() or 1000
            main_h = self.winfo_height() or int(self.winfo_screenheight() * 0.75) or 700
        except Exception:
            main_w, main_h = 1000, 600

        # Attempt to use most of the available width (open large / maximized so 30 columns are readable)
        desired_w = max(1000, int(main_w))
        desired_h = max(600, int(main_h * 0.9))

        mt = tk.Toplevel(self)
        mt.title('Room Status Matrix (Next 30 Days)')
        try:
            mt.geometry(f"{desired_w}x{desired_h}")
        except Exception:
            mt.geometry('1000x600')
        # Try to maximize the toplevel so the matrix can use full screen real-estate
        try:
            mt.state('zoomed')
        except Exception:
            try:
                mt.attributes('-zoomed', True)
            except Exception:
                pass
        mt.transient(self)
        # allow resizing
        mt.resizable(True, True)
        self._matrix_toplevel = mt

        frame = ttk.Frame(mt, padding=6)
        frame.pack(fill='both', expand=True)

        # Status label
        status_lbl = ttk.Label(frame, text="", font=('Helvetica', 9))
        status_lbl.pack(anchor='e')

        # Canvas + vertical scrollbar
        mat_canvas = tk.Canvas(frame, background=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(frame, orient='vertical', command=mat_canvas.yview)
        mat_canvas.configure(yscrollcommand=vscroll.set)
        mat_canvas.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')

        # Prepare data (same logic as dashboard)
        today = datetime.now().date()
        date_list = [(today + timedelta(days=i)) for i in range(0, 30)]

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, room_number, status FROM rooms ORDER BY room_number")
        rooms = cursor.fetchall()

        # Use date-only bounds and DATE(...) in SQL so the check-out date is treated as non-inclusive
        # (i.e. a booking with check_out = 2025-11-01 will not mark 2025-11-01 occupied for a per-day matrix).
        start_range = date_list[0].strftime('%Y-%m-%d')
        end_range = (date_list[-1] + timedelta(days=1)).strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT room_id, status, check_in, check_out FROM bookings WHERE DATE(check_out) >= ? AND DATE(check_in) <= ?",
            (start_range, end_range)
        )
        raw = cursor.fetchall()
        from collections import defaultdict
        bookings_by_room = defaultdict(list)
        for row in raw:
            room_id_b, b_status, b_ci, b_co = row
            try:
                ci_dt = datetime.strptime(str(b_ci)[:16], '%Y-%m-%d %H:%M') if b_ci else None
            except Exception:
                try:
                    ci_dt = datetime.strptime(str(b_ci)[:10], '%Y-%m-%d') if b_ci else None
                except Exception:
                    ci_dt = None
            try:
                co_dt = datetime.strptime(str(b_co)[:16], '%Y-%m-%d %H:%M') if b_co else None
            except Exception:
                try:
                    co_dt = datetime.strptime(str(b_co)[:10], '%Y-%m-%d') if b_co else None
                except Exception:
                    co_dt = None
            bookings_by_room[room_id_b].append({'status': b_status, 'check_in': ci_dt, 'check_out': co_dt})

        status_color = {
            'Available': "#b8f0b8",
            'Occupied': "#eb9797",
            'Reserved': "#f0dda5",
            'Maintenance': "#e4dcdc"
        }

        # sizing: prefer larger readable cells by using the actual toplevel width
        pad = 4
        left_margin = 110
        cols = len(date_list)
        rows_count = len(rooms)
        # Ensure geometry is realized so we can measure the toplevel canvas area
        mt.update_idletasks()
        mat_canvas.update_idletasks()
        # Prefer to use the toplevel's width (after maximizing) for cell sizing
        try:
            avail_w = mt.winfo_width() or mat_canvas.winfo_width() or mat_canvas.winfo_reqwidth() or desired_w
        except Exception:
            avail_w = mat_canvas.winfo_width() or mat_canvas.winfo_reqwidth() or desired_w

        usable_w = max(400, avail_w - left_margin - 120)
        # Compute cell width so 30 columns fit within usable_w; clamp to a readable range (18..40 px)
        cell_w = max(18, min(40, int(usable_w / max(1, cols))))
        # Make cells a bit taller for readability
        cell_h = max(20, int(cell_w * 0.9))

        header_height = int(cell_h + pad)
        content_width = left_margin + cols * (cell_w + pad) + 60
        content_height = header_height + rows_count * (cell_h + pad) + 80
        mat_canvas.configure(scrollregion=(0,0,content_width,content_height))

        # draw headers (larger, readable)
        header_font = ('Helvetica', 10)
        for col_idx, d in enumerate(date_list):
            x = left_margin + col_idx * (cell_w + pad)
            mat_canvas.create_text(x + cell_w/2, int(header_height*0.1), text=d.strftime('%d'), font=header_font, anchor='n')

        # draw rows
        room_number_by_id = {r[0]: r[1] for r in rooms}
        glyph_font = ('Helvetica', 10, 'bold')
        for i, room in enumerate(rooms):
            room_id, room_number, room_status = room
            y_top = header_height + 6 + i * (cell_h + pad)
            mat_canvas.create_text(8, y_top + cell_h/2, anchor='w', text=str(room_number), font=('Helvetica',10,'bold'))
            for col_idx, d in enumerate(date_list):
                dt_start = datetime.combine(d, datetime.min.time())
                dt_end = dt_start + timedelta(days=1)
                # compute status
                if room_status == 'Maintenance':
                    st = 'Maintenance'
                else:
                    st = 'Available'
                    for b in bookings_by_room.get(room_id, []):
                        b_ci = b.get('check_in')
                        b_co = b.get('check_out')
                        if not b_ci or not b_co:
                            continue
                        # Treat check-out as inclusive so a booking that checks out on dt_start is considered occupied
                        if b.get('status') == 'Checked-In' and (b_ci <= dt_end and b_co >= dt_start):
                            st = 'Occupied'
                            break
                    else:
                        for b in bookings_by_room.get(room_id, []):
                            b_ci = b.get('check_in')
                            b_co = b.get('check_out')
                            if not b_ci or not b_co:
                                continue
                            if b.get('status') == 'Reserved' and (b_ci <= dt_end and b_co >= dt_start):
                                st = 'Reserved'
                                break

                color = status_color.get(st, '#ffffff')
                x = left_margin + col_idx * (cell_w + pad)
                rect = mat_canvas.create_rectangle(x, y_top, x + cell_w, y_top + cell_h, fill=color, outline='#cccccc')
                tag = f"cell_{room_id}_{d.strftime('%Y%m%d')}"
                mat_canvas.addtag_withtag(tag, rect)
                glyph = 'A' if st == 'Available' else ('O' if st == 'Occupied' else ('R' if st == 'Reserved' else 'M'))
                mat_canvas.create_text(x + cell_w/2, y_top + cell_h/2, text=glyph, font=glyph_font, tags=(tag,))

        # click handler
        def _on_click(ev, canvas_widget=mat_canvas):
            try:
                x = canvas_widget.canvasx(ev.x)
                y = canvas_widget.canvasy(ev.y)
                items = canvas_widget.find_overlapping(x, y, x, y)
                if not items:
                    return
                item = items[-1]
                tags = canvas_widget.gettags(item)
                cell_tag = next((t for t in tags if t.startswith('cell_')), None)
                if not cell_tag:
                    return
                parts = cell_tag.split('_')
                if len(parts) < 3:
                    return
                rid = int(parts[1])
                date_s = parts[2]
                dt = datetime.strptime(date_s, '%Y%m%d').date()
                try:
                    # Update the toplevel status label to include computed room status (matches embedded matrix behavior)
                    try:
                        status_val = self._get_room_status_for_room_on_date(rid, dt)
                    except Exception:
                        status_val = None
                    if status_val:
                        status_lbl.config(text=f"Room {room_number_by_id.get(rid,'?')} — {dt.strftime('%d/%m/%Y')} — {status_val}")
                    else:
                        status_lbl.config(text=f"Room {room_number_by_id.get(rid,'?')} — {dt.strftime('%d/%m/%Y')}")
                except Exception:
                    pass
                self._show_bookings_for_room_on_date(rid, dt)
            except Exception:
                pass

        mat_canvas.bind('<Button-1>', _on_click)

        # When the user closes the toplevel, clear reference
        def _on_close():
            try:
                # cancel any scheduled auto-hide
                try:
                    if hasattr(self, '_matrix_hide_after_id') and self._matrix_hide_after_id:
                        self.after_cancel(self._matrix_hide_after_id)
                except Exception:
                    pass
                try:
                    mt.destroy()
                except Exception:
                    pass
                self._matrix_toplevel = None
                try:
                    if hasattr(self, '_matrix_toggle_text'):
                        self._matrix_toggle_text.set("Show 30 Day Booking Status")
                except Exception:
                    pass
            except Exception:
                pass

    def _dashboard_auto_refresh(self, interval_ms=60000):
        """Auto-refresh the dashboard on a schedule. Cancels any pending refresh and reschedules."""
        try:
            # Cancel previous scheduled call if exists
            if hasattr(self, '_dashboard_after_id') and self._dashboard_after_id:
                try:
                    self.after_cancel(self._dashboard_after_id)
                except Exception:
                    pass
        except Exception:
            pass

        # Refresh only when the Dashboard tab is currently visible to avoid blinking
        try:
            should_refresh = True
            try:
                if hasattr(self, 'notebook'):
                    current = self.notebook.tab(self.notebook.select(), 'text')
                    if str(current).lower() != 'dashboard':
                        should_refresh = False
            except Exception:
                # If any issue determining tab, fall back to refreshing
                should_refresh = True

            if should_refresh:
                try:
                    self.refresh_dashboard()
                except Exception:
                    pass
        except Exception:
            pass

        # Schedule next refresh
        try:
            self._dashboard_after_id = self.after(interval_ms, lambda: self._dashboard_auto_refresh(interval_ms))
        except Exception:
            self._dashboard_after_id = None

    def setup_finance_tab(self):
        """Create a dedicated Finance tab with chart, breakdowns and export options."""
        for w in self.finance_tab.winfo_children():
            w.destroy()

        # Create a scrollable canvas for the finance tab to allow smooth scrolling
        finance_canvas = tk.Canvas(self.finance_tab, bg=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        finance_scrollbar = ttk.Scrollbar(self.finance_tab, orient="vertical", command=finance_canvas.yview)
        frame = ttk.Frame(finance_canvas, padding=12)

        frame.bind("<Configure>", lambda e: finance_canvas.configure(scrollregion=finance_canvas.bbox("all")))
        finance_canvas.create_window((0, 0), window=frame, anchor="nw")
        finance_canvas.configure(yscrollcommand=finance_scrollbar.set)

        finance_canvas.pack(side="left", fill='both', expand=True)
        finance_scrollbar.pack(side="right", fill='y')

        # Enable smooth scrolling (mouse + keyboard)
        try:
            self._make_scrollable(finance_canvas)
        except Exception:
            pass

        header = ttk.Frame(frame)
        header.pack(fill='x')
        ttk.Label(header, text="Finance Dashboard", font=('Helvetica', 16, 'bold')).pack(side='left')
        ttk.Label(header, text=f"Showing latest 10 days (summary: 180d)", font=('Helvetica', 10)).pack(side='right')

        # Small list: Last 10 days (oldest -> newest)
        last10_frame = ttk.Labelframe(frame, text="Last 10 Days (oldest -> newest)", padding=6)
        last10_frame.pack(fill='x', pady=(6,6))
        last10_cols = ('Date', 'Room', 'Restaurant', 'Tax', 'Expense', 'Net')
        self.last10_tree = ttk.Treeview(last10_frame, columns=last10_cols, show='headings', height=5)
        for c in last10_cols:
            self.last10_tree.heading(c, text=c)
            if c == 'Date':
                self.last10_tree.column(c, width=100, anchor='center')
            else:
                self.last10_tree.column(c, width=90, anchor='e')
        self.last10_tree.pack(fill='x')

        # Today summary (shows today's breakdown)
        today_frame = ttk.Frame(frame)
        today_frame.pack(fill='x', pady=(8,6))
        ttk.Label(today_frame, text="Today - Room:", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.today_room_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_room_label.grid(row=0, column=1, sticky='w', padx=6)
        ttk.Label(today_frame, text="Today - Restaurant:", font=('Helvetica', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.today_rest_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_rest_label.grid(row=0, column=3, sticky='w', padx=6)
        ttk.Label(today_frame, text="Today - Tax:", font=('Helvetica', 10, 'bold')).grid(row=0, column=4, sticky='w', padx=(20,0))
        self.today_tax_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_tax_label.grid(row=0, column=5, sticky='w', padx=6)
        ttk.Label(today_frame, text="Today - Expenses:", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=(6,0))
        self.today_exp_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_exp_label.grid(row=1, column=1, sticky='w', padx=6, pady=(6,0))
        ttk.Label(today_frame, text="Today - Net:", font=('Helvetica', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=(20,0), pady=(6,0))
        self.today_net_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_net_label.grid(row=1, column=3, sticky='w', padx=6, pady=(6,0))

        # Top: 180-day summary boxes
        summary_frame = ttk.Frame(frame)
        summary_frame.pack(fill='x', pady=(8,10))
        ttk.Label(summary_frame, text="Room Income (180d):", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.summary_room_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_room_label.grid(row=0, column=1, sticky='w', padx=8)

        ttk.Label(summary_frame, text="Restaurant Income (180d):", font=('Helvetica', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.summary_rest_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_rest_label.grid(row=0, column=3, sticky='w', padx=8)

        ttk.Label(summary_frame, text="Tax Collected (180d):", font=('Helvetica', 10, 'bold')).grid(row=0, column=4, sticky='w', padx=(20,0))
        self.summary_tax_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_tax_label.grid(row=0, column=5, sticky='w', padx=8)

        ttk.Label(summary_frame, text="Expenses (180d):", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=(6,0))
        self.summary_exp_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_exp_label.grid(row=1, column=1, sticky='w', padx=8, pady=(6,0))

        # Chart area
        chart_frame = ttk.Labelframe(frame, text="Net Trend (last 30 days)", padding=10)
        chart_frame.pack(fill='x')
        self.finance_chart_canvas = tk.Canvas(chart_frame, height=160, background=COLOR_LIGHT_BG, highlightthickness=0)
        self.finance_chart_canvas.pack(fill='x')

        # Expense entry form (daily expense) - date, name, amount, optional note
        expense_entry_frame = ttk.Labelframe(frame, text="Add Daily Expense", padding=8)
        expense_entry_frame.pack(fill='x', pady=(8,6))
        ttk.Label(expense_entry_frame, text="Date:").grid(row=0, column=0, sticky='w')
        self.finance_expense_date = ttk.Entry(expense_entry_frame, width=12)
        self.finance_expense_date.grid(row=0, column=1, sticky='w', padx=4)
        # Show user-facing date as MM/DD/YYYY but keep DB storage in ISO when saving
        self.finance_expense_date.insert(0, datetime.now().strftime('%m/%d/%Y'))
        ttk.Label(expense_entry_frame, text="Name:").grid(row=0, column=2, sticky='w', padx=(8,0))
        self.finance_expense_name = ttk.Entry(expense_entry_frame, width=20)
        self.finance_expense_name.grid(row=0, column=3, sticky='w', padx=4)
        ttk.Label(expense_entry_frame, text="Amount:").grid(row=1, column=0, sticky='w', pady=(6,0))
        self.finance_expense_amount = ttk.Entry(expense_entry_frame, width=12)
        self.finance_expense_amount.grid(row=1, column=1, sticky='w', padx=4, pady=(6,0))
        ttk.Label(expense_entry_frame, text="Note (optional):").grid(row=1, column=2, sticky='w', padx=(8,0), pady=(6,0))
        self.finance_expense_note = ttk.Entry(expense_entry_frame, width=30)
        self.finance_expense_note.grid(row=1, column=3, sticky='w', padx=4, pady=(6,0))
        ttk.Button(expense_entry_frame, text="Add Expense", command=self._on_add_expense_in_finance, style="Success.TButton").grid(row=0, column=4, rowspan=2, padx=(12,0))

        # Exports row (PDF exports only). The detailed 180-day table is intentionally omitted from
        # the dashboard view to keep the Finance tab compact per user preference.
        export_row = ttk.Frame(frame)
        export_row.pack(fill='x', pady=(8,0))
        # PDF exports only: Today, Latest 10 Days, 180 Days
        ttk.Button(export_row, text="Export Today (PDF)", command=lambda: self.export_combined_pdf(days=1)).pack(side='left', padx=6)
        ttk.Button(export_row, text="Export Latest 10 Days (PDF)", command=lambda: self.export_combined_pdf(days=10)).pack(side='left', padx=6)
        ttk.Button(export_row, text="Export 180 Days (PDF)", command=lambda: self.export_combined_pdf(days=180)).pack(side='left', padx=6)

        # Populate summary and detail tree
        try:
            rows = self.get_finance_rows(180)
            # Today's breakdown
            today_str = datetime.now().strftime('%Y-%m-%d')
            today_room = self.calculate_room_income(today_str)
            today_rest = self.calculate_restaurant_income(today_str)
            today_tax = self.calculate_tax_collected(today_str)
            today_exp = self.get_daily_expense_total(today_str)
            today_income_total = today_room + today_rest + today_tax
            today_net = today_income_total - float(today_exp)
            try:
                self.today_room_label.config(text=f"₹{today_room:.2f}")
                self.today_rest_label.config(text=f"₹{today_rest:.2f}")
                self.today_tax_label.config(text=f"₹{today_tax:.2f}")
                self.today_exp_label.config(text=f"₹{today_exp:.2f}")
                self.today_net_label.config(text=f"₹{today_net:.2f}")
            except Exception:
                pass
            total_room = sum(r[1] for r in rows)
            total_rest = sum(r[2] for r in rows)
            total_tax = sum(r[3] for r in rows)
            total_exp = sum(r[4] for r in rows)
            self.summary_room_label.config(text=f"₹{total_room:.2f}")
            self.summary_rest_label.config(text=f"₹{total_rest:.2f}")
            self.summary_tax_label.config(text=f"₹{total_tax:.2f}")
            self.summary_exp_label.config(text=f"₹{total_exp:.2f}")

            # Populate last-10 days compact list (oldest -> newest)
            try:
                for iid in self.last10_tree.get_children():
                    self.last10_tree.delete(iid)
                last10 = self.get_finance_rows(10)
                # Show newest -> oldest as requested
                for d, room_i, rest_i, tax_i, exp, net in reversed(last10):
                    self.last10_tree.insert('', 'end', values=(d, f"₹{room_i:.2f}", f"₹{rest_i:.2f}", f"₹{tax_i:.2f}", f"₹{exp:.2f}", f"₹{net:.2f}"))
            except Exception:
                pass

            # (Note) The detailed 180-day tree is not shown here to keep the dashboard compact.
            # The same detailed data is still available via the Export 180 Days (PDF) button.

            # draw a small 30-day sparkline into finance_chart_canvas (use net values)
            spark_rows = self.get_finance_rows(30)
            vals = [r[-1] for r in spark_rows]
            # reuse draw logic from draw_finance_sparkline but draw larger
            try:
                w = self.finance_chart_canvas.winfo_width() or self.finance_chart_canvas.winfo_reqwidth()
                h = self.finance_chart_canvas.winfo_height() or 160
                pad = 10
                self.finance_chart_canvas.delete('all')
                if vals:
                    maxv = max(vals)
                    minv = min(vals)
                    rng = maxv - minv if maxv != minv else 1.0
                    points = []
                    for i, v in enumerate(vals):
                        x = pad + i * ((w - 2*pad) / max(1, len(vals)-1))
                        y = pad + (1 - (v - minv) / rng) * (h - 2*pad)
                        points.append((x, y))
                    coords = []
                    for x,y in points:
                        coords.extend([x,y])
                    poly = [pad, h-pad] + coords + [w-pad, h-pad]
                    self.finance_chart_canvas.create_polygon(poly, fill=COLOR_PRIMARY_LIGHT, outline='')
                    for i in range(len(points)-1):
                        x1,y1 = points[i]
                        x2,y2 = points[i+1]
                        self.finance_chart_canvas.create_line(x1,y1,x2,y2, fill=COLOR_PRIMARY, width=2)
                    for x,y in points:
                        self.finance_chart_canvas.create_oval(x-3, y-3, x+3, y+3, fill=COLOR_PRIMARY, outline='')
            except Exception:
                pass
        except Exception as e:
            print(f"Error populating finance tab: {e}")

    # --- FINANCE: Daily income/expense helpers ---
    def calculate_daily_income(self, date_str):
        """Calculate total income for a given date (YYYY-MM-DD) and store in daily_income.

        Strategy: sum bookings.total_amount for bookings with actual_check_out or check_out matching date
        (use substr to extract date part). Falls back to 0.0 if no records.
        """
        cursor = self.db_conn.cursor()

        # Fetch bookings checked-out on this date
        cursor.execute("""
            SELECT b.id, b.total_amount, b.num_adults, b.num_children, b.room_id, b.check_in, b.check_out, b.actual_check_in, b.actual_check_out
            FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))

        rows = cursor.fetchall()
        computed_total = 0.0

        # Load tax settings once
        cursor.execute("SELECT enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate FROM settings WHERE id=1")
        tax_settings_row = cursor.fetchone() or ('false','false',0.0,0.0,0.0)
        enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate = tax_settings_row

        for (booking_id, total_amount, num_adults, num_children, room_id, check_in_s, check_out_s, actual_in_s, actual_out_s) in rows:
            if total_amount and float(total_amount) > 0.0:
                computed_total += float(total_amount)
                continue

            # Need to reconstruct the booking total from components
            # Determine dates
            try:
                ci_str = actual_in_s.split(' ')[0] if actual_in_s else check_in_s
                co_str = actual_out_s.split(' ')[0] if actual_out_s else check_out_s
                ci = datetime.strptime(ci_str, '%Y-%m-%d')
                co = datetime.strptime(co_str, '%Y-%m-%d')
                nights = (co - ci).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1

            # Room rate
            cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
            room_rate = cursor.fetchone()
            room_rate = float(room_rate[0]) if room_rate and room_rate[0] is not None else 0.0
            room_total = nights * room_rate

            # Restaurant total for this booking
            cursor.execute("SELECT SUM(COALESCE(price_at_order,0.0) * COALESCE(quantity,0)) FROM restaurant_orders WHERE booking_id=?", (booking_id,))
            rest_total = cursor.fetchone()[0] or 0.0

            # Local government charge
            try:
                total_persons = int(num_adults or 0) + int(num_children or 0)
            except Exception:
                total_persons = 1
            local_info = self.calculate_local_charge(nights, total_persons)
            local_amt = local_info.get('amount', 0.0)

            # Total components (room + restaurant + local charges)
            booking_components_total = room_total + float(rest_total) + float(local_amt)

            # Tax should be applied only on room + local charges (exclude restaurant totals from GST)
            taxable_amount = room_total + float(local_amt)

            tax_amt = 0.0
            try:
                if enable_igst == 'true':
                    tax_amt = taxable_amount * float(igst_rate or 0.0) / 100.0
                elif enable_cgst_sgst == 'true':
                    tax_amt = taxable_amount * ((float(cgst_rate or 0.0) + float(sgst_rate or 0.0)) / 100.0)
            except Exception:
                tax_amt = 0.0

            booking_total_est = booking_components_total + tax_amt
            computed_total += float(booking_total_est)

        # Save computed total
        cursor.execute("INSERT OR REPLACE INTO daily_income (date, total, last_updated) VALUES (?,?,?)",
                       (date_str, float(computed_total), datetime.now().isoformat()))
        self.db_conn.commit()

        # Keep only last 180 days of daily_income
        try:
            cursor.execute("DELETE FROM daily_income WHERE date < date('now','-180 day')")
            self.db_conn.commit()
        except Exception:
            pass

        return float(computed_total)

    # --- Finance breakdown helpers ---
    def calculate_room_income(self, date_str):
        """Calculate room income (excluding restaurant/local charges) for the date."""
        cursor = self.db_conn.cursor()
        total = 0.0
        cursor.execute("""
            SELECT b.id, b.total_amount, b.num_adults, b.num_children, b.room_id, b.check_in, b.check_out, b.actual_check_in, b.actual_check_out
            FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))
        rows = cursor.fetchall()
        for (booking_id, total_amount, num_adults, num_children, room_id, check_in_s, check_out_s, actual_in_s, actual_out_s) in rows:
            # If total_amount present, we cannot split; estimate room portion as nights*rate
            try:
                ci_str = actual_in_s.split(' ')[0] if actual_in_s else check_in_s
                co_str = actual_out_s.split(' ')[0] if actual_out_s else check_out_s
                ci = datetime.strptime(ci_str, '%Y-%m-%d')
                co = datetime.strptime(co_str, '%Y-%m-%d')
                nights = (co - ci).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1
            cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
            room_rate = cursor.fetchone()
            room_rate = float(room_rate[0]) if room_rate and room_rate[0] is not None else 0.0
            room_total = nights * room_rate
            total += room_total
        return float(total)

    def format_datetime_for_display(self, dt_str):
        """Convert DB datetime strings (ISO-like) into display format DD/MM/YYYY or DD/MM/YYYY HH:MM.

        Accepts:
        - 'YYYY-MM-DD HH:MM:SS'
        - 'YYYY-MM-DD HH:MM'
        - 'YYYY-MM-DD'
        Returns a string in 'DD/MM/YYYY HH:MM' if time present otherwise 'DD/MM/YYYY'.
        """
        if not dt_str:
            return ''
        dt_str = str(dt_str)
        # Try common ISO-like and alternate formats. Prefer showing DD/MM/YYYY
        # If a time component exists, show in 12-hour format with AM/PM (e.g. 02:15 PM).
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y %I:%M %p', '%d/%m/%Y'):
            try:
                dt = datetime.strptime(dt_str, fmt)
                # If time present in parsed format, show date+time in 12-hour format with AM/PM
                if ('%H' in fmt) or ('%I' in fmt) or (' ' in dt_str and (':' in dt_str)):
                    # Use %I for 12-hour hour (leading zero) and %p for AM/PM
                    return dt.strftime('%d/%m/%Y %I:%M %p')
                else:
                    return dt.strftime('%d/%m/%Y')
            except Exception:
                continue
        # If all parsing fails, return original string
        return dt_str

    def _parse_display_date_to_iso(self, display_str):
        """Parse a user-facing date/time string (DD/MM/YYYY or DD/MM/YYYY HH:MM AM/PM)
        and return an ISO-like string suitable for DB storage (YYYY-MM-DD or YYYY-MM-DD HH:MM).

        If parsing fails, return the original string (caller should handle validation).
        """
        if not display_str:
            return ''
        s = str(display_str).strip()

        # Normalize a few common variations so strptime can parse them robustly:
        # - ensure a space before AM/PM ("10:30AM" -> "10:30 AM")
        # - replace '.' with ':' in times ("10.30 AM" -> "10:30 AM")
        # - expand compact times like "1030" or "930" to "10:30" / "9:30"
        try:
            import re
            s = s.replace('.', ':')
            # Ensure space before AM/PM if missing
            s = re.sub(r'(?i)\s*(am|pm)\b', r' \1', s)
            parts = s.split()
            if len(parts) >= 2:
                time_part = parts[-1]
                # If time part is compact digits (e.g. '930' or '1030' possibly followed by AM/PM), expand it
                m = re.match(r'^(?P<hm>\d{3,4})(?P<ap>(?i:am|pm))?$', time_part)
                if m:
                    hm = m.group('hm')
                    ap = m.group('ap') or ''
                    if len(hm) == 3:
                        new_time = f"{int(hm[0])}:{hm[1:]}"
                    else:
                        new_time = f"{int(hm[:2])}:{hm[2:]}"
                    time_part = (new_time + (' ' + ap.strip() if ap else '')).strip()
                    parts[-1] = time_part
                    s = ' '.join(parts)
        except Exception:
            # If normalization errors occur, fall back to raw string
            pass

        # Try a list of common user-facing formats and normalize to ISO (YYYY-MM-DD or YYYY-MM-DD HH:MM).
        # Order: explicit day-first formats, month-first variants (MM/DD/YYYY), then ISO-like inputs.
        fmts = [
            '%d/%m/%Y %I:%M %p',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%m/%d/%Y %I:%M %p',
            '%m/%d/%Y %H:%M',
            '%m/%d/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
        ]

        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                # If parsed format includes time, return YYYY-MM-DD HH:MM else date-only
                if '%H' in fmt or '%I' in fmt:
                    return dt.strftime('%Y-%m-%d %H:%M')
                return dt.strftime('%Y-%m-%d')
            except Exception:
                continue

        # As a last-ditch, if string already looks like YYYY-MM-DD, normalize
        try:
            dt = datetime.strptime(s, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

        # If all parsing attempts fail, return original string; caller should validate.
        return s

    def parse_display_datetime(self, date_str: str, time_str: str = '00:00') -> datetime:
        """Parse display date + time strings into a datetime object.

        Accepts date in DD/MM/YYYY or MM/DD/YYYY or YYYY-MM-DD and time in 24-hour HH:MM or 12-hour HH:MM AM/PM.
        Returns a datetime.datetime. Raises ValueError on failure.
        """
        if not date_str:
            raise ValueError('Empty date string')

        # Normalize inputs and be liberal in accepted formats (allow e.g. '10:30AM', '10.30 am', '1030', '10am')
        import re
        d = str(date_str).strip()
        t = str(time_str).strip() if time_str is not None else ''

        # If user passed a combined string in date_str (e.g. '01/11/2025 10:30AM'), prefer that
        combined = (d + ' ' + t).strip()
        s = combined

        try:
            s = s.replace('.', ':')
            # Ensure space before AM/PM
            s = re.sub(r'(?i)\s*(am|pm)\b', r' \1', s)
            parts = s.split()
            if len(parts) >= 2:
                time_part = parts[-1]
                m = re.match(r'^(?P<hm>\d{3,4})(?P<ap>(?i:am|pm))?$', time_part)
                if m:
                    hm = m.group('hm')
                    ap = m.group('ap') or ''
                    if len(hm) == 3:
                        new_time = f"{int(hm[0])}:{hm[1:]}"
                    else:
                        new_time = f"{int(hm[:2])}:{hm[2:]}"
                    time_part = (new_time + (' ' + ap.strip() if ap else '')).strip()
                    parts[-1] = time_part
                    s = ' '.join(parts)
        except Exception:
            pass

        # Try common patterns (12-hour with AM/PM first, then 24-hour)
        fmts = [
            '%d/%m/%Y %I:%M %p',
            '%d/%m/%Y %H:%M',
            '%m/%d/%Y %I:%M %p',
            '%m/%d/%Y %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y-%m-%d',
        ]

        last_exc = None
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                return dt
            except Exception as e:
                last_exc = e
                continue

        # If all parsing attempts fail, raise ValueError to let caller show an error
        raise ValueError(f"Could not parse date/time: {s}")

    def _get_room_status_counts_for_date(self, date_obj):
        """Return counts of room statuses for the given date (date_obj is a datetime.date).

        Logic (approximate):
        - maintenance_count: rooms with status 'Maintenance' (static)
        - occupied: rooms with a booking that overlaps the date and status in ('Checked-In','Reserved')
        - reserved: rooms with booking status 'Reserved' that overlap the date
        - available = total_rooms - occupied - maintenance
        """
        cursor = self.db_conn.cursor()
        # Use date-only bounds (treat check-out date as non-inclusive for availability)
        date_start = date_obj.strftime('%Y-%m-%d')
        date_end = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

        # maintenance count (rooms statically marked as Maintenance)
        cursor.execute("SELECT COUNT(*) FROM rooms WHERE status='Maintenance'")
        maintenance = cursor.fetchone()[0] or 0

        # occupied: rooms with a booking that overlaps the date and are Checked-In
        cursor.execute(
            "SELECT COUNT(DISTINCT r.id) FROM rooms r "
            "JOIN bookings b ON b.room_id = r.id "
            # Include check-out date as occupied (treat check-out as inclusive)
            "WHERE b.status = 'Checked-In' AND DATE(b.check_in) <= ? AND DATE(b.check_out) >= ?",
            (date_end, date_start)
        )
        occupied = cursor.fetchone()[0] or 0

        # reserved: rooms with booking status 'Reserved' overlapping the date
        cursor.execute(
            "SELECT COUNT(DISTINCT r.id) FROM rooms r "
            "JOIN bookings b ON b.room_id = r.id "
            "WHERE b.status = 'Reserved' AND DATE(b.check_in) <= ? AND DATE(b.check_out) >= ?",
            (date_end, date_start)
        )
        reserved = cursor.fetchone()[0] or 0

        # total rooms
        cursor.execute("SELECT COUNT(*) FROM rooms")
        total_rooms = cursor.fetchone()[0] or 0

        available = max(0, total_rooms - occupied - maintenance)

        return {
            'available': available,
            'occupied': occupied,
            'reserved': reserved,
            'maintenance': maintenance,
            'total': total_rooms
        }

    def _get_room_status_for_room_on_date(self, room_id, date_obj):
        """Return status string for a specific room on a given date: 'Maintenance','Occupied','Reserved','Available'."""
        cursor = self.db_conn.cursor()
        # If the room itself is marked maintenance or occupied in rooms table, treat accordingly
        cursor.execute("SELECT status FROM rooms WHERE id=?", (room_id,))
        r = cursor.fetchone()
        if r:
            if r[0] == 'Maintenance':
                return 'Maintenance'
            if r[0] == 'Occupied':
                return 'Occupied'

        # Use date-only bounds (treat check-out as non-inclusive)
        date_start = date_obj.strftime('%Y-%m-%d')
        date_end = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

        # Check for Checked-In overlapping (occupied takes precedence over reserved)
        cursor.execute("SELECT 1 FROM bookings WHERE room_id=? AND status='Checked-In' AND DATE(check_in) <= ? AND DATE(check_out) >= ? LIMIT 1", (room_id, date_end, date_start))
        if cursor.fetchone():
            return 'Occupied'

        # Check for Reserved overlapping
        cursor.execute("SELECT 1 FROM bookings WHERE room_id=? AND status='Reserved' AND DATE(check_in) <= ? AND DATE(check_out) >= ? LIMIT 1", (room_id, date_end, date_start))
        if cursor.fetchone():
            return 'Reserved'

        return 'Available'

    def _show_bookings_for_room_on_date(self, room_id, date_obj):
        """Opens a small dialog listing bookings for the given room on that date."""
        try:
            # Use date-only bounds and DATE(...) so check_out is non-inclusive for the selected date
            date_start = date_obj.strftime('%Y-%m-%d')
            date_end = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            cursor = self.db_conn.cursor()
            cursor.execute("""
                SELECT booking_ref, status, check_in, check_out FROM bookings
                WHERE room_id=? AND DATE(check_in) <= ? AND DATE(check_out) >= ?
                ORDER BY check_in
            """, (room_id, date_end, date_start))
            rows = cursor.fetchall()

            info = []
            for r in rows:
                ref, status, ci, co = r
                ci_disp = self.format_datetime_for_display(ci)
                co_disp = self.format_datetime_for_display(co)
                info.append(f"{ref} | {status} | {ci_disp} -> {co_disp}")

            dlg = tk.Toplevel(self)
            dlg.transient(self)
            dlg.grab_set()
            dlg.title(f"Bookings for Room {room_id} on {date_obj.strftime('%m/%d/%Y')}")
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill='both', expand=True)
            if not info:
                ttk.Label(frm, text="No bookings for this room on selected date.").pack()
            else:
                for line in info:
                    ttk.Label(frm, text=line).pack(anchor='w')
            ttk.Button(frm, text="Close", command=dlg.destroy).pack(pady=8)
        except Exception as e:
            messagebox.showerror("Error", f"Could not retrieve bookings: {e}")

    def calculate_restaurant_income(self, date_str):
        """Calculate restaurant income associated with bookings checked out on date."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT b.id FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))
        booking_ids = [r[0] for r in cursor.fetchall()]
        if not booking_ids:
            return 0.0
        placeholders = ','.join(['?']*len(booking_ids))
        query = f"SELECT SUM(COALESCE(price_at_order,0.0) * COALESCE(quantity,0)) FROM restaurant_orders WHERE booking_id IN ({placeholders})"
        cursor.execute(query, booking_ids)
        return float(cursor.fetchone()[0] or 0.0)

    def calculate_tax_collected(self, date_str):
        """Estimate tax collected for bookings checked out on date.

        Strategy: reconstruct subtotal (room + restaurant + local charge) per booking and apply configured tax rates.
        This is an estimate when original tax breakup isn't stored.
        """
        cursor = self.db_conn.cursor()
        total_tax = 0.0

        cursor.execute("SELECT enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate FROM settings WHERE id=1")
        tax_settings_row = cursor.fetchone() or ('false','false',0.0,0.0,0.0)
        enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate = tax_settings_row

        cursor.execute("""
            SELECT b.id, b.total_amount, b.num_adults, b.num_children, b.room_id, b.check_in, b.check_out, b.actual_check_in, b.actual_check_out
            FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))
        rows = cursor.fetchall()

        for (booking_id, total_amount, num_adults, num_children, room_id, check_in_s, check_out_s, actual_in_s, actual_out_s) in rows:
            # Determine nights
            try:
                ci_str = actual_in_s.split(' ')[0] if actual_in_s else check_in_s
                co_str = actual_out_s.split(' ')[0] if actual_out_s else check_out_s
                ci = datetime.strptime(ci_str, '%Y-%m-%d')
                co = datetime.strptime(co_str, '%Y-%m-%d')
                nights = (co - ci).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1

            # Room rate
            cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
            room_rate = cursor.fetchone()
            room_rate = float(room_rate[0]) if room_rate and room_rate[0] is not None else 0.0
            room_total = nights * room_rate

            # Restaurant total for this booking
            cursor.execute("SELECT SUM(COALESCE(price_at_order,0.0) * COALESCE(quantity,0)) FROM restaurant_orders WHERE booking_id=?", (booking_id,))
            rest_total = cursor.fetchone()[0] or 0.0

            # Local government charge
            try:
                total_persons = int(num_adults or 0) + int(num_children or 0)
            except Exception:
                total_persons = 1
            local_info = self.calculate_local_charge(nights, total_persons)
            local_amt = local_info.get('amount', 0.0)

            # Apply tax only on room + local charges (exclude restaurant totals)
            taxable_amount = room_total + float(local_amt)

            tax_amt = 0.0
            try:
                if enable_igst == 'true':
                    tax_amt = taxable_amount * float(igst_rate or 0.0) / 100.0
                elif enable_cgst_sgst == 'true':
                    tax_amt = taxable_amount * ((float(cgst_rate or 0.0) + float(sgst_rate or 0.0)) / 100.0)
            except Exception:
                tax_amt = 0.0

            total_tax += float(tax_amt)

        return float(total_tax)

    def get_finance_rows(self, n=180):
        """Return list of (date, room_income, restaurant_income, tax_collected, expense, net) for last n days."""
        results = []
        for i in range(n-1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            room_inc = self.calculate_room_income(d)
            rest_inc = self.calculate_restaurant_income(d)
            tax_col = self.calculate_tax_collected(d)
            expense = self.get_daily_expense_total(d)
            income_total = room_inc + rest_inc + tax_col
            net = income_total - float(expense)
            results.append((d, float(room_inc), float(rest_inc), float(tax_col), float(expense), float(net)))
        return results

    def get_daily_expense_total(self, date_str):
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM daily_expenses WHERE date=?", (date_str,))
        return cursor.fetchone()[0] or 0.0

    def add_daily_expense(self, date_str, name, amount, note=''):
        cursor = self.db_conn.cursor()
        cursor.execute("INSERT INTO daily_expenses (date, name, amount, note, created_at) VALUES (?,?,?,?,?)",
                       (date_str, name, float(amount), note, datetime.now().isoformat()))
        self.db_conn.commit()

        # Keep only last 180 days of expenses
        try:
            cursor.execute("DELETE FROM daily_expenses WHERE date < date('now','-180 day')")
            self.db_conn.commit()
        except Exception:
            pass

    def get_last_n_days_finances(self, n=10):
        """Return a list of (date, income, expense, net) for the last n days (including today).
        Ensures daily_income rows exist by calculating income when missing.
        """
        results = []
        for i in range(n-1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # Ensure income calculated and stored
            self.calculate_daily_income(d)
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT total FROM daily_income WHERE date=?", (d,))
            income = cursor.fetchone()[0] or 0.0
            expense = self.get_daily_expense_total(d)
            net = float(income) - float(expense)
            results.append((d, float(income), float(expense), float(net)))
        return results

    def _populate_finance_tree(self):
        try:
            for i in self.finance_tree.get_children():
                self.finance_tree.delete(i)

            rows = self.get_last_n_days_finances(10)
            for d, inc, exp, net in rows:
                self.finance_tree.insert('', 'end', values=(d, f"₹{inc:.2f}", f"₹{exp:.2f}", f"₹{net:.2f}"))
            # Draw sparkline
            try:
                self.draw_finance_sparkline(rows)
            except Exception:
                pass
        except Exception as e:
            print(f"Error populating finance tree: {e}")

    def _on_add_expense(self):
        date_str = self.expense_date_entry.get()
        # Convert user-visible date (DD/MM/YYYY) to ISO for DB storage
        try:
            date_iso = self._parse_display_date_to_iso(date_str)
        except Exception:
            date_iso = date_str
        name = self.expense_name_entry.get().strip()
        amount = self.expense_amount_entry.get().strip()
        note = self.expense_note_entry.get().strip()

        if not (date_str and name and amount):
            messagebox.showerror("Error", "Please provide date, name and amount for the expense.")
            return

        try:
            amt = float(amount)
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.")
            return

        try:
            self.add_daily_expense(date_iso, name, amt, note)
            # Recalculate income for that day using ISO date
            self.calculate_daily_income(date_iso)
            self._populate_finance_tree()
            messagebox.showinfo("Success", "Expense recorded.")
            # clear fields
            self.expense_name_entry.delete(0, 'end')
            self.expense_amount_entry.delete(0, 'end')
            self.expense_note_entry.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Error", f"Could not save expense: {e}")

    def _on_add_expense_in_finance(self):
        """Handler for Add Expense button in the Finance tab."""
        date_str = self.finance_expense_date.get()
        try:
            date_iso = self._parse_display_date_to_iso(date_str)
        except Exception:
            date_iso = date_str
        name = self.finance_expense_name.get().strip()
        amount = self.finance_expense_amount.get().strip()
        note = self.finance_expense_note.get().strip()

        if not (date_str and name and amount):
            messagebox.showerror("Error", "Please provide date, name and amount for the expense.")
            return

        try:
            amt = float(amount)
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.")
            return

        try:
            self.add_daily_expense(date_iso, name, amt, note)
            # Recalculate income for that day (in case income was missing)
            self.calculate_daily_income(date_iso)
            # Refresh the finance tab contents
            try:
                self.setup_finance_tab()
            except Exception:
                pass
            messagebox.showinfo("Success", "Expense recorded.")
            # clear fields
            self.finance_expense_name.delete(0, 'end')
            self.finance_expense_amount.delete(0, 'end')
            self.finance_expense_note.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Error", f"Could not save expense: {e}")

    # --- Export helpers for CSV/PDF ---
    def export_expenses_csv(self, days=180):
        """Export expenses to CSV for the last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, name, amount, note, created_at FROM daily_expenses WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()

            if not rows:
                messagebox.showinfo("No Data", f"No expense data available for the last {days} days.")
                return

            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'expenses_last_{days}_days.csv')
            except Exception:
                fname = os.path.abspath(f'expenses_last_{days}_days.csv')

            import csv
            with open(fname, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['date', 'name', 'amount', 'note', 'created_at'])
                for r in rows:
                    writer.writerow(r)

            messagebox.showinfo("Exported", f"Expenses exported to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export expenses: {e}")

    def export_income_csv(self, days=180):
        """Export income to CSV for the last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, total, last_updated FROM daily_income WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()

            if not rows:
                messagebox.showinfo("No Data", f"No income data available for the last {days} days.")
                return

            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'income_last_{days}_days.csv')
            except Exception:
                fname = os.path.abspath(f'income_last_{days}_days.csv')

            import csv
            with open(fname, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['date', 'total', 'last_updated'])
                for r in rows:
                    writer.writerow(r)

            messagebox.showinfo("Exported", f"Income exported to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export income: {e}")

    def export_expenses_pdf(self, days=180):
        """Generate a simple PDF listing of expenses for last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, name, amount, note FROM daily_expenses WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()
            if not rows:
                messagebox.showinfo("No Data", f"No expense data available for the last {days} days.")
                return

            # Auto-save to user's Desktop Nexuzy folder under a Finance subfolder
            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'expenses_last_{days}_days.pdf')
            except Exception:
                fname = os.path.abspath(f'expenses_last_{days}_days.pdf')

            c = canvas.Canvas(fname, pagesize=A4)
            width, height = A4
            x = 40
            y = height - 50
            c.setFont('Helvetica-Bold', 14)
            c.drawString(x, y, f"Expenses - Last {days} Days")
            y -= 25
            c.setFont('Helvetica-Bold', 10)
            c.drawString(x, y, "Date")
            c.drawString(x+100, y, "Name")
            c.drawString(x+300, y, "Amount")
            c.drawString(x+380, y, "Note")
            y -= 15
            c.setFont('Helvetica', 10)
            for r in rows:
                if y < 60:
                    c.showPage()
                    y = height - 50
                date_s, name, amount, note = r
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = str(date_s)
                c.drawString(x, y, ds)
                c.drawString(x+100, y, str(name)[:30])
                c.drawRightString(x+350, y, f"₹{float(amount):.2f}")
                c.drawString(x+380, y, str(note)[:60])
                y -= 15

            c.save()
            # Cleanup old PDFs after saving (keep 30 days)
            try:
                cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
            except Exception:
                pass
            messagebox.showinfo("Exported", f"Expenses PDF saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export expenses PDF: {e}")

    def export_income_pdf(self, days=180):
        """Generate a simple PDF listing of income for last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, total, last_updated FROM daily_income WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()
            if not rows:
                messagebox.showinfo("No Data", f"No income data available for the last {days} days.")
                return

            # Auto-save to user's Desktop Nexuzy folder under a Finance subfolder
            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'income_last_{days}_days.pdf')
            except Exception:
                fname = os.path.abspath(f'income_last_{days}_days.pdf')

            c = canvas.Canvas(fname, pagesize=A4)
            width, height = A4
            x = 40
            y = height - 50
            c.setFont('Helvetica-Bold', 14)
            c.drawString(x, y, f"Income - Last {days} Days")
            y -= 25
            c.setFont('Helvetica-Bold', 10)
            c.drawString(x, y, "Date")
            c.drawString(x+150, y, "Total")
            c.drawString(x+300, y, "Last Updated")
            y -= 15
            c.setFont('Helvetica', 10)
            for r in rows:
                if y < 60:
                    c.showPage()
                    y = height - 50
                date_s, total, updated = r
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = date_s
                c.drawString(x, y, ds)
                c.drawRightString(x+240, y, f"₹{float(total):.2f}")
                c.drawString(x+300, y, str(updated)[:30])
                y -= 15

            c.save()
            try:
                cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
            except Exception:
                pass
            messagebox.showinfo("Exported", f"Income PDF saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export income PDF: {e}")

    def export_combined_csv(self, days=180):
        """Export combined income (room+restaurant) and expenses as a CSV for last `days` days."""
        try:
            rows = self.get_finance_rows(days)
            if not rows:
                messagebox.showinfo("No Data", f"No finance data available for the last {days} days.")
                return
            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'finance_combined_last_{days}_days.csv')
            except Exception:
                fname = os.path.abspath(f'finance_combined_last_{days}_days.csv')
            import csv
            with open(fname, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['date', 'room_income', 'restaurant_income', 'tax_collected', 'expense', 'net'])
                for r in rows:
                    writer.writerow(r)
            messagebox.showinfo("Exported", f"Combined finance CSV saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export combined CSV: {e}")

    def export_combined_pdf(self, days=180):
        """Export a combined PDF report for income breakdown and expenses for last `days` days."""
        try:
            rows = self.get_finance_rows(days)
            if not rows:
                messagebox.showinfo("No Data", f"No finance data available for the last {days} days.")
                return

            # Auto-save to user's Desktop Nexuzy folder under a Finance subfolder
            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, (f'finance_today.pdf' if days==1 else f'finance_combined_last_{days}_days.pdf'))
            except Exception:
                fname = os.path.abspath((f'finance_today.pdf' if days==1 else f'finance_combined_last_{days}_days.pdf'))

            c = canvas.Canvas(fname, pagesize=A4)
            width, height = A4
            x = 40
            y = height - 50

            # Special case: Today export (days==1) should include a Today summary and today's expense names & amounts
            if days == 1:
                today_str = datetime.now().strftime('%Y-%m-%d')
                # Calculate today's breakdown
                today_room = self.calculate_room_income(today_str)
                today_rest = self.calculate_restaurant_income(today_str)
                today_tax = self.calculate_tax_collected(today_str)
                today_exp = self.get_daily_expense_total(today_str)
                today_net = (today_room + today_rest + today_tax) - float(today_exp)

                c.setFont('Helvetica-Bold', 14)
                try:
                    today_display = self.format_datetime_for_display(today_str)
                except Exception:
                    today_display = today_str
                c.drawString(x, y, f"Finance Report - Today ({today_display})")
                y -= 22

                c.setFont('Helvetica-Bold', 11)
                c.drawString(x, y, "Summary")
                y -= 16
                c.setFont('Helvetica', 10)
                c.drawString(x, y, f"Room Income:")
                c.drawRightString(x+500, y, f"₹{today_room:.2f}")
                y -= 14
                c.drawString(x, y, f"Restaurant Income:")
                c.drawRightString(x+500, y, f"₹{today_rest:.2f}")
                y -= 14
                c.drawString(x, y, f"Tax Collected (est):")
                c.drawRightString(x+500, y, f"₹{today_tax:.2f}")
                y -= 14
                c.drawString(x, y, f"Expenses (today):")
                c.drawRightString(x+500, y, f"₹{float(today_exp):.2f}")
                y -= 14
                c.setFont('Helvetica-Bold', 11)
                c.drawString(x, y, f"Net Today:")
                c.drawRightString(x+500, y, f"₹{today_net:.2f}")
                y -= 22

                # Expenses listing for today with name, amount and note
                c.setFont('Helvetica-Bold', 12)
                c.drawString(x, y, "Expenses - Today")
                y -= 18
                c.setFont('Helvetica-Bold', 10)
                c.drawString(x, y, "Name")
                c.drawRightString(x+420, y, "Amount")
                c.drawString(x+440, y, "Note")
                y -= 14
                c.setFont('Helvetica', 10)

                cursor = self.db_conn.cursor()
                cursor.execute("SELECT date, name, amount, note FROM daily_expenses WHERE date = ? ORDER BY created_at DESC", (today_str,))
                exp_rows = cursor.fetchall()

                if not exp_rows:
                    c.drawString(x, y, "No expenses recorded for today.")
                    y -= 14
                else:
                    for date_s, name, amount, note in exp_rows:
                        if y < 60:
                            c.showPage()
                            y = height - 50
                        c.drawString(x, y, str(name)[:40])
                        c.drawRightString(x+420, y, f"₹{float(amount):.2f}")
                        c.drawString(x+440, y, str(note)[:60])
                        y -= 14

                # Final Net line
                if y < 80:
                    c.showPage()
                    y = height - 50
                c.setFont('Helvetica-Bold', 11)
                c.drawString(x, y, "Net Today")
                c.drawRightString(x+500, y, f"₹{today_net:.2f}")
                y -= 18

                c.save()
                messagebox.showinfo("Exported", f"Today's finance PDF saved to {fname}")
                return

            # Default behavior for multi-day exports (unchanged formatting)
            c.setFont('Helvetica-Bold', 14)
            c.drawString(x, y, f"Finance Report - Last {days} Days")
            y -= 25
            c.setFont('Helvetica-Bold', 10)
            c.drawString(x, y, "Date")
            c.drawString(x+100, y, "Room Inc")
            c.drawString(x+180, y, "Rest Inc")
            c.drawString(x+260, y, "Tax")
            c.drawString(x+320, y, "Expense")
            c.drawString(x+400, y, "Net")
            y -= 15
            c.setFont('Helvetica', 9)
            # Show finance rows newest -> oldest in PDF exports (more intuitive)
            for date_s, room_i, rest_i, tax_i, exp, net in reversed(rows):
                if y < 60:
                    c.showPage()
                    y = height - 50
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = date_s
                c.drawString(x, y, ds)
                c.drawRightString(x+170, y, f"₹{room_i:.2f}")
                c.drawRightString(x+250, y, f"₹{rest_i:.2f}")
                c.drawRightString(x+320, y, f"₹{tax_i:.2f}")
                c.drawRightString(x+400, y, f"₹{exp:.2f}")
                c.drawRightString(x+480, y, f"₹{net:.2f}")
                y -= 12
            c.showPage()
            # Append a simple expenses listing
            c.setFont('Helvetica-Bold', 12)
            c.drawString(40, height-50, f"Expenses (Last {days} Days)")
            y = height - 80
            c.setFont('Helvetica-Bold', 10)
            c.drawString(40, y, "Date")
            c.drawString(120, y, "Name")
            c.drawString(340, y, "Note")
            c.drawString(500, y, "Amount")
            y -= 15
            c.setFont('Helvetica', 9)
            cursor = self.db_conn.cursor()
            cursor.execute(f"SELECT date, name, amount, note FROM daily_expenses WHERE date >= date('now','-{days} day') ORDER BY date DESC")
            exp_rows = cursor.fetchall()
            for date_s, name, amount, note in exp_rows:
                if y < 60:
                    c.showPage()
                    y = height - 50
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = str(date_s)
                c.drawString(40, y, ds)
                c.drawString(120, y, str(name)[:30])
                c.drawString(340, y, str(note)[:40])
                c.drawRightString(560, y, f"₹{float(amount):.2f}")
                y -= 12
            c.save()
            try:
                cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
            except Exception:
                pass
            messagebox.showinfo("Exported", f"Combined finance PDF saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export combined PDF: {e}")
    def draw_finance_sparkline(self, rows):
        """Draw a small sparkline (net values) for the provided rows list of (date, income, expense, net)."""
        try:
            # rows is a list of tuples where the last element is net
            vals = [r[-1] for r in rows]
            if not vals:
                return
            w = self.finance_spark_canvas.winfo_width() or self.finance_spark_canvas.winfo_reqwidth()
            h = self.finance_spark_canvas.winfo_height() or 60
            pad = 6
            self.finance_spark_canvas.delete('all')
            maxv = max(vals)
            minv = min(vals)
            rng = maxv - minv if maxv != minv else 1.0
            points = []
            for i, v in enumerate(vals):
                x = pad + i * ((w - 2*pad) / max(1, len(vals)-1))
                y = pad + (1 - (v - minv) / rng) * (h - 2*pad)
                points.append((x, y))

            # draw filled area
            coords = []
            for x,y in points:
                coords.extend([x,y])
            if coords:
                # polygon from left-bottom to points to right-bottom
                poly = [pad, h-pad] + coords + [w-pad, h-pad]
                self.finance_spark_canvas.create_polygon(poly, fill=COLOR_PRIMARY_LIGHT, outline='')

            # draw line
            for i in range(len(points)-1):
                x1,y1 = points[i]
                x2,y2 = points[i+1]
                self.finance_spark_canvas.create_line(x1,y1,x2,y2, fill=COLOR_PRIMARY, width=2)

            # draw small circles
            for x,y in points:
                self.finance_spark_canvas.create_oval(x-2, y-2, x+2, y+2, fill=COLOR_PRIMARY, outline='')

        except Exception:
            pass

    def setup_bookings_tab(self):
        """Set up the bookings and guests management tab."""
        for widget in self.bookings_tab.winfo_children():
            widget.destroy()

        frame = ttk.Frame(self.bookings_tab, padding=10)
        frame.pack(fill='both', expand=True)

        # Search functionality
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=5)
        ttk.Label(search_frame, text="Search Booking (Ref #, Name, Room #):").pack(side='left', padx=(0, 5))
        self.booking_search_entry = ttk.Entry(search_frame, width=40)
        self.booking_search_entry.pack(side='left', padx=5, ipady=3)
        ttk.Button(search_frame, text="Search", command=self.search_bookings).pack(side='left')
        ttk.Button(search_frame, text="Clear", command=self.load_bookings_data).pack(side='left', padx=5)

        # --- MODIFIED: Treeview columns for Booking/Guest details (Added Adults/Children) ---
        cols = ('Ref #', 'Guest Name', 'Adults', 'Children', 'Phone', 'Room #', 'Check-In', 'Check-Out', 'Status')
        self.bookings_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        for col in cols:
            self.bookings_tree.heading(col, text=col)
            if col in ('Ref #', 'Room #', 'Status', 'Adults', 'Children'):
                 self.bookings_tree.column(col, width=80, anchor='center')
            elif col in ('Check-In', 'Check-Out', 'Phone'):
                 self.bookings_tree.column(col, width=110, anchor='center')
            elif col == 'Guest Name':
                 self.bookings_tree.column(col, width=150)
            else:
                 self.bookings_tree.column(col, width=100)
                 
        # --- END MODIFIED ---


        # Add tags for alternating rows
        self.bookings_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.bookings_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.bookings_tree.pack(fill='both', expand=True, pady=10)
        # Double-click opens detailed booking dialog
        self.bookings_tree.bind('<Double-1>', self.open_booking_detail)

        # Action buttons
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', pady=5)
        ttk.Button(action_frame, text="Cancel Booking", command=self.cancel_booking, style="Danger.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(action_frame, text="Change Dates (Advanced)", command=self.change_booking_dates).pack(side='left', padx=5, ipady=5)
        # --- NEW: Extend Stay Button ---
        ttk.Button(action_frame, text="Extend Stay", command=self.extend_stay).pack(side='left', padx=(15, 5), ipady=5)
        # --- END NEW ---

        # --- NEW: Edit/Delete Booking Buttons (Bookings tab) ---
        self.edit_booking_btn = ttk.Button(action_frame, text="Edit Booking", command=self.edit_booking_from_bookings, style="Accent.TButton", state=tk.DISABLED)
        self.edit_booking_btn.pack(side='left', padx=5, ipady=5)

        self.delete_booking_btn = ttk.Button(action_frame, text="Delete Booking", command=self.delete_booking_from_bookings, style="Danger.TButton", state=tk.DISABLED)
        self.delete_booking_btn.pack(side='left', padx=5, ipady=5)
        # --- END NEW ---

        self.load_bookings_data()
        
        # --- NEW: Frame for selected guest details (Section 2 Fix) ---
        self.selected_guest_frame = ttk.Labelframe(frame, text="Selected Guest Details", padding=10)
        self.selected_guest_frame.pack(fill='x', pady=(10, 5))
        self.selected_guest_label = ttk.Label(self.selected_guest_frame, text="Select a booking above to view primary guest information and documents.", justify=tk.LEFT)
        self.selected_guest_label.pack(fill='x')
        self.bookings_tree.bind('<<TreeviewSelect>>', self.show_booking_guest_details) # BIND NEW METHOD
    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist.

        If running as a PyInstaller onefile bundle, the bundled files are extracted
        to a temporary directory (sys._MEIPASS). The bundled DB must be copied to
        a persistent, writable location (the executable directory) so that data
        persists between runs. This logic copies the bundled DB if necessary and
        ensures we always connect to a writable DB path.
        """
        # Determine DB path. If running frozen, prefer a DB next to the executable.
        try:
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                target_db = os.path.join(exe_dir, DB_NAME)

                # If the target DB doesn't exist, try to copy the bundled DB out of _MEIPASS
                if not os.path.exists(target_db):
                    bundled_db = resource_path(DB_NAME)
                    try:
                        shutil.copyfile(bundled_db, target_db)
                        print(f"Copied bundled DB from {bundled_db} to {target_db}")
                    except Exception as e:
                        print(f"Warning: failed to copy bundled DB: {e}")

                conn = sqlite3.connect(target_db)
            else:
                conn = sqlite3.connect(DB_NAME)
        except Exception:
            # Fallback to local DB name if any of the above fails
            conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Users table (Admin/Employee)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('SuperAdmin', 'Admin', 'Employee', 'Receptionist'))
            )
        ''')

        # Ensure existing users table allows SuperAdmin; if not, migrate table safely.
        try:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            row = cursor.fetchone()
            create_sql = row[0] if row and row[0] else ''
            # If existing users table lacks SuperAdmin or Receptionist in its CHECK constraint, migrate table
            if 'SuperAdmin' not in create_sql or 'Receptionist' not in create_sql:
                # Migrate table to allow SuperAdmin role
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('SuperAdmin', 'Admin', 'Employee', 'Receptionist'))
                    )
                ''')
                # Copy existing users into new table (role will be copied as-is)
                cursor.execute("INSERT OR IGNORE INTO users_new (id, username, password, role) SELECT id, username, password, role FROM users")
                cursor.execute("DROP TABLE IF EXISTS users")
                cursor.execute("ALTER TABLE users_new RENAME TO users")
                self.db_conn.commit()
                cursor = conn.cursor()
        except Exception:
            # If anything goes wrong, continue without breaking startup.
            pass

        # Create default users if they don't exist
        cursor.execute("SELECT * FROM users WHERE username='admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'Admin')")

        cursor.execute("SELECT * FROM users WHERE username='emp'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, role) VALUES ('emp', 'emp123', 'Employee')")

        # Ensure SuperAdmin user exists (username: david)
        cursor.execute("SELECT * FROM users WHERE username='david'")
        if not cursor.fetchone():
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES ('david', 'david7845', 'SuperAdmin')")
            except Exception:
                # If insert fails due to schema constraint, ignore; migration above should have handled it.
                pass

        # Settings table for hotel details (extended to store address lines, tax rates and hotel rules)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                hotel_name TEXT,
                address TEXT,
                address_line1 TEXT,
                address_line2 TEXT,
                gst_number TEXT,
                contact_number TEXT,
                cgst_rate REAL DEFAULT 0.0,
                sgst_rate REAL DEFAULT 0.0,
                igst_rate REAL DEFAULT 0.0,
                enable_cgst_sgst TEXT DEFAULT 'false',
                enable_igst TEXT DEFAULT 'false',
                hotel_rules TEXT
            )
        ''')
        cursor.execute("SELECT * FROM settings WHERE id=1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO settings (id, hotel_name, address, address_line1, address_line2, gst_number, contact_number, cgst_rate, sgst_rate, igst_rate, enable_cgst_sgst, enable_igst, hotel_rules) VALUES (1, 'My Hotel', '123, Main Street, City', '', '', 'GSTIN12345', '9876543210', 0.0, 0.0, 0.0, 'false', 'false', '')")

        # Rooms table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT UNIQUE NOT NULL,
                room_type TEXT NOT NULL,
                bed_type TEXT NOT NULL,
                rate REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance'))
            )
        ''')

        # Guests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                address TEXT
            )
        ''')

        # Bookings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_ref TEXT UNIQUE NOT NULL,
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
        
        # --- NEW: booking_persons table for multi-guest info ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS booking_persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_ref TEXT NOT NULL,
                person_name TEXT NOT NULL,
                is_primary TEXT NOT NULL CHECK(is_primary IN ('true', 'false'))
            )
        ''')

        # Restaurant Menu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL
            )
        ''')

        # Restaurant Orders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                item_id INTEGER,
                quantity INTEGER,
                price_at_order REAL,
                order_date TEXT,
                FOREIGN KEY(booking_id) REFERENCES bookings(id),
                FOREIGN KEY(item_id) REFERENCES restaurant_menu(id)
            )
        ''')

        # --- NEW: local_charges table ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_charges (
                id INTEGER PRIMARY KEY,
                enabled TEXT NOT NULL DEFAULT 'false',
                charge_name TEXT,
                amount REAL NOT NULL DEFAULT 0.0,
                calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Per Day', 'Per Person'))
            )
        ''')
        # Ensure default row exists
        cursor.execute("SELECT * FROM local_charges WHERE id=1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO local_charges (id, charge_name, amount, calculation_type) VALUES (1, 'Local Dev Fee', 50.0, 'Per Person')")
        # --- END NEW ---

        conn.commit()

        # --- MIGRATION: Ensure bookings.booking_ref is not UNIQUE so group bookings can share one ref ---
        try:
            # First, inspect the CREATE TABLE SQL to see if booking_ref was declared UNIQUE at column level.
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'")
            row = cursor.fetchone()
            create_sql = row[0] if row and row[0] else ''
            found_unique_decl = False
            try:
                if create_sql and re.search(r"booking_ref\s+TEXT\s+UNIQUE", create_sql, re.IGNORECASE):
                    found_unique_decl = True
            except Exception:
                found_unique_decl = False

            # If not found via CREATE SQL, fall back to checking indexes (implicit unique index may exist)
            unique_index_on_booking_ref = None
            if not found_unique_decl:
                cursor.execute("PRAGMA index_list('bookings')")
                indexes = cursor.fetchall()
                for idx in indexes:
                    # PRAGMA index_list returns: seq, name, unique, origin, partial
                    idx_name = idx[1]
                    is_unique = idx[2]
                    if is_unique:
                        try:
                            cursor.execute(f"PRAGMA index_info('{idx_name}')")
                            cols = cursor.fetchall()
                            for col in cols:
                                # index_info returns seqno, cid, name
                                if col and len(col) >= 3 and col[2] == 'booking_ref':
                                    unique_index_on_booking_ref = idx_name
                                    found_unique_decl = True
                                    break
                            if found_unique_decl:
                                break
                        except Exception:
                            continue

            if found_unique_decl:
                # Recreate bookings table without UNIQUE constraint on booking_ref
                cursor.execute('BEGIN')
                cursor.execute('''
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
                cursor.execute("INSERT OR REPLACE INTO bookings_new (id, booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, advance_payment) SELECT id, booking_ref, guest_id, room_id, check_in, check_out, status, total_amount, advance_payment FROM bookings")
                cursor.execute("DROP TABLE IF EXISTS bookings")
                cursor.execute("ALTER TABLE bookings_new RENAME TO bookings")
                # Remove the old unique index if it still exists
                try:
                    if unique_index_on_booking_ref:
                        cursor.execute(f"DROP INDEX IF EXISTS {unique_index_on_booking_ref}")
                except Exception:
                    pass
                conn.commit()
                logger.info("Migrated bookings table to remove UNIQUE constraint on booking_ref (index %s)", unique_index_on_booking_ref)
        except Exception as e:
            # Do not stop startup on migration failure; log and continue
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("Bookings migration check failed: %s", e)

        # --- NEW: Daily finance tables (income + expenses) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_income (
                date TEXT PRIMARY KEY,
                total REAL NOT NULL DEFAULT 0.0,
                last_updated TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()

        # --- VERSION 2.2: Add new columns robustly ---
        _add_column_if_not_exists(conn, 'bookings', 'num_adults', 'INTEGER', 1)
        _add_column_if_not_exists(conn, 'bookings', 'num_children', 'INTEGER', 0)
        _add_column_if_not_exists(conn, 'bookings', 'num_rooms', 'INTEGER', 1)
        _add_column_if_not_exists(conn, 'settings', 'enable_tax', 'TEXT', 'true')  # Kept for legacy
        _add_column_if_not_exists(conn, 'settings', 'cgst_rate', 'REAL', 9.0)
        _add_column_if_not_exists(conn, 'settings', 'sgst_rate', 'REAL', 9.0)
        _add_column_if_not_exists(conn, 'settings', 'igst_rate', 'REAL', 18.0)
        _add_column_if_not_exists(conn, 'bookings', 'actual_check_in', 'TEXT', None)
        _add_column_if_not_exists(conn, 'bookings', 'actual_check_out', 'TEXT', None)
        # --- V2.2: New independent tax columns ---
        _add_column_if_not_exists(conn, 'settings', 'enable_cgst_sgst', 'TEXT', 'true')
        _add_column_if_not_exists(conn, 'settings', 'enable_igst', 'TEXT', 'true')
        # Add separate address lines to avoid overlap in long addresses and for better PDF rendering
        _add_column_if_not_exists(conn, 'settings', 'address_line1', 'TEXT', '')
        _add_column_if_not_exists(conn, 'settings', 'address_line2', 'TEXT', '')

        return conn

    def create_login_screen(self):
        """Creates the initial login screen."""
        if hasattr(self, 'main_frame'):
            self.main_frame.destroy()

        self.login_frame = ttk.Frame(self, style="TFrame", padding=40)
        self.login_frame.place(relx=0.5, rely=0.5, anchor='center')

        # --- NEW: Load and display logo.png ---
        try:
            img_path = resource_path("logo.png")
            img = Image.open(img_path)
            img = img.resize((100, 100), Image.LANCZOS) # Resize to 100x100
            self.login_logo_image = ImageTk.PhotoImage(img)
            
            logo_label = ttk.Label(self.login_frame, image=self.login_logo_image, background=COLOR_LIGHT_BG)
            logo_label.pack(pady=(0, 15))
        except Exception as e:
            print(f"Error loading logo.png: {e}")
            # Fallback text if logo fails
            logo_frame = tk.Frame(self.login_frame, bg=COLOR_PRIMARY, width=80, height=80)
            logo_frame.pack(pady=10)
            ttk.Label(logo_frame, text="N", font=('Helvetica', 40, 'bold'), background=COLOR_PRIMARY, foreground="white").place(relx=0.5, rely=0.5, anchor='center')
        # --- END NEW ---

        ttk.Label(self.login_frame, text=SOFTWARE_NAME, font=('Helvetica', 24, 'bold'), background="white", foreground=COLOR_PRIMARY).pack(pady=(0, 20))

        ttk.Label(self.login_frame, text="Username", background="white", font=('Helvetica', 12)).pack(pady=(10, 2), anchor='w', padx=40)
        self.username_entry = ttk.Entry(self.login_frame, width=30, font=('Helvetica', 12))
        self.username_entry.pack(ipady=5, padx=40)

        ttk.Label(self.login_frame, text="Password", background="white", font=('Helvetica', 12)).pack(pady=(10, 2), anchor='w', padx=40)
        self.password_entry = ttk.Entry(self.login_frame, show="*", width=30, font=('Helvetica', 12))
        self.password_entry.pack(ipady=5, padx=40)

        login_button = ttk.Button(self.login_frame, text="Login", command=self.handle_login, style="Accent.TButton")
        login_button.pack(pady=30, ipadx=20, ipady=8, fill='x', padx=40)

        # --- MODIFIED: Footer Text ---
        footer_text = (
            "Developed by Nexuzy Tech Pvt Ltd\n"
            "For Enquiry: support@nexuzy.in | For Customization: manoj@nexuzy.in | Other: david@nexuzy.in"
        )
        ttk.Label(self.login_frame, text=footer_text, style="Footer.TLabel", justify=tk.CENTER).pack(pady=(10, 0))
        # --- END MODIFIED ---

        self.username_entry.focus()
        self.bind('<Return>', lambda event: self.handle_login())

        # Center the login frame in a more robust way
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.login_frame.grid(row=0, column=0)
        # Apply style to the login frame itself for rounded corners (theme-dependent)
        self.style.configure("Login.TFrame", background=COLOR_LIGHT_BG, relief="solid", borderwidth=1, bordercolor="#e0e0e0")
        self.login_frame.configure(style="Login.TFrame")

    def handle_login(self):
        """Validates user credentials."""
        username = self.username_entry.get()
        password = self.password_entry.get()

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        result = cursor.fetchone()

        if result:
            self.user_role = result[0]
            self.login_frame.destroy()  # Destroy frame
            self.unbind('<Return>')
            # Reset grid configuration
            self.rowconfigure(0, weight=0)
            self.columnconfigure(0, weight=0)
            self.create_main_widgets()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def update_clock(self):
        """Updates the clock label every second."""
        # e.g., 10/22/2025  11:50:30 AM (MM/DD/YYYY + 12-hour)
        now = datetime.now().strftime('%m/%d/%Y  %I:%M:%S %p')
        try:
            if self.clock_label:
                self.clock_label.config(text=now)
                # Schedule the next update
                self.after(1000, self.update_clock)
        except tk.TclError:
            # This happens if the widget is destroyed (e.g., logout)
            pass

    def create_main_widgets(self):
        """Create the main application interface after successful login."""
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        # Create the "Help > About" menu
        self.create_main_menu()

        # --- V2.1: New Header with Clock ---
        header_frame = ttk.Frame(self.main_frame, style="Header.TFrame")
        header_frame.pack(fill="x")

        # Left: Software Name with Logo (NEW)
        if self.header_logo_image:
             ttk.Label(header_frame, image=self.header_logo_image, background=COLOR_PRIMARY).pack(side='left', padx=(5, 5))
             
        ttk.Label(header_frame, text=f"{SOFTWARE_NAME}", style="Header.TLabel").pack(side='left')

        # Center: User Role
        ttk.Label(header_frame, text=f"Logged in as: {self.user_role}", style="Header.TLabel", font=('Helvetica', 11, 'normal')).pack(side='left', padx=30)

        # Right: Clock
        self.clock_label = ttk.Label(header_frame, text="", style="Header.TLabel", font=('Helvetica', 11, 'bold'))
        self.clock_label.pack(side='right')

        # Far Right: Logout Button
        logout_button = ttk.Button(header_frame, text="Logout", command=self.create_login_screen, style="TButton")
        logout_button.pack(side='right', padx=(0, 10))

        # Start the clock
        self.update_clock()
        # --- End V2.1 Header ---

        # --- Toolbar: critical quick actions visible on all tabs ---
        toolbar = ttk.Frame(self.main_frame, padding=(6,4))
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text="New Advance Booking", command=lambda: self.open_new_booking_window(booking_type="Advance"), style="Accent.TButton").pack(side='left', padx=4)
        ttk.Button(toolbar, text="New Quick Booking", command=lambda: self.open_new_booking_window(booking_type="Quick"), style="TButton").pack(side='left', padx=4)
        ttk.Button(toolbar, text="Check-In", command=self.check_in_guest, style="Success.TButton").pack(side='left', padx=4)
        ttk.Button(toolbar, text="Check-Out & Bill", command=self.check_out_guest).pack(side='left', padx=4)
        ttk.Button(toolbar, text="Add Restaurant Order", command=self.add_restaurant_order).pack(side='left', padx=4)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_dashboard).pack(side='left', padx=4)
        # --- End Toolbar ---

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Add tabs based on user role
        self.dashboard_tab = ttk.Frame(self.notebook, style="TFrame")
        self.bookings_tab = ttk.Frame(self.notebook, style="TFrame")
        self.history_tab = ttk.Frame(self.notebook, style="TFrame")  # V2.0 New Tab

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.bookings_tab, text="Bookings & Guests")
        self.notebook.add(self.history_tab, text="Booking History")  # V2.0 New Tab
        # Finance tab (separate from dashboard to avoid layout overlap)
        self.finance_tab = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.finance_tab, text="Finance")

        # Admin & SuperAdmin tabs
        if self.user_role in ('Admin', 'SuperAdmin'):
            self.rooms_tab = ttk.Frame(self.notebook, style="TFrame")
            self.restaurant_tab = ttk.Frame(self.notebook, style="TFrame")
            self.settings_tab = ttk.Frame(self.notebook, style="TFrame")
            self.backup_tab = ttk.Frame(self.notebook, style="TFrame") # <-- NEW: Backup/Restore

            self.notebook.add(self.rooms_tab, text="Room Management")
            self.notebook.add(self.restaurant_tab, text="Restaurant Menu")
            self.notebook.add(self.settings_tab, text="Settings")
            self.notebook.add(self.backup_tab, text="Backup & Restore") # <-- NEW

            # User Management is only visible to SuperAdmin
            if self.user_role == 'SuperAdmin':
                self.users_tab = ttk.Frame(self.notebook, style="TFrame") # <-- NEW: User Mgmt
                self.notebook.add(self.users_tab, text="User Management")

            self.setup_rooms_tab()
            self.setup_restaurant_tab()
            self.setup_settings_tab()
            if self.user_role == 'SuperAdmin':
                self.setup_users_tab()
            self.setup_backup_tab() # <-- NEW

        # Populate tabs
        self.setup_dashboard_tab()
        self.setup_bookings_tab()
        self.setup_history_tab()  # V2.0 New Tab
        self.setup_finance_tab()

    def create_main_menu(self):
        """Creates the main menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.open_about_window)

    def open_about_window(self):
        """Opens the About Toplevel window."""
        AboutWindow(self)

    def setup_dashboard_tab(self):
        """Setup the dashboard with room status."""
        # Debounce rebuilds: avoid rebuilding too frequently which can freeze UI
        now_ts = time.time()
        if hasattr(self, '_last_dashboard_build_time'):
            if now_ts - self._last_dashboard_build_time < 0.8:
                # schedule a refresh slightly later and skip current heavy rebuild
                try:
                    self.after(800, self.setup_dashboard_tab)
                except Exception:
                    pass
                return
        self._last_dashboard_build_time = now_ts

        # Avoid rebuilding the dashboard when it's not the active tab (prevents blinking when switching tabs)
        try:
            if hasattr(self, 'notebook'):
                current = self.notebook.tab(self.notebook.select(), 'text')
                if str(current).lower() != 'dashboard':
                    return
        except Exception:
            # on any issue determining tab, continue with build
            pass

        for widget in self.dashboard_tab.winfo_children():
            widget.destroy()

        controls_frame = ttk.Frame(self.dashboard_tab, padding=(10, 10))
        controls_frame.pack(fill='x')

        # Quick actions are available in the global toolbar above the tabs.
        # Avoid duplicating the same buttons here to prevent them appearing twice.

        # Legend
        legend_frame = ttk.Frame(controls_frame)
        legend_frame.pack(side='right', padx=20)
        ttk.Label(legend_frame, text="Legend:", font=('Helvetica', 10, 'bold')).pack(side='left', padx=5, anchor='s')
        ttk.Label(legend_frame, text="", style="Available.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Available").pack(side='left', padx=(0, 10))
        ttk.Label(legend_frame, text="", style="Occupied.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Occupied").pack(side='left', padx=(0, 10))
        ttk.Label(legend_frame, text="", style="Reserved.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Reserved (Today)").pack(side='left', padx=(0, 10))
        ttk.Label(legend_frame, text="", style="Maintenance.TLabel", width=2).pack(side='left')
        ttk.Label(legend_frame, text=" Maintenance").pack(side='left', padx=(0, 10))

        # Room display area (wrap into a top frame so the bottom matrix cannot overlap)
        cards_frame = ttk.Frame(self.dashboard_tab)
        cards_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Buttons to show/hide the 30-day matrix (Show will auto-hide after a timeout)
        try:
              # Button to toggle the 30-day matrix (click to show/hide)
              # Keep a constant user-facing label as requested: do not switch to "Hide".
              self._matrix_toggle_text = tk.StringVar(value="Show 30 Day Booking Status")
              btn = ttk.Button(controls_frame, textvariable=self._matrix_toggle_text, command=self._toggle_dashboard_matrix)
              btn.pack(side='left', padx=(0,10))
              self._matrix_toggle_btn = btn
        except Exception:
            pass

        canvas = tk.Canvas(cards_frame, bg=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(cards_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Forward enter/leave from the inner frame to the canvas so _make_scrollable can bind/unbind correctly
        try:
            scrollable_frame.bind('<Enter>', lambda e: canvas.event_generate('<Enter>'))
            scrollable_frame.bind('<Leave>', lambda e: canvas.event_generate('<Leave>'))
            # Enable smooth scrolling (mouse + keyboard) for the main dashboard cards area
            try:
                self._make_scrollable(canvas)
            except Exception:
                pass
        except Exception:
            pass

        # Finance UI moved to a dedicated Finance tab to avoid dashboard overlap

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, room_number, room_type, bed_type, status, rate FROM rooms ORDER BY room_number")
        rooms = cursor.fetchall()

        available_rooms_count = 0
        today = datetime.now().strftime('%Y-%m-%d')

        row, col = 0, 0
        for room in rooms:
            room_id, room_number, room_type, bed_type, status, rate = room

            # BUGFIX: New logic to determine status for display
            display_status = status
            if status == 'Available':
                # Check if any booking overlaps today (covers reservations with time component)
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                cursor.execute("SELECT 1 FROM bookings WHERE room_id=? AND check_in <= ? AND check_out >= ? AND status='Reserved'", (room_id, tomorrow, today))
                if cursor.fetchone():
                    display_status = 'Reserved'
                else:
                    available_rooms_count += 1

            frame = ttk.Frame(scrollable_frame, style="Room.TFrame")
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            ttk.Label(frame, text=f"Room {room_number}", font=('Helvetica', 14, 'bold'), background=COLOR_ODD_ROW).pack(pady=(10, 5))
            ttk.Label(frame, text=f"{room_type} - {bed_type}", background=COLOR_ODD_ROW).pack(pady=2)
            ttk.Label(frame, text=f"Rate: Rs.{rate:.2f}/day", background=COLOR_ODD_ROW).pack(pady=(2, 10))

            status_label = ttk.Label(frame, text=display_status.upper(), style=f"{display_status}.TLabel")
            status_label.pack(fill='x', side='bottom', ipady=5)

            col += 1
            if col > 5:  # Adjust number of columns as needed
                col = 0
                row += 1

        # Display Available Rooms Count
        status_bar = ttk.Frame(self.dashboard_tab, style="TFrame")
        status_bar.pack(fill='x', side='bottom', pady=5, padx=10)
        ttk.Label(status_bar, text=f"Total Rooms Available (Now): {available_rooms_count}", font=('Helvetica', 12, 'bold')).pack(side='right')

        # (Removed) Next 30 Days Room Status Summary - not required by user to reduce clutter

        # --- NEW: Per-Room 30-Day Status Matrix (colored cells) ---
        try:
            # Insert a visual separator to prevent the matrix from overlapping the room cards
            ttk.Separator(self.dashboard_tab, orient='horizontal').pack(fill='x', padx=10, pady=(6,4))
            matrix_frame = ttk.Labelframe(self.dashboard_tab, text="Room Status Matrix (Next 30 Days)", padding=6)
            # Keep a reference so toggle/hide helpers can operate on the latest matrix
            try:
                self._last_matrix_frame_ref = matrix_frame
            except Exception:
                pass
            # NOTE: keep the matrix hidden by default to avoid overlap; it will be packed when the user
            # requests it via the Show button (self._temp_show_matrix). This prevents the matrix from
            # appearing automatically and overlapping the room cards area.

            # Optimize: prefetch bookings for next 30 days and compute statuses in-memory
            today = datetime.now().date()
            date_list = [(today + timedelta(days=i)) for i in range(0, 30)]
            # Show all 30 days in one horizontal row (single-line display)
            chunk = 30
            date_rows = [date_list]

            # Create inner frame to hold the matrix (compact, no horizontal scroll)
            mat_inner = ttk.Frame(matrix_frame)
            mat_inner.pack(fill='both', padx=4, pady=4)

            # Header row (header on left, status label on right) so status aligns in one line with headers
            top_row = ttk.Frame(mat_inner)
            top_row.pack(fill='x')
            header = ttk.Frame(top_row)
            header.pack(side='left', fill='x', expand=True)
            # Status info label (shows last clicked cell date/status) aligned to the right of headers
            self.dashboard_matrix_status = ttk.Label(top_row, text="", font=('Helvetica', 9))
            self.dashboard_matrix_status.pack(side='right', padx=6)

            # Fetch rooms and bookings overlapping the 30-day window
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, room_number, status FROM rooms ORDER BY room_number")
            rooms = cursor.fetchall()

            # Draw header: left 'Room' label, then dates split into rows
            ttk.Label(header, text='Room', width=10).grid(row=0, column=0, rowspan=len(date_rows), padx=2, pady=2)
            for r_idx, dlist in enumerate(date_rows):
                for col_idx, d in enumerate(dlist, start=1):
                    # Compact header: show only the day number (single-line) in a smaller font
                    # This keeps the 30-day matrix narrow without changing other views.
                    lbl = ttk.Label(header, text=d.strftime('%d'), width=3, anchor='center', font=('Helvetica', 8))
                    lbl.grid(row=r_idx, column=col_idx, padx=1, pady=0)

            # Use date-only bounds so check-out date is non-inclusive
            start_range = date_list[0].strftime('%Y-%m-%d')
            end_range = (date_list[-1] + timedelta(days=1)).strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT room_id, status, check_in, check_out FROM bookings WHERE DATE(check_out) >= ? AND DATE(check_in) <= ?",
                (start_range, end_range)
            )
            raw = cursor.fetchall()

            # Build bookings_by_room to avoid DB queries per cell; normalize check-in/out to dates
            from collections import defaultdict
            bookings_by_room = defaultdict(list)
            for row in raw:
                room_id_b, b_status, b_ci, b_co = row
                ci_dt = None
                co_dt = None
                try:
                    if b_ci:
                        try:
                            ci_parsed = datetime.strptime(str(b_ci)[:16], '%Y-%m-%d %H:%M')
                        except Exception:
                            ci_parsed = datetime.strptime(str(b_ci)[:10], '%Y-%m-%d')
                        ci_dt = ci_parsed.date()
                except Exception:
                    ci_dt = None
                try:
                    if b_co:
                        try:
                            co_parsed = datetime.strptime(str(b_co)[:16], '%Y-%m-%d %H:%M')
                        except Exception:
                            co_parsed = datetime.strptime(str(b_co)[:10], '%Y-%m-%d')
                        co_dt = co_parsed.date()
                except Exception:
                    co_dt = None
                bookings_by_room[room_id_b].append({'status': b_status, 'check_in': ci_dt, 'check_out': co_dt})

            # Color legend mapping
            status_color = {
                'Available': "#b8f0b8",
                'Occupied': "#eb9797",
                'Reserved': "#f0dda5",
                'Maintenance': "#e4dcdc"
            }

            # Decide render mode: if number of widgets (cells) large, render on Canvas for speed
            total_cells = len(rooms) * len(date_list)
            use_canvas = total_cells > 500

            # Map room id -> display number for quick access
            room_number_by_id = {r[0]: r[1] for r in rooms}

            if use_canvas:
                # Canvas-based grid rendering (fewer Tk widgets, much faster)
                pad = 4
                left_margin = 90
                rows_count = len(rooms)
                cols_count = len(date_rows[0]) if date_rows else 0

                mat_canvas = tk.Canvas(mat_inner, background=COLOR_LIGHT_BG, height=min(700, rows_count * (len(date_rows) * 24) + 60))
                vscroll = ttk.Scrollbar(mat_inner, orient='vertical', command=mat_canvas.yview)
                mat_canvas.configure(yscrollcommand=vscroll.set)
                mat_canvas.pack(side='left', fill='both', expand=True)
                vscroll.pack(side='right', fill='y')

                # Forward enter/leave from the inner mat_inner frame to the matrix canvas
                try:
                    mat_inner.bind('<Enter>', lambda e: mat_canvas.event_generate('<Enter>'))
                    mat_inner.bind('<Leave>', lambda e: mat_canvas.event_generate('<Leave>'))
                    # Enable smooth scrolling for the matrix canvas as well
                    try:
                        self._make_scrollable(mat_canvas)
                    except Exception:
                        pass
                except Exception:
                    pass

                # Allow the canvas to compute a sensible width before sizing cells
                mat_canvas.update_idletasks()
                try:
                    avail_w = mat_canvas.winfo_width() or mat_canvas.winfo_reqwidth() or 800
                    # leave some padding on the right
                    usable_w = max(200, avail_w - left_margin - 60)
                    cell_w = max(22, min(48, int(usable_w / max(1, cols_count))))
                except Exception:
                    cell_w = 28
                # cell height slightly larger so we can draw a status glyph
                cell_h = max(18, int(cell_w * 0.75))

                # create a single inner canvas group and compute content size
                content_width = left_margin + (cols_count) * (cell_w + pad) + 40
                content_height = rows_count * (len(date_rows) * (cell_h + pad)) + 40
                mat_canvas.configure(scrollregion=(0,0,content_width,content_height))

                # Draw compact date headers (single-line day numbers) and compute header height
                header_font = ('Helvetica', 8)
                header_height = int(cell_h + pad)
                for col_idx, d in enumerate(date_list):
                    x = left_margin + col_idx * (cell_w + pad)
                    # center header above column (single-line day number)
                    mat_canvas.create_text(x + cell_w/2, header_height/2, text=d.strftime('%d'), font=header_font, tags=(f"hdr_{d.strftime('%Y%m%d')}",))

                # Draw grid cells and room labels: each room occupies one row; each date occupies one column
                room_label_font = ('Helvetica', 10, 'bold')
                status_glyph_font = ('Helvetica', 8, 'bold')
                for i, room in enumerate(rooms):
                    room_id, room_number, room_status = room
                    row_y_top = header_height + 6 + i * (cell_h + pad)
                    # room label (left margin)
                    mat_canvas.create_text(8, row_y_top + cell_h/2, anchor='w', text=str(room_number), font=room_label_font)
                    for col_idx, d in enumerate(date_list):
                        dt_start = datetime.combine(d, datetime.min.time())
                        dt_end = dt_start + timedelta(days=1)

                        # determine status (maintenance > occupied > reserved > available)
                        if room_status == 'Maintenance':
                            st = 'Maintenance'
                        else:
                            st = 'Available'
                            for b in bookings_by_room.get(room_id, []):
                                b_ci = b.get('check_in')
                                b_co = b.get('check_out')
                                if not b_ci or not b_co:
                                    continue
                                if b.get('status') == 'Checked-In' and (b_ci <= dt_end and b_co >= dt_start):
                                    st = 'Occupied'
                                    break
                            else:
                                for b in bookings_by_room.get(room_id, []):
                                    b_ci = b.get('check_in')
                                    b_co = b.get('check_out')
                                    if not b_ci or not b_co:
                                        continue
                                    if b.get('status') == 'Reserved' and (b_ci <= dt_end and b_co >= dt_start):
                                        st = 'Reserved'
                                        break

                        if st not in status_color:
                            st = 'Available'
                        color = status_color.get(st, '#ffffff')

                        x = left_margin + col_idx * (cell_w + pad)
                        y = row_y_top
                        rect_id = mat_canvas.create_rectangle(x, y, x + cell_w, y + cell_h, fill=color, outline='#cccccc')
                        tag = f"cell_{room_id}_{d.strftime('%Y%m%d')}"
                        mat_canvas.addtag_withtag(tag, rect_id)

                        # Draw a short status glyph/text centered in the cell to make status more visible
                        glyph = 'A' if st == 'Available' else ('O' if st == 'Occupied' else ('R' if st == 'Reserved' else 'M'))
                        mat_canvas.create_text(x + cell_w/2, y + cell_h/2, text=glyph, font=status_glyph_font, fill='#333333', tags=(tag,))

                # (Removed) the vertical 'Today' marker to keep the header compact and avoid the long bar

                # Click handler for canvas: find the cell tag and act on it
                def _on_canvas_click(ev, canvas_widget=mat_canvas):
                    try:
                        x = canvas_widget.canvasx(ev.x)
                        y = canvas_widget.canvasy(ev.y)
                        items = canvas_widget.find_overlapping(x, y, x, y)
                        if not items:
                            return
                        # Pick top-most item
                        item = items[-1]
                        tags = canvas_widget.gettags(item)
                        cell_tag = next((t for t in tags if t.startswith('cell_')), None)
                        if not cell_tag:
                            return
                        parts = cell_tag.split('_')
                        if len(parts) < 3:
                            return
                        rid = int(parts[1])
                        date_s = parts[2]
                        dt = datetime.strptime(date_s, '%Y%m%d').date()
                        # determine status and update status label in single-line format
                        try:
                            st = self._get_room_status_for_room_on_date(rid, dt)
                        except Exception:
                            st = ''
                        status_text = f"Room {room_number_by_id.get(rid,'?')} — {dt.strftime('%d/%m/%Y')} — {st}"
                        try:
                            self.dashboard_matrix_status.config(text=status_text)
                        except Exception:
                            pass
                        self._show_bookings_for_room_on_date(rid, dt)
                    except Exception:
                        pass

                mat_canvas.bind('<Button-1>', _on_canvas_click)
            else:
                # Fallback to previous Label-based grid for small numbers (keeps existing behavior)
                for i, room in enumerate(rooms, start=1):
                    rowf = ttk.Frame(mat_inner)
                    rowf.pack(fill='x', pady=2)
                    room_id, room_number, room_status = room
                    ttk.Label(rowf, text=str(room_number), width=10).grid(row=0, column=0, rowspan=len(date_rows)*1, padx=2, pady=1)

                    # For each date-row (top/bottom)
                    for r_idx, dlist in enumerate(date_rows):
                        for j, d in enumerate(dlist, start=1 + r_idx*chunk):
                            dt_start = datetime.combine(d, datetime.min.time())
                            dt_end = dt_start + timedelta(days=1)

                            if room_status == 'Maintenance':
                                st = 'Maintenance'
                            else:
                                st = 'Available'
                                for b in bookings_by_room.get(room_id, []):
                                    b_ci = b.get('check_in')
                                    b_co = b.get('check_out')
                                    if not b_ci or not b_co:
                                        continue
                                    if b.get('status') == 'Checked-In' and (b_ci <= dt_end and b_co >= dt_start):
                                        st = 'Occupied'
                                        break
                                else:
                                    for b in bookings_by_room.get(room_id, []):
                                        b_ci = b.get('check_in')
                                        b_co = b.get('check_out')
                                        if not b_ci or not b_co:
                                            continue
                                        if b.get('status') == 'Reserved' and (b_ci <= dt_end and b_co >= dt_start):
                                            st = 'Reserved'
                                            break

                            if st not in status_color:
                                st = 'Available'
                            color = status_color.get(st, '#ffffff')

                            cell = tk.Label(rowf, text='', bg=color, width=2, relief='ridge', bd=1)
                            cell.grid(row= r_idx, column=(j - (r_idx*chunk)), padx=1, pady=1)
                            def _on_click(ev, rid=room_id, dt=d, st=st):
                                try:
                                    # show MM/DD/YYYY in status
                                    self.dashboard_matrix_status.config(text=f"Room {room_number} — {dt.strftime('%d/%m/%Y')} — {st}")
                                except Exception:
                                    pass
                                self._show_bookings_for_room_on_date(rid, dt)
                            cell.bind('<Button-1>', _on_click)
        except Exception:
            pass

        # Dashboard auto-refresh will be started once during main widget creation

    def refresh_dashboard(self):
        """Refreshes the dashboard view."""
        self.setup_dashboard_tab()

    def _temp_show_matrix(self, timeout_ms=8000):
        """Temporarily show the last-created dashboard matrix for `timeout_ms` milliseconds.

        The matrix is created each time `setup_dashboard_tab` runs; that function sets
        `self._last_matrix_frame_ref` to the most recent `matrix_frame` so this method
        can operate on it. The matrix will auto-hide after `timeout_ms` unless
        another show request resets the timer.
        """
        # Show matrix temporarily as a toplevel, then auto-hide after timeout_ms.
        try:
            # cancel prior auto-hide if any
            try:
                if hasattr(self, '_matrix_hide_after_id') and self._matrix_hide_after_id:
                    self.after_cancel(self._matrix_hide_after_id)
            except Exception:
                pass

            # open or lift the compact matrix Toplevel
            try:
                if not (hasattr(self, '_matrix_toplevel') and self._matrix_toplevel and tk.Toplevel.winfo_exists(self._matrix_toplevel)):
                    self._open_matrix_window()
                else:
                    try:
                        self._matrix_toplevel.lift()
                    except Exception:
                        pass
            except Exception:
                return

            # schedule hide
            try:
                self._matrix_hide_after_id = self.after(int(timeout_ms), lambda: self._hide_dashboard_matrix())
            except Exception:
                self._matrix_hide_after_id = None
        except Exception:
            pass

    def _toggle_dashboard_matrix(self):
        """Toggle visibility of the embedded matrix labelframe (or destroy the toplevel).

        Click once to show (no auto-hide). Click again to hide. If matrix Toplevel is open,
        it will be raised/destroyed appropriately.
        """
        # Toggle behavior: open a clean Toplevel sized to current application window, or close it.
        try:
            # If a toplevel exists, close it and reset toggle text
            if hasattr(self, '_matrix_toplevel') and self._matrix_toplevel and tk.Toplevel.winfo_exists(self._matrix_toplevel):
                try:
                    self._matrix_toplevel.destroy()
                except Exception:
                    pass
                self._matrix_toplevel = None
                try:
                    if hasattr(self, '_matrix_toggle_text'):
                        self._matrix_toggle_text.set("Show 30 Day Booking Status")
                except Exception:
                    pass
                return

            # Not open: ensure embedded matrix (if any) is hidden so Toplevel won't overlap
            try:
                mf = getattr(self, '_last_matrix_frame_ref', None)
                if mf and mf.winfo_ismapped():
                    try:
                        mf.pack_forget()
                    except Exception:
                        pass
            except Exception:
                pass

            # Open a fresh toplevel sized to current application window so 30 columns fit
            try:
                self._open_matrix_window()
                try:
                    if hasattr(self, '_matrix_toggle_text'):
                        # Keep the button label constant per user preference
                        self._matrix_toggle_text.set("Show 30 Day Booking Status")
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def _open_matrix_window(self):
        """Open a Toplevel window with the 30-day room×date matrix.

        This creates an independent window so the matrix cannot overlap the main
        dashboard content. It reuses the database queries and draws a compact
        canvas grid with one cell per room×date.
        """
        # If already open, do nothing
        if hasattr(self, '_matrix_toplevel') and self._matrix_toplevel and tk.Toplevel.winfo_exists(self._matrix_toplevel):
            return

        # Size the toplevel relative to the current main window so the 30 columns can fit
        try:
            main_w = self.winfo_width() or self.winfo_screenwidth() or 1000
            main_h = self.winfo_height() or int(self.winfo_screenheight() * 0.75) or 700
        except Exception:
            main_w, main_h = 1000, 600

        # Attempt to use most of the available width (open large / maximized so 30 columns are readable)
        desired_w = max(1000, int(main_w))
        desired_h = max(600, int(main_h * 0.9))

        mt = tk.Toplevel(self)
        mt.title('Room Status Matrix (Next 30 Days)')
        try:
            mt.geometry(f"{desired_w}x{desired_h}")
        except Exception:
            mt.geometry('1000x600')
        # Try to maximize the toplevel so the matrix can use full screen real-estate
        try:
            mt.state('zoomed')
        except Exception:
            try:
                mt.attributes('-zoomed', True)
            except Exception:
                pass
        mt.transient(self)
        # allow resizing
        mt.resizable(True, True)
        self._matrix_toplevel = mt

        frame = ttk.Frame(mt, padding=6)
        frame.pack(fill='both', expand=True)

        # Status label
        status_lbl = ttk.Label(frame, text="", font=('Helvetica', 9))
        status_lbl.pack(anchor='e')

        # Canvas + vertical scrollbar
        mat_canvas = tk.Canvas(frame, background=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(frame, orient='vertical', command=mat_canvas.yview)
        mat_canvas.configure(yscrollcommand=vscroll.set)
        mat_canvas.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')

        # Prepare data (same logic as dashboard)
        today = datetime.now().date()
        date_list = [(today + timedelta(days=i)) for i in range(0, 30)]

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, room_number, status FROM rooms ORDER BY room_number")
        rooms = cursor.fetchall()

        start_range = datetime.combine(date_list[0], datetime.min.time()).strftime('%Y-%m-%d %H:%M')
        end_range = (datetime.combine(date_list[-1], datetime.min.time()) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
        cursor.execute(
            "SELECT room_id, status, check_in, check_out FROM bookings WHERE DATE(check_out) >= ? AND DATE(check_in) <= ?",
            (start_range, end_range)
        )
        raw = cursor.fetchall()
        from collections import defaultdict
        bookings_by_room = defaultdict(list)
        for row in raw:
            room_id_b, b_status, b_ci, b_co = row
            try:
                ci_dt = datetime.strptime(str(b_ci)[:16], '%Y-%m-%d %H:%M') if b_ci else None
            except Exception:
                try:
                    ci_dt = datetime.strptime(str(b_ci)[:10], '%Y-%m-%d') if b_ci else None
                except Exception:
                    ci_dt = None
            try:
                co_dt = datetime.strptime(str(b_co)[:16], '%Y-%m-%d %H:%M') if b_co else None
            except Exception:
                try:
                    co_dt = datetime.strptime(str(b_co)[:10], '%Y-%m-%d') if b_co else None
                except Exception:
                    co_dt = None
            bookings_by_room[room_id_b].append({'status': b_status, 'check_in': ci_dt, 'check_out': co_dt})

        status_color = {
            'Available': "#b8f0b8",
            'Occupied': "#eb9797",
            'Reserved': "#f0dda5",
            'Maintenance': "#e4dcdc"
        }

        # sizing: prefer larger readable cells by using the actual toplevel width
        pad = 4
        left_margin = 110
        cols = len(date_list)
        rows_count = len(rooms)
        # Ensure geometry is realized so we can measure the toplevel canvas area
        mt.update_idletasks()
        mat_canvas.update_idletasks()
        # Prefer to use the toplevel's width (after maximizing) for cell sizing
        try:
            avail_w = mt.winfo_width() or mat_canvas.winfo_width() or mat_canvas.winfo_reqwidth() or desired_w
        except Exception:
            avail_w = mat_canvas.winfo_width() or mat_canvas.winfo_reqwidth() or desired_w

        usable_w = max(400, avail_w - left_margin - 120)
        # Compute cell width so 30 columns fit within usable_w; clamp to a readable range (18..40 px)
        cell_w = max(18, min(40, int(usable_w / max(1, cols))))
        # Make cells a bit taller for readability
        cell_h = max(20, int(cell_w * 0.9))

        header_height = int(cell_h + pad)
        content_width = left_margin + cols * (cell_w + pad) + 60
        content_height = header_height + rows_count * (cell_h + pad) + 80
        mat_canvas.configure(scrollregion=(0,0,content_width,content_height))

        # draw headers (larger, readable)
        header_font = ('Helvetica', 10)
        for col_idx, d in enumerate(date_list):
            x = left_margin + col_idx * (cell_w + pad)
            mat_canvas.create_text(x + cell_w/2, int(header_height*0.1), text=d.strftime('%d'), font=header_font, anchor='n')

        # draw rows
        room_number_by_id = {r[0]: r[1] for r in rooms}
        glyph_font = ('Helvetica', 10, 'bold')
        for i, room in enumerate(rooms):
            room_id, room_number, room_status = room
            y_top = header_height + 6 + i * (cell_h + pad)
            mat_canvas.create_text(8, y_top + cell_h/2, anchor='w', text=str(room_number), font=('Helvetica',10,'bold'))
            for col_idx, d in enumerate(date_list):
                dt_start = datetime.combine(d, datetime.min.time())
                dt_end = dt_start + timedelta(days=1)
                # compute status
                if room_status == 'Maintenance':
                    st = 'Maintenance'
                else:
                    st = 'Available'
                    for b in bookings_by_room.get(room_id, []):
                        b_ci = b.get('check_in')
                        b_co = b.get('check_out')
                        if not b_ci or not b_co:
                            continue
                        if b.get('status') == 'Checked-In' and (b_ci <= dt_end and b_co >= dt_start):
                            st = 'Occupied'
                            break
                    else:
                        for b in bookings_by_room.get(room_id, []):
                            b_ci = b.get('check_in')
                            b_co = b.get('check_out')
                            if not b_ci or not b_co:
                                continue
                            if b.get('status') == 'Reserved' and (b_ci <= dt_end and b_co >= dt_start):
                                st = 'Reserved'
                                break

                color = status_color.get(st, '#ffffff')
                x = left_margin + col_idx * (cell_w + pad)
                rect = mat_canvas.create_rectangle(x, y_top, x + cell_w, y_top + cell_h, fill=color, outline='#cccccc')
                tag = f"cell_{room_id}_{d.strftime('%Y%m%d')}"
                mat_canvas.addtag_withtag(tag, rect)
                glyph = 'A' if st == 'Available' else ('O' if st == 'Occupied' else ('R' if st == 'Reserved' else 'M'))
                mat_canvas.create_text(x + cell_w/2, y_top + cell_h/2, text=glyph, font=glyph_font, tags=(tag,))

        # click handler
        def _on_click(ev, canvas_widget=mat_canvas):
            try:
                x = canvas_widget.canvasx(ev.x)
                y = canvas_widget.canvasy(ev.y)
                items = canvas_widget.find_overlapping(x, y, x, y)
                if not items:
                    return
                item = items[-1]
                tags = canvas_widget.gettags(item)
                cell_tag = next((t for t in tags if t.startswith('cell_')), None)
                if not cell_tag:
                    return
                parts = cell_tag.split('_')
                if len(parts) < 3:
                    return
                rid = int(parts[1])
                date_s = parts[2]
                dt = datetime.strptime(date_s, '%Y%m%d').date()
                try:
                    # Update the toplevel status label to include computed room status (matches embedded matrix behavior)
                    try:
                        status_val = self._get_room_status_for_room_on_date(rid, dt)
                    except Exception:
                        status_val = None
                    if status_val:
                        status_lbl.config(text=f"Room {room_number_by_id.get(rid,'?')} — {dt.strftime('%d/%m/%Y')} — {status_val}")
                    else:
                        status_lbl.config(text=f"Room {room_number_by_id.get(rid,'?')} — {dt.strftime('%d/%m/%Y')}")
                except Exception:
                    pass
                self._show_bookings_for_room_on_date(rid, dt)
            except Exception:
                pass

        mat_canvas.bind('<Button-1>', _on_click)

        # When the user closes the toplevel, clear reference
        def _on_close():
            try:
                # cancel any scheduled auto-hide
                try:
                    if hasattr(self, '_matrix_hide_after_id') and self._matrix_hide_after_id:
                        self.after_cancel(self._matrix_hide_after_id)
                except Exception:
                    pass
                try:
                    mt.destroy()
                except Exception:
                    pass
                self._matrix_toplevel = None
                try:
                    if hasattr(self, '_matrix_toggle_text'):
                        self._matrix_toggle_text.set("Show 30 Day Booking Status")
                except Exception:
                    pass
            except Exception:
                pass

    def _dashboard_auto_refresh(self, interval_ms=60000):
        """Auto-refresh the dashboard on a schedule. Cancels any pending refresh and reschedules."""
        try:
            # Cancel previous scheduled call if exists
            if hasattr(self, '_dashboard_after_id') and self._dashboard_after_id:
                try:
                    self.after_cancel(self._dashboard_after_id)
                except Exception:
                    pass
        except Exception:
            pass

        # Refresh only when the Dashboard tab is currently visible to avoid blinking
        try:
            should_refresh = True
            try:
                if hasattr(self, 'notebook'):
                    current = self.notebook.tab(self.notebook.select(), 'text')
                    if str(current).lower() != 'dashboard':
                        should_refresh = False
            except Exception:
                # If any issue determining tab, fall back to refreshing
                should_refresh = True

            if should_refresh:
                try:
                    self.refresh_dashboard()
                except Exception:
                    pass
        except Exception:
            pass

        # Schedule next refresh
        try:
            self._dashboard_after_id = self.after(interval_ms, lambda: self._dashboard_auto_refresh(interval_ms))
        except Exception:
            self._dashboard_after_id = None

    def setup_finance_tab(self):
        """Create a dedicated Finance tab with chart, breakdowns and export options."""
        for w in self.finance_tab.winfo_children():
            w.destroy()

        # Create a scrollable canvas for the finance tab to allow smooth scrolling
        finance_canvas = tk.Canvas(self.finance_tab, bg=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        finance_scrollbar = ttk.Scrollbar(self.finance_tab, orient="vertical", command=finance_canvas.yview)
        frame = ttk.Frame(finance_canvas, padding=12)

        frame.bind("<Configure>", lambda e: finance_canvas.configure(scrollregion=finance_canvas.bbox("all")))
        finance_canvas.create_window((0, 0), window=frame, anchor="nw")
        finance_canvas.configure(yscrollcommand=finance_scrollbar.set)

        finance_canvas.pack(side="left", fill='both', expand=True)
        finance_scrollbar.pack(side="right", fill='y')

        # Enable smooth scrolling (mouse + keyboard)
        try:
            self._make_scrollable(finance_canvas)
        except Exception:
            pass

        header = ttk.Frame(frame)
        header.pack(fill='x')
        ttk.Label(header, text="Finance Dashboard", font=('Helvetica', 16, 'bold')).pack(side='left')
        ttk.Label(header, text=f"Showing latest 10 days (summary: 180d)", font=('Helvetica', 10)).pack(side='right')

        # Small list: Last 10 days (oldest -> newest)
        last10_frame = ttk.Labelframe(frame, text="Last 10 Days (oldest -> newest)", padding=6)
        last10_frame.pack(fill='x', pady=(6,6))
        last10_cols = ('Date', 'Room', 'Restaurant', 'Tax', 'Expense', 'Net')
        self.last10_tree = ttk.Treeview(last10_frame, columns=last10_cols, show='headings', height=5)
        for c in last10_cols:
            self.last10_tree.heading(c, text=c)
            if c == 'Date':
                self.last10_tree.column(c, width=100, anchor='center')
            else:
                self.last10_tree.column(c, width=90, anchor='e')
        self.last10_tree.pack(fill='x')

        # Today summary (shows today's breakdown)
        today_frame = ttk.Frame(frame)
        today_frame.pack(fill='x', pady=(8,6))
        ttk.Label(today_frame, text="Today - Room:", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.today_room_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_room_label.grid(row=0, column=1, sticky='w', padx=6)
        ttk.Label(today_frame, text="Today - Restaurant:", font=('Helvetica', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.today_rest_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_rest_label.grid(row=0, column=3, sticky='w', padx=6)
        ttk.Label(today_frame, text="Today - Tax:", font=('Helvetica', 10, 'bold')).grid(row=0, column=4, sticky='w', padx=(20,0))
        self.today_tax_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_tax_label.grid(row=0, column=5, sticky='w', padx=6)
        ttk.Label(today_frame, text="Today - Expenses:", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=(6,0))
        self.today_exp_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_exp_label.grid(row=1, column=1, sticky='w', padx=6, pady=(6,0))
        ttk.Label(today_frame, text="Today - Net:", font=('Helvetica', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=(20,0), pady=(6,0))
        self.today_net_label = ttk.Label(today_frame, text="₹0.00", font=('Helvetica', 10))
        self.today_net_label.grid(row=1, column=3, sticky='w', padx=6, pady=(6,0))

        # Top: 180-day summary boxes
        summary_frame = ttk.Frame(frame)
        summary_frame.pack(fill='x', pady=(8,10))
        ttk.Label(summary_frame, text="Room Income (180d):", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.summary_room_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_room_label.grid(row=0, column=1, sticky='w', padx=8)

        ttk.Label(summary_frame, text="Restaurant Income (180d):", font=('Helvetica', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.summary_rest_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_rest_label.grid(row=0, column=3, sticky='w', padx=8)

        ttk.Label(summary_frame, text="Tax Collected (180d):", font=('Helvetica', 10, 'bold')).grid(row=0, column=4, sticky='w', padx=(20,0))
        self.summary_tax_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_tax_label.grid(row=0, column=5, sticky='w', padx=8)

        ttk.Label(summary_frame, text="Expenses (180d):", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=(6,0))
        self.summary_exp_label = ttk.Label(summary_frame, text="₹0.00", font=('Helvetica', 10))
        self.summary_exp_label.grid(row=1, column=1, sticky='w', padx=8, pady=(6,0))

        # Chart area
        chart_frame = ttk.Labelframe(frame, text="Net Trend (last 30 days)", padding=10)
        chart_frame.pack(fill='x')
        self.finance_chart_canvas = tk.Canvas(chart_frame, height=160, background=COLOR_LIGHT_BG, highlightthickness=0)
        self.finance_chart_canvas.pack(fill='x')

        # Expense entry form (daily expense) - date, name, amount, optional note
        expense_entry_frame = ttk.Labelframe(frame, text="Add Daily Expense", padding=8)
        expense_entry_frame.pack(fill='x', pady=(8,6))
        ttk.Label(expense_entry_frame, text="Date:").grid(row=0, column=0, sticky='w')
        self.finance_expense_date = ttk.Entry(expense_entry_frame, width=12)
        self.finance_expense_date.grid(row=0, column=1, sticky='w', padx=4)
        # Show user-facing date as MM/DD/YYYY but keep DB storage in ISO when saving
        self.finance_expense_date.insert(0, datetime.now().strftime('%m/%d/%Y'))
        ttk.Label(expense_entry_frame, text="Name:").grid(row=0, column=2, sticky='w', padx=(8,0))
        self.finance_expense_name = ttk.Entry(expense_entry_frame, width=20)
        self.finance_expense_name.grid(row=0, column=3, sticky='w', padx=4)
        ttk.Label(expense_entry_frame, text="Amount:").grid(row=1, column=0, sticky='w', pady=(6,0))
        self.finance_expense_amount = ttk.Entry(expense_entry_frame, width=12)
        self.finance_expense_amount.grid(row=1, column=1, sticky='w', padx=4, pady=(6,0))
        ttk.Label(expense_entry_frame, text="Note (optional):").grid(row=1, column=2, sticky='w', padx=(8,0), pady=(6,0))
        self.finance_expense_note = ttk.Entry(expense_entry_frame, width=30)
        self.finance_expense_note.grid(row=1, column=3, sticky='w', padx=4, pady=(6,0))
        ttk.Button(expense_entry_frame, text="Add Expense", command=self._on_add_expense_in_finance, style="Success.TButton").grid(row=0, column=4, rowspan=2, padx=(12,0))

        # Exports row (PDF exports only). The detailed 180-day table is intentionally omitted from
        # the dashboard view to keep the Finance tab compact per user preference.
        export_row = ttk.Frame(frame)
        export_row.pack(fill='x', pady=(8,0))
        # PDF exports only: Today, Latest 10 Days, 180 Days
        ttk.Button(export_row, text="Export Today (PDF)", command=lambda: self.export_combined_pdf(days=1)).pack(side='left', padx=6)
        ttk.Button(export_row, text="Export Latest 10 Days (PDF)", command=lambda: self.export_combined_pdf(days=10)).pack(side='left', padx=6)
        ttk.Button(export_row, text="Export 180 Days (PDF)", command=lambda: self.export_combined_pdf(days=180)).pack(side='left', padx=6)

        # Populate summary and detail tree
        try:
            rows = self.get_finance_rows(180)
            # Today's breakdown
            today_str = datetime.now().strftime('%Y-%m-%d')
            today_room = self.calculate_room_income(today_str)
            today_rest = self.calculate_restaurant_income(today_str)
            today_tax = self.calculate_tax_collected(today_str)
            today_exp = self.get_daily_expense_total(today_str)
            today_income_total = today_room + today_rest + today_tax
            today_net = today_income_total - float(today_exp)
            try:
                self.today_room_label.config(text=f"₹{today_room:.2f}")
                self.today_rest_label.config(text=f"₹{today_rest:.2f}")
                self.today_tax_label.config(text=f"₹{today_tax:.2f}")
                self.today_exp_label.config(text=f"₹{today_exp:.2f}")
                self.today_net_label.config(text=f"₹{today_net:.2f}")
            except Exception:
                pass
            total_room = sum(r[1] for r in rows)
            total_rest = sum(r[2] for r in rows)
            total_tax = sum(r[3] for r in rows)
            total_exp = sum(r[4] for r in rows)
            self.summary_room_label.config(text=f"₹{total_room:.2f}")
            self.summary_rest_label.config(text=f"₹{total_rest:.2f}")
            self.summary_tax_label.config(text=f"₹{total_tax:.2f}")
            self.summary_exp_label.config(text=f"₹{total_exp:.2f}")

            # Populate last-10 days compact list (oldest -> newest)
            try:
                for iid in self.last10_tree.get_children():
                    self.last10_tree.delete(iid)
                last10 = self.get_finance_rows(10)
                # Show newest -> oldest as requested
                for d, room_i, rest_i, tax_i, exp, net in reversed(last10):
                    self.last10_tree.insert('', 'end', values=(d, f"₹{room_i:.2f}", f"₹{rest_i:.2f}", f"₹{tax_i:.2f}", f"₹{exp:.2f}", f"₹{net:.2f}"))
            except Exception:
                pass

            # (Note) The detailed 180-day tree is not shown here to keep the dashboard compact.
            # The same detailed data is still available via the Export 180 Days (PDF) button.

            # draw a small 30-day sparkline into finance_chart_canvas (use net values)
            spark_rows = self.get_finance_rows(30)
            vals = [r[-1] for r in spark_rows]
            # reuse draw logic from draw_finance_sparkline but draw larger
            try:
                w = self.finance_chart_canvas.winfo_width() or self.finance_chart_canvas.winfo_reqwidth()
                h = self.finance_chart_canvas.winfo_height() or 160
                pad = 10
                self.finance_chart_canvas.delete('all')
                if vals:
                    maxv = max(vals)
                    minv = min(vals)
                    rng = maxv - minv if maxv != minv else 1.0
                    points = []
                    for i, v in enumerate(vals):
                        x = pad + i * ((w - 2*pad) / max(1, len(vals)-1))
                        y = pad + (1 - (v - minv) / rng) * (h - 2*pad)
                        points.append((x, y))
                    coords = []
                    for x,y in points:
                        coords.extend([x,y])
                    poly = [pad, h-pad] + coords + [w-pad, h-pad]
                    self.finance_chart_canvas.create_polygon(poly, fill=COLOR_PRIMARY_LIGHT, outline='')
                    for i in range(len(points)-1):
                        x1,y1 = points[i]
                        x2,y2 = points[i+1]
                        self.finance_chart_canvas.create_line(x1,y1,x2,y2, fill=COLOR_PRIMARY, width=2)
                    for x,y in points:
                        self.finance_chart_canvas.create_oval(x-3, y-3, x+3, y+3, fill=COLOR_PRIMARY, outline='')
            except Exception:
                pass
        except Exception as e:
            print(f"Error populating finance tab: {e}")

    # --- FINANCE: Daily income/expense helpers ---
    def calculate_daily_income(self, date_str):
        """Calculate total income for a given date (YYYY-MM-DD) and store in daily_income.

        Strategy: sum bookings.total_amount for bookings with actual_check_out or check_out matching date
        (use substr to extract date part). Falls back to 0.0 if no records.
        """
        cursor = self.db_conn.cursor()

        # Fetch bookings checked-out on this date
        cursor.execute("""
            SELECT b.id, b.total_amount, b.num_adults, b.num_children, b.room_id, b.check_in, b.check_out, b.actual_check_in, b.actual_check_out
            FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))

        rows = cursor.fetchall()
        computed_total = 0.0

        # Load tax settings once
        cursor.execute("SELECT enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate FROM settings WHERE id=1")
        tax_settings_row = cursor.fetchone() or ('false','false',0.0,0.0,0.0)
        enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate = tax_settings_row

        for (booking_id, total_amount, num_adults, num_children, room_id, check_in_s, check_out_s, actual_in_s, actual_out_s) in rows:
            if total_amount and float(total_amount) > 0.0:
                computed_total += float(total_amount)
                continue

            # Need to reconstruct the booking total from components
            # Determine dates
            try:
                ci_str = actual_in_s.split(' ')[0] if actual_in_s else check_in_s
                co_str = actual_out_s.split(' ')[0] if actual_out_s else check_out_s
                ci = datetime.strptime(ci_str, '%Y-%m-%d')
                co = datetime.strptime(co_str, '%Y-%m-%d')
                nights = (co - ci).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1

            # Room rate
            cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
            room_rate = cursor.fetchone()
            room_rate = float(room_rate[0]) if room_rate and room_rate[0] is not None else 0.0
            room_total = nights * room_rate

            # Restaurant total for this booking
            cursor.execute("SELECT SUM(COALESCE(price_at_order,0.0) * COALESCE(quantity,0)) FROM restaurant_orders WHERE booking_id=?", (booking_id,))
            rest_total = cursor.fetchone()[0] or 0.0

            # Local government charge
            try:
                total_persons = int(num_adults or 0) + int(num_children or 0)
            except Exception:
                total_persons = 1
            local_info = self.calculate_local_charge(nights, total_persons)
            local_amt = local_info.get('amount', 0.0)

            # Total components (room + restaurant + local charges)
            booking_components_total = room_total + float(rest_total) + float(local_amt)

            # Tax should be applied only on room + local charges (exclude restaurant totals from GST)
            taxable_amount = room_total + float(local_amt)

            tax_amt = 0.0
            try:
                if enable_igst == 'true':
                    tax_amt = taxable_amount * float(igst_rate or 0.0) / 100.0
                elif enable_cgst_sgst == 'true':
                    tax_amt = taxable_amount * ((float(cgst_rate or 0.0) + float(sgst_rate or 0.0)) / 100.0)
            except Exception:
                tax_amt = 0.0

            booking_total_est = booking_components_total + tax_amt
            computed_total += float(booking_total_est)

        # Save computed total
        cursor.execute("INSERT OR REPLACE INTO daily_income (date, total, last_updated) VALUES (?,?,?)",
                       (date_str, float(computed_total), datetime.now().isoformat()))
        self.db_conn.commit()

        # Keep only last 180 days of daily_income
        try:
            cursor.execute("DELETE FROM daily_income WHERE date < date('now','-180 day')")
            self.db_conn.commit()
        except Exception:
            pass

        return float(computed_total)

    # --- Finance breakdown helpers ---
    def calculate_room_income(self, date_str):
        """Calculate room income (excluding restaurant/local charges) for the date."""
        cursor = self.db_conn.cursor()
        total = 0.0
        cursor.execute("""
            SELECT b.id, b.total_amount, b.num_adults, b.num_children, b.room_id, b.check_in, b.check_out, b.actual_check_in, b.actual_check_out
            FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))
        rows = cursor.fetchall()
        for (booking_id, total_amount, num_adults, num_children, room_id, check_in_s, check_out_s, actual_in_s, actual_out_s) in rows:
            # If total_amount present, we cannot split; estimate room portion as nights*rate
            try:
                ci_str = actual_in_s.split(' ')[0] if actual_in_s else check_in_s
                co_str = actual_out_s.split(' ')[0] if actual_out_s else check_out_s
                ci = datetime.strptime(ci_str, '%Y-%m-%d')
                co = datetime.strptime(co_str, '%Y-%m-%d')
                nights = (co - ci).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1
            cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
            room_rate = cursor.fetchone()
            room_rate = float(room_rate[0]) if room_rate and room_rate[0] is not None else 0.0
            room_total = nights * room_rate
            total += room_total
        return float(total)

    def format_datetime_for_display(self, dt_str):
        """Convert DB datetime strings (ISO-like) into display format DD/MM/YYYY or DD/MM/YYYY HH:MM.

        Accepts:
        - 'YYYY-MM-DD HH:MM:SS'
        - 'YYYY-MM-DD HH:MM'
        - 'YYYY-MM-DD'
        Returns a string in 'DD/MM/YYYY HH:MM' if time present otherwise 'DD/MM/YYYY'.
        """
        if not dt_str:
            return ''
        dt_str = str(dt_str)
        # Try common ISO-like and alternate formats. Prefer showing DD/MM/YYYY
        # If a time component exists, show in 12-hour format with AM/PM (e.g. 02:15 PM).
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y %I:%M %p', '%d/%m/%Y'):
            try:
                dt = datetime.strptime(dt_str, fmt)
                # If time present in parsed format, show date+time in 12-hour format with AM/PM
                if ('%H' in fmt) or ('%I' in fmt) or (' ' in dt_str and (':' in dt_str)):
                    # Use %I for 12-hour hour (leading zero) and %p for AM/PM
                    return dt.strftime('%d/%m/%Y %I:%M %p')
                else:
                    return dt.strftime('%d/%m/%Y')
            except Exception:
                continue
        # If all parsing fails, return original string
        return dt_str

    def _parse_display_date_to_iso(self, display_str):
        """Parse a user-facing date/time string (DD/MM/YYYY or DD/MM/YYYY HH:MM AM/PM)
        and return an ISO-like string suitable for DB storage (YYYY-MM-DD or YYYY-MM-DD HH:MM).

        If parsing fails, return the original string (caller should handle validation).
        """
        if not display_str:
            return ''
        s = str(display_str).strip()

        # Try a list of common user-facing formats and normalize to ISO (YYYY-MM-DD or YYYY-MM-DD HH:MM).
        # Order: explicit day-first formats, month-first variants (MM/DD/YYYY), then ISO-like inputs.
        fmts = [
            '%d/%m/%Y %I:%M %p',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%m/%d/%Y %I:%M %p',
            '%m/%d/%Y %H:%M',
            '%m/%d/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
        ]

        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                # If parsed format includes time, return YYYY-MM-DD HH:MM else date-only
                if '%H' in fmt or '%I' in fmt:
                    return dt.strftime('%Y-%m-%d %H:%M')
                return dt.strftime('%Y-%m-%d')
            except Exception:
                continue

        # As a last-ditch, if string already looks like YYYY-MM-DD, normalize
        try:
            dt = datetime.strptime(s, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

        # If all parsing attempts fail, return original string; caller should validate.
        return s

    def _get_room_status_counts_for_date(self, date_obj):
        """Return counts of room statuses for the given date (date_obj is a datetime.date).

        Logic (approximate):
        - maintenance_count: rooms with status 'Maintenance' (static)
        - occupied: rooms with a booking that overlaps the date and status in ('Checked-In','Reserved')
        - reserved: rooms with booking status 'Reserved' that overlap the date
        - available = total_rooms - occupied - maintenance
        """
        cursor = self.db_conn.cursor()
        # Use full-day bounds as strings matching DB storage format
        date_start = datetime.combine(date_obj, datetime.min.time()).strftime('%Y-%m-%d %H:%M')
        date_end = (datetime.combine(date_obj, datetime.min.time()) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')

        # maintenance count (rooms statically marked as Maintenance)
        cursor.execute("SELECT COUNT(*) FROM rooms WHERE status='Maintenance'")
        maintenance = cursor.fetchone()[0] or 0

        # occupied: rooms with a booking that overlaps the date and are Checked-In
        cursor.execute(
            "SELECT COUNT(DISTINCT r.id) FROM rooms r "
            "JOIN bookings b ON b.room_id = r.id "
            "WHERE b.status = 'Checked-In' AND b.check_in < ? AND b.check_out > ?",
            (date_end, date_start)
        )
        occupied = cursor.fetchone()[0] or 0

        # reserved: rooms with booking status 'Reserved' overlapping the date
        cursor.execute(
            "SELECT COUNT(DISTINCT r.id) FROM rooms r "
            "JOIN bookings b ON b.room_id = r.id "
            "WHERE b.status = 'Reserved' AND b.check_in < ? AND b.check_out > ?",
            (date_end, date_start)
        )
        reserved = cursor.fetchone()[0] or 0

        # total rooms
        cursor.execute("SELECT COUNT(*) FROM rooms")
        total_rooms = cursor.fetchone()[0] or 0

        available = max(0, total_rooms - occupied - maintenance)

        return {
            'available': available,
            'occupied': occupied,
            'reserved': reserved,
            'maintenance': maintenance,
            'total': total_rooms
        }

    def _get_room_status_for_room_on_date(self, room_id, date_obj):
        """Return status string for a specific room on a given date: 'Maintenance','Occupied','Reserved','Available'."""
        cursor = self.db_conn.cursor()
        # If the room itself is marked maintenance or occupied in rooms table, treat accordingly
        cursor.execute("SELECT status FROM rooms WHERE id=?", (room_id,))
        r = cursor.fetchone()
        if r:
            if r[0] == 'Maintenance':
                return 'Maintenance'
            if r[0] == 'Occupied':
                return 'Occupied'

        date_start = datetime.combine(date_obj, datetime.min.time()).strftime('%Y-%m-%d %H:%M')
        date_end = (datetime.combine(date_obj, datetime.min.time()) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')

        # Check for Checked-In overlapping (occupied takes precedence over reserved)
        cursor.execute("SELECT 1 FROM bookings WHERE room_id=? AND status='Checked-In' AND check_in < ? AND check_out > ? LIMIT 1", (room_id, date_end, date_start))
        if cursor.fetchone():
            return 'Occupied'

        # Check for Reserved overlapping
        cursor.execute("SELECT 1 FROM bookings WHERE room_id=? AND status='Reserved' AND check_in < ? AND check_out > ? LIMIT 1", (room_id, date_end, date_start))
        if cursor.fetchone():
            return 'Reserved'

        return 'Available'

    def _show_bookings_for_room_on_date(self, room_id, date_obj):
        """Opens a small dialog listing bookings for the given room on that date."""
        try:
            date_start = datetime.combine(date_obj, datetime.min.time()).strftime('%Y-%m-%d %H:%M')
            date_end = (datetime.combine(date_obj, datetime.min.time()) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
            cursor = self.db_conn.cursor()
            cursor.execute("""
                SELECT booking_ref, status, check_in, check_out FROM bookings
                WHERE room_id=? AND check_in < ? AND check_out > ?
                ORDER BY check_in
            """, (room_id, date_end, date_start))
            rows = cursor.fetchall()

            info = []
            for r in rows:
                ref, status, ci, co = r
                ci_disp = self.format_datetime_for_display(ci)
                co_disp = self.format_datetime_for_display(co)
                info.append(f"{ref} | {status} | {ci_disp} -> {co_disp}")

            dlg = tk.Toplevel(self)
            dlg.transient(self)
            dlg.grab_set()
            dlg.title(f"Bookings for Room {room_id} on {date_obj.strftime('%m/%d/%Y')}")
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill='both', expand=True)
            if not info:
                ttk.Label(frm, text="No bookings for this room on selected date.").pack()
            else:
                for line in info:
                    ttk.Label(frm, text=line).pack(anchor='w')
            ttk.Button(frm, text="Close", command=dlg.destroy).pack(pady=8)
        except Exception as e:
            messagebox.showerror("Error", f"Could not retrieve bookings: {e}")

    def calculate_restaurant_income(self, date_str):
        """Calculate restaurant income associated with bookings checked out on date."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT b.id FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))
        booking_ids = [r[0] for r in cursor.fetchall()]
        if not booking_ids:
            return 0.0
        placeholders = ','.join(['?']*len(booking_ids))
        query = f"SELECT SUM(COALESCE(price_at_order,0.0) * COALESCE(quantity,0)) FROM restaurant_orders WHERE booking_id IN ({placeholders})"
        cursor.execute(query, booking_ids)
        return float(cursor.fetchone()[0] or 0.0)

    def calculate_tax_collected(self, date_str):
        """Estimate tax collected for bookings checked out on date.

        Strategy: reconstruct subtotal (room + restaurant + local charge) per booking and apply configured tax rates.
        This is an estimate when original tax breakup isn't stored.
        """
        cursor = self.db_conn.cursor()
        total_tax = 0.0

        cursor.execute("SELECT enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate FROM settings WHERE id=1")
        tax_settings_row = cursor.fetchone() or ('false','false',0.0,0.0,0.0)
        enable_cgst_sgst, enable_igst, cgst_rate, sgst_rate, igst_rate = tax_settings_row

        cursor.execute("""
            SELECT b.id, b.total_amount, b.num_adults, b.num_children, b.room_id, b.check_in, b.check_out, b.actual_check_in, b.actual_check_out
            FROM bookings b
            WHERE (substr(b.actual_check_out,1,10)=? OR substr(b.check_out,1,10)=?) AND b.status='Checked-Out'
        """, (date_str, date_str))
        rows = cursor.fetchall()

        for (booking_id, total_amount, num_adults, num_children, room_id, check_in_s, check_out_s, actual_in_s, actual_out_s) in rows:
            # Determine nights
            try:
                ci_str = actual_in_s.split(' ')[0] if actual_in_s else check_in_s
                co_str = actual_out_s.split(' ')[0] if actual_out_s else check_out_s
                ci = datetime.strptime(ci_str, '%Y-%m-%d')
                co = datetime.strptime(co_str, '%Y-%m-%d')
                nights = (co - ci).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1

            # Room rate
            cursor.execute("SELECT rate FROM rooms WHERE id=?", (room_id,))
            room_rate = cursor.fetchone()
            room_rate = float(room_rate[0]) if room_rate and room_rate[0] is not None else 0.0
            room_total = nights * room_rate

            # Restaurant total for this booking
            cursor.execute("SELECT SUM(COALESCE(price_at_order,0.0) * COALESCE(quantity,0)) FROM restaurant_orders WHERE booking_id=?", (booking_id,))
            rest_total = cursor.fetchone()[0] or 0.0

            # Local government charge
            try:
                total_persons = int(num_adults or 0) + int(num_children or 0)
            except Exception:
                total_persons = 1
            local_info = self.calculate_local_charge(nights, total_persons)
            local_amt = local_info.get('amount', 0.0)

            # Apply tax only on room + local charges (exclude restaurant totals)
            taxable_amount = room_total + float(local_amt)

            tax_amt = 0.0
            try:
                if enable_igst == 'true':
                    tax_amt = taxable_amount * float(igst_rate or 0.0) / 100.0
                elif enable_cgst_sgst == 'true':
                    tax_amt = taxable_amount * ((float(cgst_rate or 0.0) + float(sgst_rate or 0.0)) / 100.0)
            except Exception:
                tax_amt = 0.0

            total_tax += float(tax_amt)

        return float(total_tax)

    def get_finance_rows(self, n=180):
        """Return list of (date, room_income, restaurant_income, tax_collected, expense, net) for last n days."""
        results = []
        for i in range(n-1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            room_inc = self.calculate_room_income(d)
            rest_inc = self.calculate_restaurant_income(d)
            tax_col = self.calculate_tax_collected(d)
            expense = self.get_daily_expense_total(d)
            income_total = room_inc + rest_inc + tax_col
            net = income_total - float(expense)
            results.append((d, float(room_inc), float(rest_inc), float(tax_col), float(expense), float(net)))
        return results

    def get_daily_expense_total(self, date_str):
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM daily_expenses WHERE date=?", (date_str,))
        return cursor.fetchone()[0] or 0.0

    def add_daily_expense(self, date_str, name, amount, note=''):
        cursor = self.db_conn.cursor()
        cursor.execute("INSERT INTO daily_expenses (date, name, amount, note, created_at) VALUES (?,?,?,?,?)",
                       (date_str, name, float(amount), note, datetime.now().isoformat()))
        self.db_conn.commit()

        # Keep only last 180 days of expenses
        try:
            cursor.execute("DELETE FROM daily_expenses WHERE date < date('now','-180 day')")
            self.db_conn.commit()
        except Exception:
            pass

    def get_last_n_days_finances(self, n=10):
        """Return a list of (date, income, expense, net) for the last n days (including today).
        Ensures daily_income rows exist by calculating income when missing.
        """
        results = []
        for i in range(n-1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # Ensure income calculated and stored
            self.calculate_daily_income(d)
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT total FROM daily_income WHERE date=?", (d,))
            income = cursor.fetchone()[0] or 0.0
            expense = self.get_daily_expense_total(d)
            net = float(income) - float(expense)
            results.append((d, float(income), float(expense), float(net)))
        return results

    def _populate_finance_tree(self):
        try:
            for i in self.finance_tree.get_children():
                self.finance_tree.delete(i)

            rows = self.get_last_n_days_finances(10)
            for d, inc, exp, net in rows:
                self.finance_tree.insert('', 'end', values=(d, f"₹{inc:.2f}", f"₹{exp:.2f}", f"₹{net:.2f}"))
            # Draw sparkline
            try:
                self.draw_finance_sparkline(rows)
            except Exception:
                pass
        except Exception as e:
            print(f"Error populating finance tree: {e}")

    def _on_add_expense(self):
        date_str = self.expense_date_entry.get()
        # Convert user-visible date (DD/MM/YYYY) to ISO for DB storage
        try:
            date_iso = self._parse_display_date_to_iso(date_str)
        except Exception:
            date_iso = date_str
        name = self.expense_name_entry.get().strip()
        amount = self.expense_amount_entry.get().strip()
        note = self.expense_note_entry.get().strip()

        if not (date_str and name and amount):
            messagebox.showerror("Error", "Please provide date, name and amount for the expense.")
            return

        try:
            amt = float(amount)
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.")
            return

        try:
            self.add_daily_expense(date_iso, name, amt, note)
            # Recalculate income for that day using ISO date
            self.calculate_daily_income(date_iso)
            self._populate_finance_tree()
            messagebox.showinfo("Success", "Expense recorded.")
            # clear fields
            self.expense_name_entry.delete(0, 'end')
            self.expense_amount_entry.delete(0, 'end')
            self.expense_note_entry.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Error", f"Could not save expense: {e}")

    def _on_add_expense_in_finance(self):
        """Handler for Add Expense button in the Finance tab."""
        date_str = self.finance_expense_date.get()
        try:
            date_iso = self._parse_display_date_to_iso(date_str)
        except Exception:
            date_iso = date_str
        name = self.finance_expense_name.get().strip()
        amount = self.finance_expense_amount.get().strip()
        note = self.finance_expense_note.get().strip()

        if not (date_str and name and amount):
            messagebox.showerror("Error", "Please provide date, name and amount for the expense.")
            return

        try:
            amt = float(amount)
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.")
            return

        try:
            self.add_daily_expense(date_iso, name, amt, note)
            # Recalculate income for that day (in case income was missing)
            self.calculate_daily_income(date_iso)
            # Refresh the finance tab contents
            try:
                self.setup_finance_tab()
            except Exception:
                pass
            messagebox.showinfo("Success", "Expense recorded.")
            # clear fields
            self.finance_expense_name.delete(0, 'end')
            self.finance_expense_amount.delete(0, 'end')
            self.finance_expense_note.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Error", f"Could not save expense: {e}")

    # --- Export helpers for CSV/PDF ---
    def export_expenses_csv(self, days=180):
        """Export expenses to CSV for the last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, name, amount, note, created_at FROM daily_expenses WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()

            if not rows:
                messagebox.showinfo("No Data", f"No expense data available for the last {days} days.")
                return

            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'expenses_last_{days}_days.csv')
            except Exception:
                fname = os.path.abspath(f'expenses_last_{days}_days.csv')

            import csv
            with open(fname, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['date', 'name', 'amount', 'note', 'created_at'])
                for r in rows:
                    writer.writerow(r)

            messagebox.showinfo("Exported", f"Expenses exported to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export expenses: {e}")

    def export_income_csv(self, days=180):
        """Export income to CSV for the last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, total, last_updated FROM daily_income WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()

            if not rows:
                messagebox.showinfo("No Data", f"No income data available for the last {days} days.")
                return

            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'income_last_{days}_days.csv')
            except Exception:
                fname = os.path.abspath(f'income_last_{days}_days.csv')

            import csv
            with open(fname, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['date', 'total', 'last_updated'])
                for r in rows:
                    writer.writerow(r)

            messagebox.showinfo("Exported", f"Income exported to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export income: {e}")

    def export_expenses_pdf(self, days=180):
        """Generate a simple PDF listing of expenses for last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, name, amount, note FROM daily_expenses WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()
            if not rows:
                messagebox.showinfo("No Data", f"No expense data available for the last {days} days.")
                return

            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'expenses_last_{days}_days.pdf')
            except Exception:
                fname = os.path.abspath(f'expenses_last_{days}_days.pdf')

            c = canvas.Canvas(fname, pagesize=A4)
            width, height = A4
            x = 40
            y = height - 50
            c.setFont('Helvetica-Bold', 14)
            c.drawString(x, y, f"Expenses - Last {days} Days")
            y -= 25
            c.setFont('Helvetica-Bold', 10)
            c.drawString(x, y, "Date")
            c.drawString(x+100, y, "Name")
            c.drawString(x+300, y, "Amount")
            c.drawString(x+380, y, "Note")
            y -= 15
            c.setFont('Helvetica', 10)
            for r in rows:
                if y < 60:
                    c.showPage()
                    y = height - 50
                date_s, name, amount, note = r
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = str(date_s)
                c.drawString(x, y, ds)
                c.drawString(x+100, y, str(name)[:30])
                c.drawRightString(x+350, y, f"₹{float(amount):.2f}")
                c.drawString(x+380, y, str(note)[:60])
                y -= 15

            c.save()
            messagebox.showinfo("Exported", f"Expenses PDF saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export expenses PDF: {e}")

    def export_income_pdf(self, days=180):
        """Generate a simple PDF listing of income for last `days` days (default 180)."""
        try:
            cursor = self.db_conn.cursor()
            sql = f"SELECT date, total, last_updated FROM daily_income WHERE date >= date('now','-{days} day') ORDER BY date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()
            if not rows:
                messagebox.showinfo("No Data", f"No income data available for the last {days} days.")
                return

            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'income_last_{days}_days.pdf')
            except Exception:
                fname = os.path.abspath(f'income_last_{days}_days.pdf')

            c = canvas.Canvas(fname, pagesize=A4)
            width, height = A4
            x = 40
            y = height - 50
            c.setFont('Helvetica-Bold', 14)
            c.drawString(x, y, f"Income - Last {days} Days")
            y -= 25
            c.setFont('Helvetica-Bold', 10)
            c.drawString(x, y, "Date")
            c.drawString(x+150, y, "Total")
            c.drawString(x+300, y, "Last Updated")
            y -= 15
            c.setFont('Helvetica', 10)
            for r in rows:
                if y < 60:
                    c.showPage()
                    y = height - 50
                date_s, total, updated = r
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = str(date_s)
                c.drawString(x, y, ds)
                c.drawRightString(x+240, y, f"₹{float(total):.2f}")
                c.drawString(x+300, y, str(updated)[:30])
                y -= 15

            c.save()
            messagebox.showinfo("Exported", f"Income PDF saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export income PDF: {e}")

    def export_combined_csv(self, days=180):
        """Export combined income (room+restaurant) and expenses as a CSV for last `days` days."""
        try:
            rows = self.get_finance_rows(days)
            if not rows:
                messagebox.showinfo("No Data", f"No finance data available for the last {days} days.")
                return
            try:
                out_dir = get_user_pdfs_dir('Finance')
                fname = os.path.join(out_dir, f'finance_combined_last_{days}_days.csv')
            except Exception:
                fname = os.path.abspath(f'finance_combined_last_{days}_days.csv')
            import csv
            with open(fname, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['date', 'room_income', 'restaurant_income', 'tax_collected', 'expense', 'net'])
                for r in rows:
                    writer.writerow(r)
            messagebox.showinfo("Exported", f"Combined finance CSV saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export combined CSV: {e}")

    def export_combined_pdf(self, days=180):
        """Export a combined PDF report for income breakdown and expenses for last `days` days."""
        try:
            rows = self.get_finance_rows(days)
            if not rows:
                messagebox.showinfo("No Data", f"No finance data available for the last {days} days.")
                return

            # Auto-save PDFs to the user's Desktop Nexuzy folder under a Finance subfolder
            pdf_dir = get_user_pdfs_dir('Finance')
            os.makedirs(pdf_dir, exist_ok=True)
            fname = os.path.join(pdf_dir, (f'finance_today.pdf' if days==1 else f'finance_combined_last_{days}_days.pdf'))

            c = canvas.Canvas(fname, pagesize=A4)
            width, height = A4
            x = 40
            y = height - 50

            # Special case: Today export (days==1) should include a Today summary and today's expense names & amounts
            if days == 1:
                today_str = datetime.now().strftime('%Y-%m-%d')
                # Calculate today's breakdown
                today_room = self.calculate_room_income(today_str)
                today_rest = self.calculate_restaurant_income(today_str)
                today_tax = self.calculate_tax_collected(today_str)
                today_exp = self.get_daily_expense_total(today_str)
                today_net = (today_room + today_rest + today_tax) - float(today_exp)

                c.setFont('Helvetica-Bold', 14)
                try:
                    today_display = self.format_datetime_for_display(today_str)
                except Exception:
                    today_display = today_str
                c.drawString(x, y, f"Finance Report - Today ({today_display})")
                y -= 22

                c.setFont('Helvetica-Bold', 11)
                c.drawString(x, y, "Summary")
                y -= 16
                c.setFont('Helvetica', 10)
                c.drawString(x, y, f"Room Income:")
                c.drawRightString(x+500, y, f"₹{today_room:.2f}")
                y -= 14
                c.drawString(x, y, f"Restaurant Income:")
                c.drawRightString(x+500, y, f"₹{today_rest:.2f}")
                y -= 14
                c.drawString(x, y, f"Tax Collected (est):")
                c.drawRightString(x+500, y, f"₹{today_tax:.2f}")
                y -= 14
                c.drawString(x, y, f"Expenses (today):")
                c.drawRightString(x+500, y, f"₹{float(today_exp):.2f}")
                y -= 14
                c.setFont('Helvetica-Bold', 11)
                c.drawString(x, y, f"Net Today:")
                c.drawRightString(x+500, y, f"₹{today_net:.2f}")
                y -= 22

                # Expenses listing for today with name, amount and note
                c.setFont('Helvetica-Bold', 12)
                c.drawString(x, y, "Expenses - Today")
                y -= 18
                c.setFont('Helvetica-Bold', 10)
                c.drawString(x, y, "Name")
                c.drawRightString(x+420, y, "Amount")
                c.drawString(x+440, y, "Note")
                y -= 14
                c.setFont('Helvetica', 10)

                cursor = self.db_conn.cursor()
                cursor.execute("SELECT date, name, amount, note FROM daily_expenses WHERE date = ? ORDER BY created_at DESC", (today_str,))
                exp_rows = cursor.fetchall()

                if not exp_rows:
                    c.drawString(x, y, "No expenses recorded for today.")
                    y -= 14
                else:
                    for date_s, name, amount, note in exp_rows:
                        if y < 60:
                            c.showPage()
                            y = height - 50
                        c.drawString(x, y, str(name)[:40])
                        c.drawRightString(x+420, y, f"₹{float(amount):.2f}")
                        c.drawString(x+440, y, str(note)[:60])
                        y -= 14

                # Final Net line
                if y < 80:
                    c.showPage()
                    y = height - 50
                c.setFont('Helvetica-Bold', 11)
                c.drawString(x, y, "Net Today")
                c.drawRightString(x+500, y, f"₹{today_net:.2f}")
                y -= 18

                c.save()
                # Cleanup older PDFs after saving
                try:
                    cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
                except Exception:
                    pass
                messagebox.showinfo("Exported", f"Today's finance PDF saved to {fname}")
                return

            # Default behavior for multi-day exports (unchanged formatting)
            c.setFont('Helvetica-Bold', 14)
            c.drawString(x, y, f"Finance Report - Last {days} Days")
            y -= 25
            c.setFont('Helvetica-Bold', 10)
            c.drawString(x, y, "Date")
            c.drawString(x+100, y, "Room Inc")
            c.drawString(x+180, y, "Rest Inc")
            c.drawString(x+260, y, "Tax")
            c.drawString(x+320, y, "Expense")
            c.drawString(x+400, y, "Net")
            y -= 15
            c.setFont('Helvetica', 9)
            # Show finance rows newest -> oldest in PDF exports (more intuitive)
            for date_s, room_i, rest_i, tax_i, exp, net in reversed(rows):
                if y < 60:
                    c.showPage()
                    y = height - 50
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = date_s
                c.drawString(x, y, ds)
                c.drawRightString(x+170, y, f"₹{room_i:.2f}")
                c.drawRightString(x+250, y, f"₹{rest_i:.2f}")
                c.drawRightString(x+320, y, f"₹{tax_i:.2f}")
                c.drawRightString(x+400, y, f"₹{exp:.2f}")
                c.drawRightString(x+480, y, f"₹{net:.2f}")
                y -= 12
            c.showPage()
            # Append a simple expenses listing
            c.setFont('Helvetica-Bold', 12)
            c.drawString(40, height-50, f"Expenses (Last {days} Days)")
            y = height - 80
            c.setFont('Helvetica-Bold', 10)
            c.drawString(40, y, "Date")
            c.drawString(120, y, "Name")
            c.drawString(340, y, "Note")
            c.drawString(500, y, "Amount")
            y -= 15
            c.setFont('Helvetica', 9)
            cursor = self.db_conn.cursor()
            cursor.execute(f"SELECT date, name, amount, note FROM daily_expenses WHERE date >= date('now','-{days} day') ORDER BY date DESC")
            exp_rows = cursor.fetchall()
            for date_s, name, amount, note in exp_rows:
                if y < 60:
                    c.showPage()
                    y = height - 50
                try:
                    ds = self.format_datetime_for_display(date_s)
                except Exception:
                    ds = str(date_s)
                c.drawString(40, y, ds)
                c.drawString(120, y, str(name)[:30])
                c.drawString(340, y, str(note)[:40])
                c.drawRightString(560, y, f"₹{float(amount):.2f}")
                y -= 12
            c.save()
            # Cleanup older PDFs after saving
            try:
                cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
            except Exception:
                pass
            messagebox.showinfo("Exported", f"Combined finance PDF saved to {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export combined PDF: {e}")
    def draw_finance_sparkline(self, rows):
        """Draw a small sparkline (net values) for the provided rows list of (date, income, expense, net)."""
        try:
            # rows is a list of tuples where the last element is net
            vals = [r[-1] for r in rows]
            if not vals:
                return
            w = self.finance_spark_canvas.winfo_width() or self.finance_spark_canvas.winfo_reqwidth()
            h = self.finance_spark_canvas.winfo_height() or 60
            pad = 6
            self.finance_spark_canvas.delete('all')
            maxv = max(vals)
            minv = min(vals)
            rng = maxv - minv if maxv != minv else 1.0
            points = []
            for i, v in enumerate(vals):
                x = pad + i * ((w - 2*pad) / max(1, len(vals)-1))
                y = pad + (1 - (v - minv) / rng) * (h - 2*pad)
                points.append((x, y))

            # draw filled area
            coords = []
            for x,y in points:
                coords.extend([x,y])
            if coords:
                # polygon from left-bottom to points to right-bottom
                poly = [pad, h-pad] + coords + [w-pad, h-pad]
                self.finance_spark_canvas.create_polygon(poly, fill=COLOR_PRIMARY_LIGHT, outline='')

            # draw line
            for i in range(len(points)-1):
                x1,y1 = points[i]
                x2,y2 = points[i+1]
                self.finance_spark_canvas.create_line(x1,y1,x2,y2, fill=COLOR_PRIMARY, width=2)

            # draw small circles
            for x,y in points:
                self.finance_spark_canvas.create_oval(x-2, y-2, x+2, y+2, fill=COLOR_PRIMARY, outline='')

        except Exception:
            pass

    def setup_bookings_tab(self):
        """Set up the bookings and guests management tab."""
        for widget in self.bookings_tab.winfo_children():
            widget.destroy()

        frame = ttk.Frame(self.bookings_tab, padding=10)
        frame.pack(fill='both', expand=True)

        # Search functionality
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=5)
        ttk.Label(search_frame, text="Search Booking (Ref #, Name, Room #):").pack(side='left', padx=(0, 5))
        self.booking_search_entry = ttk.Entry(search_frame, width=40)
        self.booking_search_entry.pack(side='left', padx=5, ipady=3)
        ttk.Button(search_frame, text="Search", command=self.search_bookings).pack(side='left')
        ttk.Button(search_frame, text="Clear", command=self.load_bookings_data).pack(side='left', padx=5)

        # --- MODIFIED: Treeview columns for Booking/Guest details (Added Adults/Children) ---
        cols = ('Ref #', 'Guest Name', 'Adults', 'Children', 'Phone', 'Room #', 'Check-In', 'Check-Out', 'Status')
        self.bookings_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        for col in cols:
            self.bookings_tree.heading(col, text=col)
            if col in ('Ref #', 'Room #', 'Status', 'Adults', 'Children'):
                 self.bookings_tree.column(col, width=80, anchor='center')
            elif col in ('Check-In', 'Check-Out', 'Phone'):
                 self.bookings_tree.column(col, width=110, anchor='center')
            elif col == 'Guest Name':
                 self.bookings_tree.column(col, width=150)
            else:
                 self.bookings_tree.column(col, width=100)
                 
        # --- END MODIFIED ---


        # Add tags for alternating rows
        self.bookings_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.bookings_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.bookings_tree.pack(fill='both', expand=True, pady=10)
        # Double-click opens detailed booking dialog
        self.bookings_tree.bind('<Double-1>', self.open_booking_detail)

        # Action buttons
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', pady=5)
        ttk.Button(action_frame, text="Cancel Booking", command=self.cancel_booking, style="Danger.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(action_frame, text="Change Dates (Advanced)", command=self.change_booking_dates).pack(side='left', padx=5, ipady=5)
        # --- NEW: Extend Stay Button ---
        ttk.Button(action_frame, text="Extend Stay", command=self.extend_stay).pack(side='left', padx=(15, 5), ipady=5)
        # --- END NEW ---

        # --- NEW: Edit/Delete Booking Buttons (Bookings tab) ---
        self.edit_booking_btn = ttk.Button(action_frame, text="Edit Booking", command=self.edit_booking_from_bookings, style="Accent.TButton", state=tk.DISABLED)
        self.edit_booking_btn.pack(side='left', padx=5, ipady=5)

        self.delete_booking_btn = ttk.Button(action_frame, text="Delete Booking", command=self.delete_booking_from_bookings, style="Danger.TButton", state=tk.DISABLED)
        self.delete_booking_btn.pack(side='left', padx=5, ipady=5)
        # --- END NEW ---

        self.load_bookings_data()
        
        # --- NEW: Frame for selected guest details (Section 2 Fix) ---
        self.selected_guest_frame = ttk.Labelframe(frame, text="Selected Guest Details", padding=10)
        self.selected_guest_frame.pack(fill='x', pady=(10, 5))
        self.selected_guest_label = ttk.Label(self.selected_guest_frame, text="Select a booking above to view primary guest information and documents.", justify=tk.LEFT)
        self.selected_guest_label.pack(fill='x')
        self.bookings_tree.bind('<<TreeviewSelect>>', self.show_booking_guest_details) # BIND NEW METHOD


    def load_bookings_data(self, search_query=None):
        """Load data into the bookings treeview. (MODIFIED: Added guest detail columns)"""
        for i in self.bookings_tree.get_children():
            self.bookings_tree.delete(i)

        cursor = self.db_conn.cursor()
        # --- MODIFIED: Added g.id, g.address, g.id_proof_type, g.id_proof_number for detail display ---
        query = """
            SELECT b.id, b.booking_ref, g.name, b.num_adults, b.num_children, g.phone,
                   r.room_number, b.check_in, b.check_out, b.status,
                   g.id, g.address
            FROM bookings b
            JOIN guests g ON b.guest_id = g.id
            JOIN rooms r ON b.room_id = r.id
        """
        params = []

        if search_query:
            query += " WHERE (b.booking_ref LIKE ? OR g.name LIKE ? OR r.room_number LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])
            
            # Also filter by status (only active bookings)
            query += " AND b.status IN ('Reserved', 'Checked-In')"
        else:
             query += " WHERE b.status IN ('Reserved', 'Checked-In')"


        query += " ORDER BY b.check_in DESC"
        
        rows = cursor.execute(query, params).fetchall()

        # Aggregate rows by booking_ref so group bookings show as a single entry with combined room numbers
        grouped = {}
        ordered_refs = []
        for r in rows:
            # r: [id, booking_ref, guest_name, num_adults, num_children, phone, room_number, check_in, check_out, status, guest_id, address]
            b_id, b_ref, guest_name, num_adults, num_children, phone, room_number, check_in, check_out, status = r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]
            if b_ref not in grouped:
                grouped[b_ref] = {
                    'guest_name': guest_name or '',
                    'adults': int(num_adults or 0),
                    'children': int(num_children or 0),
                    'phone': phone or '',
                    'rooms': [str(room_number)] if room_number is not None else [],
                    'check_ins': [check_in] if check_in else [],
                    'check_outs': [check_out] if check_out else [],
                    'statuses': set([status]) if status else set()
                }
                ordered_refs.append(b_ref)
            else:
                grp = grouped[b_ref]
                grp['adults'] += int(num_adults or 0)
                grp['children'] += int(num_children or 0)
                if room_number is not None:
                    grp['rooms'].append(str(room_number))
                if check_in:
                    grp['check_ins'].append(check_in)
                if check_out:
                    grp['check_outs'].append(check_out)
                if status:
                    grp['statuses'].add(status)

        for i, ref in enumerate(ordered_refs):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            grp = grouped[ref]
            # Decide aggregated values
            guest_name = grp['guest_name']
            adults = grp['adults'] or 0
            children = grp['children'] or 0
            phone = grp['phone']
            rooms = ','.join(sorted(set(grp['rooms']), key=lambda x: int(x) if x.isdigit() else x))
            # pick earliest check-in and latest check-out for display
            try:
                cis = [d for d in grp['check_ins'] if d]
                cis_dt = [datetime.strptime(str(d), '%Y-%m-%d %H:%M') if isinstance(d, str) and len(str(d))>10 and '-' in str(d) and ':' in str(d) else datetime.strptime(str(d), '%Y-%m-%d') if isinstance(d,str) and '-' in str(d) else None for d in cis]
                cis_dt = [d for d in cis_dt if d]
                earliest_ci = min(cis_dt).strftime('%Y-%m-%d %H:%M') if cis_dt else ''
            except Exception:
                earliest_ci = grp['check_ins'][0] if grp['check_ins'] else ''

            try:
                cos = [d for d in grp['check_outs'] if d]
                cos_dt = [datetime.strptime(str(d), '%Y-%m-%d %H:%M') if isinstance(d, str) and len(str(d))>10 and '-' in str(d) and ':' in str(d) else datetime.strptime(str(d), '%Y-%m-%d') if isinstance(d,str) and '-' in str(d) else None for d in cos]
                cos_dt = [d for d in cos_dt if d]
                latest_co = max(cos_dt).strftime('%Y-%m-%d %H:%M') if cos_dt else ''
            except Exception:
                latest_co = grp['check_outs'][-1] if grp['check_outs'] else ''

            # Determine status priority: Checked-In > Reserved > Checked-Out > Cancelled
            statuses = grp['statuses']
            if 'Checked-In' in statuses:
                agg_status = 'Checked-In'
            elif 'Reserved' in statuses:
                agg_status = 'Reserved'
            elif 'Checked-Out' in statuses:
                agg_status = 'Checked-Out'
            elif 'Cancelled' in statuses:
                agg_status = 'Cancelled'
            else:
                agg_status = next(iter(statuses)) if statuses else ''

            display_row = (ref, guest_name, adults, children, phone, rooms, self.format_datetime_for_display(earliest_ci), self.format_datetime_for_display(latest_co), agg_status)
            # Use booking_ref as iid since aggregation ensures one row per ref
            self.bookings_tree.insert('', 'end', values=display_row, iid=str(ref), tags=(tag,))
        # --- END MODIFIED ---
        
    def show_booking_guest_details(self, event):
        """Displays primary guest details for the selected active booking. (Section 2 Fix)"""
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            self.selected_guest_label.config(text="Select a booking above to view primary guest information and documents.")
            return

        booking_ref = self.bookings_tree.item(selected_item)['values'][0]
        
        # Since we only stored the display values in the tree, we need to fetch the full details again.
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT g.name, g.address
            FROM bookings b
            JOIN guests g ON b.guest_id = g.id
            WHERE b.booking_ref = ?
        """, (booking_ref,))
        
        details = cursor.fetchone()
        
        if not details:
            self.selected_guest_label.config(text=f"Primary guest details not found for booking {booking_ref}.")
            return

        guest_name, address = details

        display_text = (
            f"Primary Guest: {guest_name} (Ref: {booking_ref})\n"
            f"Address: {address}"
        )
            
        self.selected_guest_label.config(text=display_text)
        # Enable/disable edit & delete buttons based on role and booking status
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT status FROM bookings WHERE booking_ref=?", (booking_ref,))
            row = cursor.fetchone()
            status = row[0] if row else None
        except Exception:
            status = None

        role = getattr(self, 'user_role', None)
        can_modify = role in ('Admin', 'SuperAdmin')

        if can_modify:
            self.edit_booking_btn.config(state=tk.NORMAL)
        else:
            self.edit_booking_btn.config(state=tk.DISABLED)

        # Delete: SuperAdmin may delete any, Admin only Reserved/Cancelled
        if role == 'SuperAdmin':
            self.delete_booking_btn.config(state=tk.NORMAL)
        elif role == 'Admin' and status in ('Reserved', 'Cancelled'):
            self.delete_booking_btn.config(state=tk.NORMAL)
        else:
            self.delete_booking_btn.config(state=tk.DISABLED)

    def select_booking_rows(self, booking_ref, include_manual_dt=False, include_proceed=False, allowed_statuses=None, include_person_count=False):
        """Open a small modal to let the user select one or more booking rows for a booking_ref.

        Returns: (selected_booking_ids_list, manual_dt_string_or_None)
        manual_dt is returned only if include_manual_dt=True and user provided a value.
        """
        cursor = self.db_conn.cursor()
        # If caller provided allowed_statuses, only include booking rows matching those statuses.
        if allowed_statuses:
            ph = ','.join(['?'] * len(allowed_statuses))
            # Include per-row person counts so selector can show defaults and allow manual override
            sql = f"SELECT b.id, r.room_number, b.check_in, b.check_out, b.status, b.room_id, b.num_adults, b.num_children FROM bookings b JOIN rooms r ON b.room_id=r.id WHERE b.booking_ref=? AND b.status IN ({ph}) ORDER BY r.room_number"
            params = (booking_ref,) + tuple(allowed_statuses)
            cursor.execute(sql, params)
        else:
            cursor.execute("SELECT b.id, r.room_number, b.check_in, b.check_out, b.status, b.room_id, b.num_adults, b.num_children FROM bookings b JOIN rooms r ON b.room_id=r.id WHERE b.booking_ref=? ORDER BY r.room_number", (booking_ref,))
        rows = cursor.fetchall()
        if not rows:
            return None, None

        sel_win = tk.Toplevel(self)
        sel_win.transient(self)
        sel_win.grab_set()
        sel_win.title(f"Select room(s) for {booking_ref}")
        # larger default so controls are visible; allow resizing so staff with many rows can expand
        # Increase default size (user requested +15 mm). Convert ~15 mm -> ~57 pixels
        # and apply to width and height so controls (AM/PM hint) and bottom buttons are visible.
        sel_win.geometry('619x459')
        sel_win.minsize(500, 340)
        try:
            sel_win.resizable(True, True)
        except Exception:
            pass

        frm = ttk.Frame(sel_win, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Select the room rows to apply the action:", font=('Helvetica', 10, 'bold')).pack(pady=(0,6))

        # Put the canvas and its scrollbar inside a top container so the bottom
        # button frame stays anchored and visible on small displays.
        list_container = ttk.Frame(frm)
        list_container.pack(fill='both', expand=True)

        canvas = tk.Canvas(list_container)
        vsb = ttk.Scrollbar(list_container, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0,0), window=inner, anchor='nw')
        # increase canvas height so more rows are visible without scrolling
        canvas.configure(yscrollcommand=vsb.set, height=220)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        var_map = {}
        person_vars = {}  # booking_id -> tk.StringVar/IntVar when include_person_count True
        for r in rows:
            # row schema: id, room_number, check_in, check_out, status, room_id, num_adults, num_children
            rid, room_no, ci, co, st, rmid = r[0], r[1], r[2], r[3], r[4], r[5]
            num_adults_row = int(r[6] or 0) if len(r) > 6 else 0
            num_children_row = int(r[7] or 0) if len(r) > 7 else 0
            default_persons = num_adults_row + num_children_row
            label = f"Room {room_no} — {self.format_datetime_for_display(ci)} → {self.format_datetime_for_display(co)} — {st}"
            v = tk.IntVar(value=1)
            cb = ttk.Checkbutton(inner, text=label, variable=v)
            cb.pack(anchor='w', pady=2)
            var_map[rid] = v
            # If requested (checkout flow), show an input to override number of persons checking out for this row
            if include_person_count:
                try:
                    # Use IntVar so it behaves like a numeric input; default to total persons for that row
                    pv = tk.IntVar(value=default_persons)
                    person_vars[rid] = pv
                    # Place a small spinbox to the right of the checkbox (pack won't align easily), so create a frame
                    subf = ttk.Frame(inner)
                    subf.pack(fill='x', pady=(0,6), padx=(24,0))
                    ttk.Label(subf, text=f"Persons for this room:").pack(side='left')
                    try:
                        sp = tk.Spinbox(subf, from_=0, to=99, width=4, textvariable=pv)
                        sp.pack(side='left', padx=(6,0))
                    except Exception:
                        # Fallback to Entry if Spinbox not available in this environment
                        ent = ttk.Entry(subf, width=4, textvariable=pv)
                        ent.pack(side='left', padx=(6,0))
                except Exception:
                    pass

        manual_dt_var = tk.StringVar()
        if include_manual_dt:
            # Show 12-hour, day-first format with AM/PM so staff can enter human-friendly times
            ttk.Label(frm, text="Optional Manual Date/Time (DD/MM/YYYY hh:mm AM/PM):").pack(pady=(8,0))
            # Make the entry a bit wider so AM/PM is visible, and provide a clear example below
            manual_entry = ttk.Entry(frm, textvariable=manual_dt_var, width=30)
            manual_entry.pack(fill='x', pady=(0,2))
            # Default to current date/time in 12-hour format so staff can accept or edit as needed
            # Provide a small helper/hint to make AM/PM visually clear
            ttk.Label(frm, text="Format: DD/MM/YYYY hh:mm AM/PM (e.g. 01/11/2025 10:30 AM)", font=('Helvetica', 9, 'italic'), foreground='#333333').pack(anchor='w', pady=(0,6))
            # Default to current date/time in 12-hour format so staff can accept or edit as needed
            try:
                manual_entry.insert(0, datetime.now().strftime('%d/%m/%Y %I:%M %p'))
            except Exception:
                # If datetime not available for some reason, leave blank
                pass
            # Allow staff to optionally enter an overall number of persons for the selected rows.
            # This is handy when selecting multiple rows but wanting to supply a single total count
            # (the code will distribute this total across rows when computing local charges).
            try:
                ttk.Label(frm, text="Optional Total Persons for selected rows:").pack(pady=(6,0))
                manual_total_var = tk.IntVar(value=0)
                try:
                    sp_total = tk.Spinbox(frm, from_=0, to=999, width=6, textvariable=manual_total_var)
                    sp_total.pack(anchor='w', pady=(0,6))
                except Exception:
                    ent_total = ttk.Entry(frm, width=6, textvariable=manual_total_var)
                    ent_total.pack(anchor='w', pady=(0,6))
            except Exception:
                manual_total_var = None

        result = {'ids': None, 'manual': None, 'persons': None}

        def _on_ok():
            chosen = [rid for rid, v in var_map.items() if v.get()]
            if not chosen:
                messagebox.showwarning('No selection', 'Select at least one room row.', parent=sel_win)
                return
            result['ids'] = chosen
            if include_manual_dt:
                val = manual_dt_var.get().strip()
                result['manual'] = val if val else None
            if include_person_count:
                # build persons map only for chosen rows
                try:
                    pm = {}
                    for rid in chosen:
                        pv = person_vars.get(rid)
                        if pv is None:
                            continue
                        try:
                            pm[rid] = int(pv.get())
                        except Exception:
                            pm[rid] = 0
                    # If the user entered an overall total, include it as a special key so
                    # callers can distribute it across rows. This keeps backward-compat.
                    try:
                        if 'manual_total_var' in locals() and manual_total_var is not None:
                            t = int(manual_total_var.get() or 0)
                            if t > 0:
                                pm['__total__'] = t
                    except Exception:
                        pass
                    result['persons'] = pm
                except Exception:
                    result['persons'] = None
            sel_win.destroy()

        def _on_cancel():
            sel_win.destroy()

        # ensure the buttons are visible even on small displays
        # Anchor button frame to the bottom so it remains visible on resize/scroll
        btnf = ttk.Frame(frm)
        btnf.pack(side='bottom', fill='x', pady=8)
        inner_btns = ttk.Frame(btnf)
        inner_btns.pack()
        # Always show a clear 'OK' and 'Cancel' so users see expected controls in the selector.
        # For historical reasons some callers passed include_proceed=True to label the action
        # as 'Proceed'; behavior remains the same (it simply triggers the OK handler) but
        # the button will be visible as 'OK' to match the common UI expectation.
        btn_text = 'OK'
        if include_proceed:
            # keep an informative variant if desired, but keep 'OK' visible
            btn_text = 'OK'
        ttk.Button(inner_btns, text=btn_text, command=_on_ok, style='Accent.TButton').pack(side='left', padx=6)
        ttk.Button(inner_btns, text='Cancel', command=_on_cancel).pack(side='left')

        sel_win.wait_window()
        if include_person_count:
            return result.get('ids'), result.get('manual'), result.get('persons')
        return result.get('ids'), result.get('manual')

    def open_booking_detail(self, event):
        """Open a dialog showing aggregated booking and guest details, with actions."""
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            return
        booking_ref = self.bookings_tree.item(selected_item)['values'][0]
        BookingDetailWindow(self, booking_ref)


    def search_bookings(self):
        """Handle search button click."""
        query = self.booking_search_entry.get()
        self.load_bookings_data(query)

    # --- VERSION 1.7 CHANGE: Add booking_type parameter ---
    def open_new_booking_window(self, booking_type="Advance"):
        """Opens a window to add a new booking."""
        NewBookingWindow(self, booking_type)

    # --- VERSION 1.8 CHANGE: New Workflow (MODIFIED: Added Multi-Guest Check) ---
    def check_in_guest(self):
        """Handles the check-in process by opening a selection window."""

        # Open the selection window, passing the status we're looking for
        selector = BookingSelectionWindow(self, status_list=['Reserved'], title="Select Booking to Check-In")
        selected_booking = selector.show()

        if not selected_booking:
            return  # User cancelled

        booking_ref = selected_booking['ref']
        room_id = selected_booking['room_id']
        num_adults = selected_booking['num_adults']
        num_children = selected_booking['num_children']
        
        total_persons = num_adults + num_children

        # NOTE: Removed the prior optional prompt for entering additional guest
        # details when multiple persons are on the booking. Per user request,
        # proceed directly to the check-in confirmation so staff can perform
        # a quick check-in even when more than one guest is present. Additional
        # guest details can still be entered later via the booking edit workflow.

        # If there are multiple rooms for this booking, allow selecting which to check-in
        try:
            # include_proceed=True shows a "Proceed" button in the selector so staff can select rooms
            # and proceed to check-in in one step (avoids a separate confirmation dialog hiding behind modals).
            # Only show rooms that are still 'Reserved' when checking in
            selected_booking_ids, manual_dt = self.select_booking_rows(booking_ref, include_manual_dt=False, include_proceed=True, allowed_statuses=['Reserved'])
        except Exception:
            selected_booking_ids, manual_dt = None, None

        if not selected_booking_ids:
            # fallback to single-room behavior if no selection made
            if not messagebox.askyesno("Confirm Check-In", f"Do you want to check-in the guest for booking {booking_ref}?"):
                return
            selected_booking_ids = [room_id]
            manual_dt = None

        try:
            cursor = self.db_conn.cursor()
            check_in_timestamp = manual_dt or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            placeholders = ','.join(['?'] * len(selected_booking_ids))
            params = [check_in_timestamp] + selected_booking_ids
            cursor.execute(f"UPDATE bookings SET status='Checked-In', actual_check_in=? WHERE id IN ({placeholders})", params)
            # Update rooms
            for bid in selected_booking_ids:
                cursor.execute("SELECT room_id FROM bookings WHERE id=?", (bid,))
                rr = cursor.fetchone()
                if rr:
                    cursor.execute("UPDATE rooms SET status='Occupied' WHERE id=?", (rr[0],))
            self.db_conn.commit()
            messagebox.showinfo("Success", f"Selected room(s) for booking {booking_ref} have been checked-in.")
            self.load_bookings_data()
            self.refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}")

    # --- VERSION 1.8 CHANGE: New Workflow ---
    def check_out_guest(self):
        """Handles checkout and billing by opening a selection window."""

        # Open the selection window for "Checked-In" guests
        selector = BookingSelectionWindow(self, status_list=['Checked-In'], title="Select Guest to Check-Out")
        selected_booking = selector.show()

        if not selected_booking:
            return  # User cancelled

        booking_ref = selected_booking['ref']

        # Allow user to select specific rooms for checkout
        try:
            # show Proceed inside selector so user can pick rooms and continue in one modal
            # Only show rooms that are currently 'Checked-In' when checking out
            # Include per-room person count so staff can override how many people are checking out from each room (for early/partial checkouts)
            sel = self.select_booking_rows(booking_ref, include_manual_dt=True, include_proceed=True, allowed_statuses=['Checked-In'], include_person_count=True)
            # Function returns (ids, manual, persons_map) when include_person_count=True
            try:
                selected_booking_ids, manual_dt, persons_map = sel
            except Exception:
                # Fallback if caller didn't return persons_map for some reason
                selected_booking_ids, manual_dt = sel
                persons_map = None
        except Exception:
            selected_booking_ids, manual_dt, persons_map = None, None, None

        if not selected_booking_ids:
            # nothing selected or user canceled
            return

        # attach temporary context for billing, including any manual persons overrides
        self._checkout_selected_booking_ids = selected_booking_ids
        self._checkout_manual_dt = manual_dt
        # Always attach the persons_map (may be empty) so downstream code can detect
        # that the selector ran with person-count awareness. This avoids a case where
        # an empty dict would be treated as False and not propagated.
        self._checkout_persons_map = persons_map
        try:
            self.generate_and_show_bill(booking_ref)
        finally:
            try:
                del self._checkout_selected_booking_ids
            except Exception:
                pass
            try:
                del self._checkout_manual_dt
            except Exception:
                pass
            try:
                del self._checkout_persons_map
            except Exception:
                pass

    def generate_and_show_bill(self, booking_ref):
        """Calculate and display the final bill."""
        cursor = self.db_conn.cursor()
        # Allow partial checkout: if self._checkout_selected_booking_ids present, use only those booking rows
        selected_booking_ids = getattr(self, '_checkout_selected_booking_ids', None)

        if selected_booking_ids:
            placeholders = ','.join(['?'] * len(selected_booking_ids))
            cursor.execute(f"SELECT b.id, g.name, g.phone, r.room_number, r.rate, b.check_in, b.check_out, s.hotel_name, s.address, s.address_line1, s.address_line2, s.gst_number, s.contact_number, r.id, b.advance_payment, b.num_adults, b.num_children FROM bookings b JOIN guests g ON b.guest_id = g.id JOIN rooms r ON b.room_id = r.id JOIN settings s ON s.id = 1 WHERE b.id IN ({placeholders}) ORDER BY r.room_number", tuple(selected_booking_ids))
            rows = cursor.fetchall()
            if not rows:
                messagebox.showerror("Error", "Could not retrieve booking details for selected rooms.")
                return
            # aggregate
            guest_name = rows[0][1]
            guest_phone = rows[0][2]
            hotel_name = rows[0][7]
            hotel_address = rows[0][8]
            hotel_address_line1 = rows[0][9]
            hotel_address_line2 = rows[0][10]
            hotel_gst = rows[0][11]
            hotel_contact = rows[0][12]
            advance_payment = sum((r[14] or 0.0) for r in rows)
            num_adults = sum((r[15] or 0) for r in rows)
            num_children = sum((r[16] or 0) for r in rows)
            room_rows = [{'booking_id': r[0], 'room_number': r[3], 'rate': r[4], 'check_in': r[5], 'check_out': r[6], 'room_id': r[13]} for r in rows]
        else:
            # default: use all rows for booking_ref
            cursor.execute("""
                SELECT b.id, g.name, g.phone, r.room_number, r.rate, b.check_in, b.check_out, 
                       s.hotel_name, s.address, s.address_line1, s.address_line2, s.gst_number, s.contact_number, r.id, b.advance_payment,
                       b.num_adults, b.num_children
                FROM bookings b
                JOIN guests g ON b.guest_id = g.id
                JOIN rooms r ON b.room_id = r.id
                JOIN settings s ON s.id = 1
                WHERE b.booking_ref = ?
                ORDER BY r.room_number
            """, (booking_ref,))
            rows = cursor.fetchall()
            if not rows:
                messagebox.showerror("Error", "Could not retrieve booking details.")
                return
            guest_name = rows[0][1]
            guest_phone = rows[0][2]
            hotel_name = rows[0][7]
            hotel_address = rows[0][8]
            hotel_address_line1 = rows[0][9]
            hotel_address_line2 = rows[0][10]
            hotel_gst = rows[0][11]
            hotel_contact = rows[0][12]
            advance_payment = sum((r[14] or 0.0) for r in rows)
            num_adults = sum((r[15] or 0) for r in rows)
            num_children = sum((r[16] or 0) for r in rows)
            room_rows = [{'booking_id': r[0], 'room_number': r[3], 'rate': r[4], 'check_in': r[5], 'check_out': r[6], 'room_id': r[13]} for r in rows]

        # Calculate stay duration — be permissive about stored date formats
        def _parse_any_to_dt(s):
            if not s:
                return None
            s = str(s).strip()
            # Accept a broad set of formats including 12-hour AM/PM variants
            fmts = [
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %I:%M %p', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                '%d/%m/%Y %I:%M %p', '%d/%m/%Y %H:%M', '%d/%m/%Y',
                '%m/%d/%Y %I:%M %p', '%m/%d/%Y %H:%M', '%m/%d/%Y',
            ]
            for f in fmts:
                try:
                    return datetime.strptime(s, f)
                except Exception:
                    continue
            # Last resort: try to extract date-like prefix
            m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
            if m:
                try:
                    return datetime.strptime(m.group(1), '%Y-%m-%d')
                except Exception:
                    pass
            return None

        # Build aggregated date/time and totals across selected room rows
        # Parse check-in/out datetimes from each row permissively
        dts_in = [ _parse_any_to_dt(r['check_in']) for r in room_rows if r.get('check_in') ]
        dts_out = [ _parse_any_to_dt(r['check_out']) for r in room_rows if r.get('check_out') ]

        earliest_ci = min(dts_in) if dts_in else None
        latest_co = max(dts_out) if dts_out else None

        # If caller provided a manual checkout datetime (from select dialog), prefer it
        manual_dt_val = getattr(self, '_checkout_manual_dt', None)
        manual_dt_obj = _parse_any_to_dt(manual_dt_val) if manual_dt_val else None

        now_dt = datetime.now()
        final_checkout_dt = manual_dt_obj if manual_dt_obj else max(now_dt, latest_co or now_dt)

        # Choose a sensible check-in baseline
        if earliest_ci:
            check_in_dt = earliest_ci
        else:
            # fallback to first room's check-in or now
            check_in_dt = _parse_any_to_dt(room_rows[0].get('check_in')) or now_dt

        # Compute nights (minimum 1)
        try:
            num_nights = (final_checkout_dt.date() - check_in_dt.date()).days
            if num_nights <= 0:
                num_nights = 1
        except Exception:
            num_nights = 1

        # Room totals: sum each room rate * nights
        room_total = sum((float(r.get('rate') or 0.0) * num_nights) for r in room_rows)

        # Aggregate restaurant charges across the selected booking ids
        booking_ids_for_orders = [r['booking_id'] for r in room_rows]
        restaurant_total = 0.0
        restaurant_items = []
        try:
            placeholders = ','.join(['?'] * len(booking_ids_for_orders))
            cursor.execute(f"SELECT SUM(price_at_order * quantity) FROM restaurant_orders WHERE booking_id IN ({placeholders})", tuple(booking_ids_for_orders))
            restaurant_total = cursor.fetchone()[0] or 0.0

            cursor.execute(f"""
                SELECT m.item_name, o.quantity, o.price_at_order, (o.quantity * o.price_at_order)
                FROM restaurant_orders o
                JOIN restaurant_menu m ON o.item_id = m.id
                WHERE o.booking_id IN ({placeholders}) ORDER BY o.order_date
            """, tuple(booking_ids_for_orders))
            restaurant_items = cursor.fetchall()
        except Exception:
            restaurant_total = 0.0
            restaurant_items = []

        # Representative fields plus per-room line items for multi-room bookings
        room_number = ','.join([str(r.get('room_number') or '') for r in room_rows])
        room_id = room_rows[0].get('room_id')
        booking_id = room_rows[0].get('booking_id')
        check_in_str = check_in_dt.strftime('%Y-%m-%d %H:%M:%S') if check_in_dt else (room_rows[0].get('check_in') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # Build explicit per-room items: (room_number, nights, rate, amount)
        room_items = []
        for r in room_rows:
            rt = float(r.get('rate') or 0.0)
            amt = rt * num_nights
            room_items.append((r.get('room_number'), num_nights, rt, amt))
        # Keep a fallback single-room rate for compatibility with older code
        room_rate = float(room_rows[0].get('rate') or 0.0)
        
        # --- NEW: Calculate Local Government Charge ---
        # For partial checkout, prefer any manual per-room person counts collected
        # via the select dialog (self._checkout_persons_map). Fall back to stored
        # per-row adults/children values. For full-group checkout, include adults+children.
        try:
            if selected_booking_ids:
                manual_map = getattr(self, '_checkout_persons_map', None)
                if manual_map:
                    # If the selector included a special overall total (key '__total__'),
                    # distribute that total across the selected rows (proportionally to
                    # stored per-row totals) and clamp to per-row stored totals so we
                    # never exceed the physical booking counts. Otherwise normalize
                    # the per-row map as before.
                    try:
                        raw_total = None
                        if '__total__' in manual_map:
                            try:
                                raw_total = int(manual_map.get('__total__') or 0)
                            except Exception:
                                raw_total = None

                        # Build stored totals map for selected rows
                        stored_totals = {}
                        for r in rows:
                            bid = r[0]
                            stored_totals[bid] = int((r[15] or 0) + (r[16] or 0))

                        if raw_total is not None and raw_total > 0:
                            # Allow the manual total to draw from the entire booking's capacity
                            # (not only the selected rows). This lets staff check out people
                            # who are recorded in other rooms of the same booking.
                            try:
                                cursor2 = self.db_conn.cursor()
                                cursor2.execute(
                                    "SELECT SUM(COALESCE(num_adults,0) + COALESCE(num_children,0)) FROM bookings WHERE booking_ref=?",
                                    (self.bill_data.get('booking_ref') or booking_ref,)
                                )
                                booking_cap_row = cursor2.fetchone()
                                booking_total_cap = int(booking_cap_row[0] or 0)
                            except Exception:
                                booking_total_cap = sum(stored_totals.values())

                            # Cap the manual total at the booking-level capacity
                            raw_total_allowed = min(raw_total, booking_total_cap if booking_total_cap > 0 else raw_total)

                            # Distribute raw_total_allowed across stored_totals (selected rows)
                            total_cap = sum(stored_totals.values())
                            alloc = {bid: 0 for bid in stored_totals}
                            if len(stored_totals) == 1:
                                # Single row: assign min(total_allowed, capacity)
                                only = next(iter(stored_totals))
                                alloc[only] = min(raw_total_allowed, stored_totals[only])
                            elif total_cap <= 0:
                                # No capacities found; fallback to assigning to first row
                                first = next(iter(stored_totals))
                                alloc[first] = raw_total_allowed
                            else:
                                # Proportional floor allocation then distribute remainder across selected rows
                                remainders = []
                                assigned_sum = 0
                                for bid, cap in stored_totals.items():
                                    share = (cap / total_cap) * raw_total_allowed
                                    base = int(math.floor(share))
                                    base = min(base, cap)
                                    alloc[bid] = base
                                    assigned_sum += base
                                    remainders.append((bid, share - base, cap - base))
                                rem = int(raw_total_allowed - assigned_sum)
                                # Sort by largest fractional remainder and available capacity
                                remainders.sort(key=lambda x: (x[1], x[2]), reverse=True)
                                for bid, frac, avail in remainders:
                                    if rem <= 0:
                                        break
                                    if avail <= 0:
                                        continue
                                    add = min(rem, int(min(avail, 1)))
                                    alloc[bid] += add
                                    rem -= add
                                # If still remainder, fill any available capacity
                                if rem > 0:
                                    for bid, cap in stored_totals.items():
                                        avail = cap - alloc[bid]
                                        if avail <= 0:
                                            continue
                                        add = min(avail, rem)
                                        alloc[bid] += add
                                        rem -= add
                                        if rem <= 0:
                                            break

                            # Final clamp and compute total based on booking-level allowed total
                            person_count_for_local = 0
                            norm_map = {}
                            for bid, v in alloc.items():
                                try:
                                    vv = int(v)
                                except Exception:
                                    vv = 0
                                if vv < 0:
                                    vv = 0
                                if vv > stored_totals.get(bid, 0):
                                    vv = stored_totals.get(bid, 0)
                                norm_map[bid] = vv
                                person_count_for_local += vv
                            # If the manual allowed total exceeds what we've allocated to selected rows,
                            # reflect the full manual allowed total when computing the local charge
                            if raw_total_allowed > person_count_for_local:
                                person_count_for_local = raw_total_allowed
                        else:
                            # No overall total provided, fall back to per-row manual map
                            norm_map = {}
                            for k, v in manual_map.items():
                                # skip special keys
                                if k == '__total__':
                                    continue
                                try:
                                    kk = int(k)
                                except Exception:
                                    try:
                                        kk = int(str(k).strip())
                                    except Exception:
                                        continue
                                try:
                                    vv = int(v)
                                except Exception:
                                    try:
                                        vv = int(str(v).strip())
                                    except Exception:
                                        vv = 0
                                norm_map[kk] = vv

                            person_count_for_local = 0
                            for r in rows:
                                bid = r[0]
                                stored_total = int((r[15] or 0) + (r[16] or 0))
                                val = norm_map.get(bid, stored_total)
                                try:
                                    val = int(val)
                                except Exception:
                                    val = stored_total
                                # Clamp between 0 and stored_total to avoid accidental overcount
                                if val < 0:
                                    val = 0
                                if val > stored_total:
                                    val = stored_total
                                person_count_for_local += val
                    except Exception:
                        # Fallback to legacy per-row adult-only behavior
                        norm_map = {}
                        person_count_for_local = int(num_adults or 0)
                else:
                    # legacy behavior: when doing a partial checkout, charge only on adults
                    person_count_for_local = int(num_adults or 0)
            else:
                person_count_for_local = int((num_adults or 0) + (num_children or 0))
        except Exception:
            person_count_for_local = int(num_adults or 0)

        local_charge_info = self.calculate_local_charge(num_nights, person_count_for_local)
        # --- END NEW ---

        # Display bill in a new window (include selected booking ids for partial checkout)
        BillWindow(self, {
            "booking_ref": booking_ref,
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "room_number": room_number,
            "check_in": check_in_str,
            "check_out": final_checkout_dt.strftime('%Y-%m-%d %H:%M:%S'),  # Show actual checkout datetime
            "num_nights": num_nights,
            "room_rate": room_rate,
            "room_total": room_total,
            "room_items": room_items,
            "restaurant_total": restaurant_total,
            "restaurant_items": restaurant_items,
            "advance_payment": advance_payment or 0.0,
            "hotel_name": hotel_name,
            "hotel_address": hotel_address,
            "hotel_address_line1": hotel_address_line1,
            "hotel_address_line2": hotel_address_line2,
            "hotel_gst": hotel_gst,
            "hotel_contact": hotel_contact,
            "room_id": room_id,
            "local_charge_info": local_charge_info, # <-- NEW
            "orig_num_adults": num_adults,
            "orig_num_children": num_children,
            # Override the visible persons fields when a manual display total was provided
            # so that any remaining code paths that reference num_adults/num_children
            # show the manual count.
            "num_adults": (person_count_for_local if selected_booking_ids and 'person_count_for_local' in locals() else num_adults),
            "num_children": (0 if selected_booking_ids and 'person_count_for_local' in locals() else num_children),
            # When doing a partial checkout with manual per-row person counts, expose
            # the effective display total so the BillWindow and PDF prefer showing the
            # manually-entered count rather than stored aggregated adults/children.
            "manual_persons_map": (norm_map if selected_booking_ids and 'norm_map' in locals() else None),
            "display_persons_total": (person_count_for_local if selected_booking_ids else None),
            "selected_booking_ids": selected_booking_ids or booking_ids_for_orders
        })

    # --- NEW: Local Charge Calculation Method ---
    def calculate_local_charge(self, num_nights, total_persons):
        """Calculates the fixed local charge based on settings and stay duration/persons."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT enabled, charge_name, amount, calculation_type FROM local_charges WHERE id=1")
        charge_settings = cursor.fetchone()

        if not charge_settings or charge_settings[0] != 'true':
            return {"name": "", "amount": 0.0, "details": ""}

        enabled, name, amount, calc_type = charge_settings

        charge_amount = 0.0
        details = ""

        if calc_type == "Per Day":
            charge_amount = amount * num_nights
            details = f"{num_nights} days @ Rs.{amount:.2f}/day"
        elif calc_type == "Per Person":
            charge_amount = amount * total_persons
            details = f"{total_persons} persons @ Rs.{amount:.2f}/person"
        
        return {"name": name, "amount": charge_amount, "details": details}
    # --- END NEW ---
    
    # --- NEW: Local Charge Calculation for ADVANCE RECEIPT ---
    def calculate_local_charge_for_advance(self, num_nights, num_adults, num_children):
        """Calculates the fixed local charge for advance receipts.

        Per policy, children are not charged local government fee on advance receipts.
        This helper keeps the same signature for compatibility but only uses adults.
        """
        try:
            adults_only = int(num_adults or 0)
        except Exception:
            adults_only = 0
        return self.calculate_local_charge(num_nights, adults_only)
    # --- END NEW ---


    def add_restaurant_order(self):
        """Open window to add restaurant order by opening a selection window."""

        # Open the selection window for "Checked-In" guests
        selector = BookingSelectionWindow(self, status_list=['Checked-In'], title="Select Guest to Add Order")
        selected_booking = selector.show()

        if not selected_booking:
            return  # User cancelled

        booking_ref = selected_booking['ref']
        room_number = selected_booking['room_number']

        RestaurantOrderWindow(self, booking_ref, room_number)

    def cancel_booking(self):
        """Cancel a selected booking."""
        # This action is only on the Bookings tab, so it can still use the tree focus
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a booking to cancel.")
            return

        item_values = self.bookings_tree.item(selected_item)['values']
        booking_ref, status = item_values[0], item_values[8] # Index adjusted for new columns

        if status not in ['Reserved']:
            messagebox.showerror("Error", "Can only cancel 'Reserved' bookings. For active stays, please use Check-Out.")
            return

        if messagebox.askyesno("Confirm Cancel", f"Are you sure you want to cancel booking {booking_ref}? This cannot be undone."):
            try:
                cursor = self.db_conn.cursor()

                # BUGFIX: Only update booking status. Do NOT change room status.
                cursor.execute("UPDATE bookings SET status='Cancelled' WHERE booking_ref=?", (booking_ref,))
                
                # OPTIONAL: Delete entries from booking_persons
                cursor.execute("DELETE FROM booking_persons WHERE booking_ref=?", (booking_ref,))


                self.db_conn.commit()
                messagebox.showinfo("Success", f"Booking {booking_ref} has been cancelled.")
                self.load_bookings_data()
                self.refresh_dashboard()  # Dashboard will now show room as available for today
            except Exception as e:
                messagebox.showerror("Database Error", f"An error occurred: {e}")

    def change_booking_dates(self):
        """Allow changing check-in/check-out dates for a reservation."""
        # This action is only on the Bookings tab, so it can still use the tree focus
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a booking to modify.")
            return

        item_values = self.bookings_tree.item(selected_item)['values']
        booking_ref, status = item_values[0], item_values[8] # Index adjusted for new columns

        if status not in ['Reserved', 'Checked-In']:
            messagebox.showerror("Error", "Can only change dates for 'Reserved' or 'Checked-In' bookings.")
            return

        ChangeDatesWindow(self, booking_ref)
        
    def extend_stay(self):
        """Allows extension of stay for a checked-in guest."""
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a booking to extend the stay for.")
            return

        item_values = self.bookings_tree.item(selected_item)['values']
        booking_ref, status = item_values[0], item_values[8]

        if status not in ['Reserved', 'Checked-In']:
            messagebox.showerror("Error", "Can only extend stay for 'Reserved' or 'Checked-In' bookings.")
            return
            
        ExtendStayWindow(self, booking_ref)
        

    def setup_rooms_tab(self):
        """Set up the room management tab (Admin only)."""
        frame = ttk.Frame(self.rooms_tab, padding=10)
        frame.pack(fill='both', expand=True)

        form_frame = ttk.Labelframe(frame, text="Room Details", padding=15)
        form_frame.pack(fill='x', pady=10)

        # Form fields - Added more padding (pady=10)
        ttk.Label(form_frame, text="Room Number:").grid(row=0, column=0, padx=5, pady=10, sticky='w')
        self.room_num_entry = ttk.Entry(form_frame, width=25)
        self.room_num_entry.grid(row=0, column=1, padx=5, pady=10, ipady=3)

        ttk.Label(form_frame, text="Room Type:").grid(row=0, column=2, padx=(20, 5), pady=10, sticky='w')
        self.room_type_combo = ttk.Combobox(form_frame, values=["AC", "Non-AC", "Deluxe", "Super Deluxe"], width=23)
        self.room_type_combo.grid(row=0, column=3, padx=5, pady=10, ipady=3)

        ttk.Label(form_frame, text="Bed Type:").grid(row=1, column=0, padx=5, pady=10, sticky='w')
        # --- MODIFIED: Added King Size and Queen Size Bed ---
        self.bed_type_combo = ttk.Combobox(form_frame, values=["Single Bed", "Double Bed", "King Size Bed", "Queen Size Bed", "Two Bed"], width=23)
        self.bed_type_combo.grid(row=1, column=1, padx=5, pady=10, ipady=3)
        # --- END MODIFIED ---

        ttk.Label(form_frame, text="Daily Rate (Rs.):").grid(row=1, column=2, padx=(20, 5), pady=10, sticky='w')
        self.rate_entry = ttk.Entry(form_frame, width=25)
        self.rate_entry.grid(row=1, column=3, padx=5, pady=10, ipady=3)

        ttk.Label(form_frame, text="Status:").grid(row=2, column=0, padx=5, pady=10, sticky='w')
        self.room_status_combo = ttk.Combobox(form_frame, values=["Available", "Occupied", "Maintenance"], width=23)
        self.room_status_combo.grid(row=2, column=1, padx=5, pady=10, ipady=3)
        ttk.Label(form_frame, text="(Note: 'Occupied' status is best managed via Check-In/Out)").grid(row=2, column=2, columnspan=2, sticky='w', padx=5)

        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Add Room", command=self.add_room, style="Success.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(btn_frame, text="Update Room", command=self.update_room, style="Accent.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(btn_frame, text="Delete Room", command=self.delete_room, style="Danger.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(btn_frame, text="Clear Fields", command=self.clear_room_fields).pack(side='left', padx=5, ipady=5)

        # Treeview for rooms
        cols = ('Room #', 'Room Type', 'Bed Type', 'Rate', 'Status')
        self.rooms_tree = ttk.Treeview(frame, columns=cols, show='headings')
        for col in cols:
            self.rooms_tree.heading(col, text=col)
        self.rooms_tree.column('Rate', anchor='e')
        self.rooms_tree.column('Status', anchor='center')

        self.rooms_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.rooms_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.rooms_tree.pack(fill='both', expand=True, pady=10)
        self.rooms_tree.bind('<<TreeviewSelect>>', self.on_room_select)

        self.load_rooms_data()

    def load_rooms_data(self):
        """Load rooms into the treeview."""
        for i in self.rooms_tree.get_children():
            self.rooms_tree.delete(i)
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT room_number, room_type, bed_type, rate, status FROM rooms ORDER BY room_number")
        for i, row in enumerate(cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.rooms_tree.insert('', 'end', values=row, tags=(tag,))

    def on_room_select(self, event):
        """Fill form when a room is selected."""
        selected_item = self.rooms_tree.focus()
        if not selected_item:
            return
        item = self.rooms_tree.item(selected_item)
        values = item['values']

        self.clear_room_fields()
        self.room_num_entry.insert(0, values[0])
        self.room_type_combo.set(values[1])
        self.bed_type_combo.set(values[2])
        self.rate_entry.insert(0, values[3])
        self.room_status_combo.set(values[4])  # Set status

    def add_room(self):
        """Add a new room to the database."""
        room_num = self.room_num_entry.get()
        room_type = self.room_type_combo.get()
        bed_type = self.bed_type_combo.get()
        rate = self.rate_entry.get()
        status = self.room_status_combo.get() or 'Available'  # Default to Available

        if not all([room_num, room_type, bed_type, rate]):
            messagebox.showerror("Error", "Room Number, Type, Bed Type, and Rate are required.")
            return

        try:
            rate_val = float(rate)
            cursor = self.db_conn.cursor()
            cursor.execute("INSERT INTO rooms (room_number, room_type, bed_type, rate, status) VALUES (?, ?, ?, ?, ?)",
                           (room_num, room_type, bed_type, rate_val, status))
            self.db_conn.commit()
            messagebox.showinfo("Success", "Room added successfully.")
            self.load_rooms_data()
            self.clear_room_fields()
            self.refresh_dashboard()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"Room number '{room_num}' already exists.")
        except ValueError:
            messagebox.showerror("Error", "Rate must be a valid number.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def update_room(self):
        """Update selected room's details."""
        selected_item = self.rooms_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a room to update.")
            return

        original_room_num = self.rooms_tree.item(selected_item)['values'][0]

        new_room_num = self.room_num_entry.get()
        room_type = self.room_type_combo.get()
        bed_type = self.bed_type_combo.get()
        rate = self.rate_entry.get()
        status = self.room_status_combo.get()

        if not all([new_room_num, room_type, bed_type, rate, status]):
            messagebox.showerror("Error", "All fields are required.")
            return

        try:
            rate_val = float(rate)
            cursor = self.db_conn.cursor()
            cursor.execute("""
                UPDATE rooms 
                SET room_number=?, room_type=?, bed_type=?, rate=?, status=? 
                WHERE room_number=?
            """, (new_room_num, room_type, bed_type, rate_val, status, original_room_num))
            self.db_conn.commit()
            messagebox.showinfo("Success", "Room updated successfully.")
            self.load_rooms_data()
            self.clear_room_fields()
            self.refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def delete_room(self):
        """Delete a selected room."""
        selected_item = self.rooms_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a room to delete.")
            return

        room_num = self.rooms_tree.item(selected_item)['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete room {room_num}? This cannot be undone."):
            try:
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM rooms WHERE room_number=?", (room_num,))
                self.db_conn.commit()
                messagebox.showinfo("Success", "Room deleted successfully.")
                self.load_rooms_data()
                self.clear_room_fields()
                self.refresh_dashboard()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete room. It might be associated with a booking.\nError: {e}")

    def clear_room_fields(self):
        """Clear the room form fields."""
        self.room_num_entry.delete(0, 'end')
        self.room_type_combo.set('')
        self.bed_type_combo.set('')
        self.rate_entry.delete(0, 'end')
        self.room_status_combo.set('')
        if self.rooms_tree.focus():
            self.rooms_tree.selection_remove(self.rooms_tree.focus())

    def setup_restaurant_tab(self):
        """Setup restaurant menu management tab (Admin only)."""
        frame = ttk.Frame(self.restaurant_tab, padding=10)
        frame.pack(fill='both', expand=True)

        form_frame = ttk.Labelframe(frame, text="Menu Item Details", padding=15)
        form_frame.pack(fill='x', pady=10)

        # Form fields - Added more padding (pady=10)
        ttk.Label(form_frame, text="Item Name:").grid(row=0, column=0, padx=5, pady=10, sticky='w')
        self.item_name_entry = ttk.Entry(form_frame, width=40)
        self.item_name_entry.grid(row=0, column=1, padx=5, pady=10, ipady=3)

        ttk.Label(form_frame, text="Price (Rs.):").grid(row=0, column=2, padx=(20, 5), pady=10, sticky='w')
        self.item_price_entry = ttk.Entry(form_frame, width=20)
        self.item_price_entry.grid(row=0, column=3, padx=5, pady=10, ipady=3)

        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Add Item", command=self.add_menu_item, style="Success.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(btn_frame, text="Update Item", command=self.update_menu_item, style="Accent.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(btn_frame, text="Delete Item", command=self.delete_menu_item, style="Danger.TButton").pack(side='left', padx=5, ipady=5)
        ttk.Button(btn_frame, text="Clear Fields", command=self.clear_menu_fields).pack(side='left', padx=5, ipady=5)

        # Treeview for menu
        cols = ('Item Name', 'Price')
        self.menu_tree = ttk.Treeview(frame, columns=cols, show='headings')
        self.menu_tree.heading('Item Name', text='Item Name')
        self.menu_tree.heading('Price', text='Price (Rs.)')
        self.menu_tree.column('Price', anchor='e', width=100)
        self.menu_tree.column('Item Name', width=500)

        self.menu_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.menu_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.menu_tree.pack(fill='both', expand=True, pady=10)
        self.menu_tree.bind('<<TreeviewSelect>>', self.on_menu_item_select)

        self.load_menu_data()

    def load_menu_data(self):
        """Load menu items into the treeview."""
        for i in self.menu_tree.get_children():
            self.menu_tree.delete(i)
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, item_name, price FROM restaurant_menu ORDER BY item_name")
        for i, row in enumerate(cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.menu_tree.insert('', 'end', values=(row[1], f"{row[2]:.2f}"), iid=row[0], tags=(tag,))

    def on_menu_item_select(self, event):
        """Fill form when a menu item is selected."""
        selected_item = self.menu_tree.focus()
        if not selected_item:
            return
        values = self.menu_tree.item(selected_item)['values']
        self.clear_menu_fields()
        self.item_name_entry.insert(0, values[0])
        self.item_price_entry.insert(0, values[1])

    def add_menu_item(self):
        """Add a new item to the restaurant menu."""
        name = self.item_name_entry.get()
        price_str = self.item_price_entry.get()

        if not name or not price_str:
            messagebox.showerror("Error", "Both item name and price are required.")
            return

        try:
            price = float(price_str)
            cursor = self.db_conn.cursor()
            cursor.execute("INSERT INTO restaurant_menu (item_name, price) VALUES (?, ?)", (name, price))
            self.db_conn.commit()
            messagebox.showinfo("Success", "Menu item added successfully.")
            self.load_menu_data()
            self.clear_menu_fields()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"Item '{name}' already exists in the menu.")
        except ValueError:
            messagebox.showerror("Error", "Price must be a valid number.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def update_menu_item(self):
        """Update a selected menu item."""
        selected_item = self.menu_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select an item to update.")
            return

        # The selected_item returned by Treeview.focus() is the item's iid (we set it during insert)
        item_id = selected_item
        new_name = self.item_name_entry.get()
        price_str = self.item_price_entry.get()

        if not new_name or not price_str:
            messagebox.showerror("Error", "All fields are required.")
            return

        try:
            # Sanitize price input (strip currency symbols, commas)
            import re as _re
            price_clean = _re.sub(r'[^0-9\.]', '', price_str)
            price = float(price_clean)
            cursor = self.db_conn.cursor()
            # Update by ID
            cursor.execute("UPDATE restaurant_menu SET item_name=?, price=? WHERE id=?", (new_name, price, item_id))
            self.db_conn.commit()
            messagebox.showinfo("Success", "Menu item updated successfully.")
            self.load_menu_data()
            self.clear_menu_fields()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def delete_menu_item(self):
        """Delete a selected menu item."""
        selected_item = self.menu_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select an item to delete.")
            return

        values = self.menu_tree.item(selected_item).get('values', [])
        item_name = values[0] if values else ''
        # selected_item itself is the iid we inserted earlier
        item_id = selected_item

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{item_name}' from the menu?"):
            try:
                cursor = self.db_conn.cursor()
                # Prevent deletion if there are existing orders referencing this item
                cursor.execute("SELECT COUNT(*) FROM restaurant_orders WHERE item_id=?", (item_id,))
                linked = cursor.fetchone()[0] or 0
                if linked > 0:
                    messagebox.showerror("Cannot Delete", f"This menu item has {linked} existing order(s) and cannot be deleted.\nEither remove related orders first or update the item instead.")
                    return

                cursor.execute("DELETE FROM restaurant_menu WHERE id=?", (item_id,))
                self.db_conn.commit()
                messagebox.showinfo("Success", "Menu item deleted successfully.")
                self.load_menu_data()
                self.clear_menu_fields()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete item. Error: {e}")

    def clear_menu_fields(self):
        """Clear the menu form fields."""
        self.item_name_entry.delete(0, 'end')
        self.item_price_entry.delete(0, 'end')
        if self.menu_tree.focus():
            self.menu_tree.selection_remove(self.menu_tree.focus())

    # --- MODIFIED: Settings Tab with Local Charge Management ---
    def setup_settings_tab(self):
        """Set up the settings tab for hotel details (Admin only)."""
        # Create a canvas and scrollbar for a scrollable settings page
        canvas = tk.Canvas(self.settings_tab, bg=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.settings_tab, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=20)  # This is the scrollable frame

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable smooth scrolling (mouse + keyboard) for settings
        try:
            self._make_scrollable(canvas)
        except Exception:
            pass

        # --- Section 1: Hotel Information ---
        info_frame = ttk.Labelframe(frame, text="Hotel Information", padding=20)
        info_frame.pack(fill='x', pady=10)

        ttk.Label(info_frame, text="Hotel Name:").grid(row=0, column=0, sticky='w', padx=10, pady=8)
        self.hotel_name_entry = ttk.Entry(info_frame, width=50)
        self.hotel_name_entry.grid(row=0, column=1, pady=8, ipady=3)

        ttk.Label(info_frame, text="Address Line 1:").grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.address1_entry = ttk.Entry(info_frame, width=50)
        self.address1_entry.grid(row=1, column=1, pady=8, ipady=3)

        ttk.Label(info_frame, text="Address Line 2:").grid(row=2, column=0, sticky='w', padx=10, pady=8)
        self.address2_entry = ttk.Entry(info_frame, width=50)
        self.address2_entry.grid(row=2, column=1, pady=8, ipady=3)

        ttk.Label(info_frame, text="GST Number:").grid(row=3, column=0, sticky='w', padx=10, pady=8)
        self.gst_entry = ttk.Entry(info_frame, width=50)
        self.gst_entry.grid(row=3, column=1, pady=8, ipady=3)

        ttk.Label(info_frame, text="Contact Number:").grid(row=4, column=0, sticky='w', padx=10, pady=8)
        self.contact_entry = ttk.Entry(info_frame, width=50)
        self.contact_entry.grid(row=4, column=1, pady=8, ipady=3)

        # --- Section 2: Tax Settings (GST) ---
        tax_frame = ttk.Labelframe(frame, text="Tax Settings (GST/IGST)", padding=20)
        tax_frame.pack(fill='x', pady=10)

        # V2.2: Independent Checkboxes
        self.enable_cgst_sgst_var = tk.StringVar()
        ttk.Checkbutton(tax_frame, text="Enable CGST/SGST (Intra-State)", variable=self.enable_cgst_sgst_var, onvalue='true', offvalue='false').grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=10)

        self.enable_igst_var = tk.StringVar()
        ttk.Checkbutton(tax_frame, text="Enable IGST (Inter-State)", variable=self.enable_igst_var, onvalue='true', offvalue='false').grid(row=0, column=2, columnspan=2, sticky='w', padx=10, pady=10)

        ttk.Label(tax_frame, text="CGST Rate (%):").grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.cgst_rate_entry = ttk.Entry(tax_frame, width=10)
        self.cgst_rate_entry.grid(row=1, column=1, pady=8, ipady=3, padx=5)

        ttk.Label(tax_frame, text="SGST Rate (%):").grid(row=1, column=2, sticky='w', padx=10, pady=8)
        self.sgst_rate_entry = ttk.Entry(tax_frame, width=10)
        self.sgst_rate_entry.grid(row=1, column=3, pady=8, ipady=3, padx=5)

        ttk.Label(tax_frame, text="IGST Rate (%):").grid(row=2, column=0, sticky='w', padx=10, pady=8)
        self.igst_rate_entry = ttk.Entry(tax_frame, width=10)
        self.igst_rate_entry.grid(row=2, column=1, pady=8, ipady=3, padx=5)

        # --- Section 3: Local Government Charge/Fee ---
        charge_frame = ttk.Labelframe(frame, text="Local Government Charge/Fee", padding=20)
        charge_frame.pack(fill='x', pady=10)
        
        self.local_charge_enabled_var = tk.StringVar()
        ttk.Checkbutton(charge_frame, text="Enable Local Government Charge", variable=self.local_charge_enabled_var, onvalue='true', offvalue='false').grid(row=0, column=0, columnspan=4, sticky='w', padx=10, pady=(0, 10))

        ttk.Label(charge_frame, text="Charge Name:").grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.local_charge_name_entry = ttk.Entry(charge_frame, width=30)
        self.local_charge_name_entry.grid(row=1, column=1, pady=8, ipady=3)

        ttk.Label(charge_frame, text="Amount (Rs.):").grid(row=1, column=2, sticky='w', padx=10, pady=8)
        self.local_charge_amount_entry = ttk.Entry(charge_frame, width=10)
        self.local_charge_amount_entry.grid(row=1, column=3, pady=8, ipady=3)
        
        ttk.Label(charge_frame, text="Calculate Per:").grid(row=2, column=0, sticky='w', padx=10, pady=8)
        self.local_charge_type_combo = ttk.Combobox(charge_frame, values=["Per Day", "Per Person"], width=15)
        self.local_charge_type_combo.grid(row=2, column=1, pady=8, ipady=3)
        
        # --- Section 4: Save Button ---
        save_btn = ttk.Button(frame, text="Save All Settings", command=self.save_settings, style="Accent.TButton")
        save_btn.pack(pady=20, ipady=8, ipadx=15)

        # --- Section 5: Hotel Rules (for Advance Receipt) ---
        # Show 7 visible rule lines by default, allow up to 10 optional lines.
        rules_frame = ttk.Labelframe(frame, text="Hotel Rules for Advance Receipt (up to 10 lines, 7 visible by default)", padding=10)
        rules_frame.pack(fill='both', pady=10)

        self.hotel_rules_inputs_frame = ttk.Frame(rules_frame)
        self.hotel_rules_inputs_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Manage up to 10 single-line rule entries; show 7 initially
        self.hotel_rule_entries = []
        self._hotel_rules_visible_count = 7
        for i in range(10):
            ent = ttk.Entry(self.hotel_rules_inputs_frame, width=120)
            if i < self._hotel_rules_visible_count:
                ent.grid(row=i, column=0, sticky='we', pady=2)
            else:
                # keep grid but hidden (we'll grid/remove when showing)
                ent.grid_forget()
            self.hotel_rule_entries.append(ent)

        # Controls to add/remove optional rule lines
        rules_control_frame = ttk.Frame(rules_frame)
        rules_control_frame.pack(fill='x', padx=5, pady=(4,0))
        self.add_rule_btn = ttk.Button(rules_control_frame, text="Add Rule", command=lambda: self._add_rule_line(), style="Accent.TButton")
        self.add_rule_btn.pack(side='left')
        self.remove_rule_btn = ttk.Button(rules_control_frame, text="Remove Rule", command=lambda: self._remove_rule_line())
        self.remove_rule_btn.pack(side='left', padx=6)

        # Word count label
        self.hotel_rules_count_label = ttk.Label(rules_control_frame, text="Words: 0")
        self.hotel_rules_count_label.pack(side='right')

        def _update_rules_count(event=None):
            text = '\n'.join([e.get().strip() for e in self.hotel_rule_entries if e.get().strip()])
            words = len(text.split()) if text else 0
            self.hotel_rules_count_label.config(text=f"Words: {words}")
            if words > 500:
                self.hotel_rules_count_label.config(foreground='red')
            else:
                self.hotel_rules_count_label.config(foreground='black')

        # Bind updates for each entry
        for e in self.hotel_rule_entries:
            e.bind('<KeyRelease>', _update_rules_count)

        # Make hotel information read-only for non-SuperAdmin users.
        if getattr(self, 'user_role', None) != 'SuperAdmin':
            for e in (self.hotel_name_entry, self.address1_entry, self.address2_entry,):
                try:
                    e.state(['readonly'])
                except Exception:
                    try:
                        e.config(state='readonly')
                    except Exception:
                        pass
            # GST and Contact are editable by Admin (per request) - keep enabled for Admin
            # Tax and Local Charge fields remain editable for Admin/Employee

        self.load_settings()

    def load_settings(self):
        """Load hotel settings and local charge from the database."""
        cursor = self.db_conn.cursor()
        
        # Load Hotel/Tax Settings
        cursor.execute("""
            SELECT hotel_name, address, address_line1, address_line2, gst_number, contact_number, 
                   cgst_rate, sgst_rate, igst_rate, 
                   enable_cgst_sgst, enable_igst, hotel_rules
            FROM settings WHERE id=1
        """)
        settings = cursor.fetchone()
        
        # Load Local Charge Settings
        cursor.execute("SELECT enabled, charge_name, amount, calculation_type FROM local_charges WHERE id=1")
        local_charge_settings = cursor.fetchone()
        
        if settings:
            self.hotel_name_entry.delete(0, 'end')
            self.address1_entry.delete(0, 'end')
            self.address2_entry.delete(0, 'end')
            self.gst_entry.delete(0, 'end')
            self.contact_entry.delete(0, 'end')
            self.cgst_rate_entry.delete(0, 'end')
            self.sgst_rate_entry.delete(0, 'end')
            self.igst_rate_entry.delete(0, 'end')

            # Map settings columns
            hotel_name = settings[0]
            address_combined = settings[1] or ''
            address_line1 = settings[2] or ''
            address_line2 = settings[3] or ''
            gst = settings[4]
            contact = settings[5]
            cgst_rate = settings[6]
            sgst_rate = settings[7]
            igst_rate = settings[8]
            enable_cgst_sgst = settings[9]
            enable_igst = settings[10]
            hotel_rules = settings[11] if len(settings) > 11 else ''

            self.hotel_name_entry.insert(0, hotel_name)

            # Prefer explicit address lines; if missing, try to split the legacy combined address
            if address_line1 or address_line2:
                self.address1_entry.insert(0, address_line1)
                self.address2_entry.insert(0, address_line2)
            else:
                # Heuristic: split on first comma
                parts = [p.strip() for p in address_combined.split(',', 1)] if address_combined else ['', '']
                self.address1_entry.insert(0, parts[0])
                if len(parts) > 1:
                    self.address2_entry.insert(0, parts[1])

            self.gst_entry.insert(0, gst)
            self.contact_entry.insert(0, contact)

            self.cgst_rate_entry.insert(0, cgst_rate)
            self.sgst_rate_entry.insert(0, sgst_rate)
            self.igst_rate_entry.insert(0, igst_rate)

            self.enable_cgst_sgst_var.set(enable_cgst_sgst)
            self.enable_igst_var.set(enable_igst)
            # Load hotel rules into the entry lines (split by newline)
            try:
                lines = [l for l in (hotel_rules or '').split('\n') if l.strip()]
                # Populate up to 10 entries
                for i, ent in enumerate(self.hotel_rule_entries):
                    ent.delete(0, 'end')
                    if i < len(lines):
                        ent.insert(0, lines[i])
                        if i >= self._hotel_rules_visible_count:
                            ent.grid(row=i, column=0, sticky='we', pady=2)
                    else:
                        # hide optional entries beyond initial visible count
                        if i >= self._hotel_rules_visible_count:
                            ent.grid_forget()
                words = len((hotel_rules or '').split())
                self.hotel_rules_count_label.config(text=f"Words: {words}")
            except Exception:
                pass
            
        if local_charge_settings:
            self.local_charge_enabled_var.set(local_charge_settings[0])
            self.local_charge_name_entry.delete(0, 'end')
            self.local_charge_name_entry.insert(0, local_charge_settings[1])
            self.local_charge_amount_entry.delete(0, 'end')
            self.local_charge_amount_entry.insert(0, local_charge_settings[2])
            self.local_charge_type_combo.set(local_charge_settings[3])


    def save_settings(self):
        """Save all settings to the database."""
        try:
            name = self.hotel_name_entry.get()
            address1 = self.address1_entry.get()
            address2 = self.address2_entry.get()
            # Maintain a legacy combined address field for compatibility
            address = ', '.join([p for p in [address1, address2] if p])
            gst = self.gst_entry.get()
            contact = self.contact_entry.get()

            # Tax settings
            enable_cgst_sgst = self.enable_cgst_sgst_var.get()
            enable_igst = self.enable_igst_var.get()
            cgst_rate = float(self.cgst_rate_entry.get())
            sgst_rate = float(self.sgst_rate_entry.get())
            igst_rate = float(self.igst_rate_entry.get())
            
            # Local charge settings
            local_enabled = self.local_charge_enabled_var.get()
            local_name = self.local_charge_name_entry.get()
            local_amount = float(self.local_charge_amount_entry.get())
            local_type = self.local_charge_type_combo.get()

            # Hotel rules lines (join non-empty entries with newline)
            hotel_rules_lines = [e.get().strip() for e in self.hotel_rule_entries if e.get().strip()]
            hotel_rules = '\n'.join(hotel_rules_lines).strip()
            if len(hotel_rules.split()) > 1000:
                # Hard cap to avoid massive DB entries (unlikely), trim to first 1000 words
                hotel_rules = ' '.join(hotel_rules.split()[:1000])

            cursor = self.db_conn.cursor()
            
            # 1. Save Hotel/Tax Settings
            cursor.execute("""
                UPDATE settings 
                SET hotel_name=?, address=?, address_line1=?, address_line2=?, gst_number=?, contact_number=?, 
                    cgst_rate=?, sgst_rate=?, igst_rate=?, 
                    enable_cgst_sgst=?, enable_igst=?, hotel_rules=?
                WHERE id=1
            """, (name, address, address1, address2, gst, contact,
                  cgst_rate, sgst_rate, igst_rate,
                  enable_cgst_sgst, enable_igst, hotel_rules))
                  
            # 2. Save Local Charge Settings
            if not local_name or not local_type:
                raise ValueError("Local charge name and calculation type are required if enabled.")
                
            cursor.execute("""
                UPDATE local_charges
                SET enabled=?, charge_name=?, amount=?, calculation_type=?
                WHERE id=1
            """, (local_enabled, local_name, local_amount, local_type))


            self.db_conn.commit()
            messagebox.showinfo("Success", "Hotel settings saved successfully.")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    # Hotel Rules helpers (manage showing up to 10 single-line rules)
    def _add_rule_line(self):
        """Expose one more rule input line up to a maximum of 10."""
        try:
            if self._hotel_rules_visible_count >= 10:
                messagebox.showinfo("Limit Reached", "Maximum of 10 rule lines allowed.", parent=self)
                return
            idx = self._hotel_rules_visible_count
            ent = self.hotel_rule_entries[idx]
            ent.grid(row=idx, column=0, sticky='we', pady=2)
            self._hotel_rules_visible_count += 1
        except Exception:
            pass

    def _remove_rule_line(self):
        """Hide the last visible optional rule line (do not delete content unless user explicitly clears it)."""
        try:
            if self._hotel_rules_visible_count <= 7:
                messagebox.showinfo("Minimum Visible", "At least 7 rule lines remain visible by default.", parent=self)
                return
            idx = self._hotel_rules_visible_count - 1
            ent = self.hotel_rule_entries[idx]
            ent.grid_forget()
            self._hotel_rules_visible_count -= 1
        except Exception:
            pass

    def _make_scrollable(self, canvas):
        """Enable smooth scrolling (mouse wheel + keyboard) for the provided Canvas.

        Binds mouse wheel when the pointer is over the canvas and unbinds when it leaves.
        Supports Windows, macOS and X11 (Button-4/5) and adds keyboard support for arrows and page keys.
        """
        def _on_mousewheel(event):
            try:
                if platform.system() == 'Windows':
                    # On Windows, event.delta is multiples of 120
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                elif platform.system() == 'Darwin':
                    # macOS sends smaller delta values
                    canvas.yview_scroll(int(-1 * event.delta), 'units')
                else:
                    # X11: use Button-4 (up) and Button-5 (down)
                    if hasattr(event, 'num'):
                        if event.num == 4:
                            canvas.yview_scroll(-1, 'units')
                        elif event.num == 5:
                            canvas.yview_scroll(1, 'units')
            except Exception:
                pass

        def _on_up(e):
            canvas.yview_scroll(-1, 'units')

        def _on_down(e):
            canvas.yview_scroll(1, 'units')

        def _on_page_up(e):
            canvas.yview_scroll(-1, 'pages')

        def _on_page_down(e):
            canvas.yview_scroll(1, 'pages')

        def _on_home(e):
            canvas.yview_moveto(0)

        def _on_end(e):
            canvas.yview_moveto(1)

        def _bind_all(e=None):
            # Bind wheel and keyboard events when cursor enters canvas
            canvas.bind_all('<MouseWheel>', _on_mousewheel)
            canvas.bind_all('<Button-4>', _on_mousewheel)
            canvas.bind_all('<Button-5>', _on_mousewheel)
            canvas.bind_all('<Up>', _on_up)
            canvas.bind_all('<Down>', _on_down)
            canvas.bind_all('<Prior>', _on_page_up)
            canvas.bind_all('<Next>', _on_page_down)
            canvas.bind_all('<Home>', _on_home)
            canvas.bind_all('<End>', _on_end)

        def _unbind_all(e=None):
            # Unbind global handlers when cursor leaves to avoid capturing events elsewhere
            try:
                canvas.unbind_all('<MouseWheel>')
                canvas.unbind_all('<Button-4>')
                canvas.unbind_all('<Button-5>')
                canvas.unbind_all('<Up>')
                canvas.unbind_all('<Down>')
                canvas.unbind_all('<Prior>')
                canvas.unbind_all('<Next>')
                canvas.unbind_all('<Home>')
                canvas.unbind_all('<End>')
            except Exception:
                pass

        # Bind enter/leave to scope the global binds to when pointer is over the canvas
        canvas.bind('<Enter>', _bind_all)
        canvas.bind('<Leave>', _unbind_all)

    # --- REMOVED: Extra Charges Management Helper Methods ---


    # --- VERSION 2.0: New Tab for Booking History (MODIFIED: Added Search & 180-day default) ---
    def setup_history_tab(self):
        for widget in self.history_tab.winfo_children():
            widget.destroy()

        frame = ttk.Frame(self.history_tab, padding=10)
        frame.pack(fill='both', expand=True)

        # Filter functionality
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill='x', pady=5)
        
        # Row 1: Search Box
        ttk.Label(filter_frame, text="Search (Ref #, Name, Room #):").pack(side='left', padx=(0, 5))
        self.history_search_entry = ttk.Entry(filter_frame, width=30)
        self.history_search_entry.pack(side='left', padx=5, ipady=3)

        # Row 2: Days Filter
        ttk.Label(filter_frame, text="Show Past Bookings from last").pack(side='left', padx=(15, 5))
        self.history_days_entry = ttk.Entry(filter_frame, width=5)
        self.history_days_entry.insert(0, "180") # <-- CHANGED TO 180 DAYS
        self.history_days_entry.pack(side='left', padx=5, ipady=3)
        ttk.Label(filter_frame, text="days").pack(side='left', padx=5)

        ttk.Button(filter_frame, text="Apply Filters / Refresh History", command=self.load_history_data).pack(side='left', padx=10)

        # Treeview for history
        cols = ('Ref #', 'Guest Name', 'Room #', 'Check-In', 'Check-Out', 'Status', 'Total Bill', 'Persons')
        self.history_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        for col in cols:
            self.history_tree.heading(col, text=col)
        self.history_tree.column('Ref #', width=120, anchor='center')
        self.history_tree.column('Guest Name', width=150)
        self.history_tree.column('Room #', width=80, anchor='center')
        # V2.1: Widen columns for timestamps
        self.history_tree.column('Check-In', width=150, anchor='center')
        self.history_tree.column('Check-Out', width=150, anchor='center')
        self.history_tree.column('Status', width=80, anchor='center')
        self.history_tree.column('Total Bill', width=100, anchor='e')
        self.history_tree.column('Persons', width=80, anchor='center')

        self.history_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.history_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)
        
        # Add binding to show detailed guest info and actions
        self.history_tree.bind('<<TreeviewSelect>>', self.show_detailed_history_info)


        self.history_tree.pack(fill='both', expand=True, pady=10)
        
        # --- MODIFIED: Frame for detailed history actions/details ---
        self.detailed_history_frame = ttk.Labelframe(frame, text="Detailed Booking Information & Actions", padding=10)
        self.detailed_history_frame.pack(fill='x', pady=(0, 5))
        
        self.history_detail_label = ttk.Label(self.detailed_history_frame, text="Select a booking above to view associated documents and actions.", justify=tk.LEFT)
        self.history_detail_label.pack(fill='x')
        
        # Action buttons for history
        history_action_frame = ttk.Frame(self.detailed_history_frame)
        history_action_frame.pack(fill='x', pady=(5,0))
        
        self.reprint_button = ttk.Button(history_action_frame, text="Reprint Invoice", command=self.reprint_invoice_from_history, style="Accent.TButton", state=tk.DISABLED)
        self.reprint_button.pack(side='left', padx=5, ipady=5)
        
        self.save_pdf_button = ttk.Button(history_action_frame, text="Save Invoice PDF", command=self.save_invoice_from_history, style="Accent.TButton", state=tk.DISABLED)
        self.save_pdf_button.pack(side='left', padx=5, ipady=5)
    # Note: Edit/Delete actions have been moved to the 'Bookings & Guests' tab to centralize active booking management.
    # The History tab remains read-only for past bookings; admins should use the Bookings tab to edit or delete active records.
        # --- END MODIFIED ---


        self.load_history_data()
        
    def show_detailed_history_info(self, event):
        """Displays documents for non-primary guests and enables actions for the selected booking."""
        selected_item = self.history_tree.focus()
        if not selected_item:
            self.history_detail_label.config(text="Select a booking above to view associated documents and actions.")
            self.reprint_button.config(state=tk.DISABLED)
            self.save_pdf_button.config(state=tk.DISABLED)
            return

        item_values = self.history_tree.item(selected_item)['values']
        booking_ref = item_values[0]
        status = item_values[5]
        
        # Enable/Disable buttons based on status
        if status in ['Checked-Out']:
            self.reprint_button.config(state=tk.NORMAL)
            self.save_pdf_button.config(state=tk.NORMAL)
        else:
            self.reprint_button.config(state=tk.DISABLED)
            self.save_pdf_button.config(state=tk.DISABLED)
        # Enable edit/delete only for Admin/SuperAdmin
        role = getattr(self, 'user_role', None)
        can_modify = role in ('Admin', 'SuperAdmin')
        if can_modify:
            self.edit_booking_button.config(state=tk.NORMAL)
            # Only allow delete for non-checked-out bookings for Admin; SuperAdmin may delete any
            if role == 'SuperAdmin':
                self.delete_booking_button.config(state=tk.NORMAL)
            else:
                # Admin: allow delete only if booking is Reserved or Cancelled
                if status in ('Reserved', 'Cancelled'):
                    self.delete_booking_button.config(state=tk.NORMAL)
                else:
                    self.delete_booking_button.config(state=tk.DISABLED)
        else:
            self.edit_booking_button.config(state=tk.DISABLED)
            self.delete_booking_button.config(state=tk.DISABLED)

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT person_name, is_primary
            FROM booking_persons
            WHERE booking_ref = ?
            ORDER BY is_primary DESC, person_name
        """, (booking_ref,))

        persons = cursor.fetchall()

        if not persons:
            self.history_detail_label.config(text=f"Booking Ref: {booking_ref} | Status: {status}\nNo associated guest records found.")
            return

        details = [f"Booking Ref: {booking_ref} | Status: {status}\n\nGuests:\n"]
        for name, is_primary in persons:
            primary_tag = "(Primary Guest)" if is_primary == 'true' else ""
            details.append(f"• Name: {name} {primary_tag}")

        # Also include all room numbers associated with this booking_ref
        try:
            cursor.execute("SELECT GROUP_CONCAT(r.room_number, ',') FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.booking_ref = ?", (booking_ref,))
            rooms_row = cursor.fetchone()
            rooms_list = rooms_row[0] if rooms_row and rooms_row[0] else ''
            if rooms_list:
                details.insert(1, f"Rooms: {rooms_list}\n")
        except Exception:
            pass

        self.history_detail_label.config(text="\n".join(details))

    # --- NEW: History Actions ---
    def _prepare_bill_data_for_history(self, booking_ref):
        """Utility to fetch all necessary data to reconstruct the bill for PDF generation."""
        cursor = self.db_conn.cursor()

        # 1. Get Booking/Guest/Room/Hotel/Final Totals (Crucial for checked-out bookings)
        cursor.execute("""
            SELECT b.id, g.name, g.phone, r.room_number, r.rate, b.check_in, b.check_out,
                   s.hotel_name, s.address, s.gst_number, s.contact_number, r.id as room_id, b.advance_payment,
                   b.num_adults, b.num_children, b.total_amount, b.actual_check_in, b.actual_check_out
            FROM bookings b
            JOIN guests g ON b.guest_id = g.id
            JOIN rooms r ON b.room_id = r.id
            JOIN settings s ON s.id = 1
            WHERE b.booking_ref = ? AND b.status='Checked-Out'
        """, (booking_ref,))
        rows = cursor.fetchall()

        if not rows:
            messagebox.showerror("Error", "Could not retrieve checked-out booking details for reprint.")
            return None

        # Aggregate across all rows in the group booking
        booking_ids = [r[0] for r in rows]
        guest_name = rows[0][1]
        guest_phone = rows[0][2]
        hotel_name = rows[0][7]
        hotel_address = rows[0][8]
        hotel_gst = rows[0][9]
        hotel_contact = rows[0][10]
        advance_payment = rows[0][12]

        # Room numbers and room ids
        room_numbers = [str(r[3]) for r in rows]
        room_number = ','.join(room_numbers)

        # Compute earliest check-in and latest check-out across the group
        def _parse_dt_safe(s):
            if not s:
                return None
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y'):
                try:
                    return datetime.strptime(str(s), fmt)
                except Exception:
                    continue
            try:
                return datetime.fromisoformat(str(s))
            except Exception:
                return None

        cis = []
        cos = []
        room_total = 0.0
        for r in rows:
            rate = float(r[4] or 0.0)
            # prefer actual timestamps if available
            actual_in = r[16]
            actual_out = r[17]
            ci = _parse_dt_safe(actual_in) or _parse_dt_safe(r[5])
            co = _parse_dt_safe(actual_out) or _parse_dt_safe(r[6])
            if ci:
                cis.append(ci)
            if co:
                cos.append(co)
            # compute nights for this row
            try:
                if ci and co:
                    nights = (co.date() - ci.date()).days
                    if nights <= 0:
                        nights = 1
                else:
                    nights = 1
            except Exception:
                nights = 1
            room_total += nights * rate

        earliest_ci = min(cis) if cis else None
        latest_co = max(cos) if cos else None
        if earliest_ci and latest_co:
            num_nights = (latest_co.date() - earliest_ci.date()).days
            if num_nights <= 0:
                num_nights = 1
        else:
            num_nights = 1

        # Restaurant totals & items aggregated across all booking ids
        restaurant_total = 0.0
        restaurant_items = []
        try:
            placeholders = ','.join(['?'] * len(booking_ids))
            cursor.execute(f"SELECT SUM(price_at_order * quantity) FROM restaurant_orders WHERE booking_id IN ({placeholders})", booking_ids)
            restaurant_total = cursor.fetchone()[0] or 0.0

            cursor.execute(f"SELECT m.item_name, o.quantity, o.price_at_order, (o.quantity * o.price_at_order) FROM restaurant_orders o JOIN restaurant_menu m ON o.item_id = m.id WHERE o.booking_id IN ({placeholders}) ORDER BY o.order_date", booking_ids)
            restaurant_items = cursor.fetchall()
        except Exception:
            restaurant_total = 0.0
            restaurant_items = []

        # Local government charge based on aggregated persons and group duration
        total_persons = 0
        try:
            total_persons = sum(int(r[13] or 0) + int(r[14] or 0) for r in rows)
        except Exception:
            total_persons = (rows[0][13] or 0) + (rows[0][14] or 0)

        local_charge_info = self.calculate_local_charge(num_nights, total_persons)

        # Determine grand total: prefer stored total_amount if present on any row (assume consistent), else compute
        grand_totals = [r[15] for r in rows if r[15] is not None]
        if grand_totals:
            grand_total = grand_totals[0]
        else:
            grand_total = room_total + restaurant_total

        # Subtotal before tax (taxable base guess)
        taxable_sub_total = room_total + local_charge_info.get('amount', 0.0)
        sub_total = taxable_sub_total + restaurant_total

        # Try to infer tax split (best-effort) using stored settings
        tax_settings = self._get_tax_settings()
        cgst_amount = 0.0
        sgst_amount = 0.0
        igst_amount = 0.0
        tax_type_to_display = 'none'

        # Compute tax amounts directly from the taxable_sub_total using stored tax settings.
        # This is more reliable than trying to infer tax from the stored grand_total.
        if tax_settings['enable_igst']:
            igst_amount = taxable_sub_total * (tax_settings['igst_rate'] / 100.0)
            cgst_amount = 0.0
            sgst_amount = 0.0
            tax_type_to_display = 'igst'
        elif tax_settings['enable_cgst_sgst']:
            cgst_amount = taxable_sub_total * (tax_settings['cgst_rate'] / 100.0)
            sgst_amount = taxable_sub_total * (tax_settings['sgst_rate'] / 100.0)
            igst_amount = 0.0
            tax_type_to_display = 'cgsg'
        else:
            cgst_amount = 0.0
            sgst_amount = 0.0
            igst_amount = 0.0

        # Choose representative fields from first row where single-value is expected elsewhere
        representative = rows[0]
        room_rate = float(representative[4] or 0.0)
        room_id = representative[11]

        return {
            "booking_ref": booking_ref,
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "room_number": room_number,
            "check_in": (earliest_ci.strftime('%Y-%m-%d') if earliest_ci else None),
            "check_out": (latest_co.strftime('%Y-%m-%d') if latest_co else None),
            "num_nights": num_nights,
            "room_rate": room_rate,
            "room_total": room_total,
            "restaurant_total": restaurant_total,
            "restaurant_items": restaurant_items,
            "advance_payment": advance_payment or 0.0,
            "hotel_name": hotel_name,
            "hotel_address": hotel_address,
            "hotel_gst": hotel_gst,
            "hotel_contact": hotel_contact,
            "room_id": room_id,
            "local_charge_info": local_charge_info,
            "num_adults": sum(int(r[13] or 0) for r in rows),
            "num_children": sum(int(r[14] or 0) for r in rows),
            # Any difference between stored grand_total and the recomputed components is treated as manual/other charges
            "extra_charges_total": max(0.0, grand_total - (taxable_sub_total + restaurant_total + (cgst_amount + sgst_amount + igst_amount))),
            "extra_charges_list": [],
            "sub_total": sub_total,
            "grand_total": grand_total,
            "cgst_amount": cgst_amount,
            "sgst_amount": sgst_amount,
            "igst_amount": igst_amount,
            "tax_type_to_display": tax_type_to_display
        }
        
    def reprint_invoice_from_history(self):
        """Re-generates and prints the invoice PDF from history data."""
        selected_item = self.history_tree.focus()
        if not selected_item: return

        booking_ref = self.history_tree.item(selected_item)['values'][0]
        bill_data = self._prepare_bill_data_for_history(booking_ref)
        
        if bill_data:
            utility = BillUtility(self, bill_data)
            utility.tax_type_to_display = bill_data['tax_type_to_display']
            utility.print_invoice(self)
        
    def save_invoice_from_history(self):
        """Re-generates and saves the invoice PDF from history data."""
        selected_item = self.history_tree.focus()
        if not selected_item: return

        booking_ref = self.history_tree.item(selected_item)['values'][0]
        bill_data = self._prepare_bill_data_for_history(booking_ref)
        
        if bill_data:
            utility = BillUtility(self, bill_data)
            utility.tax_type_to_display = bill_data['tax_type_to_display']
            utility.save_pdf(self)

    def delete_booking_from_history(self):
        """Deletes the selected booking (Admin/SuperAdmin only). Removes related booking_persons and restaurant_orders, but not guest record."""
        selected_item = self.history_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "No booking selected.", parent=self.history_tab)
            return
        booking_ref = self.history_tree.item(selected_item)['values'][0]

        # Confirm
        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete booking {booking_ref}? This will remove associated orders and guest links but will NOT delete the guest record.", parent=self.history_tab):
            return

        try:
            cursor = self.db_conn.cursor()
            # Handle group bookings: collect all booking rows for this booking_ref
            cursor.execute("SELECT id, status FROM bookings WHERE booking_ref=?", (booking_ref,))
            rows = cursor.fetchall()
            if not rows:
                messagebox.showerror("Error", "Booking not found in database.", parent=self.history_tab)
                return

            booking_ids = [r[0] for r in rows]
            statuses = set(r[1] for r in rows)
            role = getattr(self, 'user_role', None)
            # Admin restrictions: if any row is in an active state, disallow for Admin
            if role == 'Admin' and any(s not in ('Reserved', 'Cancelled') for s in statuses):
                messagebox.showerror("Permission Denied", "Admin may only delete bookings that are Reserved or Cancelled.", parent=self.history_tab)
                return

            # Delete related restaurant orders for all booking ids and booking_persons, then bookings
            for bid in booking_ids:
                try:
                    cursor.execute("DELETE FROM restaurant_orders WHERE booking_id=?", (bid,))
                except Exception:
                    # continue deleting other related rows even if one fails
                    logger.exception("Failed to delete restaurant orders for booking_id %s", bid)
            cursor.execute("DELETE FROM booking_persons WHERE booking_ref=?", (booking_ref,))
            cursor.execute("DELETE FROM bookings WHERE booking_ref=?", (booking_ref,))
            self.db_conn.commit()
            messagebox.showinfo("Deleted", f"Booking {booking_ref} and related data have been deleted.", parent=self.history_tab)
            self.load_history_data()
            self.refresh_dashboard()
        except Exception as e:
            self.db_conn.rollback()
            messagebox.showerror("Error", f"Could not delete booking: {e}", parent=self.history_tab)

    def edit_booking_from_history(self):
        """Opens a small dialog to edit booking dates and status."""
        selected_item = self.history_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "No booking selected.", parent=self.history_tab)
            return
        booking_ref = self.history_tree.item(selected_item)['values'][0]

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, check_in, check_out, status, room_id, num_adults, num_children, num_rooms FROM bookings WHERE booking_ref=?", (booking_ref,))
        row = cursor.fetchone()
        if not row:
            messagebox.showerror("Error", "Booking not found.", parent=self.history_tab)
            return
        booking_id, check_in, check_out, status, room_id, num_adults, num_children, num_rooms = row

        role = getattr(self, 'user_role', None)
        if role not in ('Admin', 'SuperAdmin'):
            messagebox.showerror("Permission Denied", "Only Admin or SuperAdmin can edit bookings.", parent=self.history_tab)
            return

        # Small edit dialog
        edit_win = tk.Toplevel(self)
        edit_win.transient(self)
        edit_win.grab_set()
        edit_win.title(f"Edit Booking {booking_ref}")
        edit_win.geometry("660x660")

        frm = ttk.Frame(edit_win, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Check-In (YYYY-MM-DD HH:MM):").grid(row=0, column=0, sticky='w')
        ci_entry = ttk.Entry(frm, width=30)
        ci_entry.grid(row=0, column=1, pady=5)
        ci_entry.insert(0, check_in)

        ttk.Label(frm, text="Check-Out (YYYY-MM-DD HH:MM):").grid(row=1, column=0, sticky='w')
        co_entry = ttk.Entry(frm, width=30)
        co_entry.grid(row=1, column=1, pady=5)
        co_entry.insert(0, check_out)

        ttk.Label(frm, text="Status:").grid(row=2, column=0, sticky='w')
        status_combo = ttk.Combobox(frm, values=['Reserved', 'Checked-In', 'Checked-Out', 'Cancelled'], width=20)
        status_combo.grid(row=2, column=1, pady=5)
        status_combo.set(status)

        ttk.Label(frm, text="Adults:").grid(row=3, column=0, sticky='w')
        adults_entry = ttk.Entry(frm, width=10)
        adults_entry.grid(row=3, column=1, sticky='w')
        adults_entry.insert(0, str(num_adults or 1))

        ttk.Label(frm, text="Children:").grid(row=4, column=0, sticky='w')
        children_entry = ttk.Entry(frm, width=10)
        children_entry.grid(row=4, column=1, sticky='w')
        children_entry.insert(0, str(num_children or 0))

        def _save_edit():
            new_ci = ci_entry.get().strip()
            new_co = co_entry.get().strip()
            new_status = status_combo.get()
            try:
                # Minimal validation: ensure parseable (allow both date or datetime strings)
                # Try parsing full datetime first
                try:
                    datetime.strptime(new_ci, '%Y-%m-%d %H:%M')
                except Exception:
                    # fallback to date only
                    datetime.strptime(new_ci, '%Y-%m-%d')
                try:
                    datetime.strptime(new_co, '%Y-%m-%d %H:%M')
                except Exception:
                    datetime.strptime(new_co, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD or YYYY-MM-DD HH:MM formats.", parent=edit_win)
                return

            # Simple conflict check if room_id set and status implies occupancy
            if room_id and new_status in ('Reserved', 'Checked-In'):
                cursor.execute("SELECT COUNT(*) FROM bookings WHERE room_id=? AND booking_ref!=? AND status IN ('Reserved','Checked-In') AND check_in <= ? AND check_out >= ?", (room_id, booking_ref, new_co, new_ci))
                conflict = cursor.fetchone()[0]
                if conflict > 0:
                    messagebox.showerror("Conflict", "Selected dates conflict with another booking for the same room.", parent=edit_win)
                    return

            try:
                cursor.execute("UPDATE bookings SET check_in=?, check_out=?, status=?, num_adults=?, num_children=? WHERE booking_ref=?", (new_ci, new_co, new_status, int(adults_entry.get()), int(children_entry.get()), booking_ref))
                self.db_conn.commit()
                messagebox.showinfo("Saved", "Booking updated successfully.", parent=edit_win)
                edit_win.destroy()
                self.load_history_data()
                self.refresh_dashboard()
            except Exception as e:
                self.db_conn.rollback()
                messagebox.showerror("Error", f"Could not save changes: {e}", parent=edit_win)

        btn_frame = ttk.Frame(edit_win)
        btn_frame.pack(side='bottom', fill='x', pady=8)
        ttk.Button(btn_frame, text="Save Changes", command=_save_edit, style="Accent.TButton").pack(side='right', padx=8)
        ttk.Button(btn_frame, text="Cancel", command=edit_win.destroy).pack(side='right')

    # --- Booking actions wired into Bookings & Guests tab (mirrors history actions but operates on bookings_tree) ---
    def delete_booking_from_bookings(self):
        """Deletes the selected booking from the Bookings tab (Admin/SuperAdmin only)."""
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "No booking selected.", parent=self.bookings_tab)
            return
        booking_ref = self.bookings_tree.item(selected_item)['values'][0]

        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete booking {booking_ref}? This will remove associated orders and guest links but will NOT delete the guest record.", parent=self.bookings_tab):
            return

        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, status FROM bookings WHERE booking_ref=?", (booking_ref,))
            rows = cursor.fetchall()
            if not rows:
                messagebox.showerror("Error", "Booking not found in database.", parent=self.bookings_tab)
                return

            booking_ids = [r[0] for r in rows]
            statuses = set(r[1] for r in rows)
            role = getattr(self, 'user_role', None)
            if role == 'Admin' and any(s not in ('Reserved', 'Cancelled') for s in statuses):
                messagebox.showerror("Permission Denied", "Admin may only delete bookings that are Reserved or Cancelled.", parent=self.bookings_tab)
                return

            for bid in booking_ids:
                try:
                    cursor.execute("DELETE FROM restaurant_orders WHERE booking_id=?", (bid,))
                except Exception:
                    logger.exception("Failed to delete restaurant orders for booking_id %s", bid)

            cursor.execute("DELETE FROM booking_persons WHERE booking_ref=?", (booking_ref,))
            cursor.execute("DELETE FROM bookings WHERE booking_ref=?", (booking_ref,))
            self.db_conn.commit()
            messagebox.showinfo("Deleted", f"Booking {booking_ref} and related data have been deleted.", parent=self.bookings_tab)
            self.load_bookings_data()
            self.refresh_dashboard()
        except Exception as e:
            try:
                self.db_conn.rollback()
            except Exception:
                logger.exception("Rollback failed after delete_booking_from_bookings error")
            messagebox.showerror("Error", f"Could not delete booking: {e}", parent=self.bookings_tab)


    def edit_booking_from_bookings(self):
        """Opens an edit dialog for the selected booking in Bookings tab."""
        selected_item = self.bookings_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "No booking selected.", parent=self.bookings_tab)
            return
        booking_ref = self.bookings_tree.item(selected_item)['values'][0]

        cursor = self.db_conn.cursor()
        # Fetch all booking rows for this reference so we can allow per-row edits for group bookings
        cursor.execute("SELECT id, guest_id, check_in, check_out, status, room_id, num_adults, num_children, num_rooms FROM bookings WHERE booking_ref=?", (booking_ref,))
        all_rows = cursor.fetchall()
        if not all_rows:
            messagebox.showerror("Error", "Booking not found.", parent=self.bookings_tab)
            return

        # If this is a group booking (multiple rows), allow the user to choose which room rows to edit
        if len(all_rows) > 1:
            # Build a simple modal to let the user pick one or more booking rows from the group
            def _open_row_selector(rows):
                sel_win = tk.Toplevel(self)
                sel_win.transient(self)
                sel_win.grab_set()
                sel_win.title(f"Select room(s) to edit for {booking_ref}")
                sel_win.geometry('500x560')
                try:
                    sel_win.minsize(360, 240)
                    sel_win.resizable(True, True)
                except Exception:
                    pass

                frm_sel = ttk.Frame(sel_win, padding=10)
                frm_sel.pack(fill='both', expand=True)

                ttk.Label(frm_sel, text='Select room rows to apply edits to:', font=('Helvetica', 10, 'bold')).pack(pady=(0,6))
                canvas = tk.Canvas(frm_sel)
                vsb = ttk.Scrollbar(frm_sel, orient='vertical', command=canvas.yview)
                inner = ttk.Frame(canvas)
                inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
                canvas.create_window((0,0), window=inner, anchor='nw')
                canvas.configure(yscrollcommand=vsb.set, height=140)
                canvas.pack(side='left', fill='both', expand=True)
                vsb.pack(side='right', fill='y')

                var_map = {}
                for rid, g_id, ci, co, st, r_id, na, nc, nr in rows:
                    try:
                        cursor.execute('SELECT room_number FROM rooms WHERE id=?', (r_id,))
                        rn = cursor.fetchone()
                        room_no = rn[0] if rn else str(r_id)
                    except Exception:
                        room_no = str(r_id)
                    lbl = f"ID:{rid} Room:{room_no} [{self.format_datetime_for_display(ci)} -> {self.format_datetime_for_display(co)}] Status:{st}"
                    v = tk.IntVar(value=1 if len(rows)==1 else 0)
                    cb = ttk.Checkbutton(inner, text=lbl, variable=v)
                    cb.pack(anchor='w', pady=2)
                    var_map[rid] = v

                res = {'ids': None}

                def _on_ok():
                    chosen = [rid for rid, v in var_map.items() if v.get()]
                    if not chosen:
                        messagebox.showwarning('No selection', 'Please select at least one room row to edit.', parent=sel_win)
                        return
                    res['ids'] = chosen
                    sel_win.destroy()

                def _on_cancel():
                    sel_win.destroy()

                btnf = ttk.Frame(frm_sel)
                # Anchor button frame to bottom so OK/Cancel remain visible on small/resized windows
                btnf.pack(side='bottom', fill='x', pady=8)
                inner_btns = ttk.Frame(btnf)
                inner_btns.pack()
                ttk.Button(inner_btns, text='OK', command=_on_ok, style='Accent.TButton').pack(side='left', padx=6)
                ttk.Button(inner_btns, text='Cancel', command=_on_cancel).pack(side='left')

                sel_win.wait_window()
                return res['ids']

            selected_booking_ids = _open_row_selector(all_rows)
            if not selected_booking_ids:
                return

            # Use the first selected booking row to prefill the edit dialog
            sel_id = selected_booking_ids[0]
            cursor.execute("SELECT id, guest_id, check_in, check_out, status, room_id, num_adults, num_children, num_rooms FROM bookings WHERE id=?", (sel_id,))
            row = cursor.fetchone()
            if not row:
                messagebox.showerror("Error", "Selected booking row not found.", parent=self.bookings_tab)
                return
            booking_id, guest_id, check_in, check_out, status, room_id, num_adults, num_children, num_rooms = row
            target_booking_ids = selected_booking_ids
        else:
            # Single-row booking: proceed to edit that row only
            row = all_rows[0]
            booking_id, guest_id, check_in, check_out, status, room_id, num_adults, num_children, num_rooms = row
            target_booking_ids = [booking_id]

        # fetch primary guest name
        try:
            cursor.execute("SELECT name FROM guests WHERE id=?", (guest_id,))
            guest_row = cursor.fetchone()
            guest_name = guest_row[0] if guest_row else ''
        except Exception:
            guest_name = ''

        role = getattr(self, 'user_role', None)
        if role not in ('Admin', 'SuperAdmin'):
            messagebox.showerror("Permission Denied", "Only Admin or SuperAdmin can edit bookings.", parent=self.bookings_tab)
            return

        edit_win = tk.Toplevel(self)
        edit_win.transient(self)
        edit_win.grab_set()
        edit_win.title(f"Edit Booking {booking_ref}")
        edit_win.geometry("660x660")

        frm = ttk.Frame(edit_win, padding=10)
        frm.pack(fill='both', expand=True)

        # Guest editable fields
        ttk.Label(frm, text="Guest Name:").grid(row=0, column=0, sticky='w')
        guest_name_entry = ttk.Entry(frm, width=30)
        guest_name_entry.grid(row=0, column=1, pady=5)
        guest_name_entry.insert(0, guest_name)

        ttk.Label(frm, text="Room Number:").grid(row=1, column=0, sticky='w')
        # Populate room numbers
        cursor.execute("SELECT room_number FROM rooms ORDER BY room_number")
        rooms_list = [r[0] for r in cursor.fetchall()]
        room_combo = ttk.Combobox(frm, values=rooms_list, width=28)
        # get current room number
        try:
            cursor.execute("SELECT room_number FROM rooms WHERE id=?", (room_id,))
            rn = cursor.fetchone()
            current_room_number = rn[0] if rn else ''
        except Exception:
            current_room_number = ''
        room_combo.set(current_room_number)
        room_combo.grid(row=1, column=1, pady=5)

        # Date/time editing (show in DD/MM/YYYY HH:MM format)
        ttk.Label(frm, text="Check-In (DD/MM/YYYY HH:MM):").grid(row=2, column=0, sticky='w')
        ci_entry = ttk.Entry(frm, width=30)
        ci_entry.grid(row=2, column=1, pady=5)
        try:
            ci_entry.insert(0, self.format_datetime_for_display(check_in))
        except Exception:
            ci_entry.insert(0, check_in)

        ttk.Label(frm, text="Check-Out (DD/MM/YYYY HH:MM):").grid(row=3, column=0, sticky='w')
        co_entry = ttk.Entry(frm, width=30)
        co_entry.grid(row=3, column=1, pady=5)
        try:
            co_entry.insert(0, self.format_datetime_for_display(check_out))
        except Exception:
            co_entry.insert(0, check_out)

        ttk.Label(frm, text="Status:").grid(row=4, column=0, sticky='w')
        status_combo = ttk.Combobox(frm, values=['Reserved', 'Checked-In', 'Checked-Out', 'Cancelled'], width=20)
        status_combo.grid(row=4, column=1, pady=5)
        status_combo.set(status)

        ttk.Label(frm, text="Adults:").grid(row=5, column=0, sticky='w')
        adults_entry = ttk.Entry(frm, width=10)
        adults_entry.grid(row=5, column=1, sticky='w')
        adults_entry.insert(0, str(num_adults or 1))

        ttk.Label(frm, text="Children:").grid(row=6, column=0, sticky='w')
        children_entry = ttk.Entry(frm, width=10)
        children_entry.grid(row=6, column=1, sticky='w')
        children_entry.insert(0, str(num_children or 0))

        def _save_edit():
            # Read and normalize inputs
            new_guest_name = guest_name_entry.get().strip()
            new_room_number = room_combo.get().strip()
            new_ci_display = ci_entry.get().strip()
            new_co_display = co_entry.get().strip()
            new_status = status_combo.get()

            # Convert display dates (DD/MM/YYYY or ISO) to ISO-like for DB
            try:
                new_ci_iso = self._parse_display_date_to_iso(new_ci_display)
                new_co_iso = self._parse_display_date_to_iso(new_co_display)
            except Exception:
                messagebox.showerror("Invalid Date", "Please use DD/MM/YYYY or YYYY-MM-DD formats for dates.", parent=edit_win)
                return

            # Check room conflicts if status requires reservation/checked-in
            try:
                # Resolve room id from room number if changed
                cursor.execute("SELECT id FROM rooms WHERE room_number=?", (new_room_number,))
                room_row = cursor.fetchone()
                new_room_id = room_row[0] if room_row else None
            except Exception:
                new_room_id = None

            if new_room_id and new_status in ('Reserved', 'Checked-In'):
                cursor.execute("SELECT COUNT(*) FROM bookings WHERE room_id=? AND booking_ref!=? AND status IN ('Reserved','Checked-In') AND check_in <= ? AND check_out >= ?", (new_room_id, booking_ref, new_co_iso, new_ci_iso))
                conflict = cursor.fetchone()[0]
                if conflict > 0:
                    messagebox.showerror("Conflict", "Selected dates conflict with another booking for the same room.", parent=edit_win)
                    return

            try:
                # Update guest name if changed
                if new_guest_name:
                    cursor.execute("UPDATE guests SET name=? WHERE id=?", (new_guest_name, guest_id))

                # Update bookings rows selected (apply only to chosen booking ids)
                placeholders = ','.join(['?'] * len(target_booking_ids))
                params = [new_ci_iso, new_co_iso, new_status, int(adults_entry.get()), int(children_entry.get()), new_room_id or room_id] + target_booking_ids
                cursor.execute(f"UPDATE bookings SET check_in=?, check_out=?, status=?, num_adults=?, num_children=?, room_id=? WHERE id IN ({placeholders})", tuple(params))
                self.db_conn.commit()

                # If any of the updated rows had an advance payment, offer to regenerate the advance receipt
                try:
                    cur = self.db_conn.cursor()
                    placeholders2 = ','.join(['?'] * len(target_booking_ids))
                    cur.execute(f"SELECT SUM(advance_payment), MAX(guest_id) FROM bookings WHERE id IN ({placeholders2})", tuple(target_booking_ids))
                    adv_row = cur.fetchone() or (0.0, None)
                    total_advance = adv_row[0] or 0.0
                    adv_guest_id = adv_row[1]
                    if total_advance and float(total_advance) > 0.0:
                        if messagebox.askyesno("Reprint Advance Receipt", "An advance payment was recorded for the selected room(s). Reprint the advance receipt now?", parent=edit_win):
                            try:
                                # Build minimal pdf_data similar to ChangeDatesWindow but scoped to selected rows
                                cur.execute(f"SELECT r.room_type, r.rate FROM rooms r JOIN bookings b ON r.id=b.room_id WHERE b.id IN ({placeholders2}) LIMIT 1", tuple(target_booking_ids))
                                rr = cur.fetchone()
                                room_type = rr[0] if rr and rr[0] else ''
                                first_room_rate = float(rr[1]) if rr and rr[1] is not None else 0.0

                                # compute nights from new dates
                                try:
                                    nights = (datetime.strptime(new_co_iso[:16], '%Y-%m-%d %H:%M') - datetime.strptime(new_ci_iso[:16], '%Y-%m-%d %H:%M')).days
                                    if nights <= 0:
                                        nights = 1
                                except Exception:
                                    nights = 1

                                cur.execute(f"SELECT SUM(r.rate) FROM rooms r JOIN bookings b ON r.id=b.room_id WHERE b.id IN ({placeholders2})", tuple(target_booking_ids))
                                sum_rates = cur.fetchone()[0] or 0.0
                                total_room_cost = float(sum_rates) * nights

                                # local charge
                                # Use SUM to aggregate adults/children across all selected rows (was MAX which returned per-row max)
                                cur.execute(f"SELECT SUM(b.num_adults), SUM(b.num_children) FROM bookings b WHERE b.id IN ({placeholders2})", tuple(target_booking_ids))
                                persons = cur.fetchone() or (1, 0)
                                local_charge_info = self.calculate_local_charge_for_advance(nights, int(persons[0] or 1), int(persons[1] or 0))

                                # tax
                                tax_rates = self._get_tax_settings()
                                cgst = sgst = igst = 0.0
                                # Per user request: exclude Local Fee from advance receipt shown to guest.
                                # Compute taxes on room total only (projected for advance).
                                sub_total = total_room_cost
                                if tax_rates['enable_igst']:
                                    igst = sub_total * (tax_rates['igst_rate'] / 100.0)
                                elif tax_rates['enable_cgst_sgst']:
                                    cgst = sub_total * (tax_rates['cgst_rate'] / 100.0)
                                    sgst = sub_total * (tax_rates['sgst_rate'] / 100.0)

                                grand_total_after_tax = sub_total + cgst + sgst + igst

                                # guest info
                                cur.execute("SELECT name, phone, address FROM guests WHERE id=?", (adv_guest_id,))
                                g = cur.fetchone() or ('', '', '')

                                pdf_data = {
                                    'booking_ref': booking_ref,
                                    'hotel_name': '',
                                    'hotel_address': '',
                                    'hotel_address_line1': '',
                                    'hotel_address_line2': '',
                                    'hotel_gst': '',
                                    'hotel_contact': '',
                                    'hotel_rules': '',
                                    'guest_name': g[0],
                                    'guest_phone': g[1],
                                    'guest_address': g[2],
                                    'room_type': room_type,
                                    'num_rooms': len(target_booking_ids),
                                    'room_rate': first_room_rate,
                                    'check_in': datetime.strptime(new_ci_iso[:16], '%Y-%m-%d %H:%M').strftime('%d/%m/%Y') if new_ci_iso else '',
                                    'check_out': datetime.strptime(new_co_iso[:16], '%Y-%m-%d %H:%M').strftime('%d/%m/%Y') if new_co_iso else '',
                                    'num_nights': nights,
                                    'room_total': total_room_cost,
                                    'cgst_amount': cgst,
                                    'sgst_amount': sgst,
                                    'igst_amount': igst,
                                    'total_after_tax': grand_total_after_tax,
                                    'advance_paid': float(total_advance),
                                    'balance_due': grand_total_after_tax - float(total_advance),
                                    'num_adults': int(persons[0] or 1),
                                    'num_children': int(persons[1] or 0)
                                }

                                try:
                                    # Use the standalone generator so this code path does not rely on
                                    # the calling window or master having a method named
                                    # generate_advance_invoice_pdf (which may not exist).
                                    generate_advance_invoice_pdf_standalone(pdf_data)
                                    messagebox.showinfo('Advance Receipt', 'Advance receipt PDF generated/opened.', parent=edit_win)
                                except Exception as e:
                                    messagebox.showerror('PDF Error', f'Could not generate advance receipt: {e}', parent=edit_win)
                            except Exception as e:
                                messagebox.showerror('Error', f'Could not prepare advance receipt: {e}', parent=edit_win)
                except Exception:
                    pass

                messagebox.showinfo("Saved", "Booking updated successfully.", parent=edit_win)
                edit_win.destroy()
                self.load_bookings_data()
                self.refresh_dashboard()
            except Exception as e:
                try:
                    self.db_conn.rollback()
                except Exception:
                    logger.exception("Rollback failed after edit_booking_from_bookings error")
                messagebox.showerror("Error", f"Could not save changes: {e}", parent=edit_win)

        btn_frame = ttk.Frame(edit_win)
        btn_frame.pack(side='bottom', fill='x', pady=8)
        ttk.Button(btn_frame, text="Save Changes", command=_save_edit, style="Accent.TButton").pack(side='right', padx=8)
        ttk.Button(btn_frame, text="Cancel", command=edit_win.destroy).pack(side='right')

    def load_history_data(self):
        for i in self.history_tree.get_children():
            self.history_tree.delete(i)

        try:
            days = int(self.history_days_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Days must be a valid number.", parent=self.history_tab)
            return

        search_query = self.history_search_entry.get()

        cursor = self.db_conn.cursor()
        # V2.3: Aggregate rooms for group bookings using GROUP_CONCAT so a single booking_ref shows all room numbers
        query = """
            SELECT b.booking_ref, g.name, GROUP_CONCAT(r.room_number, ',') as rooms, 
                   MIN(IFNULL(b.actual_check_in, b.check_in)) AS check_in, 
                   MAX(IFNULL(b.actual_check_out, b.check_out)) AS check_out, 
                   b.status, IFNULL(SUM(b.total_amount), 0.0) as total_amount, 
                   MAX(b.num_adults) as num_adults, MAX(b.num_children) as num_children
            FROM bookings b
            JOIN guests g ON b.guest_id = g.id
            JOIN rooms r ON b.room_id = r.id
            WHERE b.status IN ('Checked-Out', 'Cancelled')
            AND b.check_out >= date('now', '-' || ? || ' days')
            GROUP BY b.booking_ref, g.name, b.status
        """
        params = [days]

        if search_query:
            query += " HAVING (b.booking_ref LIKE ? OR g.name LIKE ? OR rooms LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

        query += " ORDER BY check_out DESC"

        cursor.execute(query, params)

        for i, row in enumerate(cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            # Format the bill amount
            total_bill = f"Rs.{row[6]:.2f}" if row[6] else "N/A"

            # Format check-in/out times for display (DD/MM/YYYY HH:MM)
            check_in_val = self.format_datetime_for_display(row[3])
            check_out_val = self.format_datetime_for_display(row[4])

            # Format persons count
            persons_count = f"A:{row[7]}/C:{row[8]}"

            values = (row[0], row[1], row[2], check_in_val, check_out_val, row[5], total_bill, persons_count)
            self.history_tree.insert('', 'end', values=values, tags=(tag,))


    # --- NEW: User Management Tab (Admin Only) ---
    def setup_users_tab(self):
        """Set up the user management tab."""
        frame = ttk.Frame(self.users_tab, padding=10)
        frame.pack(fill='both', expand=True)

        # --- Add User Form ---
        form_frame = ttk.Labelframe(frame, text="Add New User", padding=15)
        form_frame.pack(fill='x', pady=10)

        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, padx=5, pady=8, sticky='w')
        self.new_user_entry = ttk.Entry(form_frame, width=30)
        self.new_user_entry.grid(row=0, column=1, padx=5, pady=8, ipady=3)

        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, padx=5, pady=8, sticky='w')
        self.new_pass_entry = ttk.Entry(form_frame, width=30, show="*")
        self.new_pass_entry.grid(row=1, column=1, padx=5, pady=8, ipady=3)

        ttk.Label(form_frame, text="Role:").grid(row=0, column=2, padx=(20, 5), pady=8, sticky='w')
        # Only SuperAdmin may create another SuperAdmin. Show SuperAdmin option only for SuperAdmin.
        role_choices = ["Admin", "Employee"]
        if getattr(self, 'user_role', None) == 'SuperAdmin':
            role_choices.insert(0, 'SuperAdmin')
        self.new_role_combo = ttk.Combobox(form_frame, values=role_choices, width=20)
        self.new_role_combo.set("Employee")
        self.new_role_combo.grid(row=0, column=3, padx=5, pady=8, ipady=3)

        ttk.Button(form_frame, text="Add User", command=self.add_user, style="Success.TButton").grid(row=1, column=3, padx=10, ipady=5)

        # --- User List ---
        list_frame = ttk.Labelframe(frame, text="Existing Users", padding=15)
        list_frame.pack(fill='both', expand=True, pady=10)

        cols = ('ID', 'Username', 'Role')
        self.users_tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='browse')
        self.users_tree.heading('ID', text='ID')
        self.users_tree.heading('Username', text='Username')
        self.users_tree.heading('Role', text='Role')
        self.users_tree.column('ID', width=50, anchor='center')
        self.users_tree.column('Username', width=200)
        self.users_tree.column('Role', width=100, anchor='center')

        self.users_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.users_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.users_tree.pack(side='left', fill='both', expand=True)

        user_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=user_scrollbar.set)
        user_scrollbar.pack(side='right', fill='y')

        # --- User Actions ---
        user_action_frame = ttk.Frame(frame)
        user_action_frame.pack(fill='x')

        ttk.Button(user_action_frame, text="Delete Selected User", command=self.delete_user, style="Danger.TButton").pack(side='left', padx=5, ipady=5)

        self.load_users_data()

    def load_users_data(self):
        """Load users into the user management treeview."""
        for i in self.users_tree.get_children():
            self.users_tree.delete(i)
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, username, role FROM users ORDER BY username")
        for i, row in enumerate(cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.users_tree.insert('', 'end', values=row, iid=row[0], tags=(tag,))

    def add_user(self):
        """Adds a new user to the database."""
        username = self.new_user_entry.get()
        password = self.new_pass_entry.get()
        role = self.new_role_combo.get()

        if not username or not password or not role:
            messagebox.showerror("Error", "All fields are required.", parent=self.users_tab)
            return

        try:
            cursor = self.db_conn.cursor()
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, password, role))
            self.db_conn.commit()
            logger.info("Added user '%s' with role '%s'", username, role)
            messagebox.showinfo("Success", "User added successfully.", parent=self.users_tab)
            self.new_user_entry.delete(0, 'end')
            self.new_pass_entry.delete(0, 'end')
            self.load_users_data()
        except sqlite3.IntegrityError:
            logger.warning("Attempt to add duplicate username: %s", username)
            messagebox.showerror("Error", f"Username '{username}' already exists.", parent=self.users_tab)
        except Exception as e:
            logger.exception("Error adding user %s: %s", username, e)
            messagebox.showerror("Error", f"An error occurred: {e}", parent=self.users_tab)

    def delete_user(self):
        """Deletes a selected user from the database."""
        selected_item = self.users_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a user to delete.", parent=self.users_tab)
            return

        item_values = self.users_tree.item(selected_item)['values']
        user_id, username = item_values[0], item_values[1]

        # --- CRITICAL: Protect the default admin and superadmin ---
        if username in ('admin', 'david'):
            messagebox.showerror("Action Prohibited", f"Cannot delete the default '{username}' account.", parent=self.users_tab)
            return

        # Prevent deleting SuperAdmin accounts unless current user is SuperAdmin
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT role FROM users WHERE id=?", (user_id,))
        role_row = cursor.fetchone()
        if role_row and role_row[0] == 'SuperAdmin' and getattr(self, 'user_role', None) != 'SuperAdmin':
            messagebox.showerror("Action Prohibited", "Only SuperAdmin can delete another SuperAdmin.", parent=self.users_tab)
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{username}'? This cannot be undone.", parent=self.users_tab):
            try:
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
                self.db_conn.commit()
                logger.info("Deleted user '%s' (id=%s) by user_role=%s", username, user_id, getattr(self, 'user_role', None))
                messagebox.showinfo("Success", f"User '{username}' deleted successfully.", parent=self.users_tab)
                self.load_users_data()
            except Exception as e:
                logger.exception("Error deleting user %s (id=%s): %s", username, user_id, e)
                messagebox.showerror("Error", f"An error occurred: {e}", parent=self.users_tab)


    ## --- MODIFIED: Backup & Restore Tab (Admin Only) ---
    def setup_backup_tab(self):
        """Set up the database backup and restore tab."""
        # Create a canvas and vertical scrollbar so the Backup tab can scroll when its
        # contents are larger than the available area (mouse wheel + keyboard support).
        canvas = tk.Canvas(self.backup_tab, bg=COLOR_LIGHT_BG, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.backup_tab, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=20)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # Ensure the canvas enter/leave handlers are triggered even when the
        # pointer is over widgets inside the inner frame. Some widgets receive
        # enter/leave instead of the canvas, so forward those events to the
        # canvas so _make_scrollable can bind/unbind mousewheel and keyboard
        # handlers reliably.
        frame.bind('<Enter>', lambda e: canvas.event_generate('<Enter>'))
        frame.bind('<Leave>', lambda e: canvas.event_generate('<Leave>'))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable smooth scrolling (mouse + keyboard) for backup tab
        try:
            self._make_scrollable(canvas)
        except Exception:
            pass

        # --- Backup Section ---
        backup_frame = ttk.Labelframe(frame, text="Database Backup (Local)", padding=20)
        backup_frame.pack(fill='x', pady=20)
        
        ttk.Label(backup_frame, text="Save a copy of the entire hotel database (bookings, rooms, settings, etc.) to a secure local backup file.", wraplength=500).pack(pady=5)
        ttk.Button(backup_frame, text="Backup Database (.nxt)", command=self.backup_database, style="Accent.TButton").pack(pady=15, ipady=8, ipadx=10)
        
        # --- Google Drive/Cloud Synchronization Section (Simulated) ---
        cloud_frame = ttk.Labelframe(frame, text="Cloud Synchronization (Google Drive)", padding=20)
        cloud_frame.pack(fill='x', pady=20)

        ttk.Label(cloud_frame, 
                  text="To enable **automatic backup** on every data entry and restore from Google Drive, the software requires advanced setup with Google's API, including OAuth authentication and local token management. This functionality is planned for a future enterprise version.",
                  wraplength=500,
                  foreground=COLOR_WARNING,
                  font=('Helvetica', 10, 'bold')).pack(pady=5)
        ttk.Label(cloud_frame, 
                  text="Current operation remains local for security and simplicity.",
                  wraplength=500).pack(pady=5)
        
        ttk.Button(cloud_frame, text="Sync Now (Enterprise Feature)", state=tk.DISABLED).pack(pady=10)


        # --- Restore Section ---
        restore_frame = ttk.Labelframe(frame, text="Database Restore (Local)", padding=20)
        restore_frame.pack(fill='x', pady=20)
        
        ttk.Label(restore_frame, text="WARNING: Restoring from a backup will completely overwrite all current data. This action cannot be undone.", wraplength=500, foreground=COLOR_DANGER, font=('Helvetica', 10, 'bold')).pack(pady=5)
        ttk.Button(restore_frame, text="Restore from Backup (.nxt)", command=self.restore_database, style="Danger.TButton").pack(pady=15, ipady=8, ipadx=10)

    def backup_database(self):
        """Saves a copy of the database file."""
        try:
            # Generate a default filename
            today = datetime.now().strftime('%Y-%m-%d')
            default_filename = f"backup_nexuzy_{today}.nxt"
            
            save_path = filedialog.asksaveasfilename(
                parent=self.backup_tab,
                title="Save Database Backup",
                initialfile=default_filename,
                defaultextension=".nxt",
                filetypes=[("Nexuzy Backup File", "*.nxt"), ("All Files", "*.*")]
            )

            if not save_path:
                return # User cancelled

            logger.info("Starting backup to %s", save_path)
            # Close DB connection to safely copy
            try:
                self.db_conn.close()
            except Exception:
                logger.exception("Error closing DB before backup")

            # Copy the file
            shutil.copyfile(DB_NAME, save_path)

            # Re-open the database connection
            self.db_conn = self.init_database()

            logger.info("Backup successful: %s", save_path)
            messagebox.showinfo("Success", f"Backup successful!\nSaved to: {save_path}", parent=self.backup_tab)

        except Exception as e:
            logger.exception("Backup failed: %s", e)
            messagebox.showerror("Backup Failed", f"An error occurred: {e}", parent=self.backup_tab)
            # Ensure connection is reopened even if copy fails
            try:
                if not getattr(self, 'db_conn', None):
                    self.db_conn = self.init_database()
            except Exception:
                logger.exception("Failed to re-open DB after backup failure")

    def restore_database(self):
        """Restores the database from a backup file."""
        if not messagebox.askyesno("Confirm Restore", "ARE YOU SURE?\n\nThis will permanently delete all current data and replace it with the data from the backup file. This cannot be undone.", parent=self.backup_tab):
            return

        try:
            restore_path = filedialog.askopenfilename(
                parent=self.backup_tab,
                title="Select Backup File to Restore",
                filetypes=[("Nexuzy Backup File", "*.nxt"), ("All Files", "*.*")]
            )

            if not restore_path:
                return # User cancelled
            
            # --- File extension check ---
            if not restore_path.endswith('.nxt'):
                messagebox.showerror("Invalid File", "Please select a valid '.nxt' backup file.", parent=self.backup_tab)
                return

            logger.info("Starting restore from %s", restore_path)
            # Close DB connection to safely overwrite
            try:
                self.db_conn.close()
            except Exception:
                logger.exception("Error closing DB before restore")

            # Overwrite the current DB with the backup
            shutil.copyfile(restore_path, DB_NAME)

            # Re-initialize the database (which opens the new file)
            self.db_conn = self.init_database()

            logger.info("Restore complete from %s", restore_path)
            messagebox.showinfo("Restore Complete", "Database restore successful. The application will now return to the login screen.", parent=self)
            
            # Force user to log out and log back in to reload all data
            self.main_frame.destroy()
            self.create_login_screen()

        except Exception as e:
            logger.exception("Restore failed: %s", e)
            messagebox.showerror("Restore Failed", f"An error occurred: {e}", parent=self.backup_tab)
            # Ensure connection is reopened even if copy fails
            try:
                if not getattr(self, 'db_conn', None):
                    self.db_conn = self.init_database()
            except Exception:
                logger.exception("Failed to re-open DB after restore failure")
                
    def _get_tax_settings(self):
        """Fetches tax settings from the database."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT cgst_rate, sgst_rate, igst_rate, enable_cgst_sgst, enable_igst FROM settings WHERE id=1")
        settings = cursor.fetchone()
        if settings:
            return {
                "cgst_rate": settings[0],
                "sgst_rate": settings[1],
                "igst_rate": settings[2],
                "enable_cgst_sgst": settings[3] == 'true',
                "enable_igst": settings[4] == 'true'
            }
        return {"cgst_rate": 0.0, "sgst_rate": 0.0, "igst_rate": 0.0, "enable_cgst_sgst": False, "enable_igst": False}


# --- Toplevel Windows for specific actions ---

class NewBookingWindow(tk.Toplevel):
    def __init__(self, master, booking_type):
        super().__init__(master)
        self.master = master
        self.booking_type = booking_type
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass

        title_prefix = "New Advance Booking" if booking_type == "Advance" else "New Quick Booking"
        self.title(title_prefix)

        # Increase overall size to accommodate additional fields and avoid hiding bottom controls
        self.geometry("926x826")  # Increased height and width (+~19px)
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        # --- TOP ELEMENTS ---
        guest_frame = ttk.LabelFrame(frame, text="Guest Details", padding=15)
        guest_frame.pack(fill='x', pady=10, side='top')

        ttk.Label(guest_frame, text="Full Name*: (Primary Guest)").grid(row=0, column=0, sticky='w', padx=5, pady=8)
        self.guest_name_entry = ttk.Entry(guest_frame, width=30)
        self.guest_name_entry.grid(row=0, column=1, padx=5, pady=8, ipady=3)

        ttk.Label(guest_frame, text="Phone Number*:").grid(row=0, column=2, sticky='w', padx=(20, 5), pady=8)
        self.guest_phone_entry = ttk.Entry(guest_frame, width=30)
        self.guest_phone_entry.grid(row=0, column=3, padx=5, pady=8, ipady=3)

        ttk.Label(guest_frame, text="Email:").grid(row=1, column=0, sticky='w', padx=5, pady=8)
        self.guest_email_entry = ttk.Entry(guest_frame, width=30)
        self.guest_email_entry.grid(row=1, column=1, padx=5, pady=8, ipady=3)

        ttk.Label(guest_frame, text="Address:").grid(row=1, column=2, sticky='w', padx=(20, 5), pady=8)
        self.guest_address_entry = ttk.Entry(guest_frame, width=30)
        self.guest_address_entry.grid(row=1, column=3, padx=5, pady=8, ipady=3)

    # Documents removed by request: ID proof fields hidden

        # --- VERSION 2.0: Adults and Children ---
        ttk.Label(guest_frame, text="Adults:").grid(row=3, column=0, sticky='w', padx=5, pady=8)
        self.adults_spinbox = ttk.Spinbox(guest_frame, from_=1, to=10, width=5)
        self.adults_spinbox.set(1)
        self.adults_spinbox.grid(row=3, column=1, sticky='w', padx=5, pady=8, ipady=3)

        ttk.Label(guest_frame, text="Children:").grid(row=3, column=2, sticky='w', padx=(20, 5), pady=8)
        self.children_spinbox = ttk.Spinbox(guest_frame, from_=0, to=10, width=5)
        self.children_spinbox.set(0)
        self.children_spinbox.grid(row=3, column=3, sticky='w', padx=5, pady=8, ipady=3)
        # --- END V2.0 ---

        booking_frame = ttk.LabelFrame(frame, text="Booking Details", padding=15)
        booking_frame.pack(fill='x', pady=10, side='top')

        ttk.Label(booking_frame, text="Check-In Date (DD/MM/YYYY):").grid(row=0, column=0, sticky='w', padx=5, pady=8)
        self.check_in_entry = ttk.Entry(booking_frame, width=15)
        # Use DD/MM/YYYY display format as requested
        today = datetime.now()
        next_day_default = today + timedelta(days=1)
        # Default check-in = today, check-out = next day
        self.check_in_entry.insert(0, today.strftime('%d/%m/%Y'))
        self.check_in_entry.grid(row=0, column=1, padx=5, pady=8, ipady=3)

        ttk.Label(booking_frame, text="Time (HH:MM):").grid(row=0, column=2, sticky='w', padx=(20,5), pady=8)
        self.check_in_time_entry = ttk.Entry(booking_frame, width=10)
        # Default time shown in 12-hour AM/PM format
        self.check_in_time_entry.insert(0, datetime.now().strftime('%I:%M %p'))
        self.check_in_time_entry.grid(row=0, column=3, padx=5, pady=8, ipady=3)

        ttk.Label(booking_frame, text="Check-Out Date (DD/MM/YYYY):").grid(row=1, column=0, sticky='w', padx=5, pady=8)
        self.check_out_entry = ttk.Entry(booking_frame, width=15)
        # Use DD/MM/YYYY display format as requested
        # Default checkout date to next day (editable)
        self.check_out_entry.insert(0, next_day_default.strftime('%d/%m/%Y'))
        self.check_out_entry.grid(row=1, column=1, padx=5, pady=8, ipady=3)

        ttk.Label(booking_frame, text="Time (HH:MM):").grid(row=1, column=2, sticky='w', padx=(20,5), pady=8)
        self.check_out_time_entry = ttk.Entry(booking_frame, width=10)
        # Default checkout time to current time (editable) - show in 12-hour AM/PM
        self.check_out_time_entry.insert(0, datetime.now().strftime('%I:%M %p'))
        self.check_out_time_entry.grid(row=1, column=3, padx=5, pady=8, ipady=3)

        ttk.Label(booking_frame, text="Room Type:").grid(row=0, column=2, sticky='w', padx=(20, 5), pady=8)
        self.room_type_combo = ttk.Combobox(booking_frame, values=["Any", "AC", "Non-AC", "Deluxe", "Super Deluxe"], width=18)
        self.room_type_combo.set("Any")
        self.room_type_combo.grid(row=0, column=3, padx=5, pady=8, ipady=3)

        ttk.Button(booking_frame, text="Find Available Rooms", command=self.find_available_rooms, style="Accent.TButton").grid(row=1, column=2, columnspan=2, padx=10, ipady=5)

        ttk.Label(booking_frame, text="Number of Rooms:").grid(row=2, column=0, sticky='w', padx=5, pady=8)
        self.num_rooms_spinbox = ttk.Spinbox(booking_frame, from_=1, to=20, width=5)
        self.num_rooms_spinbox.set(1)
        self.num_rooms_spinbox.grid(row=2, column=1, sticky='w', padx=5, pady=8, ipady=3)

        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', pady=(10, 0), side='bottom')

        ttk.Button(action_frame, text="Confirm Booking", command=self.confirm_booking, style="Success.TButton").pack(pady=0, ipady=8, ipadx=20)

        rooms_frame = ttk.LabelFrame(frame, text="Select a Room", padding=15)
        rooms_frame.pack(fill='both', expand=True, pady=10, side='top')

        cols = ('Room #', 'Type', 'Bed', 'Rate')
        # Allow multi-selection of room rows so staff can select multiple rooms for a single booking
        self.available_rooms_tree = ttk.Treeview(rooms_frame, columns=cols, show='headings', selectmode='extended')
        self.available_rooms_tree.heading('Room #', text='Room #')
        self.available_rooms_tree.heading('Type', text='Type')
        self.available_rooms_tree.heading('Bed', text='Bed')
        self.available_rooms_tree.heading('Rate', text='Rate')
        self.available_rooms_tree.column('Rate', anchor='e', width=100)
        self.available_rooms_tree.column('Room #', anchor='center', width=100)

        self.available_rooms_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.available_rooms_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.available_rooms_tree.pack(fill='both', expand=True)

        # Initialize selection tracking and bind selection change to enforce num_rooms limit
        self._prev_selected_rooms = set()
        self._suspend_selection_handler = False
        self.available_rooms_tree.bind('<<TreeviewSelect>>', self._on_room_selection_change)

        # Helper buttons to select / unselect multiple rooms quickly (limited to Number of Rooms)
        btn_frame = ttk.Frame(rooms_frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_frame, text="Select All", command=self._select_all_limited).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Unselect All", command=self._unselect_all).pack(side='left', padx=5)

        self.find_available_rooms()  # Initially load all available rooms

    def find_available_rooms(self):
        """Finds and displays rooms available for the selected dates."""
        for i in self.available_rooms_tree.get_children():
            self.available_rooms_tree.delete(i)

        check_in_date_str = self.check_in_entry.get()
        check_in_time_str = getattr(self, 'check_in_time_entry', None) and self.check_in_time_entry.get() or '00:00'
        check_out_date_str = self.check_out_entry.get()
        check_out_time_str = getattr(self, 'check_out_time_entry', None) and self.check_out_time_entry.get() or '00:00'
        room_type = self.room_type_combo.get()

        try:
            # Parse DD/MM/YYYY and optional times into full datetimes (accept 12h/24h input)
            check_in_dt = self.master.parse_display_datetime(check_in_date_str, check_in_time_str)
            check_out_dt = self.master.parse_display_datetime(check_out_date_str, check_out_time_str)
            check_in_date = check_in_dt.date()
            check_out_date = check_out_dt.date()

            if check_out_date <= check_in_date:
                messagebox.showerror("Invalid Dates", "Check-out date must be after check-in date.", parent=self)
                return
            if check_in_date < datetime.now().date():
                messagebox.showerror("Invalid Dates", "Check-in date cannot be in the past.", parent=self)
                return

        except ValueError:
            messagebox.showerror("Invalid Date", "Please use DD/MM/YYYY for dates and HH:MM for times.", parent=self)
            return

        cursor = self.master.db_conn.cursor()

        # This query checks for overlapping bookings.
        # It finds rooms that are *not* in the set of booked rooms
        # where the booking *starts before* the new checkout date
        # AND *ends after* the new checkin date.
        query = """
            SELECT r.id, r.room_number, r.room_type, r.bed_type, r.rate 
            FROM rooms r
            WHERE r.status != 'Maintenance' AND r.id NOT IN (
                SELECT b.room_id FROM bookings b
                WHERE b.status IN ('Reserved', 'Checked-In')
                AND b.check_in <= ?    
                AND b.check_out >= ?   
            )
        """
        # Use ISO-like sortable strings for comparison (YYYY-MM-DD HH:MM)
        params = [check_out_dt.strftime('%Y-%m-%d %H:%M'), check_in_dt.strftime('%Y-%m-%d %H:%M')]

        if room_type != "Any":
            query += " AND r.room_type = ?"
            params.append(room_type)

        query += " ORDER BY r.room_number"

        cursor.execute(query, params)

        for i, room in enumerate(cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.available_rooms_tree.insert(
                '', 'end',
                values=(room[1], room[2], room[3], f"{room[4]:.2f}"),
                iid=room[0],  # Use room ID as item ID
                tags=(tag,)
            )
        # reset previous selection tracking whenever the room list is refreshed
        try:
            self._prev_selected_rooms = set()
        except Exception:
            self._prev_selected_rooms = set()

    def _on_room_selection_change(self, event=None):
        """Enforce the Number of Rooms selection limit when user changes Treeview selection."""
        if getattr(self, '_suspend_selection_handler', False):
            return

        try:
            current_sel = list(self.available_rooms_tree.selection())
            sel_count = len(current_sel)
            # Enforce maximum based on the 'Number of Rooms' spinbox.
            # If the spinbox is not available or invalid, fall back to 20.
            try:
                num_rooms_allowed = int(self.num_rooms_spinbox.get())
                if num_rooms_allowed < 1:
                    num_rooms_allowed = 1
            except Exception:
                num_rooms_allowed = 20

            if sel_count > num_rooms_allowed:
                # reduce selection to first N items where N == num_rooms_allowed
                allowed = current_sel[:num_rooms_allowed]
                self._suspend_selection_handler = True
                try:
                    self.available_rooms_tree.selection_set(allowed)
                finally:
                    self._suspend_selection_handler = False
                messagebox.showwarning("Selection Limit",
                                       f"You can only select up to {num_rooms_allowed} room(s) to match 'Number of Rooms'. Selection has been reduced.",
                                       parent=self)
                sel_count = num_rooms_allowed

            # Auto-update Number of Rooms spinbox to match selection (if >0)
            try:
                if sel_count > 0:
                    # Ensure within spinbox allowed range
                    max_spin = int(self.num_rooms_spinbox.cget('to')) if hasattr(self.num_rooms_spinbox, 'cget') else MAX_ROOMS
                    new_val = min(sel_count, max_spin)
                    self.num_rooms_spinbox.set(str(new_val))
            except Exception:
                pass

            # Update prev selection for next event
            self._prev_selected_rooms = set(current_sel)
        except Exception:
            # Silently ignore handler errors to avoid blocking UI
            try:
                self._prev_selected_rooms = set(self.available_rooms_tree.selection())
            except Exception:
                self._prev_selected_rooms = set()

    def _select_all_limited(self):
        """Select up to Number of Rooms items (first N visible rows)."""
        try:
            children = list(self.available_rooms_tree.get_children())
            if not children:
                return
            num_rooms = int(getattr(self, 'num_rooms_spinbox', None) and self.num_rooms_spinbox.get() or 1)
            allowed = children[:min(len(children), num_rooms)]
            self._suspend_selection_handler = True
            try:
                self.available_rooms_tree.selection_set(allowed)
                self._prev_selected_rooms = set(allowed)
            finally:
                self._suspend_selection_handler = False
        except Exception:
            pass

    def _unselect_all(self):
        try:
            self._suspend_selection_handler = True
            try:
                self.available_rooms_tree.selection_remove(self.available_rooms_tree.get_children())
                self._prev_selected_rooms = set()
            finally:
                self._suspend_selection_handler = False
        except Exception:
            pass

    def confirm_booking(self):
        """Confirms and saves the booking."""
        logger.info("Attempting to confirm booking (guest=%s, phone=%s)", self.guest_name_entry.get(), self.guest_phone_entry.get())
        # 1. Get Guest Data
        guest_name = self.guest_name_entry.get()
        guest_phone = self.guest_phone_entry.get()
        guest_email = self.guest_email_entry.get()
        guest_address = self.guest_address_entry.get()
        # ID Proof fields removed - do not collect sensitive document data

        # 2. Get Booking Data
        selection_list = list(self.available_rooms_tree.selection())
        check_in_date_str = self.check_in_entry.get()
        check_in_time_str = getattr(self, 'check_in_time_entry', None) and self.check_in_time_entry.get() or '00:00'
        check_out_date_str = self.check_out_entry.get()
        check_out_time_str = getattr(self, 'check_out_time_entry', None) and self.check_out_time_entry.get() or '00:00'
        num_rooms = int(getattr(self, 'num_rooms_spinbox', None) and self.num_rooms_spinbox.get() or 1)

        # 3. Validation
        if not all([guest_name, guest_phone]):
            messagebox.showerror("Error", "Name and Phone are mandatory.", parent=self)
            return

        if not selection_list:
            messagebox.showerror("Error", "Please select at least one room from the list.", parent=self)
            return

        # If the number of selected rooms doesn't match the "Number of Rooms" field, confirm with user
        if len(selection_list) != num_rooms:
            proceed = messagebox.askyesno("Confirm Room Count",
                                          f"You selected {len(selection_list)} room(s) but 'Number of Rooms' is set to {num_rooms}.\nProceed with the selected rooms?",
                                          parent=self)
            if not proceed:
                return

        try:
            # Expect display dates in DD/MM/YYYY (optionally with HH:MM or AM/PM)
            d_in = self.master.parse_display_datetime(check_in_date_str, check_in_time_str)
            d_out = self.master.parse_display_datetime(check_out_date_str, check_out_time_str)
            if d_out <= d_in:
                messagebox.showerror("Invalid Dates", "Check-out date must be after check-in date.", parent=self)
                return
            num_nights = (d_out - d_in).days
            if num_nights <= 0:
                num_nights = 1

            # V2.0: Get Adults/Children
            num_adults = int(self.adults_spinbox.get())
            num_children = int(self.children_spinbox.get())

        except ValueError:
            messagebox.showerror("Invalid Date/Number Format", "Please use DD/MM/YYYY format and valid numbers for adults/children.", parent=self)
            return

        # Aggregate room costs across all selected rooms
        total_room_cost = 0.0
        room_details_first = None
        selected_room_ids = []
        # store per-room rates so we can allocate advance and persons proportionally/fairly
        rates_by_room = {}
        for sel in selection_list:
            rd = self.available_rooms_tree.item(sel)
            if room_details_first is None:
                room_details_first = rd
            try:
                rate_str = rd['values'][3]
                room_rate = float(rate_str)
            except Exception:
                room_rate = 0.0
            total_room_cost += room_rate * num_nights
            selected_room_ids.append(sel)
            try:
                rates_by_room[sel] = float(room_rate)
            except Exception:
                rates_by_room[sel] = 0.0

        # --- ADVANCE PAYMENT LOGIC ---
        
    # 1. Base Room Cost
    # total_room_cost already contains the aggregated cost for selected rooms
        
        # 2. Local Charge Calculation for Advance (known fixed charge)
        local_charge_info = self.master.calculate_local_charge_for_advance(num_nights, num_adults, num_children)
        
        # Per user request, do not include Local Fee in advance receipt calculations shown to guest.
        # Taxes for the advance are computed on room charges only (projected), local fee is excluded here.
        sub_total = total_room_cost
        
        # 3. Tax Calculation for Advance (based on settings)
        tax_rates = self.master._get_tax_settings()
        tax_amount = 0.0
        cgst = 0.0
        sgst = 0.0
        igst = 0.0
        
        # Simple Logic: Only apply tax if one set is enabled. Prioritize IGST if enabled.
        if tax_rates['enable_igst']:
            igst = sub_total * (tax_rates['igst_rate'] / 100.0)
            tax_amount = igst
        elif tax_rates['enable_cgst_sgst']:
            cgst = sub_total * (tax_rates['cgst_rate'] / 100.0)
            sgst = sub_total * (tax_rates['sgst_rate'] / 100.0)
            tax_amount = cgst + sgst
            
        grand_total_after_tax = sub_total + tax_amount

        advance_paid = 0.0

        if self.booking_type == "Advance":
            suggested_advance = grand_total_after_tax * 0.20 # 20% of full projected bill

            advance_paid_input = simpledialog.askfloat("Advance Payment",
                                                       f"Projected Total (Incl. Fees/Tax): Rs.{grand_total_after_tax:.2f} ({num_nights} nights)\n"
                                                       f"Suggested 20% Advance: Rs.{suggested_advance:.2f}\n\n"
                                                       f"Enter advance amount paid (enter 0 if none):",
                                                       parent=self, minvalue=0.0, maxvalue=grand_total_after_tax
                                                       )

            if advance_paid_input is None:
                messagebox.showwarning("Cancelled", "Booking cancelled.", parent=self)
                return
            else:
                advance_paid = advance_paid_input
        elif self.booking_type == "Quick":
            # Quick bookings should NOT prompt for deposit by default per user request.
            # Always treat Quick bookings as having no advance unless later edited.
            advance_paid = 0.0
        # --- END ADVANCE LOGIC ---

        try:
            cursor = self.master.db_conn.cursor()

            # 4. Add guest (Primary Guest) -- do not store document fields
            cursor.execute("""
                INSERT INTO guests (name, phone, email, address)
                VALUES (?, ?, ?, ?)
                """,
                           (guest_name, guest_phone, guest_email, guest_address)
                           )
            guest_id = cursor.lastrowid

            # 5. Generate booking ref
            # New format: starts with 'NXT-<random>' for single bookings.
            # For group bookings we append '-GRO' to indicate group (e.g. NXT-123456789-GRO).
            try:
                rand_num = random.randint(100000000, 999999999)
                if len(selected_room_ids) > 1:
                    booking_ref = f"NXT-{rand_num}-GRO"
                else:
                    booking_ref = f"NXT-{rand_num}"
            except Exception:
                # Fallback to timestamp-based ref if random fails
                try:
                    if len(selected_room_ids) > 1:
                        booking_ref = f"NXT-{int(time.time())}-GRO"
                    else:
                        booking_ref = f"NXT-{int(time.time())}"
                except Exception:
                    booking_ref = f"NXT-{int(time.time())}"
            
            # --- NEW: Save Primary Guest to booking_persons table ---
            cursor.execute("""
                INSERT INTO booking_persons (booking_ref, person_name, is_primary)
                VALUES (?, ?, 'true')
            """, (booking_ref, guest_name))
            # --- END NEW ---

            # 6. Add booking(s) (one DB row per selected room)
            # Use the list of selected_room_ids collected above and insert a booking row for each
            first_room_rate = 0.0
            try:
                if room_details_first:
                    try:
                        first_room_rate = float(room_details_first['values'][3])
                    except Exception:
                        first_room_rate = 0.0
            except Exception:
                first_room_rate = 0.0

            # Distribute adults/children across rooms to avoid multiplying totals
            per_room_adults = []
            per_room_children = []
            try:
                a_base = int(num_adults) // len(selected_room_ids)
                a_rem = int(num_adults) % len(selected_room_ids)
            except Exception:
                a_base = int(num_adults or 0)
                a_rem = 0
            try:
                c_base = int(num_children) // len(selected_room_ids)
                c_rem = int(num_children) % len(selected_room_ids)
            except Exception:
                c_base = int(num_children or 0)
                c_rem = 0

            for i in range(len(selected_room_ids)):
                per_room_adults.append(a_base + (1 if i < a_rem else 0))
                per_room_children.append(c_base + (1 if i < c_rem else 0))

            # Allocate advance proportionally to each room's share of projected cost (fair split)
            per_room_advance = []
            if advance_paid and total_room_cost > 0:
                allocated = 0.0
                for idx, rid in enumerate(selected_room_ids[:-1]):
                    room_share = (rates_by_room.get(rid, 0.0) * num_nights) / total_room_cost
                    amt = round(float(advance_paid) * room_share, 2)
                    per_room_advance.append(amt)
                    allocated += amt
                # last room gets remainder to ensure total matches
                last_amt = round(float(advance_paid) - allocated, 2)
                per_room_advance.append(last_amt)
            else:
                per_room_advance = [0.0] * len(selected_room_ids)

            # Insert one DB row per selected room with per-room persons and allocated advance
            for idx, rid in enumerate(selected_room_ids):
                cursor.execute("""
                    INSERT INTO bookings (booking_ref, guest_id, room_id, check_in, check_out, 
                                          status, advance_payment, num_adults, num_children, num_rooms) 
                    VALUES (?, ?, ?, ?, ?, 'Reserved', ?, ?, ?, ?)
                    """,
                               (booking_ref, guest_id, rid, d_in.strftime('%Y-%m-%d %H:%M'), d_out.strftime('%Y-%m-%d %H:%M'), per_room_advance[idx], per_room_adults[idx], per_room_children[idx], num_rooms)
                               )

            self.master.db_conn.commit()

            logger.info("Booking saved: %s (guest_id=%s, room_ids=%s)", booking_ref, guest_id, ','.join(map(str, selected_room_ids)))

            # --- GENERATE ADVANCE RECEIPT PDF (Only if advance > 0) ---
            if advance_paid > 0.0:
                try:
                    cursor.execute("SELECT hotel_name, address, address_line1, address_line2, gst_number, contact_number, hotel_rules FROM settings WHERE id=1")
                    hotel_details = cursor.fetchone()

                    # Prepare PDF data: do not include any ID proof fields.
                    pdf_data = {
                        "booking_ref": booking_ref,
                        "hotel_name": hotel_details[0],
                        "hotel_address": hotel_details[1],
                        "hotel_address_line1": hotel_details[2],
                        "hotel_address_line2": hotel_details[3],
                        "hotel_gst": hotel_details[4], 
                        "hotel_contact": hotel_details[5],
                        "hotel_rules": hotel_details[6] if len(hotel_details) > 6 else '',
                        "guest_name": guest_name,
                        "guest_phone": guest_phone,
                        "guest_address": guest_address,
                        # Include room type and number of rooms instead of a specific room number
                        "room_type": room_details_first['values'][1] if room_details_first and 'values' in room_details_first else '',
                        "num_rooms": num_rooms,
                        "room_rate": first_room_rate,
                        "check_in": d_in.strftime('%d/%m/%Y'),
                        "check_out": d_out.strftime('%d/%m/%Y'),
                        "num_nights": num_nights,
                        "room_total": total_room_cost,
                        "cgst_amount": cgst,             # NEW
                        "sgst_amount": sgst,             # NEW
                        "igst_amount": igst,             # NEW
                        "total_after_tax": grand_total_after_tax, # NEW
                        "advance_paid": advance_paid,
                        "balance_due": grand_total_after_tax - advance_paid,
                        "num_adults": num_adults,       # NEW: Added for PDF display
                        "num_children": num_children    # NEW: Added for PDF display
                    }
                    self.generate_advance_invoice_pdf(pdf_data)

                    messagebox.showinfo("Success",
                                        f"Booking confirmed! Reference #: {booking_ref}\n"
                                        f"Advance Receipt PDF saved and opened.",
                                        parent=self
                                        )
                except Exception as pdf_e:
                    messagebox.showerror("PDF Error", f"Booking saved, but could not generate PDF: {pdf_e}", parent=self)
            else:
                messagebox.showinfo("Success",
                                    f"Booking confirmed! Reference #: {booking_ref}",
                                    parent=self
                                    )

            self.master.load_bookings_data()
            self.master.refresh_dashboard()
            self.destroy()

        except Exception as e:
            logger.exception("Error during confirm_booking: %s", e)
            messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=self)
            try:
                self.master.db_conn.rollback()
            except Exception:
                logger.exception("Failed to rollback DB after confirm_booking error")

    # --- MODIFIED: Fixed overlapping text, removed ID number for security & Fixed Rupee Symbol, Added Persons ---
    def generate_advance_invoice_pdf(self, data):
        """Generates an advance receipt PDF without ID proofs and without printing specific room numbers.
        Shows room type and number of rooms, includes check-in/check-out date+time (DD/MM/YYYY HH:MM).
        Attempts to include `logohotel.png` from resources if present.
        """
        # Per user request: show DATE only (no time) on Advance Receipt.
        try:
            def _date_only(s):
                if not s:
                    return ''
                s = str(s)
                s = s.split(' ')[0]
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        dt = datetime.strptime(s, fmt)
                        return dt.strftime('%d/%m/%Y')
                    except Exception:
                        continue
                return s
            data['check_in'] = _date_only(data.get('check_in'))
            data['check_out'] = _date_only(data.get('check_out'))
        except Exception:
            pass

        # Log key fields to aid debugging (date-only)
        try:
            logger.info("Advance PDF data (check_in=%s, check_out=%s, local_charge=%s)", data.get('check_in'), data.get('check_out'), data.get('local_charge'))
        except Exception:
            pass

        # Delegate to standalone generator for robustness (so other windows can call it without needing the app instance)
        try:
            generate_advance_invoice_pdf_standalone(data)
            return
        except Exception:
            # Fallback to in-method generation if standalone fails
            pass

        filename = f"Advance_Receipt_{data['booking_ref']}.pdf"
        # Save advance receipts into user's Documents/NexuzyHotelPDFs (create folder on first use)
        try:
            out_dir = get_user_pdfs_dir('AdvanceReceipts')
            filename = os.path.join(out_dir, filename)
        except Exception:
            pass
        c = canvas.Canvas(filename, pagesize=A4)

        LINE_HEIGHT = 0.18 * inch
        LARGE_SPACING = 0.4 * inch
        SMALL_SPACING = 0.25 * inch

        y_cursor = 10.8 * inch

        # Header: optional logo
        try:
            logo_path = resource_path('logohotel.png')
            if os.path.exists(logo_path):
                # drawImage(x, y, width, height) - place at top-left
                c.drawImage(logo_path, 1 * inch, y_cursor - 0.6 * inch, width=0.9 * inch, height=0.9 * inch, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

        # Hotel name & address
        c.setFont("Helvetica-Bold", 18)
        c.drawString(2.1 * inch, y_cursor, data.get('hotel_name', ''))
        y_cursor -= LINE_HEIGHT
        c.setFont("Helvetica", 10)

        addr1 = data.get('hotel_address_line1') or ''
        addr2 = data.get('hotel_address_line2') or ''
        if not (addr1 or addr2):
            combined = data.get('hotel_address') or ''
            parts = [p.strip() for p in combined.split(',', 1)] if combined else ['', '']
            addr1 = parts[0]
            addr2 = parts[1] if len(parts) > 1 else ''

        for line in (addr1, addr2):
            if line:
                for part in textwrap.wrap(line, width=90):
                    c.drawString(2.1 * inch, y_cursor, part)
                    y_cursor -= LINE_HEIGHT

        c.drawString(2.1 * inch, y_cursor, f"Contact: {data.get('hotel_contact','')} | GSTIN: {data.get('hotel_gst','')}")
        y_cursor -= LARGE_SPACING

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(4.25 * inch, y_cursor, "BOOKING CONFIRMATION & ADVANCE RECEIPT")
        y_cursor -= SMALL_SPACING
        c.line(1 * inch, y_cursor, 7.5 * inch, y_cursor)
        y_cursor -= SMALL_SPACING

        # Guest details (left) and booking details (right)
        start_y = y_cursor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(1 * inch, start_y, "Primary Guest Details:")
        cur = start_y - LINE_HEIGHT
        c.setFont("Helvetica", 10)
        c.drawString(1 * inch, cur, f"Name: {data.get('guest_name','')}")
        cur -= LINE_HEIGHT
        c.drawString(1 * inch, cur, f"Phone: {data.get('guest_phone','')}")
        cur -= LINE_HEIGHT
        c.drawString(1 * inch, cur, f"Address: {data.get('guest_address','')}")

        # Right column
        right_y = start_y
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(7.5 * inch, right_y, "Booking Details:")
        right_y -= LINE_HEIGHT
        c.setFont("Helvetica", 10)
        c.drawRightString(7.5 * inch, right_y, f"Booking Ref: {data.get('booking_ref','')}")
        right_y -= LINE_HEIGHT
        # Local helper to format datetimes to 12-hour AM/PM when possible
        def _fmt_local_dt(s):
            try:
                if not s:
                    return ''
                s = str(s)
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S.%f'):
                    try:
                        dt = datetime.strptime(s, fmt)
                        return dt.strftime('%d/%m/%Y %I:%M %p')
                    except Exception:
                        continue
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        dt = datetime.strptime(s, fmt)
                        return dt.strftime('%d/%m/%Y')
                    except Exception:
                        continue
                return s
            except Exception:
                return s

        try:
            issued_local = _fmt_local_dt(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        except Exception:
            issued_local = datetime.now().strftime('%d/%m/%Y')
        c.drawRightString(7.5 * inch, right_y, f"Date Issued: {issued_local}")
        right_y -= LINE_HEIGHT
        c.drawRightString(7.5 * inch, right_y, f"Room Type: {data.get('room_type','')} | Rooms: {data.get('num_rooms',1)}")
        right_y -= LINE_HEIGHT
        c.drawRightString(7.5 * inch, right_y, f"Check-In: {_fmt_local_dt(data.get('check_in',''))}")
        right_y -= LINE_HEIGHT
        c.drawRightString(7.5 * inch, right_y, f"Check-Out: {_fmt_local_dt(data.get('check_out',''))}")
        right_y -= LINE_HEIGHT
        c.drawRightString(7.5 * inch, right_y, f"Duration: {data.get('num_nights',1)} nights")
        right_y -= LINE_HEIGHT
        # Prefer a caller-supplied display total when present (partial checkout/manual override)
        if data.get('display_persons_total') is not None:
            c.drawRightString(7.5 * inch, right_y, f"Persons: {data.get('display_persons_total')} Person(s)")
        else:
            c.drawRightString(7.5 * inch, right_y, f"Persons: {data.get('num_adults',1)} Adult(s), {data.get('num_children',0)} Child(ren)")

        y_cursor = min(cur, right_y) - LARGE_SPACING
        c.line(1 * inch, y_cursor, 7.5 * inch, y_cursor)
        y_cursor -= SMALL_SPACING

        # PAYMENT BREAKDOWN: room + local charges -> TAX only on these (restaurant excluded)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1 * inch, y_cursor, "Projected Total Bill (Before Check-Out)")
        y_cursor -= SMALL_SPACING

        c.setFont("Helvetica", 11)
        c.drawRightString(6.0 * inch, y_cursor, "Room Charges:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('room_total',0.0):.2f}")
        y_cursor -= LINE_HEIGHT

        # Per user request: do NOT show Local Fee on Advance Receipt. Subtotal is room charges only.
        sub_total_before_tax = data.get('room_total', 0.0)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(6.0 * inch, y_cursor, "Sub Total:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{sub_total_before_tax:.2f}")
        y_cursor -= SMALL_SPACING

        # Tax lines (values computed earlier and passed in)
        c.setFont("Helvetica", 10)
        if data.get('cgst_amount', 0.0) > 0:
            c.drawRightString(6.0 * inch, y_cursor, "CGST:")
            c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('cgst_amount',0.0):.2f}")
            y_cursor -= LINE_HEIGHT
        if data.get('sgst_amount', 0.0) > 0:
            c.drawRightString(6.0 * inch, y_cursor, "SGST:")
            c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('sgst_amount',0.0):.2f}")
            y_cursor -= LINE_HEIGHT
        if data.get('igst_amount', 0.0) > 0:
            c.drawRightString(6.0 * inch, y_cursor, "IGST:")
            c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('igst_amount',0.0):.2f}")
            y_cursor -= LINE_HEIGHT

        y_cursor -= SMALL_SPACING

        c.setFont("Helvetica-Bold", 13)
        c.drawRightString(6.0 * inch, y_cursor, "GRAND TOTAL:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('total_after_tax',0.0):.2f}")
        y_cursor -= LARGE_SPACING

        c.setFont("Helvetica-Bold", 13)
        c.drawRightString(6.0 * inch, y_cursor, "ADVANCE PAID:")
        c.drawRightString(7.3 * inch, y_cursor, f"- Rs.{data.get('advance_paid',0.0):.2f}")
        y_cursor -= SMALL_SPACING
        c.line(5.0 * inch, y_cursor, 7.3 * inch, y_cursor)
        y_cursor -= SMALL_SPACING

        c.setFont("Helvetica-Bold", 15)
        c.drawRightString(6.0 * inch, y_cursor, "BALANCE DUE:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('balance_due',0.0):.2f}")
        y_cursor -= LARGE_SPACING

        # Footer rules or thank you
        # Attempt to use a Bengali-capable TTF if present so hotel_rules can be written in Bangla.
        font_name = 'Helvetica-Oblique'
        try:
            for fname in ('NotoSansBengali-Regular.ttf', 'NotoSansBengali.ttf', 'SolaimanLipi.ttf'):
                fpath = resource_path(fname)
                if os.path.exists(fpath):
                    try:
                        pdfmetrics.registerFont(TTFont('BengaliFont', fpath))
                        font_name = 'BengaliFont'
                        break
                    except Exception:
                        continue
        except Exception:
            pass

        c.setFont(font_name, 9)
        rules = data.get('hotel_rules', '')
        if rules:
            # Show up to two lines of rules in footer (user can configure longer, but keep space)
            for part in textwrap.wrap(rules, width=120):
                c.drawCentredString(4.25 * inch, 1.2 * inch, part)
                break

        c.drawCentredString(4.25 * inch, 1.0 * inch, "This is a computer-generated receipt. Balance is due at check-in or check-out.")
        c.drawCentredString(4.25 * inch, 0.8 * inch, "Thank you for choosing " + data.get('hotel_name','') + "!")

        c.save()

        try:
            webbrowser.open(f"file://{os.path.abspath(filename)}")
        except Exception:
            pass


def generate_advance_invoice_pdf_standalone(data):
    """Standalone advance receipt generator (so other windows can call it without needing the app instance).

    Accepts the same `data` dict used by the class method.
    """
    # Per user request: show DATE only (no time) on Advance Receipt.
    try:
        def _date_only(s):
            if not s:
                return ''
            s = str(s)
            s = s.split(' ')[0]
            for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                try:
                    dt = datetime.strptime(s, fmt)
                    return dt.strftime('%d/%m/%Y')
                except Exception:
                    continue
            return s
        data['check_in'] = _date_only(data.get('check_in'))
        data['check_out'] = _date_only(data.get('check_out'))
    except Exception:
        pass

    # Log key fields to help debugging (date-only)
    try:
        logger.info("Advance (standalone) PDF data (check_in=%s, check_out=%s, local_charge=%s)", data.get('check_in'), data.get('check_out'), data.get('local_charge'))
    except Exception:
        pass

    filename = f"Advance_Receipt_{data['booking_ref']}.pdf"
    try:
        out_dir = get_user_pdfs_dir('AdvanceReceipts')
        filename = os.path.join(out_dir, filename)
    except Exception:
        pass
    c = canvas.Canvas(filename, pagesize=A4)

    LINE_HEIGHT = 0.18 * inch
    LARGE_SPACING = 0.4 * inch
    SMALL_SPACING = 0.25 * inch

    y_cursor = 10.8 * inch

    # Header: optional logo
    try:
        logo_path = resource_path('logohotel.png')
        if os.path.exists(logo_path):
            c.drawImage(logo_path, 1 * inch, y_cursor - 0.6 * inch, width=0.9 * inch, height=0.9 * inch, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass

    # Hotel name & address
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2.1 * inch, y_cursor, data.get('hotel_name', ''))
    y_cursor -= LINE_HEIGHT
    c.setFont("Helvetica", 10)

    addr1 = data.get('hotel_address_line1') or ''
    addr2 = data.get('hotel_address_line2') or ''
    if not (addr1 or addr2):
        combined = data.get('hotel_address') or ''
        parts = [p.strip() for p in combined.split(',', 1)] if combined else ['', '']
        addr1 = parts[0]
        addr2 = parts[1] if len(parts) > 1 else ''

    for line in (addr1, addr2):
        if line:
            for part in textwrap.wrap(line, width=90):
                c.drawString(2.1 * inch, y_cursor, part)
                y_cursor -= LINE_HEIGHT

    c.drawString(2.1 * inch, y_cursor, f"Contact: {data.get('hotel_contact','')} | GSTIN: {data.get('hotel_gst','')}")
    y_cursor -= LARGE_SPACING

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(4.25 * inch, y_cursor, "BOOKING CONFIRMATION & ADVANCE RECEIPT")
    y_cursor -= SMALL_SPACING
    c.line(1 * inch, y_cursor, 7.5 * inch, y_cursor)
    y_cursor -= SMALL_SPACING

    # Guest details (left) and booking details (right)
    start_y = y_cursor
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1 * inch, start_y, "Primary Guest Details:")
    cur = start_y - LINE_HEIGHT
    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, cur, f"Name: {data.get('guest_name','')}")
    cur -= LINE_HEIGHT
    c.drawString(1 * inch, cur, f"Phone: {data.get('guest_phone','')}")
    cur -= LINE_HEIGHT
    c.drawString(1 * inch, cur, f"Address: {data.get('guest_address','')}")

    # Right column
    right_y = start_y
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(7.5 * inch, right_y, "Booking Details:")
    right_y -= LINE_HEIGHT
    c.setFont("Helvetica", 10)
    c.drawRightString(7.5 * inch, right_y, f"Booking Ref: {data.get('booking_ref','')}")
    right_y -= LINE_HEIGHT
    # Local helper to format datetimes to 12-hour AM/PM when possible
    def _fmt_local_dt(s):
        try:
            if not s:
                return ''
            s = str(s)
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S.%f'):
                try:
                    dt = datetime.strptime(s, fmt)
                    return dt.strftime('%d/%m/%Y %I:%M %p')
                except Exception:
                    continue
            for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                try:
                    dt = datetime.strptime(s, fmt)
                    return dt.strftime('%d/%m/%Y')
                except Exception:
                    continue
            return s
        except Exception:
            return s

    try:
        issued_local = _fmt_local_dt(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception:
        issued_local = datetime.now().strftime('%d/%m/%Y')
    c.drawRightString(7.5 * inch, right_y, f"Date Issued: {issued_local}")
    right_y -= LINE_HEIGHT
    c.drawRightString(7.5 * inch, right_y, f"Room Type: {data.get('room_type','')} | Rooms: {data.get('num_rooms',1)}")
    right_y -= LINE_HEIGHT
    c.drawRightString(7.5 * inch, right_y, f"Check-In: {_fmt_local_dt(data.get('check_in',''))}")
    right_y -= LINE_HEIGHT
    c.drawRightString(7.5 * inch, right_y, f"Check-Out: {_fmt_local_dt(data.get('check_out',''))}")
    right_y -= LINE_HEIGHT
    c.drawRightString(7.5 * inch, right_y, f"Duration: {data.get('num_nights',1)} nights")
    right_y -= LINE_HEIGHT
    c.drawRightString(7.5 * inch, right_y, f"Persons: {data.get('num_adults',1)} Adult(s), {data.get('num_children',0)} Child(ren)")

    y_cursor = min(cur, right_y) - LARGE_SPACING
    c.line(1 * inch, y_cursor, 7.5 * inch, y_cursor)
    y_cursor -= SMALL_SPACING

    # PAYMENT BREAKDOWN: room + local charges -> TAX only on these (restaurant excluded)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, y_cursor, "Projected Total Bill (Before Check-Out)")
    y_cursor -= SMALL_SPACING

    c.setFont("Helvetica", 11)
    c.drawRightString(6.0 * inch, y_cursor, "Room Charges:")
    c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('room_total',0.0):.2f}")
    y_cursor -= LINE_HEIGHT

    if data.get('local_charge', {}).get('amount', 0.0) > 0:
        c.drawRightString(6.0 * inch, y_cursor, f"Local Fee ({data['local_charge'].get('name','')}):")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data['local_charge']['amount']:.2f}")
        y_cursor -= LINE_HEIGHT

    # Per user request: do NOT show Local Fee on Advance Receipt. Subtotal is room charges only.
    sub_total_before_tax = data.get('room_total', 0.0)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(6.0 * inch, y_cursor, "Sub Total:")
    c.drawRightString(7.3 * inch, y_cursor, f"Rs.{sub_total_before_tax:.2f}")
    y_cursor -= SMALL_SPACING

    # Tax lines (values computed earlier and passed in)
    c.setFont("Helvetica", 10)
    if data.get('cgst_amount', 0.0) > 0:
        c.drawRightString(6.0 * inch, y_cursor, "CGST:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('cgst_amount',0.0):.2f}")
        y_cursor -= LINE_HEIGHT
    if data.get('sgst_amount', 0.0) > 0:
        c.drawRightString(6.0 * inch, y_cursor, "SGST:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('sgst_amount',0.0):.2f}")
        y_cursor -= LINE_HEIGHT
    if data.get('igst_amount', 0.0) > 0:
        c.drawRightString(6.0 * inch, y_cursor, "IGST:")
        c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('igst_amount',0.0):.2f}")
        y_cursor -= LINE_HEIGHT

    y_cursor -= SMALL_SPACING

    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(6.0 * inch, y_cursor, "GRAND TOTAL:")
    c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('total_after_tax',0.0):.2f}")
    y_cursor -= LARGE_SPACING

    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(6.0 * inch, y_cursor, "ADVANCE PAID:")
    c.drawRightString(7.3 * inch, y_cursor, f"- Rs.{data.get('advance_paid',0.0):.2f}")
    y_cursor -= SMALL_SPACING
    c.line(5.0 * inch, y_cursor, 7.3 * inch, y_cursor)
    y_cursor -= SMALL_SPACING

    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(6.0 * inch, y_cursor, "BALANCE DUE:")
    c.drawRightString(7.3 * inch, y_cursor, f"Rs.{data.get('balance_due',0.0):.2f}")
    y_cursor -= LARGE_SPACING

    # Footer rules or thank you
    # Attempt to use a Bengali-capable TTF if present so hotel_rules can be written in Bangla.
    font_name = 'Helvetica-Oblique'
    try:
        for fname in ('NotoSansBengali-Regular.ttf', 'NotoSansBengali.ttf', 'SolaimanLipi.ttf'):
            fpath = resource_path(fname)
            if os.path.exists(fpath):
                try:
                    pdfmetrics.registerFont(TTFont('BengaliFont', fpath))
                    font_name = 'BengaliFont'
                    break
                except Exception:
                    continue
    except Exception:
        pass

    c.setFont(font_name, 9)
    rules = data.get('hotel_rules', '')
    if rules:
        for part in textwrap.wrap(rules, width=120):
            c.drawCentredString(4.25 * inch, 1.2 * inch, part)
            break

    c.drawCentredString(4.25 * inch, 1.0 * inch, "This is a computer-generated receipt. Balance is due at check-in or check-out.")
    c.drawCentredString(4.25 * inch, 0.8 * inch, "Thank you for choosing " + data.get('hotel_name','') + "!")

    c.save()

    try:
        webbrowser.open(f"file://{os.path.abspath(filename)}")
    except Exception:
        pass


## --- NEW: Utility Class for Bill/Print Functions ---
class BillUtility:
    """A helper class to generate PDFs and handle printing/sharing without being a Toplevel window."""
    def __init__(self, master, bill_data):
        self.master = master
        self.bill_data = bill_data
        # Determine initial tax type from bill_data if provided (for history/reprint)
        self.tax_type_to_display = bill_data.get('tax_type_to_display', 'none')

        # Need to load tax settings from the master app/DB context
        self.load_tax_settings(master)

        # Recalculate totals just before performing an action (important for integrity)
        self._recalculate_totals()

    def load_tax_settings(self, master):
        """Loads tax settings directly from the database. (FIXED: Added robust check for local_charges)"""
        try:
            cursor = master.db_conn.cursor()
            cursor.execute("""
                SELECT cgst_rate, sgst_rate, igst_rate, 
                       enable_cgst_sgst, enable_igst 
                FROM settings WHERE id=1
            """)
            settings = cursor.fetchone()
            
            self.cgst_rate = settings[0]
            self.sgst_rate = settings[1]
            self.igst_rate = settings[2]
            self.enable_cgst_sgst = (settings[3] == 'true')
            self.enable_igst = (settings[4] == 'true')
            
            # --- Local Charge Data ---
            cursor.execute("SELECT enabled, charge_name, amount, calculation_type FROM local_charges WHERE id=1")
            local_charge_settings = cursor.fetchone()
            
            # FIX: Robust check for local_charge_settings being None/empty
            if local_charge_settings:
                self.local_charge_settings = {
                    "name": local_charge_settings[1],
                    "amount": local_charge_settings[2],
                    "enabled": local_charge_settings[0] == 'true'
                }
            else:
                self.local_charge_settings = {"name": "", "amount": 0.0, "enabled": False}


            # If loading from an active bill window, use its current tax choice
            if 'tax_type_var' in self.master.__dict__:
                 self.tax_type_to_display = self.master.tax_type_var.get()
            elif self.tax_type_to_display == 'none':
                 # Fallback/Initial Guess: if tax exists, guess cgsg
                 if self.bill_data['grand_total'] > self.bill_data['sub_total'] and self.enable_cgst_sgst:
                     self.tax_type_to_display = 'cgsg' 
                 elif self.bill_data['grand_total'] > self.bill_data['sub_total'] and self.enable_igst:
                     self.tax_type_to_display = 'igst'


        except Exception as e:
            print(f"Error loading tax settings in utility: {e}")
            self.cgst_rate, self.sgst_rate, self.igst_rate = 0.0, 0.0, 0.0
            self.tax_type_to_display = 'none'
            self.local_charge_settings = {"name": "", "amount": 0.0, "enabled": False}


    def _recalculate_totals(self):
        """Recalculates subtotals and grand total from the bill data dictionary."""
        bd = self.bill_data

        # Reset tax amounts
        bd['cgst_amount'] = 0.0
        bd['sgst_amount'] = 0.0
        bd['igst_amount'] = 0.0

        # For BillUtility (history/final print) we reconstruct totals.
        # Restaurant totals are considered non-taxable — tax is only applied to room/local/extra charges.
        restaurant_total = bd.get('restaurant_total', 0.0)

        # Honor any stored room discount (applies only to room portion)
        room_total = float(bd.get('room_total', 0.0) or 0.0)
        room_discount = float(bd.get('room_discount', 0.0) or 0.0)
        room_total_after_discount = max(0.0, room_total - room_discount)

        taxable_sub_total = bd.get('taxable_sub_total') or (
            room_total_after_discount + bd.get('extra_charges_total', 0.0) + bd.get('local_charge_info', {}).get('amount', 0.0)
        )

        # Display subtotal includes restaurant, but taxable_sub_total excludes it.
        sub_total = bd.get('sub_total') or (taxable_sub_total + restaurant_total)

        # Prefer explicit grand_total if present; otherwise assume subtotal (tax already baked-in or zero)
        grand_total = bd.get('grand_total') or sub_total

        # Compute tax amount: grand_total excluding restaurant part, minus taxable_sub_total
        non_rest_total = max(0.0, grand_total - restaurant_total)
        total_tax_amount = max(0.0, non_rest_total - taxable_sub_total)

        # Distribute the tax based on the inferred/selected tax type
        if self.tax_type_to_display == 'cgsg':
            bd['cgst_amount'] = total_tax_amount / 2.0 if total_tax_amount > 0 else 0.0
            bd['sgst_amount'] = total_tax_amount / 2.0 if total_tax_amount > 0 else 0.0
            bd['igst_amount'] = 0.0
        elif self.tax_type_to_display == 'igst':
            bd['igst_amount'] = total_tax_amount
            bd['cgst_amount'] = 0.0
            bd['sgst_amount'] = 0.0
        else:
            bd['cgst_amount'] = 0.0
            bd['sgst_amount'] = 0.0
            bd['igst_amount'] = 0.0

        # If no tax was inferred from stored grand_total but tax rates are configured
        # and a tax type is selected, compute tax directly from taxable_sub_total.
        # This handles the live-print scenario where grand_total might not have tax baked-in yet.
        try:
            # Only apply when total_tax_amount is zero (nothing inferred) and taxable_sub_total > 0
            if total_tax_amount == 0.0 and taxable_sub_total > 0.0:
                if self.tax_type_to_display == 'cgsg' and self.enable_cgst_sgst:
                    bd['cgst_amount'] = taxable_sub_total * (float(self.cgst_rate or 0.0) / 100.0)
                    bd['sgst_amount'] = taxable_sub_total * (float(self.sgst_rate or 0.0) / 100.0)
                    bd['igst_amount'] = 0.0
                elif self.tax_type_to_display == 'igst' and self.enable_igst:
                    bd['igst_amount'] = taxable_sub_total * (float(self.igst_rate or 0.0) / 100.0)
                    bd['cgst_amount'] = 0.0
                    bd['sgst_amount'] = 0.0
                # Recompute grand_total to include freshly computed taxes
                grand_total = taxable_sub_total + restaurant_total + bd.get('cgst_amount', 0.0) + bd.get('sgst_amount', 0.0) + bd.get('igst_amount', 0.0)
        except Exception:
            # If anything goes wrong, leave previously computed values
            pass

        # Re-set computed values back into bill dictionary
        bd['sub_total'] = sub_total
        bd['taxable_sub_total'] = taxable_sub_total
        bd['grand_total'] = grand_total
        bd['balance_due'] = bd['grand_total'] - bd.get('advance_payment', 0.0)
        # keep room_discount and room_total_after_discount helpful for PDF rendering
        bd['room_discount'] = room_discount
        bd['room_total_after_discount'] = room_total_after_discount


    # --- MODIFIED: Fixed table overlap issue and added signature blocks & Fixed Rupee Symbol ---
    def get_pdf_content(self, c):
        """Writes the bill content to a ReportLab canvas."""
        self._recalculate_totals()
        bd = self.bill_data
        
        # Define Colors
        color_primary = colors.HexColor(COLOR_PRIMARY)
        color_dark_text = colors.HexColor(COLOR_DARK_TEXT)
        color_odd_row = colors.HexColor(COLOR_ODD_ROW)
        
        c.setFont("Helvetica", 10)
        c.setFillColor(color_dark_text)

        # --- 1. Header ---
        y_cursor = 11 * inch
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(color_primary)
        c.drawString(1 * inch, y_cursor, bd['hotel_name']) 
        y_cursor -= 0.2 * inch
        c.setFont("Helvetica", 10)
        c.setFillColor(color_dark_text)
        # Draw the hotel address using the two address lines if present, otherwise fallback
        addr1 = bd.get('hotel_address_line1') or ''
        addr2 = bd.get('hotel_address_line2') or ''
        if not (addr1 or addr2):
            combined = bd.get('hotel_address') or ''
            parts = [p.strip() for p in combined.split(',', 1)] if combined else ['', '']
            addr1 = parts[0]
            addr2 = parts[1] if len(parts) > 1 else ''

        # Use a slightly smaller line spacing for header address
        header_line_h = 0.18 * inch
        for line in (addr1, addr2):
            if line:
                for part in textwrap.wrap(line, width=90):
                    c.drawString(1 * inch, y_cursor, part)
                    y_cursor -= header_line_h

        c.drawString(1 * inch, y_cursor, f"Contact: {bd.get('hotel_contact','')} | GSTIN: {bd.get('hotel_gst','')}")

        # Title / Right-aligned info (reduce size and increase spacing to avoid overlap)
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors.darkgrey)
        # Allow specific invoice labels for room/restaurant types
        invoice_label = bd.get('invoice_label')
        if not invoice_label:
            if bd.get('file_suffix') == '_restaurant':
                invoice_label = 'RESTAURANT INVOICE'
            elif bd.get('file_suffix') == '_room':
                invoice_label = 'ROOM INVOICE'
            else:
                invoice_label = 'INVOICE'
        c.drawRightString(7.5 * inch, 10.8 * inch, invoice_label)

        c.setFont("Helvetica", 10)
        c.drawRightString(7.5 * inch, 10.55 * inch, f"Booking Ref: {bd['booking_ref']}")
        # Use master formatter to ensure 12-hour AM/PM formatting for issued datetime
        try:
            issued = self.master.format_datetime_for_display(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        except Exception:
            issued = datetime.now().strftime('%d/%m/%Y %I:%M %p')
        c.drawRightString(7.5 * inch, 10.35 * inch, f"Date Issued: {issued}")

        y_cursor = 10.05 * inch


        # --- 2. Guest Info Section ---
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(color_primary)
        c.drawString(1 * inch, y_cursor, "BILL TO")
        
        c.setStrokeColor(color_primary)
        c.setLineWidth(1)
        c.line(1 * inch, y_cursor - 0.05 * inch, 2 * inch, y_cursor - 0.05 * inch)
        y_cursor -= 0.3 * inch

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(color_dark_text)
        c.drawString(1 * inch, y_cursor, bd['guest_name'])
        
        c.setFont("Helvetica", 10)
        y_cursor -= 0.2 * inch
        c.drawString(1 * inch, y_cursor, f"Phone: {bd['guest_phone']}")
        y_cursor -= 0.2 * inch
        try:
            ci_text = self.master.format_datetime_for_display(bd.get('check_in'))
        except Exception:
            ci_text = bd.get('check_in')
        c.drawString(1 * inch, y_cursor, f"Check-In: {ci_text}")
        y_cursor -= 0.2 * inch
        try:
            co_text = self.master.format_datetime_for_display(bd.get('check_out'))
        except Exception:
            co_text = bd.get('check_out')
        c.drawString(1 * inch, y_cursor, f"Check-Out: {co_text}") # Final Check-out Date
        y_cursor -= 0.2 * inch
        # Prefer an explicit display total when provided (partial checkout with manual counts)
        if bd.get('display_persons_total') is not None:
            c.drawString(1 * inch, y_cursor, f"Persons: {bd.get('display_persons_total')} Person(s)")
        else:
            c.drawString(1 * inch, y_cursor, f"Persons: {bd['num_adults']} Adult(s), {bd['num_children']} Child(ren)")


        y_cursor -= 0.4 * inch


        # Determine invoice mode
        is_restaurant_only = (bd.get('file_suffix') == '_restaurant') or (bd.get('invoice_label','').upper().find('RESTAURANT') != -1)
        is_room_only = (bd.get('file_suffix') == '_room') or (bd.get('invoice_label','').upper().find('ROOM') != -1)

        # --- 3. Line Items Table ---
        # Use plain "Rs." prefix for currency to avoid missing-glyph boxes in PDFs
        data = [['Description', 'Qty/Nights', 'Rate', 'Amount']]
        # If restaurant-only invoice, list only restaurant items
        if is_restaurant_only:
            if bd.get('restaurant_items'):
                for item in bd['restaurant_items']:
                    data.append([f"Restaurant: {item[0]}", item[1], f"Rs.{item[2]:.2f}", f"Rs.{item[3]:.2f}"])
            else:
                data.append(["Restaurant: (No items)", '', '', "Rs.0.00"])
        else:
            # Room/resource invoice (normal or room-only)
            if bd.get('room_items'):
                for item in bd['room_items']:
                    rn, nights, rate, amt = item
                    data.append([f"Room Charges (Room {rn})", nights, f"Rs.{rate:.2f}", f"Rs.{amt:.2f}"])
            else:
                # If no per-room items, show the aggregate
                data.append([f"Room Charges (Room {bd.get('room_number','')})", bd.get('num_nights',1), f"Rs.{bd.get('room_rate',0.0):.2f}", f"Rs.{bd.get('room_total',0.0):.2f}"])

            # Append restaurant items only when not room-only
            if bd.get('restaurant_items') and not is_room_only:
                for item in bd['restaurant_items']:
                    data.append([f"Restaurant: {item[0]}", item[1], f"Rs.{item[2]:.2f}", f"Rs.{item[3]:.2f}"])

        if not is_restaurant_only and bd.get('local_charge_info', {}).get('amount', 0.0) > 0:
            local_charge = bd['local_charge_info']
            data.append([f"Local Charge: {local_charge['name']} ({local_charge['details']})", 1, f"Rs.{local_charge['amount']:.2f}", f"Rs.{local_charge['amount']:.2f}"])

        # NOTE: For history reprints, this will only show if total_amount in DB was higher than known components
        if not is_restaurant_only and bd.get('extra_charges_total', 0.0) > 0:
            # For history reprint, show only the aggregate when itemized detail is unavailable
            if 'extra_charges_list' not in bd or not bd['extra_charges_list']:
                data.append(['Extra Services Added (Manual/Unsaved Detail)', 1, 'N/A', f"Rs.{bd['extra_charges_total']:.2f}"])
            else:
                # For live bill print, list individual extra-service items (do not prepend a duplicate aggregate row)
                for item in bd['extra_charges_list']:
                    desc = item.get('desc', 'Custom Charge')
                    amount = item.get('amount', 0.0)
                    data.append([f"Extra: {desc}", 1, f"Rs.{amount:.2f}", f"Rs.{amount:.2f}"])

        table = Table(data, colWidths=[3.5*inch, 1*inch, 1*inch, 1*inch])
        
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_primary),
            ('TEXTCOLOR',(0,0),(-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('ALIGN', (0,1), (0,-1), 'LEFT'),
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            
            ('GRID', (0,0), (-1,-1), 0.5, colors.white), 
        ])
        
        for i in range(1, len(data)):
            if i % 2 != 0: 
                style.add('BACKGROUND', (0, i), (-1, i), color_odd_row)

        table.setStyle(style)
        
        table_height = table.wrapOn(c, 7.5*inch, 8*inch)[1]
        table_y_pos = y_cursor - table_height
        table.drawOn(c, 1*inch, table_y_pos)

        
        # --- 4. Totals Section ---
        
        # Start totals section further down if table is small, but no higher than 8.5"
        totals_section_start = min(table_y_pos - 0.25 * inch, 8.5 * inch) 
        
        totals_data = []
        totals_style_cmds = []

        # Use Rs. prefix for currency to avoid missing-glyph boxes in PDFs
        # Build totals depending on invoice mode
        if is_restaurant_only:
            totals_data.append(['Restaurant Charges:', f"Rs.{bd.get('restaurant_total',0.0):.2f}"])
            # For restaurant-only invoice, do not show taxes, local charge, advance paid
        else:
            totals_data.append(['Room Charges:', f"Rs.{bd.get('room_total',0.0):.2f}"])
            # Include special discount row (room-only) if present
            try:
                if float(bd.get('room_discount', 0.0) or 0.0) > 0.0:
                    totals_data.append(['Special Discount (Room):', f"- Rs.{float(bd.get('room_discount', 0.0)):.2f}"])
            except Exception:
                pass
            # Only include restaurant totals when this is NOT a room-only invoice
            # and when there is a non-zero restaurant total to show.
            if not is_room_only and bd.get('restaurant_total', 0.0) > 0:
                totals_data.append(['Restaurant Charges:', f"Rs.{bd.get('restaurant_total',0.0):.2f}"])
            if bd.get('local_charge_info', {}).get('amount', 0.0) > 0:
                totals_data.append([f"Local Charge ({bd['local_charge_info']['name']}):", f"Rs.{bd['local_charge_info']['amount']:.2f}"])
            if bd.get('extra_charges_total', 0.0) > 0:
                totals_data.append(['Extra Charges (Manual):', f"Rs.{bd['extra_charges_total']:.2f}"])

        subtotal_row = len(totals_data)
        # Use bd['sub_total'] for the subtotal amount (the base for tax calculation)
        totals_data.append(['Sub Total (Before Tax):', f"Rs.{bd['sub_total']:.2f}"])
        totals_style_cmds.append(('LINEABOVE', (0, subtotal_row), (-1, subtotal_row), 1, colors.grey))
        totals_style_cmds.append(('FONTNAME', (0, subtotal_row), (-1, subtotal_row), 'Helvetica-Bold'))
        totals_style_cmds.append(('TOPPADDING', (0, subtotal_row), (-1, subtotal_row), 5))

        # Tax Display using inferred/stored tax details (only when not restaurant-only)
        if not is_restaurant_only:
            if self.tax_type_to_display == 'cgsg':
                totals_data.append([f"CGST ({self.cgst_rate:.1f}%):", f"Rs.{bd['cgst_amount']:.2f}"])
                totals_data.append([f"SGST ({self.sgst_rate:.1f}%):", f"Rs.{bd['sgst_amount']:.2f}"])
            elif self.tax_type_to_display == 'igst':
                totals_data.append([f"IGST ({self.igst_rate:.1f}%):", f"Rs.{bd['igst_amount']:.2f}"])

        grandtotal_row = len(totals_data)
        totals_data.append(['Grand Total:', f"Rs.{bd['grand_total']:.2f}"])
        totals_style_cmds.append(('FONTNAME', (0, grandtotal_row), (-1, grandtotal_row), 'Helvetica-Bold'))

        # Show advance paid only when not restaurant-only
        if not is_restaurant_only:
            advance_row = len(totals_data)
            totals_data.append(['Advance Paid:', f"- Rs.{bd.get('advance_payment',0.0):.2f}"])
            totals_style_cmds.append(('TEXTCOLOR', (0, advance_row), (-1, advance_row), colors.HexColor(COLOR_SUCCESS)))
            totals_style_cmds.append(('FONTNAME', (0, advance_row), (-1, advance_row), 'Helvetica-Bold'))

        balance_row = len(totals_data)
        totals_data.append(['Balance Due:', f"Rs.{bd['balance_due']:.2f}"])
        totals_style_cmds.append(('LINEABOVE', (0, balance_row), (-1, balance_row), 1, colors.black))
        totals_style_cmds.append(('FONTNAME', (0, balance_row), (-1, balance_row), 'Helvetica-Bold'))
        totals_style_cmds.append(('TEXTCOLOR', (0, balance_row), (-1, balance_row), color_primary))
        totals_style_cmds.append(('SIZE', (0, balance_row), (-1, balance_row), 14))
        totals_style_cmds.append(('TOPPADDING', (0, balance_row), (-1, balance_row), 6))

        # We constrain the totals table to the right side
        totals_table = Table(totals_data, colWidths=[3.0*inch, 1*inch]) # Adjusted colWidths to fit on the right
        totals_style = TableStyle([('ALIGN', (0,0), (-1,-1), 'RIGHT')])
        for cmd in totals_style_cmds:
            # We only apply styles to the second column, which holds the amounts.
            # cmd is expected to be like: (CMD, (col_start, row_start), (col_end, row_end), value)
            try:
                if 'COLOR' in cmd[0] or 'SIZE' in cmd[0]:
                    # Safely extract the start/end row indices and apply to column 1 only
                    row_start = cmd[1][1]
                    row_end = cmd[2][1] if len(cmd) > 2 and isinstance(cmd[2], tuple) else row_start
                    totals_style.add(cmd[0], (1, row_start), (1, row_end), cmd[3])
                else:
                    totals_style.add(*cmd)
            except Exception:
                # If a style command is malformed, skip it rather than crashing PDF generation
                print(f"Warning: skipping malformed totals style command: {cmd}")
            
        totals_table.setStyle(totals_style)
        
        totals_width = 4.0 * inch # Combined width of totals table
        
        # FIX: Ensure drawOn uses correct coordinate for table alignment
        totals_height = totals_table.wrapOn(c, totals_width, totals_section_start)[1]
        
        # Draw the totals table starting at 7.5 inches - totals_width from the right
        totals_table.drawOn(c, 7.5 * inch - totals_width, totals_section_start - totals_height)

        
        # --- 5. Signature Block ---
        # Ensure signatures are placed below the drawn totals section
        signature_y = totals_section_start - totals_height - 0.8 * inch 
        
        # Hotel Signature
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1 * inch, signature_y, "Hotel Manager Signature")
        c.line(1 * inch, signature_y - 0.05 * inch, 3.5 * inch, signature_y - 0.05 * inch)

        # Guest Signature
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(7.5 * inch, signature_y, "Guest Signature")
        c.line(5.0 * inch, signature_y - 0.05 * inch, 7.5 * inch, signature_y - 0.05 * inch)
        
        
        # --- 6. Footer ---
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(colors.grey)
        c.drawCentredString(4.25 * inch, 1.0 * inch, "Thank you for staying at " + bd['hotel_name'] + "!")
        c.drawCentredString(4.25 * inch, 0.8 * inch, "This is a computer-generated invoice.")

        c.save()

    def save_pdf(self, parent):
        """Saves the invoice as a PDF file."""
        suffix = str(self.bill_data.get('file_suffix',''))
        filename = f"Invoice_{self.bill_data['booking_ref']}{suffix}.pdf"
        # Save invoices into user's Documents/NexuzyHotelPDFs/Invoices
        try:
            out_dir = get_user_pdfs_dir('Invoices')
            filename = os.path.join(out_dir, filename)
        except Exception:
            pass
        try:
            c = canvas.Canvas(filename, pagesize=A4)
            self.get_pdf_content(c)
            # Cleanup old PDFs after saving (keep 30 days)
            try:
                cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
            except Exception:
                pass
            # c.save() # c.save() is inside get_pdf_content
            messagebox.showinfo("Success", f"Invoice saved as {filename}", parent=parent)
            
            try:
                webbrowser.open(f"file://{os.path.abspath(filename)}")
            except Exception as e:
                print(f"Could not auto-open PDF: {e}")
                
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save PDF file. Ensure you have write permissions.\nError: {e}", parent=parent)

    def print_invoice(self, parent):
        """Prints the invoice."""
        suffix = str(self.bill_data.get('file_suffix',''))
        filename = f"Invoice_Print_{self.bill_data['booking_ref']}{suffix}.pdf"
        try:
            out_dir = get_user_pdfs_dir('Invoices')
            filename = os.path.join(out_dir, filename)
        except Exception:
            pass
        try:
            c = canvas.Canvas(filename, pagesize=A4)
            self.get_pdf_content(c)
            try:
                cleanup_old_pdfs(get_user_pdfs_dir(), days=30)
            except Exception:
                pass
            # c.save() # c.save() is inside get_pdf_content
        except Exception as e:
            messagebox.showerror("PDF Error", f"Could not create PDF for printing.\nError: {e}", parent=parent)
            return

        try:
            if platform.system() == "Windows":
                os.startfile(filename, "print")
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["lpr", filename])
            else:  # Linux
                subprocess.call(["lp", filename])
            messagebox.showinfo("Printing", "Invoice sent to the default printer.", parent=parent)
        except Exception as e:
            messagebox.showerror("Print Error", f"Could not print file. Please ensure you have a default printer configured.\nError: {e}", parent=parent)


# --- BILL WINDOW (MODIFIED TO USE LOCAL CHARGES) ---
class BillWindow(tk.Toplevel):
    def __init__(self, master, bill_data):
        super().__init__(master)
        self.master = master
        self.bill_data = bill_data
        # If a manual display total was provided (partial checkout), promote it
        # immediately so all display and PDF paths use the manual total.
        try:
            dpt = self.bill_data.get('display_persons_total')
            if dpt is not None:
                try:
                    dpt_int = int(dpt)
                except Exception:
                    dpt_int = None
                if dpt_int is not None:
                    # store originals and override visible fields
                    self.bill_data['orig_num_adults'] = self.bill_data.get('num_adults')
                    self.bill_data['orig_num_children'] = self.bill_data.get('num_children')
                    self.bill_data['num_adults'] = dpt_int
                    self.bill_data['num_children'] = 0
                    self._used_manual_persons = True
                else:
                    self._used_manual_persons = False
            else:
                self._used_manual_persons = False
        except Exception:
            self._used_manual_persons = False
        self.title(f"Invoice - {bill_data['booking_ref']}")
        
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass
        
        # Store for custom charges: LIST IS KEPT FOR MANUAL, ON-THE-FLY ADDITIONS
        self.extra_charges = []
        
        # Load tax settings and determine local charge status
        self.load_tax_settings()
        
        # V2.2: Tax type to apply. 'cgsg', 'igst', or 'none'
        self.tax_type_var = tk.StringVar(value='none') 
        self.tax_type_var.trace_add('write', self.rebuild_bill_display)

        self.action_frame = ttk.Frame(self, padding=(10, 10))
        self.action_frame.pack(side='bottom', fill='x')

        self.bill_frame = ttk.Frame(self, padding=10) 
        self.bill_frame.pack(side='top', fill='both', expand=True) 
        
        # V2.2: Set default tax type based on settings
        if self.enable_cgst_sgst:
            self.tax_type_var.set('cgsg')
        elif self.enable_igst:
            self.tax_type_var.set('igst')
        else:
            self.tax_type_var.set('none')
        
        # Ensure local charge calculation is in the bill_data for first display
        self.bill_data['local_charge_info'] = self.local_charge_info 
        
        self.rebuild_bill_display() # Initial build
        
        # Populate the action_frame
        # NOTE: This button is for manual extras *not* predefined local charges
        ttk.Button(self.action_frame, text="Add Extra Service/Charge", command=self.open_add_charge_window).pack(side='left', padx=10, ipady=5)
        # Special Discount: prompts for an amount and applies only to room charges
        ttk.Button(self.action_frame, text="Special Discount", command=self.apply_special_discount).pack(side='left', padx=10, ipady=5)
        ttk.Button(self.action_frame, text="Confirm Payment & Check-Out", command=self.process_checkout, style="Success.TButton").pack(side='left', padx=10, ipady=5)
        ttk.Button(self.action_frame, text="Save as PDF", command=self.save_pdf).pack(side='left', padx=10, ipady=5)
        ttk.Button(self.action_frame, text="Print", command=self.print_invoice).pack(side='left', padx=10, ipady=5)
    
    def load_tax_settings(self):
        """Loads tax settings and local charge settings from the database."""
        try:
            cursor = self.master.db_conn.cursor()
            
            # 1. Load Tax Settings
            cursor.execute("""
                SELECT cgst_rate, sgst_rate, igst_rate, 
                       enable_cgst_sgst, enable_igst 
                FROM settings WHERE id=1
            """)
            settings = cursor.fetchone()
            
            self.cgst_rate = settings[0]
            self.sgst_rate = settings[1]
            self.igst_rate = settings[2]
            self.enable_cgst_sgst = (settings[3] == 'true')
            self.enable_igst = (settings[4] == 'true')
            
            # 2. Load Local Charge Settings
            cursor.execute("SELECT enabled, charge_name, amount, calculation_type FROM local_charges WHERE id=1")
            charge_settings = cursor.fetchone()
            
            # Determine local charge info.
            # If the caller (generate_and_show_bill) supplied a precomputed local_charge_info
            # (for example during a partial checkout with selected_booking_ids and manual counts),
            # prefer that and do NOT re-aggregate across the whole booking_ref which would
            # incorrectly overwrite the caller-provided value.
            if self.bill_data.get('local_charge_info') and isinstance(self.bill_data.get('local_charge_info'), dict):
                # Use the provided local charge info as-is
                self.local_charge_info = self.bill_data['local_charge_info']
            elif charge_settings and charge_settings[0] == 'true':
                # Re-run calculation based on initial data passed to the window
                # Aggregate persons across all booking rows for this booking_ref (group bookings)
                cursor.execute("SELECT SUM(num_adults), SUM(num_children) FROM bookings WHERE booking_ref=?", (self.bill_data.get('booking_ref'),))
                agg = cursor.fetchone() or (0, 0)
                try:
                    na = int(agg[0] or 0)
                except Exception:
                    na = 0
                try:
                    nc = int(agg[1] or 0)
                except Exception:
                    nc = 0

                # Use master method to calculate charge based on aggregated persons
                self.local_charge_info = self.master.calculate_local_charge(
                    self.bill_data.get('num_nights', 1), 
                    na + nc
                )
            else:
                self.local_charge_info = {"name": "", "amount": 0.0, "details": ""}


        except Exception as e:
            print(f"Error loading tax settings: {e}")
            self.enable_cgst_sgst = False
            self.enable_igst = False
            self.cgst_rate, self.sgst_rate, self.igst_rate = 0.0, 0.0, 0.0
            self.local_charge_info = {"name": "", "amount": 0.0, "details": ""}

    def open_add_charge_window(self):
        """Opens the new window to add a predefined or custom charge (Only for manual extras)."""
        AddChargeWindow(self)

    def add_charge_item(self, description, amount):
        """Callback function for AddChargeWindow to add the manual charge."""
        if amount > 0:
            self.extra_charges.append({'desc': description, 'amount': amount})
            self.rebuild_bill_display() # Recalculate and redraw

    def apply_special_discount(self):
        """Prompt for a special discount amount and apply it to the room portion only."""
        try:
            room_total = float(self.bill_data.get('room_total', 0.0))
        except Exception:
            room_total = 0.0

        # Prompt user for discount amount; limit to room_total
        try:
            amount = simpledialog.askfloat("Special Discount", "Enter discount amount to apply to room charges:", parent=self, minvalue=0.0, maxvalue=room_total)
        except Exception:
            amount = None

        if amount is None:
            # user cancelled
            return

        try:
            amount = float(amount)
        except Exception:
            messagebox.showerror("Invalid", "Please enter a valid numeric discount amount.", parent=self)
            return

        if amount < 0:
            messagebox.showerror("Invalid", "Discount cannot be negative.", parent=self)
            return

        if amount > room_total:
            messagebox.showwarning("Adjusted", "Discount exceeds room total; it will be capped to room total.", parent=self)
            amount = room_total

        # Store discount in bill_data and refresh UI
        self.bill_data['room_discount'] = amount
        self.rebuild_bill_display()

    def _recalculate_totals(self):
        """Recalculates all totals based on current data, local charges, and tax settings."""
        bd = self.bill_data
        # Reset tax amounts
        bd['cgst_amount'] = 0.0
        bd['sgst_amount'] = 0.0
        bd['igst_amount'] = 0.0

        # Get base totals
        room_total = float(bd.get('room_total', 0.0) or 0.0)
        restaurant_total = float(bd.get('restaurant_total', 0.0) or 0.0)

        # Apply any special discount that applies only to room charges
        room_discount = float(bd.get('room_discount', 0.0) or 0.0)
        room_total_after_discount = max(0.0, room_total - room_discount)

        # Get extra charges total
        extra_charges_total = sum(item.get('amount', 0.0) for item in getattr(self, 'extra_charges', []))
        local_charge_amount = float(bd.get('local_charge_info', {}).get('amount', 0.0) or 0.0)

        # Recalculate sub_total (includes restaurant and other components)
        # Note: the discount only affects the room portion
        sub_total = room_total_after_discount + restaurant_total + extra_charges_total + local_charge_amount

        # Taxable amount: exclude restaurant_total (restaurant items should not attract GST)
        taxable_amount = room_total_after_discount + extra_charges_total + local_charge_amount

        # V2.2: Apply taxes based on radio button selection but only on taxable_amount
        tax_type = self.tax_type_var.get() if hasattr(self, 'tax_type_var') else bd.get('tax_type_to_display', 'none')

        if tax_type == 'cgsg' and getattr(self, 'enable_cgst_sgst', False):
            bd['cgst_amount'] = taxable_amount * (float(self.cgst_rate or 0.0) / 100.0)
            bd['sgst_amount'] = taxable_amount * (float(self.sgst_rate or 0.0) / 100.0)
            bd['igst_amount'] = 0.0
        elif tax_type == 'igst' and getattr(self, 'enable_igst', False):
            bd['igst_amount'] = taxable_amount * (float(self.igst_rate or 0.0) / 100.0)
            bd['cgst_amount'] = 0.0
            bd['sgst_amount'] = 0.0
        else:
            bd['cgst_amount'] = 0.0
            bd['sgst_amount'] = 0.0
            bd['igst_amount'] = 0.0

        # Update the bill_data dictionary
        bd['extra_charges_total'] = extra_charges_total
        bd['extra_charges_list'] = getattr(self, 'extra_charges', [])
        # Store discount fields for display/pdf usage
        bd['room_discount'] = room_discount
        bd['room_total_after_discount'] = room_total_after_discount
        bd['sub_total'] = sub_total
        bd['taxable_sub_total'] = taxable_amount
        bd['grand_total'] = sub_total + bd.get('cgst_amount', 0.0) + bd.get('sgst_amount', 0.0) + bd.get('igst_amount', 0.0)
        bd['balance_due'] = bd['grand_total'] - bd.get('advance_payment', 0.0)

    def rebuild_bill_display(self, *args):
        """Wipes and rebuilds the entire bill UI."""
        # If this BillWindow was called for a partial checkout and the caller
        # already supplied a precomputed local_charge_info (based on selected rows),
        # prefer that and skip the full-booking aggregation which would otherwise
        # overwrite it with totals across the whole booking_ref.
        try:
            bd = self.bill_data
            if bd.get('selected_booking_ids') and bd.get('local_charge_info'):
                # Use caller-provided local charge and rebuild display immediately
                self._recalculate_totals()
                for widget in self.bill_frame.winfo_children():
                    widget.destroy()
                self._build_invoice_display()
                return
        except Exception:
            # if anything goes wrong here, fall through and let the normal
            # aggregation logic run below
            pass
        # Recompute local charge using aggregated persons across all booking rows for this booking_ref.
        # This ensures group bookings charge local fees based on total persons, not a single row.
        try:
            cursor = self.master.db_conn.cursor()
            cursor.execute("SELECT SUM(num_adults), SUM(num_children) FROM bookings WHERE booking_ref=?", (self.bill_data.get('booking_ref'),))
            pa = cursor.fetchone() or (0, 0)
            na = int(pa[0] or 0)
            nc = int(pa[1] or 0)
            self.bill_data['local_charge_info'] = self.master.calculate_local_charge(self.bill_data.get('num_nights', 1), na + nc)
        except Exception:
            # fall back to already-loaded value
            pass

        self._recalculate_totals()
        
        for widget in self.bill_frame.winfo_children():
            widget.destroy()
        
        self._build_invoice_display()

    def _build_invoice_display(self):
        """Create the text-based invoice display."""
        bd = self.bill_data
        
        # --- 1. Header Frame ---
        header_frame = ttk.Frame(self.bill_frame)
        header_frame.pack(fill='x')

        ttk.Label(header_frame, text=bd['hotel_name'], font=('Helvetica', 20, 'bold')).pack()
        ttk.Label(header_frame, text=bd['hotel_address']).pack()
        ttk.Label(header_frame, text=f"Contact: {bd['hotel_contact']} | GSTIN: {bd['hotel_gst']}").pack()
        ttk.Separator(header_frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(header_frame, text="TAX INVOICE", font=('Helvetica', 16, 'bold')).pack()

        details_frame = ttk.Frame(header_frame)
        details_frame.pack(fill='x', pady=10)
        ttk.Label(details_frame, text=f"Booking Ref: {bd['booking_ref']}").grid(row=0, column=0, sticky='w')
        ttk.Label(details_frame, text=f"Date: {datetime.now().strftime('%d/%m/%Y')}").grid(row=0, column=1, sticky='e')
        ttk.Label(details_frame, text=f"Guest Name: {bd['guest_name']}").grid(row=1, column=0, sticky='w')
        # If the caller supplied an explicit display total (partial checkout with manual counts), prefer that
        if bd.get('display_persons_total') is not None:
            ttk.Label(details_frame, text=f"Persons: {bd.get('display_persons_total')} Person(s)").grid(row=1, column=1, sticky='e')
        else:
            ttk.Label(details_frame, text=f"Persons: {bd['num_adults']} Adult(s), {bd['num_children']} Child(ren)").grid(row=1, column=1, sticky='e')
        # Format check-in/out for display if possible
        try:
            ci_disp = self.master.format_datetime_for_display(bd.get('check_in'))
        except Exception:
            ci_disp = bd.get('check_in')
        try:
            co_disp = self.master.format_datetime_for_display(bd.get('check_out'))
        except Exception:
            co_disp = bd.get('check_out')
        ttk.Label(details_frame, text=f"Check-In: {ci_disp}").grid(row=2, column=0, sticky='w')
        ttk.Label(details_frame, text=f"Check-Out: {co_disp}").grid(row=2, column=1, sticky='e')
        details_frame.columnconfigure(1, weight=1)
        ttk.Separator(header_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- 2. Treeview Frame ---
        tree_frame = ttk.Frame(self.bill_frame)
        tree_frame.pack(fill='x', expand=True, pady=(0, 10))

        cols = ('Description', 'Qty/Nights', 'Rate', 'Amount')
        self.bill_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols:
            self.bill_tree.heading(col, text=col)
        self.bill_tree.column('Description', anchor='w', width=300)
        self.bill_tree.column('Qty/Nights', anchor='center')
        self.bill_tree.column('Rate', anchor='e')
        self.bill_tree.column('Amount', anchor='e')
        
        self.bill_tree.pack(side='left', fill='x', expand=True) 

        self.bill_tree.tag_configure('odd', background=COLOR_ODD_ROW)
        self.bill_tree.tag_configure('even', background=COLOR_EVEN_ROW)
        
        # Room Charges: show one row per room if available
        # Determine UI mode
        is_restaurant_only_ui = (bd.get('file_suffix') == '_restaurant') or (bd.get('invoice_label','').upper().find('RESTAURANT') != -1)
        is_room_only_ui = (bd.get('file_suffix') == '_room') or (bd.get('invoice_label','').upper().find('ROOM') != -1)

        if is_restaurant_only_ui:
            # Restaurant-only UI: we'll populate restaurant items below
            pass
        else:
            # Show room items for normal and room-only invoices
            if bd.get('room_items'):
                for idx, item in enumerate(bd['room_items']):
                    rn, nights, rate, amt = item
                    tag = 'even' if idx % 2 == 0 else 'odd'
                    self.bill_tree.insert('', 'end', values=(f"Room Charges (Room {rn})", nights, f"Rs.{rate:.2f}", f"Rs.{amt:.2f}"), tags=(tag,))
            else:
                self.bill_tree.insert('', 'end', values=(
                    f"Room Charges (Room {bd.get('room_number','')})",
                    bd.get('num_nights', 1),
                    f"Rs.{bd.get('room_rate',0.0):.2f}",
                    f"Rs.{bd.get('room_total',0.0):.2f}"
                ), tags=('even',))
        # Restaurant Charges - show only when UI is not restaurant-only (restaurant-only shows only restaurant items below)
        if not is_restaurant_only_ui and bd.get('restaurant_items'):
            list_start_index = len(self.bill_tree.get_children()) - 1
            for i, item in enumerate(bd['restaurant_items']):
                tag = 'even' if (i + list_start_index) % 2 == 0 else 'odd'
                self.bill_tree.insert('', 'end', values=(f"Restaurant: {item[0]}", item[1], f"Rs.{item[2]:.2f}", f"Rs.{item[3]:.2f}"), tags=(tag,))

        # If UI is restaurant-only, populate table with only restaurant items
        if is_restaurant_only_ui and bd.get('restaurant_items'):
            for i, item in enumerate(bd['restaurant_items']):
                tag = 'even' if i % 2 == 0 else 'odd'
                self.bill_tree.insert('', 'end', values=(f"Restaurant: {item[0]}", item[1], f"Rs.{item[2]:.2f}", f"Rs.{item[3]:.2f}"), tags=(tag,))
        
        # --- NEW: Local Government Charge ---
        if bd.get('local_charge_info', {}).get('amount', 0.0) > 0:
            local_charge = bd['local_charge_info']
            tag = 'evenrow' if len(self.bill_tree.get_children()) % 2 == 0 else 'oddrow'
            self.bill_tree.insert('', 'end', values=(
                f"{local_charge['name']} ({local_charge['details']})",
                1,
                f"Rs.{local_charge['amount']:.2f}",
                f"Rs.{local_charge['amount']:.2f}"
            ), tags=(tag,))
        # --- END NEW ---
        
        # Extra Charges (Manual)
        # Extra Charges (Manual) - show only individual item rows (avoid duplicate aggregate row)
        if bd.get('extra_charges_list'):
            list_start_index = len(self.bill_tree.get_children())
            for i, item in enumerate(bd['extra_charges_list']):
                tag = 'even' if (i + list_start_index) % 2 == 0 else 'odd'
                desc = item.get('desc', 'Custom Charge')
                amt = item.get('amount', 0.0)
                self.bill_tree.insert('', 'end', values=(f"Extra: {desc}", 1, f"Rs.{amt:.2f}", f"Rs.{amt:.2f}"), tags=(tag,))

        # *** FIX: SET DYNAMIC HEIGHT ***
        num_items = len(self.bill_tree.get_children())
        if num_items == 0:
             num_items = 1 
        self.bill_tree.configure(height=num_items)
        # *** END FIX ***

        # --- 3. Totals Frame ---
        totals_frame = ttk.Frame(self.bill_frame)
        totals_frame.pack(fill='x')
        
        row_index = 0
        
        # --- V2.2: Tax Type Radio Buttons ---
        if self.enable_cgst_sgst or self.enable_igst: 
            tax_choice_frame = ttk.Frame(totals_frame)
            tax_choice_frame.grid(row=row_index, column=0, columnspan=2, pady=(5, 10))
            ttk.Label(tax_choice_frame, text="Apply Tax:", font=('Helvetica', 10, 'bold')).pack(side='left', padx=10)
            
            ttk.Radiobutton(tax_choice_frame, text="No Tax", variable=self.tax_type_var, value='none').pack(side='left', padx=10)

            cgst_state = 'normal' if self.enable_cgst_sgst else 'disabled'
            ttk.Radiobutton(tax_choice_frame, text="CGST/SGST", variable=self.tax_type_var, value='cgsg', state=cgst_state).pack(side='left', padx=10)
            
            igst_state = 'normal' if self.enable_igst else 'disabled'
            ttk.Radiobutton(tax_choice_frame, text="IGST", variable=self.tax_type_var, value='igst', state=igst_state).pack(side='left', padx=10)

            row_index += 1

        # Helper to add rows
        def add_total_row(label, value, font_weight='normal', color=COLOR_DARK_TEXT):
            nonlocal row_index
            
            if "Balance Due" in label:
                ttk.Label(totals_frame, text=label, style="Balance.TLabel").grid(row=row_index, column=0, sticky='e', padx=10, pady=1)
                ttk.Label(totals_frame, text=f"Rs.{value:.2f}", style="Balance.TLabel").grid(row=row_index, column=1, sticky='e', pady=1)
            else:
                font_spec = ('Helvetica', 10, font_weight)
                if "Grand Total" in label:
                    font_spec = ('Helvetica', 11, 'bold')
                
                ttk.Label(totals_frame, text=label, font=font_spec, foreground=color).grid(row=row_index, column=0, sticky='e', padx=10, pady=1)
                ttk.Label(totals_frame, text=f"Rs.{value:.2f}", font=font_spec, foreground=color).grid(row=row_index, column=1, sticky='e', pady=1)
            
            row_index += 1

        # Add totals depending on invoice mode
        if is_restaurant_only_ui:
            # Restaurant-only: show restaurant total and extra charges only; no tax, no local charge, no advance
            if bd.get('restaurant_total', 0.0) is not None:
                add_total_row("Restaurant Charges Total:", bd.get('restaurant_total', 0.0))
            if bd.get('extra_charges_total', 0.0) > 0:
                add_total_row("Extra Services Total:", bd['extra_charges_total'])
            grand = bd.get('restaurant_total', 0.0) + bd.get('extra_charges_total', 0.0)
            add_total_row("Grand Total:", grand)
        else:
            add_total_row("Room Charges Total:", bd['room_total'])
            # Show special discount (room-only) if present
            if bd.get('room_discount', 0.0) and float(bd.get('room_discount', 0.0)) > 0.0:
                add_total_row("Special Discount (Room only):", -float(bd.get('room_discount', 0.0)))
            add_total_row("Restaurant Charges Total (Non-taxable):", bd['restaurant_total'])

            if bd.get('local_charge_info', {}).get('amount', 0.0) > 0:
                add_total_row(f"Local Charge ({bd['local_charge_info']['name']}):", bd['local_charge_info']['amount'])

            if bd.get('extra_charges_total', 0.0) > 0:
                 add_total_row("Extra Services Total:", bd['extra_charges_total'])

            # Show taxable subtotal (exclude restaurant items from taxable base)
            taxable_display = bd.get('taxable_sub_total', bd.get('sub_total', 0.0) - bd.get('restaurant_total', 0.0))
            add_total_row("Sub Total (Before Tax):", taxable_display, 'bold')

            # V2.2: Conditional Tax Display
            tax_type = self.tax_type_var.get()
            if tax_type == 'cgsg':
                add_total_row(f"CGST ({self.cgst_rate:.1f}%):", bd['cgst_amount'])
                add_total_row(f"SGST ({self.sgst_rate:.1f}%):", bd['sgst_amount'])
            elif tax_type == 'igst':
                add_total_row(f"IGST ({self.igst_rate:.1f}%):", bd['igst_amount'])

            add_total_row("Grand Total:", bd['grand_total'])

            # Advance Paid
            add_total_row("Advance Paid:", -bd.get('advance_payment', 0.0))
        
        # Separator
        ttk.Separator(totals_frame, orient='horizontal').grid(row=row_index, column=0, columnspan=2, sticky='ew', pady=(3, 5), padx=50)
        row_index += 1
        
        # Balance Due
        add_total_row("Balance Due:", bd['balance_due'])
        
        totals_frame.columnconfigure(0, weight=1)

    def process_checkout(self):
        """Finalize checkout in the database and open post-checkout window."""
        if messagebox.askyesno("Confirm", "Confirm payment has been received and proceed with check-out?", parent=self):
            try:
                # Recalculate one last time
                self._recalculate_totals()
                
                cursor = self.master.db_conn.cursor()
                
                # V2.1: Use provided checkout timestamp if available (e.g., manual entry), else now
                check_out_timestamp = self.bill_data.get('check_out') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # If this bill_data contains selected_booking_ids, update only those rows (partial checkout)
                selected_ids = self.bill_data.get('selected_booking_ids')
                if selected_ids:
                    try:
                        placeholders = ','.join(['?'] * len(selected_ids))
                        params = [self.bill_data['grand_total'], check_out_timestamp] + list(selected_ids)
                        cursor.execute(f"UPDATE bookings SET status='Checked-Out', total_amount=?, actual_check_out=? WHERE id IN ({placeholders})", tuple(params))
                    except Exception:
                        # fallback to booking_ref-based update if something goes wrong
                        cursor.execute("UPDATE bookings SET status='Checked-Out', total_amount=?, actual_check_out=? WHERE booking_ref=?",
                                       (self.bill_data['grand_total'], check_out_timestamp, self.bill_data['booking_ref']))

                    # Update room status only for the affected booking rows
                    try:
                        placeholders = ','.join(['?'] * len(selected_ids))
                        cursor.execute(f"SELECT room_id FROM bookings WHERE id IN ({placeholders})", tuple(selected_ids))
                        room_rows = cursor.fetchall()
                        for rr in room_rows:
                            try:
                                cursor.execute("UPDATE rooms SET status='Available' WHERE id=?", (rr[0],))
                            except Exception:
                                logger.exception("Failed to update room status for room id %s", rr[0])
                    except Exception:
                        logger.exception("Failed to update rooms during partial checkout; attempting fallback")
                        try:
                            if 'room_id' in self.bill_data and self.bill_data['room_id']:
                                cursor.execute("UPDATE rooms SET status='Available' WHERE id=?", (self.bill_data['room_id'],))
                        except Exception:
                            logger.exception("Failed to update fallback room status during checkout")
                else:
                    # Update booking status, total amount, and actual check-out time for whole booking_ref
                    cursor.execute("UPDATE bookings SET status='Checked-Out', total_amount=?, actual_check_out=? WHERE booking_ref=?",
                                   (self.bill_data['grand_total'], check_out_timestamp, self.bill_data['booking_ref']))

                    # Update room status for all rooms associated with this booking_ref
                    try:
                        cursor.execute("SELECT room_id FROM bookings WHERE booking_ref=?", (self.bill_data['booking_ref'],))
                        room_rows = cursor.fetchall()
                        for rr in room_rows:
                            try:
                                cursor.execute("UPDATE rooms SET status='Available' WHERE id=?", (rr[0],))
                            except Exception:
                                # continue updating other rooms even if one fails
                                logger.exception("Failed to update room status for room id %s", rr[0])
                    except Exception:
                        # Fallback: if no rooms found or error, attempt to update single room if present in bill_data
                        try:
                            if 'room_id' in self.bill_data and self.bill_data['room_id']:
                                cursor.execute("UPDATE rooms SET status='Available' WHERE id=?", (self.bill_data['room_id'],))
                        except Exception:
                            logger.exception("Failed to update fallback room status during checkout")
                
                self.master.db_conn.commit()
                messagebox.showinfo("Success", "Check-out completed successfully.", parent=self.master)
                self.master.load_bookings_data()
                self.master.refresh_dashboard()
                self.master.load_history_data() 
                
                # --- NEW: Open Post-Checkout Actions Window ---
                final_bill_data = self.bill_data.copy()
                # Ensure correct total values are captured
                final_bill_data['extra_charges_list'] = self.extra_charges
                final_bill_data['extra_charges_total'] = sum(item['amount'] for item in self.extra_charges)
                final_bill_data['local_charge_info'] = self.bill_data['local_charge_info']
                
                # Set the correct tax type for the PDF utility
                final_bill_data['tax_type_to_display'] = self.tax_type_var.get()
                # Ensure checkout timestamp is included in the final bill data so PDFs/history show exact time
                final_bill_data['actual_check_out'] = check_out_timestamp
                # Also set check_out to the precise timestamp for immediate PDF display
                final_bill_data['check_out'] = check_out_timestamp
                
                self.destroy()
                PostCheckoutWindow(self.master, final_bill_data)
                # --- END NEW ---
                
            except Exception as e:
                messagebox.showerror("Database Error", f"An error occurred: {e}", parent=self)
                
    # --- BillWindow PDF/Print/Save methods simply call the utility class now ---
    def save_pdf(self):
        # Create BillUtility instance with current bill data and manual extras
        utility = BillUtility(self.master, self.bill_data)
        utility.bill_data['extra_charges_list'] = self.extra_charges
        # Force tax type from UI selection to utility display
        utility.tax_type_to_display = self.tax_type_var.get()

        utility.save_pdf(self)

    def print_invoice(self):
        # Create BillUtility instance with current bill data and manual extras
        utility = BillUtility(self.master, self.bill_data)
        utility.bill_data['extra_charges_list'] = self.extra_charges
        # Force tax type from UI selection to utility display
        utility.tax_type_to_display = self.tax_type_var.get()
             
        utility.print_invoice(self)


# --- NEW: Post-Checkout Action Window ---
class PostCheckoutWindow(tk.Toplevel):
    def __init__(self, master, bill_data):
        super().__init__(master)
        self.master = master
        self.bill_data = bill_data
        self.title("Check-Out Actions")
        # Make dialog wider so all action buttons are visible and text does not wrap
        self.geometry("760x240")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except Exception:
            pass

        # Instantiate BillUtility once and set tax display
        self.bill_utility = BillUtility(master, bill_data)
        self.bill_utility.tax_type_to_display = bill_data.get('tax_type_to_display', 'none')

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame,
                  text=f"Check-Out Complete for {bill_data['booking_ref']}!",
                  font=('Helvetica', 14, 'bold'),
                  foreground=COLOR_SUCCESS).pack(pady=10)

        ttk.Label(frame,
                  text="What would you like to do with the final invoice?",
                  font=('Helvetica', 10)).pack(pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10, fill='x')

        # Arrange primary actions in two rows so all buttons are visible on narrow windows
        top_btns = ttk.Frame(btn_frame)
        top_btns.grid(row=0, column=0, sticky='w', pady=(0,6))
        bottom_btns = ttk.Frame(btn_frame)
        bottom_btns.grid(row=1, column=0, sticky='w')

        # Primary actions (row 0) - do not auto-close so the user can perform multiple saves/prints
        ttk.Button(top_btns, text="Save as PDF",
               command=lambda: self.bill_utility.save_pdf(self),
               style="Accent.TButton").pack(side='left', padx=5, ipady=5)

        ttk.Button(top_btns, text="Print Bill",
               command=lambda: self.bill_utility.print_invoice(self),
               style="TButton").pack(side='left', padx=5, ipady=5)

        # Separate Room-only and Restaurant-only actions
        def _room_pdf_and_close():
            rd = dict(self.bill_data)
            # Remove restaurant items/totals for room-only invoice
            rd['restaurant_items'] = []
            rd['restaurant_total'] = 0.0
            rd['file_suffix'] = '_room'
            rd['invoice_label'] = 'ROOM INVOICE'
            util = BillUtility(self.master, rd)
            # keep tax selection for room-only (room taxes apply)
            util.tax_type_to_display = self.bill_data.get('tax_type_to_display', 'none')
            # Clear cached subtotal/grandtotal so BillUtility recalculates totals without restaurant
            rd.pop('sub_total', None)
            rd.pop('taxable_sub_total', None)
            rd.pop('grand_total', None)
            util.bill_data = rd
            util.save_pdf(self)

        def _restaurant_pdf_and_close():
            rd = dict(self.bill_data)
            # Remove room charges for restaurant-only invoice
            rd['room_total'] = 0.0
            rd['room_rate'] = 0.0
            rd['room_number'] = ''
            rd['file_suffix'] = '_restaurant'
            rd['invoice_label'] = 'RESTAURANT INVOICE'
            # Ensure restaurant invoice shows no tax
            util = BillUtility(self.master, rd)
            util.tax_type_to_display = 'none'
            # Clear cached subtotal/grandtotal so BillUtility recalculates totals for restaurant-only
            # Remove any room-specific items so restaurant invoice contains only restaurant orders
            rd['room_items'] = []
            rd['room_total'] = 0.0
            rd['room_rate'] = 0.0
            rd['room_number'] = ''
            # Restaurant invoice should not show advance, local charges, or taxes
            rd['advance_payment'] = 0.0
            rd['advance_paid'] = 0.0
            rd['local_charge_info'] = {"name": "", "amount": 0.0, "details": ""}
            rd.pop('sub_total', None)
            rd.pop('taxable_sub_total', None)
            rd.pop('grand_total', None)
            util.bill_data = rd
            util.save_pdf(self)

        def _room_print_and_close():
            rd = dict(self.bill_data)
            rd['restaurant_items'] = []
            rd['restaurant_total'] = 0.0
            rd['file_suffix'] = '_room'
            util = BillUtility(self.master, rd)
            util.tax_type_to_display = self.bill_data.get('tax_type_to_display', 'none')
            rd.pop('sub_total', None)
            rd.pop('taxable_sub_total', None)
            rd.pop('grand_total', None)
            util.bill_data = rd
            util.print_invoice(self)

        def _restaurant_print_and_close():
            rd = dict(self.bill_data)
            rd['room_total'] = 0.0
            rd['room_rate'] = 0.0
            rd['room_number'] = ''
            rd['file_suffix'] = '_restaurant'
            util = BillUtility(self.master, rd)
            util.tax_type_to_display = 'none'
            # Remove any room-specific items so restaurant invoice contains only restaurant orders
            rd['room_items'] = []
            rd['room_total'] = 0.0
            rd['room_rate'] = 0.0
            rd['room_number'] = ''
            rd['advance_payment'] = 0.0
            rd['advance_paid'] = 0.0
            rd['local_charge_info'] = {"name": "", "amount": 0.0, "details": ""}
            rd.pop('sub_total', None)
            rd.pop('taxable_sub_total', None)
            rd.pop('grand_total', None)
            util.bill_data = rd
            util.print_invoice(self)

        # Room & Restaurant actions (row 1)
        ttk.Button(bottom_btns, text="Save Room Bill (PDF)", command=_room_pdf_and_close).pack(side='left', padx=5, ipady=5)
        ttk.Button(bottom_btns, text="Print Room Bill", command=_room_print_and_close).pack(side='left', padx=5, ipady=5)
        ttk.Button(bottom_btns, text="Save Restaurant Bill (PDF)", command=_restaurant_pdf_and_close).pack(side='left', padx=5, ipady=5)
        ttk.Button(bottom_btns, text="Print Restaurant Bill", command=_restaurant_print_and_close).pack(side='left', padx=5, ipady=5)

        # Share option
        ttk.Button(bottom_btns, text="Share (Email)",
               command=lambda: [messagebox.showinfo("Share", "Sharing via Email is a planned feature.\nPDF is saved locally.", parent=self), self.destroy()],
               style="TButton").pack(side='left', padx=5, ipady=5)

        ttk.Button(frame, text="Close", command=self.destroy).pack(pady=10)

        # Prevent window deletion errors by only destroying this window
        self.protocol("WM_DELETE_WINDOW", self.destroy)


# --- NEW: Additional Guest Documentation Entry Window ---
class AdditionalGuestEntryWindow(tk.Toplevel):
    def __init__(self, master, booking_ref, total_persons):
        super().__init__(master)
        self.master = master
        self.booking_ref = booking_ref
        self.total_persons = total_persons
        self.current_person = 2 # Start from the second person
        self.guest_entries = []
        self.result = False

        self.title(f"Enter Documents for Additional Guests (1 of {total_persons-1})")
        self.geometry("500x350")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        try:
            self.iconbitmap('logo.ico')
        except:
             pass
        
        self.frame = ttk.Frame(self, padding=20)
        self.frame.pack(fill='both', expand=True)

        ttk.Label(self.frame, text=f"Booking Ref: {booking_ref}", font=('Helvetica', 12, 'bold')).pack(pady=5)
        ttk.Label(self.frame, text=f"Total Guests Booked: {total_persons} (Primary Guest details saved)", font=('Helvetica', 10)).pack(pady=(0, 10))

        self.person_label = ttk.Label(self.frame, text="", font=('Helvetica', 11, 'bold'), foreground=COLOR_PRIMARY)
        self.person_label.pack(pady=(10, 5))

        self.create_input_fields()
        self.next_button = ttk.Button(self.frame, text="Next Guest", command=self.next_person, style="Accent.TButton")
        # Anchor the Next/Finish button to the bottom so it stays visible
        btnf = ttk.Frame(self)
        btnf.pack(side='bottom', fill='x', pady=10)
        self.next_button.pack(in_=btnf, side='right', padx=10, ipady=5, ipadx=10)
        
        self.update_ui()
        
    def create_input_fields(self):
        """Creates dynamic input fields for one guest."""
        self.input_frame = ttk.Frame(self.frame)
        self.input_frame.pack(fill='x', pady=10)
        
        ttk.Label(self.input_frame, text="Guest Full Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        name_entry = ttk.Entry(self.input_frame, width=30)
        name_entry.grid(row=0, column=1, padx=5, pady=5, ipady=3)
        
        # ID proof collection removed - only collect guest name now
        self.input_frame.columnconfigure(1, weight=1)
        self.guest_entries = [name_entry]

    def update_ui(self):
        """Updates the person counter and button text."""
        self.person_label.config(text=f"Enter Details for Person {self.current_person} of {self.total_persons}")
        
        # Reset fields for new entry
        for entry in self.guest_entries:
            if entry.winfo_class() == 'TCombobox':
                entry.set("Aadhaar Card")
            else:
                entry.delete(0, 'end')
        
        if self.current_person == self.total_persons:
             self.next_button.config(text="Finish Check-In")

    def next_person(self):
        """Saves the current person's details and moves to the next."""
        name = self.guest_entries[0].get()
        if not name:
            messagebox.showerror("Error", "Name is mandatory.", parent=self)
            return

        try:
            cursor = self.master.db_conn.cursor()
            # Do not store ID proofs; only save booking_ref, person_name and is_primary
            cursor.execute("""
                INSERT INTO booking_persons (booking_ref, person_name, is_primary)
                VALUES (?, ?, 'false')
            """, (self.booking_ref, name))
            self.master.db_conn.commit()
            logger.info("Added additional guest '%s' for booking %s", name, self.booking_ref)
        except Exception as e:
            logger.exception("Could not save additional guest %s for booking %s: %s", name, self.booking_ref, e)
            messagebox.showerror("Database Error", f"Could not save guest {name}: {e}", parent=self)
            return

        if self.current_person < self.total_persons:
            self.current_person += 1
            self.update_ui()
        else:
            self.result = True
            self.destroy()

    def show(self):
        """Makes the window modal and returns the result."""
        self.grab_set()
        self.wait_window()
        return self.result

# --- NEW: Extend Stay Window ---
class ExtendStayWindow(tk.Toplevel):
    def __init__(self, master, booking_ref):
        super().__init__(master)
        self.master = master
        self.booking_ref = booking_ref
        self.title(f"Extend Stay for {booking_ref}")
        self.geometry("469x269")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        cursor = self.master.db_conn.cursor()
        # Fetch all bookings for this reference (group bookings may have multiple room rows)
        cursor.execute("SELECT check_out, room_id FROM bookings WHERE booking_ref=?", (booking_ref,))
        rows = cursor.fetchall()
        if not rows:
            messagebox.showerror("Error", "Booking not found.", parent=self)
            self.destroy()
            return

        # If multiple bookings exist, store list of room_ids and use the latest check_out as current
        self.room_rows = rows
        try:
            # Use the maximum check_out (latest) as representative
            check_outs = [r[0] for r in rows]
            self.current_check_out = max(check_outs)
        except Exception:
            self.current_check_out = rows[0][0]
        # Keep room_id as None to indicate group operation unless single
        if len(rows) == 1:
            self.room_id = rows[0][1]
        else:
            self.room_id = None

        ttk.Label(frame, text=f"Booking Reference: {self.booking_ref}", font=('Helvetica', 11, 'bold')).pack(pady=5)
        try:
            cur_co_disp = self.master.format_datetime_for_display(self.current_check_out)
        except Exception:
            cur_co_disp = str(self.current_check_out)
        ttk.Label(frame, text=f"Current Check-Out: {cur_co_disp}", font=('Helvetica', 10)).pack(pady=5)

        ttk.Label(frame, text="New Check-Out Date (DD/MM/YYYY or DD/MM/YYYY HH:MM):").pack(pady=(10, 0))
        self.new_check_out_entry = ttk.Entry(frame)
        # Suggest current check-out + 1 day (work with master parsing helper)
        try:
            cur_iso = self.master._parse_display_date_to_iso(self.current_check_out)
            try:
                cur_dt = datetime.strptime(cur_iso, '%Y-%m-%d %H:%M')
            except Exception:
                cur_dt = datetime.strptime(cur_iso, '%Y-%m-%d')
            next_day = cur_dt + timedelta(days=1)
        except Exception:
            next_day = datetime.now() + timedelta(days=1)

        self.new_check_out_entry.insert(0, next_day.strftime('%d/%m/%Y'))
        self.new_check_out_entry.pack(ipady=3)

        # Anchor the Extend button to the bottom so it is never clipped
        btnf = ttk.Frame(self)
        btnf.pack(side='bottom', fill='x', pady=10)
        ttk.Button(btnf, text="Extend Booking", command=self.update_extension, style="Accent.TButton").pack(side='right', padx=10, ipady=5, ipadx=10)
        try:
            self.minsize(420, 220)
        except Exception:
            pass

    def update_extension(self):
        """Validates and updates the booking's check-out date."""
        new_check_out = self.new_check_out_entry.get()

        # Normalize display date to ISO for DB
        new_co_iso = self.master._parse_display_date_to_iso(new_check_out)
        try:
            try:
                d_out_new = datetime.strptime(new_co_iso, '%Y-%m-%d %H:%M')
            except Exception:
                d_out_new = datetime.strptime(new_co_iso, '%Y-%m-%d')

            try:
                cur_iso = self.master._parse_display_date_to_iso(self.current_check_out)
                try:
                    d_out_current = datetime.strptime(cur_iso, '%Y-%m-%d %H:%M')
                except Exception:
                    d_out_current = datetime.strptime(cur_iso, '%Y-%m-%d')
            except Exception:
                d_out_current = datetime.now()

            if d_out_new <= d_out_current:
                messagebox.showerror("Invalid Date", "The new check-out date must be *after* the current check-out date.", parent=self)
                return
        except Exception:
            messagebox.showerror("Invalid Date Format", "Please use DD/MM/YYYY or YYYY-MM-DD formats.", parent=self)
            return

        cursor = self.master.db_conn.cursor()
        # For group bookings, check conflicts for ANY room in the group
        try:
            if getattr(self, 'room_rows', None) and len(self.room_rows) > 1:
                room_ids = [str(r[1]) for r in self.room_rows]
                placeholders = ','.join(['?'] * len(room_ids))
                params = room_ids + [self.booking_ref, new_co_iso, self.current_check_out]
                query_check_conflict = f"SELECT COUNT(*) FROM bookings WHERE room_id IN ({placeholders}) AND booking_ref != ? AND status IN ('Reserved', 'Checked-In') AND check_in <= ? AND check_out >= ?"
                cursor.execute(query_check_conflict, params)
            else:
                # Single room case
                cursor.execute("SELECT COUNT(*) FROM bookings WHERE room_id = ? AND booking_ref != ? AND status IN ('Reserved', 'Checked-In') AND check_in <= ? AND check_out >= ?", (self.room_id, self.booking_ref, new_co_iso, self.current_check_out))

            conflict = cursor.fetchone()[0]
            if conflict > 0:
                messagebox.showerror("Booking Conflict", "The room(s) are reserved by another guest immediately after the current check-out. Extension denied.", parent=self)
                return
        except Exception as e:
            messagebox.showerror("Error", f"Could not verify booking conflicts: {e}", parent=self)
            return

        try:
            # Apply the extension to all booking rows for this booking_ref (group extension)
            cursor.execute("UPDATE bookings SET check_out=? WHERE booking_ref=?",
                           (new_co_iso, self.booking_ref))
            self.master.db_conn.commit()
            messagebox.showinfo("Success", f"Stay extended successfully to {new_check_out}.", parent=self)
            self.master.load_bookings_data()
            self.master.refresh_dashboard()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}", parent=self)


class AddChargeWindow(tk.Toplevel):
    def __init__(self, master_bill_window):
        super().__init__(master_bill_window)
        self.master_bill = master_bill_window
        self.title("Add Charge / Fee")
        # Slightly taller so the action button is always visible on smaller screens
        self.geometry("420x300")
        self.transient(master_bill_window)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass

        # Removed loading predefined charges from DB as requested, this is now for manual, one-off charges only.
        self.charge_var = tk.StringVar(value="Custom Service Fee")

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Charge Type:").pack(anchor='w')
        # Simple label/entry for the charge type description (no combobox)
        ttk.Entry(frame, textvariable=self.charge_var).pack(fill='x', ipady=3)

        ttk.Label(frame, text="Description: (Optional)").pack(anchor='w', pady=(10, 0))
        self.desc_entry = ttk.Entry(frame)
        self.desc_entry.pack(fill='x', ipady=3)

        ttk.Label(frame, text="Amount (Rs.):").pack(anchor='w', pady=(10, 0))
        self.amount_entry = ttk.Entry(frame)
        self.amount_entry.pack(fill='x', ipady=3)

        add_btn = ttk.Button(frame, text="Add to Bill", command=self.add_to_bill, style="Accent.TButton")
        # Anchor the button at the bottom so it doesn't get clipped by overlapping windows
        add_btn.pack(side='bottom', pady=(12,6), ipadx=12, ipady=8)

        # Ensure the dialog is lifted and receives focus so users can see the action button
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

        # Set focus to amount entry for quick keyboard entry
        try:
            self.amount_entry.focus()
        except Exception:
            pass


    def add_to_bill(self):
        desc = self.charge_var.get()
        if self.desc_entry.get():
            desc = f"{desc}: {self.desc_entry.get()}"
            
        try:
            amount = float(self.amount_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Amount must be a valid number.", parent=self)
            return

        if not desc:
            messagebox.showerror("Error", "Description cannot be empty.", parent=self)
            return

        # Call the BillWindow's callback function
        self.master_bill.add_charge_item(desc, amount)
        self.destroy()


class RestaurantOrderWindow(tk.Toplevel):
    def __init__(self, master, booking_ref, room_number):
        super().__init__(master)
        self.master = master
        self.booking_ref = booking_ref
        self.room_number = room_number
        self.title(f"Add Order to Room {room_number} (Ref: {self.booking_ref})")

        self.geometry("600x500")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill='both', expand=True)

        # --- V1.9 FIX: Create action frame at the bottom FIRST ---
        action_frame = ttk.Frame(frame)
        action_frame.pack(side='bottom', fill='x', pady=(10, 0))

        ttk.Button(action_frame, text="Confirm and Add Order to Room", command=self.confirm_order, style="Success.TButton").pack(ipady=5, ipadx=10)
        # --- END FIX ---

        # Menu selection
        menu_frame = ttk.LabelFrame(frame, text="Select Menu Items", padding=15)
        menu_frame.pack(side='top', fill='x')

        cursor = self.master.db_conn.cursor()
        cursor.execute("SELECT id, item_name, price FROM restaurant_menu")
        # Use the rupee symbol in the UI (will render on most systems); fallback handled elsewhere for PDFs
        self.menu_items = {f"{name} (₹{price:.2f})": (item_id, price) for item_id, name, price in cursor.fetchall()}

        self.item_combo = ttk.Combobox(menu_frame, values=list(self.menu_items.keys()), width=40)
        self.item_combo.pack(side='left', padx=5, ipady=3)

        ttk.Label(menu_frame, text="Qty:").pack(side='left', padx=(10, 0))
        self.qty_spinbox = ttk.Spinbox(menu_frame, from_=1, to=20, width=5, font=('Helvetica', 10))
        self.qty_spinbox.set(1)  # --- V2.0: Set default value to 1 ---
        self.qty_spinbox.pack(side='left', padx=5, ipady=3)

        ttk.Button(menu_frame, text="Add to Order", command=self.add_to_cart).pack(side='left', padx=10, ipady=3)

        # Cart
        cart_frame = ttk.LabelFrame(frame, text="Current Order", padding=15)
        cart_frame.pack(side='top', fill='both', expand=True, pady=10)

        cols = ('Item', 'Qty', 'Price (₹)', 'Total (₹)')
        self.cart_tree = ttk.Treeview(cart_frame, columns=cols, show='headings')
        for col in cols:
            self.cart_tree.heading(col, text=col)
        self.cart_tree.column('Qty', anchor='center', width=50)
        self.cart_tree.column('Price (₹)', anchor='e', width=80)
        self.cart_tree.column('Total (₹)', anchor='e', width=80)

        self.cart_tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.cart_tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        self.cart_tree.pack(fill='both', expand=True)

    def add_to_cart(self):
        """Adds the selected item to the order cart."""
        selected_item_str = self.item_combo.get()
        if not selected_item_str:
            return

        try:
            quantity = int(self.qty_spinbox.get())
        except ValueError:
            messagebox.showerror("Error", "Quantity must be a number.", parent=self)
            return

        item_id, price = self.menu_items[selected_item_str]
        # Extract the name robustly (split on last ' (') so it works regardless of currency formatting
        item_name = selected_item_str.rsplit(' (', 1)[0]
        total = price * quantity

        # Check if item is already in cart
        for item_iid in self.cart_tree.get_children():
            if str(item_iid) == str(item_id):
                current_qty = int(self.cart_tree.item(item_iid)['values'][1])
                new_qty = current_qty + quantity
                new_total = price * new_qty
                # Show rupee symbol in UI
                self.cart_tree.item(item_iid, values=(item_name, new_qty, f"₹{price:.2f}", f"₹{new_total:.2f}"))
                self.qty_spinbox.set(1)  # Reset qty to 1
                self.item_combo.set("")  # Reset combo
                return

        tag = 'evenrow' if len(self.cart_tree.get_children()) % 2 == 0 else 'oddrow'
        # Insert with rupee symbol for price and total
        self.cart_tree.insert('', 'end', values=(item_name, quantity, f"₹{price:.2f}", f"₹{total:.2f}"), iid=item_id, tags=(tag,))
        self.qty_spinbox.set(1)  # Reset qty to 1
        self.item_combo.set("")  # Reset combo

    def confirm_order(self):
        """Saves the order details to the database."""
        if not self.cart_tree.get_children():
            messagebox.showwarning("Empty Order", "Please add items to the order first.", parent=self)
            return

        try:
            cursor = self.master.db_conn.cursor()
            # For group bookings, there may be multiple booking rows. If so, ask user to choose which room to attach the order to.
            cursor.execute("SELECT b.id, r.room_number FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.booking_ref=? ORDER BY b.id", (self.booking_ref,))
            booking_rows = cursor.fetchall()
            if not booking_rows:
                messagebox.showerror("Error", "Booking not found for adding order.", parent=self)
                return

            if len(booking_rows) == 1:
                booking_id = booking_rows[0][0]
            else:
                # Prompt user to pick a room/booking id
                sel_win = tk.Toplevel(self)
                sel_win.transient(self)
                sel_win.grab_set()
                sel_win.title("Select Room for Order")
                sel_win.geometry("399x279")

                ttk.Label(sel_win, text="Multiple rooms found for this booking.\nSelect the room to attach the order:", wraplength=300).pack(pady=8)
                listbox = tk.Listbox(sel_win, height=8)
                mapping = []
                for bid, rn in booking_rows:
                    mapping.append((bid, rn))
                    listbox.insert('end', f"Room {rn} (Booking ID: {bid})")
                listbox.pack(fill='both', expand=True, padx=10)

                chosen = {'value': None}

                def _on_ok():
                    sel = listbox.curselection()
                    if not sel:
                        messagebox.showwarning("No Selection", "Please select a room.", parent=sel_win)
                        return
                    idx = sel[0]
                    chosen['value'] = mapping[idx][0]
                    sel_win.destroy()

                def _on_cancel():
                    sel_win.destroy()

                btn_frame = ttk.Frame(sel_win)
                btn_frame.pack(pady=8)
                ttk.Button(btn_frame, text="OK", command=_on_ok, style="Accent.TButton").pack(side='left', padx=8)
                ttk.Button(btn_frame, text="Cancel", command=_on_cancel).pack(side='left', padx=8)

                sel_win.wait_window()
                if not chosen['value']:
                    # user cancelled
                    return
                booking_id = chosen['value']

            for item in self.cart_tree.get_children():
                item_id = item
                values = self.cart_tree.item(item)['values']
                # Quantity may be int or string
                try:
                    quantity = int(values[1])
                except Exception:
                    # Fallback: try to coerce to int
                    try:
                        quantity = int(str(values[1]).strip())
                    except Exception:
                        quantity = 1

                price_raw = str(values[2])
                # Price in the tree is shown as '₹123.45' (or could be plain '123.45').
                # Strip any non-numeric characters except dot and minus.
                price = None
                try:
                    cleaned = re.sub(r"[^0-9.\-]", "", price_raw)
                    if cleaned == "":
                        raise ValueError("Empty price")
                    price = float(cleaned)
                except Exception:
                    # As a robust fallback, fetch the current menu price from DB by item id
                    try:
                        cur = self.master.db_conn.cursor()
                        cur.execute("SELECT price FROM restaurant_menu WHERE id=?", (item_id,))
                        pr = cur.fetchone()
                        price = float(pr[0]) if pr and pr[0] is not None else 0.0
                    except Exception:
                        price = 0.0

                cursor.execute("""
                    INSERT INTO restaurant_orders (booking_id, item_id, quantity, price_at_order, order_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (booking_id, item_id, quantity, price, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            self.master.db_conn.commit()
            messagebox.showinfo("Success", "Order added to the room bill successfully.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}", parent=self)


class ChangeDatesWindow(tk.Toplevel):
    def __init__(self, master, booking_ref):
        super().__init__(master)
        self.master = master
        self.booking_ref = booking_ref
        self.title(f"Update Dates for {booking_ref}")
        # Increase default size so the Update button and controls are visible on smaller screens
        self.geometry("520x340")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
            pass

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        cursor = self.master.db_conn.cursor()
        # Fetch all bookings for this reference; group bookings may have multiple rows
        cursor.execute("SELECT check_in, check_out, room_id FROM bookings WHERE booking_ref=?", (booking_ref,))
        rows = cursor.fetchall()
        if not rows:
            messagebox.showerror("Error", "Booking not found.", parent=self)
            self.destroy()
            return

        self.booking_rows = rows
        try:
            # Use earliest check_in and latest check_out across the group for display
            check_ins = [r[0] for r in rows]
            check_outs = [r[1] for r in rows]
            self.current_check_in = min(check_ins)
            self.current_check_out = max(check_outs)
        except Exception:
            self.current_check_in, self.current_check_out = rows[0][0], rows[0][1]

        # If single room in the group, keep room_id for per-room operations; otherwise None
        if len(rows) == 1:
            self.room_id = rows[0][2]
        else:
            self.room_id = None

        # For multi-row bookings allow selecting a subset to apply date changes to
        self.selected_booking_ids = None
        if len(rows) > 1:
            sel_frame = ttk.Frame(frame)
            sel_frame.pack(fill='x', pady=(6,0))
            self._sel_label_var = tk.StringVar(value=f"Applying to: All rooms ({len(rows)})")
            ttk.Label(sel_frame, textvariable=self._sel_label_var).pack(side='left', padx=(0,8))
            def _open_selector():
                # Show 'Proceed' in the selector so staff can select rows and continue in one modal
                ids, _ = self.master.select_booking_rows(self.booking_ref, include_manual_dt=False, include_proceed=True)
                if ids:
                    self.selected_booking_ids = ids
                    # display friendly room numbers for selected ids
                    try:
                        cur = self.master.db_conn.cursor()
                        placeholders = ','.join(['?'] * len(ids))
                        cur.execute(f"SELECT GROUP_CONCAT(r.room_number, ',') FROM bookings b JOIN rooms r ON b.room_id=r.id WHERE b.id IN ({placeholders})", tuple(ids))
                        rn = cur.fetchone()
                        rooms_display = rn[0] if rn and rn[0] else ','.join([str(i) for i in ids])
                    except Exception:
                        rooms_display = ','.join([str(i) for i in ids])
                    self._sel_label_var.set(f"Applying to: {rooms_display}")
                else:
                    # clear to indicate all
                    self.selected_booking_ids = None
                    self._sel_label_var.set(f"Applying to: All rooms ({len(self.booking_rows)})")

            ttk.Button(sel_frame, text="Select rooms...", command=_open_selector).pack(side='left')

        ttk.Label(frame, text=f"Booking Reference: {self.booking_ref}", font=('Helvetica', 11, 'bold')).pack(pady=5)
        ttk.Label(frame, text="WARNING: This is for advanced changes (in/out dates). Use 'Extend Stay' for simple extensions.", wraplength=350, foreground=COLOR_DANGER).pack(pady=5)

        ttk.Label(frame, text="New Check-In Date (DD/MM/YYYY or DD/MM/YYYY HH:MM):").pack(pady=(10, 0))
        self.new_check_in_entry = ttk.Entry(frame)
        try:
            self.new_check_in_entry.insert(0, self.master.format_datetime_for_display(self.current_check_in))
        except Exception:
            self.new_check_in_entry.insert(0, self.current_check_in)
        self.new_check_in_entry.pack(ipady=3)

        ttk.Label(frame, text="New Check-Out Date (DD/MM/YYYY or DD/MM/YYYY HH:MM):").pack(pady=(10, 0))
        self.new_check_out_entry = ttk.Entry(frame)
        try:
            self.new_check_out_entry.insert(0, self.master.format_datetime_for_display(self.current_check_out))
        except Exception:
            self.new_check_out_entry.insert(0, self.current_check_out)
        self.new_check_out_entry.pack(ipady=3)

        # Anchor Update button to the bottom so it remains visible on small screens
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side='bottom', fill='x', pady=10)
        btn = ttk.Button(btn_frame, text="Update Dates", command=self.update_dates, style="Accent.TButton")
        btn.pack(side='right', padx=10, ipady=8, ipadx=12)
        try:
            # Ensure dialog is visible and focused so the Update button isn't clipped by OS windowing
            self.lift()
            self.focus_force()
            btn.focus()
        except Exception:
            pass
        try:
            self.minsize(420, 260)
        except Exception:
            pass

    def update_dates(self):
        """Validates and updates the booking dates."""
        new_check_in = self.new_check_in_entry.get()
        new_check_out = self.new_check_out_entry.get()

        # Convert display date strings to ISO-like strings using master helper
        new_ci_iso = self.master._parse_display_date_to_iso(new_check_in)
        new_co_iso = self.master._parse_display_date_to_iso(new_check_out)

        try:
            try:
                d_in = datetime.strptime(new_ci_iso, '%Y-%m-%d %H:%M')
            except Exception:
                d_in = datetime.strptime(new_ci_iso, '%Y-%m-%d')
            try:
                d_out = datetime.strptime(new_co_iso, '%Y-%m-%d %H:%M')
            except Exception:
                d_out = datetime.strptime(new_co_iso, '%Y-%m-%d')
            if d_out <= d_in:
                messagebox.showerror("Invalid Dates", "Check-out date must be after check-in date.", parent=self)
                return
        except Exception:
            messagebox.showerror("Invalid Date Format", "Please use DD/MM/YYYY or YYYY-MM-DD formats.", parent=self)
            return

        cursor = self.master.db_conn.cursor()

        # 1) Conflict check (scoped to selected rows or to all rooms in this booking_ref)
        try:
            # If user selected specific booking rows, restrict conflict check to those rooms
            if getattr(self, 'selected_booking_ids', None):
                sel_ids = self.selected_booking_ids
                # fetch room_ids for these booking rows
                placeholders = ','.join(['?'] * len(sel_ids))
                cursor.execute(f"SELECT DISTINCT room_id FROM bookings WHERE id IN ({placeholders})", tuple(sel_ids))
                room_ids = [str(r[0]) for r in cursor.fetchall()]
                if room_ids:
                    ph = ','.join(['?'] * len(room_ids))
                    params = room_ids + [self.booking_ref, new_co_iso, new_ci_iso]
                    query = f"SELECT COUNT(*) FROM bookings WHERE room_id IN ({ph}) AND booking_ref != ? AND status IN ('Reserved','Checked-In') AND check_in <= ? AND check_out >= ?"
                    cursor.execute(query, params)
                else:
                    conflict = 0
            else:
                # If this booking has multiple room rows, check conflicts across all room ids
                if getattr(self, 'booking_rows', None) and len(self.booking_rows) > 1:
                    room_ids = [str(r[2]) for r in self.booking_rows]
                    ph = ','.join(['?'] * len(room_ids))
                    params = room_ids + [self.booking_ref, new_co_iso, new_ci_iso]
                    query = f"SELECT COUNT(*) FROM bookings WHERE room_id IN ({ph}) AND booking_ref != ? AND status IN ('Reserved','Checked-In') AND check_in <= ? AND check_out >= ?"
                    cursor.execute(query, params)
                else:
                    cursor.execute("SELECT COUNT(*) FROM bookings WHERE room_id = ? AND booking_ref != ? AND status IN ('Reserved','Checked-In') AND check_in <= ? AND check_out >= ?", (self.room_id, self.booking_ref, new_co_iso, new_ci_iso))

            conflict = cursor.fetchone()[0]
            if conflict > 0:
                messagebox.showerror("Booking Conflict", "The room(s) are already booked for the new dates selected. Please choose different dates.", parent=self)
                return
        except Exception as e:
            messagebox.showerror("Booking Conflict Check Failed", f"Could not verify booking conflicts: {e}", parent=self)
            return

        # 2) Apply date updates
        try:
            # Apply date update to either selected rows (if provided) or all rows of the booking_ref (group booking)
            if getattr(self, 'selected_booking_ids', None):
                ids = self.selected_booking_ids
                placeholders = ','.join(['?'] * len(ids))
                params = [new_ci_iso, new_co_iso] + ids
                cursor.execute(f"UPDATE bookings SET check_in=?, check_out=? WHERE id IN ({placeholders})", tuple(params))
            else:
                cursor.execute("UPDATE bookings SET check_in=?, check_out=? WHERE booking_ref=?",
                               (new_ci_iso, new_co_iso, self.booking_ref))
            self.master.db_conn.commit()
            messagebox.showinfo("Success", "Booking dates have been updated.", parent=self)
            self.master.load_bookings_data()
            self.master.refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred while updating booking dates: {e}", parent=self)
            return

        # NOTE: The previous behavior offered to reprint the advance receipt automatically when dates were changed.
        # Per user preference that behavior has been disabled to avoid unexpected PDF regeneration during date edits.

        self.destroy()


class BookingSelectionWindow(tk.Toplevel):
    def __init__(self, master, status_list, title):
        super().__init__(master)
        self.master = master
        self.status_list = status_list
        self.title(title)
        # Increase default size by ~15mm to ensure action buttons remain visible
        self.geometry("776x476") # Increased width/height for visibility
        self.transient(master)
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass

        self.selected_booking = None

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Please select a guest from the list:", font=('Helvetica', 11, 'bold')).pack(pady=5)

        cols = ('Ref #', 'Guest Name', 'Room #', 'Adults', 'Children', 'Check-In', 'Status')
        self.tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        
        for col in cols:
            self.tree.heading(col, text=col)
            if col in ('Adults', 'Children'):
                self.tree.column(col, width=60, anchor='center')
            elif col in ('Ref #', 'Room #', 'Status'):
                self.tree.column(col, width=100, anchor='center')
            elif col in ('Check-In'):
                self.tree.column(col, width=110, anchor='center')
            elif col == 'Guest Name':
                self.tree.column(col, width=150)
            
        self.tree.tag_configure('oddrow', background=COLOR_ODD_ROW)
        self.tree.tag_configure('evenrow', background=COLOR_EVEN_ROW)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True, pady=10)

        self.tree.bind("<Double-1>", self.confirm_selection)

        action_frame = ttk.Frame(frame)
        # Anchor action buttons at the bottom so they don't get pushed off-screen
        action_frame.pack(side='bottom', fill='x', pady=5)

        ttk.Button(action_frame, text="Confirm", command=self.confirm_selection, style="Success.TButton").pack(side='right', padx=5, ipady=5)
        ttk.Button(action_frame, text="Cancel", command=self.cancel_selection).pack(side='right', padx=5, ipady=5)

        self.load_data()

    def load_data(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        cursor = self.master.db_conn.cursor()

        placeholders = ','.join(['?'] * len(self.status_list))

        query = f"""
            SELECT b.id, b.booking_ref, g.name, r.room_number, b.num_adults, b.num_children, b.check_in, b.status, b.room_id
            FROM bookings b
            JOIN guests g ON b.guest_id = g.id
            JOIN rooms r ON b.room_id = r.id
            WHERE b.status IN ({placeholders})
            ORDER BY g.name
        """

        cursor.execute(query, self.status_list)

        for i, row in enumerate(cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            # row[0] = booking id (primary key), row[1] = booking_ref
            display_values = (row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            # Use booking id as the Treeview iid to avoid collisions when multiple rows share the same booking_ref
            self.tree.insert('', 'end', values=display_values, iid=str(row[0]), tags=(tag,))

    def confirm_selection(self, event=None):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a booking.", parent=self)
            return

        # selected_item is the booking row id (string). Fetch its booking_ref and then all rows for that ref.
        try:
            booking_row_id = int(selected_item)
        except Exception:
            messagebox.showerror("Error", "Invalid selection identifier.", parent=self)
            return

        cursor = self.master.db_conn.cursor()
        cursor.execute("SELECT booking_ref FROM bookings WHERE id=?", (booking_row_id,))
        br = cursor.fetchone()
        if not br:
            messagebox.showerror("Error", "No booking data found for the selected item.", parent=self)
            return

        booking_ref = br[0]

        # Fetch all booking rows for this reference (group bookings may have multiple rows)
        cursor.execute("SELECT b.booking_ref, r.room_number, b.room_id, b.num_adults, b.num_children FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.booking_ref=?", (booking_ref,))
        rows = cursor.fetchall()
        if not rows:
            messagebox.showerror("Error", "No booking data found for the selected reference.", parent=self)
            return

        # If multiple rooms are present, aggregate room numbers for display but keep first room_id for compatibility
        if len(rows) == 1:
            r = rows[0]
            room_number_display = r[1]
            room_id_value = r[2]
            num_adults = r[3]
            num_children = r[4]
        else:
            room_numbers = [str(r[1]) for r in rows]
            room_number_display = ','.join(room_numbers)
            room_id_value = rows[0][2]
            # Use aggregated adults/children as sum of all rows if available
            try:
                num_adults = sum(int(r[3]) for r in rows)
                num_children = sum(int(r[4]) for r in rows)
            except Exception:
                num_adults = rows[0][3]
                num_children = rows[0][4]

        self.selected_booking = {
            'ref': booking_ref,
            'room_number': room_number_display,
            'room_id': room_id_value,
            'num_adults': num_adults,
            'num_children': num_children
        }
        self.destroy()

    def cancel_selection(self):
        self.selected_booking = None
        self.destroy()

    def show(self):
        """Makes the window modal and returns the selection."""
        self.grab_set()
        self.wait_window()
        return self.selected_booking


class BookingDetailWindow(tk.Toplevel):
    """Dialog that shows booking + guest aggregated details and provides Edit/Delete/Reprint actions."""
    def __init__(self, master, booking_ref):
        super().__init__(master)
        self.master = master
        self.booking_ref = booking_ref
        self.title(f"Booking Details - {booking_ref}")
        # Make detail window slightly larger so the bottom controls remain visible
        self.geometry("596x436")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill='both', expand=True)

        cursor = self.master.db_conn.cursor()
        cursor.execute("SELECT b.booking_ref, g.name, g.phone, g.address, r.room_number, b.check_in, b.check_out, b.status FROM bookings b JOIN guests g ON b.guest_id = g.id JOIN rooms r ON b.room_id = r.id WHERE b.booking_ref = ? ORDER BY r.room_number", (booking_ref,))
        rows = cursor.fetchall()

        if not rows:
            ttk.Label(frame, text=f"No booking found for {booking_ref}").pack(pady=10)
            ttk.Button(frame, text="Close", command=self.destroy).pack(pady=8)
            return

        # Aggregate
        guest_name = rows[0][1]
        phone = rows[0][2] or ''
        address = rows[0][3] or ''
        rooms = [str(r[4]) for r in rows]
        check_ins = [r[5] for r in rows if r[5]]
        check_outs = [r[6] for r in rows if r[6]]
        statuses = set(r[7] for r in rows if r[7])

        # earliest check-in / latest check-out
        def _to_dt(s):
            try:
                if not s:
                    return None
                return datetime.strptime(str(s), '%Y-%m-%d %H:%M') if ':' in str(s) else datetime.strptime(str(s), '%Y-%m-%d')
            except Exception:
                return None

        cis = [_to_dt(s) for s in check_ins]
        cis = [d for d in cis if d]
        earliest_ci = min(cis) if cis else None
        cos = [_to_dt(s) for s in check_outs]
        cos = [d for d in cos if d]
        latest_co = max(cos) if cos else None

        # Layout
        ttk.Label(frame, text=f"Booking Reference: {booking_ref}", font=('Helvetica', 12, 'bold')).pack(anchor='w', pady=(0,6))
        ttk.Label(frame, text=f"Primary Guest: {guest_name}").pack(anchor='w')
        ttk.Label(frame, text=f"Phone: {phone}").pack(anchor='w')
        ttk.Label(frame, text=f"Address: {address}", wraplength=480).pack(anchor='w', pady=(0,6))
        ttk.Label(frame, text=f"Rooms: {', '.join(rooms)}").pack(anchor='w')
        ttk.Label(frame, text=f"Check-In: {self.master.format_datetime_for_display(earliest_ci.strftime('%Y-%m-%d %H:%M') if earliest_ci else '')}").pack(anchor='w')
        ttk.Label(frame, text=f"Check-Out: {self.master.format_datetime_for_display(latest_co.strftime('%Y-%m-%d %H:%M') if latest_co else '')}").pack(anchor='w')
        ttk.Label(frame, text=f"Status: {', '.join(sorted(statuses))}").pack(anchor='w', pady=(0,8))

        btn_frame = ttk.Frame(frame)
        # Keep edit/delete/reprint/close controls anchored to bottom so they remain visible
        btn_frame.pack(side='bottom', fill='x', pady=12)

        def _do_edit():
            # Select in main tree and call existing edit flow
            try:
                # Find a tree item whose first column (Ref #) matches booking_ref and select it
                for iid in self.master.bookings_tree.get_children():
                    vals = self.master.bookings_tree.item(iid).get('values', [])
                    if vals and vals[0] == booking_ref:
                        self.master.bookings_tree.selection_set(iid)
                        self.master.bookings_tree.focus(iid)
                        break
            except Exception:
                pass
            self.destroy()
            self.master.edit_booking_from_bookings()

        def _do_delete():
            try:
                # Select a tree item that matches booking_ref so delete flow operates on the same reference
                for iid in self.master.bookings_tree.get_children():
                    vals = self.master.bookings_tree.item(iid).get('values', [])
                    if vals and vals[0] == booking_ref:
                        self.master.bookings_tree.selection_set(iid)
                        self.master.bookings_tree.focus(iid)
                        break
            except Exception:
                pass
            self.destroy()
            self.master.delete_booking_from_bookings()

        # Determine whether to show Advance Receipt reprint or final Invoice reprint
        try:
            cur = self.master.db_conn.cursor()
            cur.execute("SELECT SUM(advance_payment), SUM(CASE WHEN status='Checked-In' THEN 1 ELSE 0 END) FROM bookings WHERE booking_ref=?", (booking_ref,))
            adv_row = cur.fetchone() or (0.0, 0)
            total_advance = adv_row[0] or 0.0
            any_checked_in = (adv_row[1] and int(adv_row[1]) > 0)
        except Exception:
            total_advance = 0.0
            any_checked_in = False

        def _do_reprint():
            try:
                # If this booking only has advance payment(s) and none of the rooms are checked in,
                # reprint the Advance Receipt PDF (not the final invoice)
                if total_advance and not any_checked_in:
                    # Build minimal pdf_data similar to advance receipt generator
                    cur = self.master.db_conn.cursor()
                    cur.execute("SELECT b.id FROM bookings b WHERE b.booking_ref=?", (booking_ref,))
                    ids = [r[0] for r in cur.fetchall()]
                    if not ids:
                        raise Exception('No booking rows found for this reference')

                    # compute number of rooms and rates
                    placeholders = ','.join(['?'] * len(ids))
                    cur.execute(f"SELECT SUM(r.rate), COUNT(*) FROM rooms r JOIN bookings b ON r.id=b.room_id WHERE b.id IN ({placeholders})", tuple(ids))
                    sum_rate, room_count = cur.fetchone() or (0.0, 0)

                    # compute nights from stored check_in/check_out
                    cur.execute(f"SELECT MIN(b.check_in), MAX(b.check_out) FROM bookings b WHERE b.id IN ({placeholders})", tuple(ids))
                    min_ci, max_co = cur.fetchone() or (None, None)
                    try:
                        nights = 1
                        if min_ci and max_co:
                            try:
                                d_ci = datetime.strptime(str(min_ci)[:16], '%Y-%m-%d %H:%M')
                                d_co = datetime.strptime(str(max_co)[:16], '%Y-%m-%d %H:%M')
                                nights = (d_co.date() - d_ci.date()).days
                                if nights <= 0:
                                    nights = 1
                            except Exception:
                                nights = 1
                    except Exception:
                        nights = 1

                    # determine persons for local charge calculation
                    try:
                        # Sum adults/children across all booking rows for this reference (fix: was MAX which returned the per-row maximum)
                        cur.execute(f"SELECT SUM(b.num_adults), SUM(b.num_children) FROM bookings b WHERE b.id IN ({placeholders})", tuple(ids))
                        pa = cur.fetchone() or (1, 0)
                        num_adults_calc = int(pa[0] or 1)
                        num_children_calc = int(pa[1] or 0)
                    except Exception:
                        num_adults_calc, num_children_calc = 1, 0

                    local_info = self.master.calculate_local_charge_for_advance(nights, num_adults_calc, num_children_calc)

                    # guest info
                    cur.execute("SELECT name, phone, address FROM guests WHERE id=(SELECT guest_id FROM bookings WHERE booking_ref=? LIMIT 1)", (booking_ref,))
                    g = cur.fetchone() or ('', '', '')

                    # Ensure check-in/check-out display is DATE only (user requested no times on advance receipt)
                    def _date_only_display(s):
                        try:
                            disp = self.master.format_datetime_for_display(s) if s else ''
                        except Exception:
                            disp = str(s) if s else ''
                        # If time component present, strip it and return date-only
                        if disp and ':' in disp:
                            return disp.split(' ')[0]
                        return disp

                    ci_disp = _date_only_display(min_ci)
                    co_disp = _date_only_display(max_co)

                    pdf_data = {
                        'booking_ref': booking_ref,
                        'hotel_name': '',
                        'hotel_address': '',
                        'hotel_address_line1': '',
                        'hotel_address_line2': '',
                        'hotel_gst': '',
                        'hotel_contact': '',
                        'hotel_rules': '',
                        'guest_name': g[0],
                        'guest_phone': g[1],
                        'guest_address': g[2],
                        'room_type': '',
                        'num_rooms': room_count,
                        'room_rate': float(sum_rate or 0.0) / room_count if room_count else 0.0,
                        'check_in': ci_disp,
                        'check_out': co_disp,
                        'num_nights': nights,
                        'room_total': (float(sum_rate or 0.0) * nights),
                        'cgst_amount': 0.0,
                        'sgst_amount': 0.0,
                        'igst_amount': 0.0,
                        'total_after_tax': 0.0,
                        'advance_paid': float(total_advance),
                        'balance_due': 0.0,
                        'num_adults': num_adults_calc,
                        'num_children': num_children_calc
                    }

                    # Generate advance receipt using the standalone generator (do not rely on
                    # the master or caller having a bound method).
                    try:
                        generate_advance_invoice_pdf_standalone(pdf_data)
                    except Exception:
                        # Let the outer exception handler report the error to user
                        raise
                else:
                    # Fallback: reprint final invoice
                    self.master.generate_and_show_bill(booking_ref)
            except Exception as e:
                messagebox.showerror("Error", f"Could not reprint: {e}")

        ttk.Button(btn_frame, text="Edit", command=_do_edit, style="Accent.TButton").pack(side='left', padx=6)
        ttk.Button(btn_frame, text="Delete", command=_do_delete, style="Danger.TButton").pack(side='left', padx=6)
        # Only show Advance reprint if there is an advance and none checked-in; otherwise show invoice reprint
        if total_advance and not any_checked_in:
            ttk.Button(btn_frame, text="Reprint Advance Receipt", command=_do_reprint).pack(side='left', padx=6)
        else:
            ttk.Button(btn_frame, text="Reprint Invoice", command=_do_reprint).pack(side='left', padx=6)

        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side='right', padx=6)


class AboutWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("About Nexuzy Hotel Management Software")
        self.geometry("500x550")
        self.transient(master)
        self.grab_set()
        self.configure(background=COLOR_LIGHT_BG)
        # Set icon for this window
        try:
            self.iconbitmap('logo.ico')
        except:
             pass

        self.logo_image = None

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        try:
            img = Image.open("logo.png")
            img = img.resize((150, 150), Image.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(img)

            logo_label = ttk.Label(frame, image=self.logo_image, background=COLOR_LIGHT_BG)
            logo_label.pack(pady=10)
        except FileNotFoundError:
            ttk.Label(frame, text="[logo.png Not Found]", font=('Helvetica', 10, 'italic')).pack(pady=10)
        except Exception as e:
            ttk.Label(frame, text=f"[Error loading logo: {e}]", font=('Helvetica', 10, 'italic')).pack(pady=10)

        ttk.Label(frame, text=SOFTWARE_NAME, font=('Helvetica', 18, 'bold')).pack(pady=(10, 5))
        ttk.Label(frame, text=f"Version {SOFTWARE_VERSION}", font=('Helvetica', 10, 'italic')).pack()

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)

        info_frame = ttk.Frame(frame)
        info_frame.pack(fill='x', padx=20)

        def add_info_row(label_text, value_text, row):
            ttk.Label(info_frame, text=label_text, font=('Helvetica', 10, 'bold')).grid(row=row, column=0, sticky='e', padx=5, pady=3)
            ttk.Label(info_frame, text=value_text, font=('Helvetica', 10), wraplength=300).grid(row=row, column=1, sticky='w', padx=5, pady=3)

        add_info_row("Developer:", "David", 0)
        add_info_row("Company:", "Nexuzy Tech Pvt Ltd", 1)
        add_info_row("Contact:", "7602811147", 2)
        add_info_row("Email:", "davidk76011@gmail.com", 3)
        add_info_row("Address:", "Kolkata, West Bengal", 4)

        info_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)

        close_button = ttk.Button(frame, text="Close", command=self.destroy, style="Accent.TButton")
        close_button.pack(side='bottom', pady=20, ipadx=10, ipady=3)


# --- Main execution ---
if __name__ == "__main__":
    app = HotelManagementApp()
    app.mainloop()