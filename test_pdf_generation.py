import sqlite3
import os
from reportlab.pdfgen import canvas
from nexuzy_hotel_management import BillUtility

class DummyMaster:
    def __init__(self):
        # Use the same DB file used by the app
        self.db_conn = sqlite3.connect('nexuzy_hotel.db')

# Build a minimal bill_data dict with required keys
bill_data = {
    'booking_ref': 'TEST-123',
    'guest_name': 'Test Guest',
    'guest_phone': '9999999999',
    'room_number': '101',
    'check_in': '2025-10-20',
    'check_out': '2025-10-21',
    'num_nights': 1,
    'room_rate': 1000.0,
    'room_total': 1000.0,
    'restaurant_total': 0.0,
    'restaurant_items': [],
    'advance_payment': 0.0,
    'hotel_name': 'Test Hotel',
    'hotel_address': '123 Test St',
    'hotel_gst': 'GST123',
    'hotel_contact': '0123456789',
    'room_id': 1,
    'local_charge_info': {'name': '', 'amount': 0.0, 'details': ''},
    'num_adults': 1,
    'num_children': 0,
    'extra_charges_total': 0.0,
    'extra_charges_list': [],
    'sub_total': 1000.0,
    'grand_total': 1000.0,
    'cgst_amount': 0.0,
    'sgst_amount': 0.0,
    'igst_amount': 0.0,
    'tax_type_to_display': 'none'
}

master = DummyMaster()
utility = BillUtility(master, bill_data)
# Force a save to ensure PDF generation path runs
utility.save_pdf(None)
print('PDF generation test finished.')
