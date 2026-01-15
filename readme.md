```

I've created the "Nexuzy Hotel Management Software" as a single, comprehensive Python file. Here’s a summary of what's included and how to get started.

### Key Features Implemented:

1.  **Beautiful & Modern UI:** The application uses themed Tkinter widgets for a clean, professional look. The dashboard provides a clear, at-a-glance view of all room statuses.
2.  **Two User Roles (Admin & Employee):**
    * **Admin:** Has full access to everything, including setting hotel details, managing rooms, and updating the restaurant menu.
    * **Employee:** Can manage bookings, perform check-ins/check-outs, and add restaurant orders but cannot change core hotel settings.
3.  **Advanced Booking System:**
    * Create new bookings and advance reservations with a user-friendly form.
    * The system automatically finds available rooms for the selected dates.
    * Each booking gets a unique reference number (e.g., `DV0001NEXUZY`).
    * Easily update booking dates, extend stays, or cancel a reservation.
4.  **Full Room & Guest Management:**
    * **Admin:** Can add, update, or delete rooms, set their type (AC, Deluxe, etc.), bed type, and daily rate.
    * Guest details are saved with each booking for future reference.
5.  **Integrated Restaurant Module:**
    * **Admin:** Can add or modify items on the restaurant menu.
    * **Employee/Admin:** Can add food and beverage orders directly to a guest's room bill at any time during their stay.
6.  **Complete Billing & Invoicing:**
    * At check-out, the software automatically calculates the final bill, including room charges for the number of nights and all restaurant orders. It also adds a standard GST amount.
    * You can generate a professional, A4-sized invoice.
7.  **PDF & Direct Printing:**
    * The generated invoice can be saved directly as a **PDF file**.
    * There is also a **Print button** that sends the invoice to your computer's default printer.
8.  **100% Offline:** The software uses an internal SQLite database (`nexuzy_hotel.db` file will be created in the same folder), so it works completely offline. No internet connection is needed.

### How to Run the Software:

1.  **Save the Code:** Save the code above into a file named `nexuzy_hotel_management.py`.
2.  **Install Necessary Libraries:** You will need Python and one external library (`reportlab`) for PDF generation. Open your terminal or command prompt and run:
    ```bash
    pip install reportlab
    ```
    python3 -m pip install reportlab pillow
3.  **Run the File:** Execute the Python script from your terminal:
    ```bash
    python nexuzy_hotel_management.py


    virtual env 
       
          python3 -m venv venv

          source venv/bin/activate
    
