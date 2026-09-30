import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

DATABASE = 'parking_app.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            address TEXT,
            pincode TEXT,
            role TEXT DEFAULT "user",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prime_location_name TEXT NOT NULL,
            price REAL NOT NULL,
            address TEXT NOT NULL,
            pin_code TEXT NOT NULL,
            maximum_number_of_spots INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    sql_schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='parking_spots'").fetchone()
    if sql_schema and "CHECK" in sql_schema['sql'] and "'R'" not in sql_schema['sql']:
        conn.execute("DROP TABLE IF EXISTS parking_spots")

    conn.execute('''
        CREATE TABLE IF NOT EXISTS parking_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            spot_number TEXT UNIQUE NOT NULL,
            zone TEXT DEFAULT "Zone A - Ground Floor",
            spot_type TEXT DEFAULT "Car",
            status TEXT NOT NULL CHECK (status IN ("A", "O", "R", "M")),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT UNIQUE NOT NULL,
            vehicle_type TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            spot_id INTEGER NOT NULL,
            user_id INTEGER,
            vehicle_number TEXT NOT NULL,
            vehicle_type TEXT DEFAULT "Car",
            owner_name TEXT,
            phone_number TEXT,
            parking_timestamp TIMESTAMP NOT NULL,
            leaving_timestamp TIMESTAMP,
            duration_type TEXT DEFAULT "Hourly",
            expected_duration_hours INTEGER DEFAULT 2,
            parking_cost REAL,
            payment_status TEXT DEFAULT "Paid",
            status TEXT DEFAULT "Active",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (spot_id) REFERENCES parking_spots (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT "info",
            is_read INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS tariffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_type TEXT UNIQUE NOT NULL,
            hourly_rate REAL NOT NULL,
            daily_rate REAL NOT NULL,
            custom_rate REAL NOT NULL
        )
    ''')

    users_info = conn.execute("PRAGMA table_info(users)").fetchall()
    user_cols = [col['name'] for col in users_info]
    if 'role' not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

    conn.execute("UPDATE users SET role = 'user' WHERE role = 'operator'")

    admin_exists = conn.execute('SELECT COUNT(*) as count FROM users WHERE email = "admin@parking.com" OR username = "admin"').fetchone()['count']
    if admin_exists == 0:
        admin_pass = generate_password_hash('admin@123')
        conn.execute('''
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@parking.com', admin_pass, 'admin'))

    user_exists = conn.execute('SELECT COUNT(*) as count FROM users WHERE email = "user@parking.com" OR username = "user1"').fetchone()['count']
    if user_exists == 0:
        user_pass = generate_password_hash('user@123')
        conn.execute('''
            INSERT INTO users (username, email, password, role, address, pincode)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('user1', 'user@parking.com', user_pass, 'user', '123 Market Road, Sector 18', '110001'))

    existing_tariffs = conn.execute('SELECT COUNT(*) as count FROM tariffs').fetchone()['count']
    if existing_tariffs == 0:
        default_tariffs = [
            ('Car', 50.0, 350.0, 1500.0),
            ('Bike', 20.0, 150.0, 600.0),
            ('Motorcycle', 20.0, 150.0, 600.0),
            ('Scooter', 20.0, 150.0, 600.0),
            ('SUV', 70.0, 500.0, 2000.0),
            ('EV', 80.0, 600.0, 2500.0),
            ('Truck', 100.0, 800.0, 3000.0)
        ]
        for t in default_tariffs:
            conn.execute('INSERT OR REPLACE INTO tariffs (vehicle_type, hourly_rate, daily_rate, custom_rate) VALUES (?, ?, ?, ?)', t)

    existing_spots = conn.execute('SELECT COUNT(*) as count FROM parking_spots').fetchone()['count']
    if existing_spots == 0:
        existing_lots = conn.execute('SELECT COUNT(*) as count FROM parking_lots').fetchone()['count']
        if existing_lots == 0:
            sample_lots = [
                ('Central Mall - Main Parking Garage', 50.0, 'Central Mall Complex, Sector 18', '110001', 20),
                ('Indira Gandhi International Airport - T3', 80.0, 'IGI Airport Terminal 3 Parking Structure', '110037', 20),
                ('City Center Commercial Complex', 40.0, 'Connaught Place, Block B', '110002', 15)
            ]
            for lot_data in sample_lots:
                conn.execute('''
                    INSERT INTO parking_lots (prime_location_name, price, address, pin_code, maximum_number_of_spots)
                    VALUES (?, ?, ?, ?, ?)
                ''', lot_data)

        lots = conn.execute('SELECT * FROM parking_lots').fetchall()
        for lot in lots:
            lot_id = lot['id']
            zone_prefix = chr(65 + ((lot_id - 1) % 26)) if lot_id <= 26 else f"L{lot_id}"
            zone_name = lot['prime_location_name']
            max_spots = lot['maximum_number_of_spots']

            for i in range(1, max_spots + 1):
                spot_num = f"{zone_prefix}{lot_id if lot_id > 3 else ''}{str(i).zfill(2)}"
                v_type = 'EV' if (lot_id == 3 and i <= 5) else ('Bike' if i % 4 == 0 else 'Car')
                initial_status = 'A'
                if lot_id <= 3:
                    if i in (2, 4, 7, 11, 14, 18):
                        initial_status = 'O'
                    elif i in (5, 12):
                        initial_status = 'R'
                    elif i == 9:
                        initial_status = 'M'

                conn.execute('''
                    INSERT OR IGNORE INTO parking_spots (lot_id, spot_number, zone, spot_type, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (lot_id, spot_num, zone_name, v_type, initial_status))

    existing_vehicles = conn.execute('SELECT COUNT(*) as count FROM vehicles').fetchone()['count']
    if existing_vehicles == 0:
        sample_vehicles = [
            ('RJ14 AB 1234', 'Car', 'Rajesh Sharma', '+91 98765 43210'),
            ('RJ14 XY 4521', 'Bike', 'Priya Verma', '+91 98123 67890'),
            ('DL03 CA 9081', 'SUV', 'Amitabh Patel', '+91 99887 76655'),
            ('MH12 KP 5590', 'Car', 'Siddharth Rao', '+91 97654 32109'),
            ('KA05 EV 1002', 'Car', 'Neha Gupta', '+91 95432 10987'),
            ('HR26 DQ 3311', 'Motorcycle', 'Vikram Singh', '+91 98711 22334'),
            ('UP16 BT 7823', 'Truck', 'Ramesh Kumar', '+91 99100 88776'),
            ('GJ01 AB 9988', 'Scooter', 'Ananya Shah', '+91 98250 11223')
        ]
        for v in sample_vehicles:
            conn.execute('INSERT OR IGNORE INTO vehicles (vehicle_number, vehicle_type, owner_name, phone_number) VALUES (?, ?, ?, ?)', v)

        occupied_spots = conn.execute('SELECT id, lot_id, spot_number FROM parking_spots WHERE status = "O"').fetchall()
        now = datetime.now()
        for idx, spot in enumerate(occupied_spots):
            v_data = sample_vehicles[idx % len(sample_vehicles)]
            ticket_id = "TKT-" + str(random.randint(10000, 99999))
            entry_time = now - timedelta(hours=random.randint(1, 4), minutes=random.randint(5, 50))
            conn.execute('''
                INSERT INTO reservations (ticket_id, spot_id, user_id, vehicle_number, vehicle_type, owner_name, phone_number, parking_timestamp, duration_type, parking_cost, payment_status, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticket_id, spot['id'], 2, v_data[0], v_data[1], v_data[2], v_data[3], entry_time, 'Hourly', 80.0, 'Pending', 'Active'))

        for i in range(1, 10):
            v_data = sample_vehicles[i % len(sample_vehicles)]
            ticket_id = "TKT-" + str(random.randint(10000, 99999))
            entry_time = now - timedelta(days=random.randint(1, 5), hours=random.randint(1, 10))
            leaving_time = entry_time + timedelta(hours=random.randint(1, 5), minutes=random.randint(10, 45))
            spot_id = (i % 15) + 1
            cost = random.choice([50.0, 75.0, 100.0, 150.0, 200.0])
            conn.execute('''
                INSERT INTO reservations (ticket_id, spot_id, user_id, vehicle_number, vehicle_type, owner_name, phone_number, parking_timestamp, leaving_timestamp, duration_type, parking_cost, payment_status, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticket_id, spot_id, 2, v_data[0], v_data[1], v_data[2], v_data[3], entry_time, leaving_time, 'Hourly', cost, 'Paid', 'Completed'))

    existing_notifs = conn.execute('SELECT COUNT(*) as count FROM notifications').fetchone()['count']
    if existing_notifs == 0:
        sample_notifs = [
            ('Capacity Alert', 'Ground Floor - Zone A capacity is over 85% full.', 'warning', 0),
            ('Vehicle Overstay', 'Vehicle RJ14 AB 1234 has exceeded reserved duration by 45 mins.', 'danger', 0),
            ('Maintenance Status', 'Slot A09 has been marked under maintenance.', 'info', 0),
            ('Upcoming Reservation', 'Reservation TKT-48192 scheduled for 02:00 PM today.', 'info', 1)
        ]
        for notif in sample_notifs:
            conn.execute('INSERT INTO notifications (title, message, type, is_read) VALUES (?, ?, ?, ?)', notif)

    conn.commit()
    conn.close()
