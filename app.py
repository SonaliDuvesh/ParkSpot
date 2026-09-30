from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
import math
from models import init_db, get_db_connection
from forms import LoginForm, RegisterForm, ParkingLotForm
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'parkspot-secret-key-2026'
app.config['WTF_CSRF_ENABLED'] = False
app.config['DATABASE'] = 'parking_app.db'
app.jinja_env.globals.update(max=max, min=min, round=round)

init_db()

def format_duration(start_time, end_time=None):
    if not start_time:
        return "N/A"
    if isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        except:
            return "N/A"

    if not end_time:
        end_time = datetime.now()
    elif isinstance(end_time, str):
        try:
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except:
            end_time = datetime.now()

    delta = end_time - start_time
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{max(1, minutes)}m"

app.jinja_env.filters['duration'] = format_duration

@app.context_processor
def inject_global_context():
    try:
        conn = get_db_connection()
        all_lots = conn.execute('SELECT * FROM parking_lots ORDER BY id ASC').fetchall()

        active_lot_id = session.get('active_lot_id', 0)
        current_lot_name = "All Parking Facilities"
        if active_lot_id > 0:
            match = next((l for l in all_lots if l['id'] == active_lot_id), None)
            if match:
                current_lot_name = match['prime_location_name']

        notif_count = conn.execute('SELECT COUNT(*) as count FROM notifications WHERE is_read = 0').fetchone()['count']
        notifications = conn.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 5').fetchall()

        conn.close()
        return dict(
            all_lots=all_lots,
            active_lot_id=active_lot_id,
            current_lot_name=current_lot_name,
            unread_notif_count=notif_count,
            recent_notifs=notifications
        )
    except Exception:
        return dict(all_lots=[], active_lot_id=0, current_lot_name="All Parking Facilities", unread_notif_count=0, recent_notifs=[])

@app.route('/set_active_lot/<int:lot_id>')
def set_active_lot(lot_id):
    session['active_lot_id'] = lot_id
    if lot_id == 0:
        flash('Showing all parking facilities globally.', 'info')
    else:
        conn = get_db_connection()
        lot = conn.execute('SELECT prime_location_name FROM parking_lots WHERE id = ?', (lot_id,)).fetchone()
        conn.close()
        lot_name = lot['prime_location_name'] if lot else f"Facility #{lot_id}"
        flash(f'Switched view to {lot_name}.', 'info')
    return redirect(request.referrer or url_for('index'))

@app.before_request
def require_login():
    public_endpoints = ['login', 'register', 'static']
    endpoint = request.endpoint
    if endpoint and (endpoint in public_endpoints or endpoint.startswith('static')):
        return None

    is_authenticated = session.get('user_id') or session.get('is_admin')
    if not is_authenticated:
        flash('Please sign in or register to access ParkSpot.', 'warning')
        return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
def index():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('user_dashboard'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    active_lot_id = session.get('active_lot_id', 0)

    lot_filter_sql = ""
    params = ()
    if active_lot_id > 0:
        lot_filter_sql = " WHERE lot_id = ?"
        params = (active_lot_id,)

    total_spots = conn.execute(f'SELECT COUNT(*) as count FROM parking_spots{lot_filter_sql}', params).fetchone()['count']
    available_spots = conn.execute(f'SELECT COUNT(*) as count FROM parking_spots WHERE status = "A"{(" AND lot_id = ?" if active_lot_id > 0 else "")}', params).fetchone()['count']
    occupied_spots = conn.execute(f'SELECT COUNT(*) as count FROM parking_spots WHERE status = "O"{(" AND lot_id = ?" if active_lot_id > 0 else "")}', params).fetchone()['count']
    reserved_spots = conn.execute(f'SELECT COUNT(*) as count FROM parking_spots WHERE status = "R"{(" AND lot_id = ?" if active_lot_id > 0 else "")}', params).fetchone()['count']
    maintenance_spots = conn.execute(f'SELECT COUNT(*) as count FROM parking_spots WHERE status = "M"{(" AND lot_id = ?" if active_lot_id > 0 else "")}', params).fetchone()['count']

    avail_pct = round((available_spots / max(1, total_spots)) * 100)
    occ_pct = round((occupied_spots / max(1, total_spots)) * 100)
    res_pct = round((reserved_spots / max(1, total_spots)) * 100)

    lots_filter = " WHERE pl.id = ?" if active_lot_id > 0 else ""
    lots_params = (active_lot_id,) if active_lot_id > 0 else ()

    lots_summary = conn.execute(f'''
        SELECT pl.*,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id) as total_spots,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id AND status = 'O') as occupied_spots,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id AND status = 'A') as available_spots,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id AND status = 'R') as reserved_spots
        FROM parking_lots pl
        {lots_filter}
        ORDER BY pl.id ASC
    ''', lots_params).fetchall()

    total_lots = len(lots_summary)
    total_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'").fetchone()['count']
    registered_users = conn.execute("SELECT id, username, email, address, pincode, created_at FROM users WHERE role = 'user' ORDER BY id DESC LIMIT 5").fetchall()

    tariffs_rows = conn.execute('SELECT * FROM tariffs').fetchall()
    tariffs = {t['vehicle_type']: dict(t) for t in tariffs_rows}

    today_str = datetime.now().strftime("%A, %B %d, %Y")
    conn.close()

    return render_template('admin/dashboard.html',
                           active_page='dashboard',
                           today_date=today_str,
                           total_lots=total_lots,
                           total_spots=total_spots,
                           available_spots=available_spots,
                           occupied_spots=occupied_spots,
                           reserved_spots=reserved_spots,
                           maintenance_spots=maintenance_spots,
                           avail_pct=avail_pct,
                           occ_pct=occ_pct,
                           res_pct=res_pct,
                           lots_summary=lots_summary,
                           all_lots=lots_summary,
                           total_users=total_users,
                           registered_users=registered_users,
                           tariffs=tariffs)

@app.route('/user/dashboard')
def user_dashboard():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    user_id = session.get('user_id')
    conn = get_db_connection()

    active_bookings_raw = conn.execute('''
        SELECT r.*, ps.spot_number, pl.prime_location_name, pl.price
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.user_id = ? AND r.status IN ('Active', 'Parked', 'Occupied')
        ORDER BY r.id DESC
    ''', (user_id,)).fetchall()

    active_bookings = [dict(b) for b in active_bookings_raw]

    booking_history_raw = conn.execute('''
        SELECT r.*, ps.spot_number, pl.prime_location_name, pl.price
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.user_id = ? AND r.status = 'Completed'
        ORDER BY r.id DESC
    ''', (user_id,)).fetchall()

    booking_history = [dict(b) for b in booking_history_raw]

    all_user_bookings = conn.execute('''
        SELECT r.*, pl.prime_location_name
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.user_id = ?
    ''', (user_id,)).fetchall()

    total_bookings = len(all_user_bookings)
    active_count = len(active_bookings)
    completed_count = len(booking_history)
    total_spent = sum([float(b['parking_cost'] or 0) for b in booking_history])

    location_stats = {}
    cost_by_location = {}
    monthly_data = {}

    for b in all_user_bookings:
        loc = b['prime_location_name']
        location_stats[loc] = location_stats.get(loc, 0) + 1

        cost = float(b['parking_cost'] or 0)
        cost_by_location[loc] = cost_by_location.get(loc, 0) + cost

        ts_str = b['parking_timestamp']
        if ts_str:
            month_key = ts_str[:7]
            monthly_data[month_key] = monthly_data.get(month_key, 0) + 1

    if not monthly_data:
        curr_month = datetime.now().strftime("%Y-%m")
        monthly_data[curr_month] = total_bookings

    conn.close()

    return render_template('user/dashboard.html',
                           active_page='dashboard',
                           total_bookings=total_bookings,
                           active_count=active_count,
                           completed_count=completed_count,
                           total_spent=total_spent,
                           location_stats=location_stats,
                           monthly_data=monthly_data,
                           cost_by_location=cost_by_location,
                           active_bookings=active_bookings,
                           booking_history=booking_history)

@app.route('/book_parking')
def book_parking():
    if session.get('is_admin'):
        flash('Admins can view and manage parking lots from Admin Console.', 'info')
        return redirect(url_for('admin_parking_lots'))

    user_id = session.get('user_id')
    conn = get_db_connection()
    active_lot_id = session.get('active_lot_id', 0)
    lot_filter_sql = " WHERE pl.id = ?" if active_lot_id > 0 else ""
    params = (active_lot_id,) if active_lot_id > 0 else ()
    lots_rows = conn.execute(f'''
        SELECT pl.*,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id) as total_spots,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id AND status = 'A') as available_spots
        FROM parking_lots pl
        {lot_filter_sql}
        ORDER BY pl.id ASC
    ''', params).fetchall()

    lots = []
    for l in lots_rows:
        ld = dict(l)
        spots = conn.execute('''
            SELECT ps.*, r.vehicle_number, r.vehicle_type
            FROM parking_spots ps
            LEFT JOIN reservations r ON r.id = (
                SELECT id FROM reservations
                WHERE spot_id = ps.id AND status IN ('Active', 'Parked', 'Occupied')
                ORDER BY id DESC LIMIT 1
            )
            WHERE ps.lot_id = ?
            ORDER BY ps.id ASC
        ''', (l['id'],)).fetchall()
        ld['spots'] = [dict(s) for s in spots]
        lots.append(ld)

    conn.close()

    return render_template('user/book_parking.html', active_page='book_parking', parking_lots=lots)

@app.route('/confirm_booking', methods=['GET', 'POST'])
@app.route('/confirm_booking/<int:lot_id>', methods=['GET', 'POST'])
def confirm_booking(lot_id=None):
    if session.get('is_admin'):
        flash('Admins cannot make user bookings.', 'error')
        return redirect(url_for('admin_dashboard'))

    user_id = session.get('user_id')
    if request.method == 'POST':
        conn = get_db_connection()
        req_lot_id = request.form.get('lot_id') or lot_id
        req_spot_id = request.form.get('spot_id')
        vehicle_number = (request.form.get('vehicle_number') or '').strip().upper()
        vehicle_type = (request.form.get('vehicle_type') or 'Car').strip()

        if not vehicle_number:
            conn.close()
            flash('Please enter your vehicle number to complete the reservation.', 'error')
            return redirect(url_for('book_parking'))

        lot = conn.execute('SELECT * FROM parking_lots WHERE id = ?', (req_lot_id,)).fetchone()
        if not lot:
            conn.close()
            flash('Selected parking facility not found.', 'error')
            return redirect(url_for('book_parking'))

        if req_spot_id:
            spot = conn.execute('SELECT * FROM parking_spots WHERE id = ? AND lot_id = ? AND status = "A"', (req_spot_id, req_lot_id)).fetchone()
        else:
            spot = conn.execute('SELECT * FROM parking_spots WHERE lot_id = ? AND status = "A" ORDER BY id ASC LIMIT 1', (req_lot_id,)).fetchone()

        if not spot:
            conn.close()
            flash(f'Selected parking bay at {lot["prime_location_name"]} is currently occupied or unavailable.', 'error')
            return redirect(url_for('book_parking'))

        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        user_name = user['username'] if user else 'Customer'

        ticket_id = f"TKT-{random.randint(10000, 99999)}"
        now = datetime.now()

        # Update spot status to Occupied
        conn.execute('UPDATE parking_spots SET status = "O" WHERE id = ?', (spot['id'],))

        conn.execute('''
            INSERT INTO reservations (
                ticket_id, spot_id, user_id, vehicle_number, vehicle_type,
                owner_name, phone_number, parking_timestamp, duration_type,
                parking_cost, payment_status, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Hourly', ?, 'Pending', 'Active')
        ''', (
            ticket_id,
            spot['id'],
            user_id,
            vehicle_number,
            vehicle_type,
            user_name,
            user['address'] if user and 'address' in user.keys() else '+91 98000 00000',
            now,
            lot['price']
        ))

        conn.commit()
        conn.close()

        flash(f'Parking Spot {spot["spot_number"]} at {lot["prime_location_name"]} successfully reserved for vehicle {vehicle_number} ({vehicle_type})!', 'success')
        return redirect(url_for('user_dashboard'))

    return redirect(url_for('book_parking'))

@app.route('/release_parking/<int:reservation_id>', methods=['GET', 'POST'])
def release_parking(reservation_id):
    user_id = session.get('user_id')
    conn = get_db_connection()

    reservation = conn.execute('''
        SELECT r.*, pl.price, pl.prime_location_name, ps.spot_number
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.id = ?
    ''', (reservation_id,)).fetchone()

    if not reservation:
        conn.close()
        flash('Reservation not found.', 'error')
        return redirect(url_for('user_dashboard'))

    if not session.get('is_admin') and reservation['user_id'] != user_id:
        conn.close()
        flash('Unauthorized to release this parking reservation.', 'error')
        return redirect(url_for('user_dashboard'))

    now = datetime.now()
    start_time = reservation['parking_timestamp']
    if isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        except Exception:
            start_time = now - timedelta(hours=1)

    delta = now - start_time
    total_hours = max(1, math.ceil(delta.total_seconds() / 3600.0))
    rate_per_hour = float(reservation['price'] or 50.0)
    calculated_cost = round(total_hours * rate_per_hour, 2)

    conn.execute('''
        UPDATE reservations
        SET leaving_timestamp = ?,
            parking_cost = ?,
            payment_status = 'Paid',
            status = 'Completed'
        WHERE id = ?
    ''', (now, calculated_cost, reservation_id))

    conn.execute('''
        UPDATE parking_spots
        SET status = 'A'
        WHERE id = ?
    ''', (reservation['spot_id'],))

    conn.commit()
    conn.close()

    flash(f'Vehicle moved out and spot {reservation["spot_number"]} released! Total duration charged: {total_hours} hr(s) - Total Fee: ₹{calculated_cost}', 'success')
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('user_dashboard'))

@app.route('/admin/parking_lots', methods=['GET', 'POST'])
def admin_parking_lots():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('prime_location_name', '').strip()
        price = float(request.form.get('price', 50.0))
        address = request.form.get('address', '').strip()
        pincode = request.form.get('pin_code', '').strip()
        max_spots = int(request.form.get('maximum_number_of_spots', 20))

        if name:
            conn.execute('''
                INSERT INTO parking_lots (prime_location_name, price, address, pin_code, maximum_number_of_spots)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, price, address, pincode, max_spots))
            new_lot_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

            prefix = name[:1].upper() if name else 'L'
            for i in range(1, max_spots + 1):
                s_num = f"{prefix}{new_lot_id}{i:02d}"
                stype = 'EV' if i % 5 == 0 else ('Bike' if i % 3 == 0 else 'Car')
                conn.execute('''
                    INSERT OR IGNORE INTO parking_spots (lot_id, spot_number, zone, spot_type, status)
                    VALUES (?, ?, ?, ?, 'A')
                ''', (new_lot_id, s_num, name, stype))

            conn.commit()
            flash(f'New Parking Lot "{name}" created with {max_spots} automated parking spots!', 'success')
            conn.close()
            return redirect(url_for('admin_parking_lots'))

    active_lot_id = session.get('active_lot_id', 0)
    lot_filter_sql = " WHERE pl.id = ?" if active_lot_id > 0 else ""
    params = (active_lot_id,) if active_lot_id > 0 else ()
    parking_lots = conn.execute(f'''
        SELECT pl.*,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id) as total_spots,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id AND status = 'O') as occupied_spots,
               (SELECT COUNT(*) FROM parking_spots WHERE lot_id = pl.id AND status = 'A') as available_spots
        FROM parking_lots pl
        {lot_filter_sql}
        ORDER BY pl.id ASC
    ''', params).fetchall()

    conn.close()
    return render_template('admin/parking_lots.html', active_page='admin_lots', parking_lots=parking_lots)

@app.route('/admin/parking_lot_details/<int:lot_id>')
def admin_parking_lot_details(lot_id):
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    lot = conn.execute('SELECT * FROM parking_lots WHERE id = ?', (lot_id,)).fetchone()
    if not lot:
        conn.close()
        flash('Parking lot not found.', 'error')
        return redirect(url_for('admin_parking_lots'))

    spots = conn.execute('''
        SELECT ps.*,
               r.vehicle_number, r.vehicle_type, r.owner_name, r.parking_timestamp,
               u.username
        FROM parking_spots ps
        LEFT JOIN reservations r ON r.id = (
            SELECT id FROM reservations
            WHERE spot_id = ps.id AND status IN ('Active', 'Parked', 'Occupied')
            ORDER BY id DESC LIMIT 1
        )
        LEFT JOIN users u ON r.user_id = u.id
        WHERE ps.lot_id = ?
        ORDER BY ps.id ASC
    ''', (lot_id,)).fetchall()

    total_spots = len(spots)
    available_spots = sum(1 for s in spots if s['status'] == 'A')
    occupied_spots = sum(1 for s in spots if s['status'] == 'O')

    conn.close()
    return render_template('admin/parking_lot_details.html',
                           active_page='admin_lots',
                           lot=lot,
                           spots=spots,
                           total_spots=total_spots,
                           available_spots=available_spots,
                           occupied_spots=occupied_spots)

@app.route('/admin/lots/edit/<int:lot_id>', methods=['POST'])
def edit_parking_lot(lot_id):
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    name = request.form.get('prime_location_name', '').strip()
    price = float(request.form.get('price', 50.0))
    address = request.form.get('address', '').strip()
    pincode = request.form.get('pin_code', '').strip()
    max_spots = int(request.form.get('maximum_number_of_spots', 20))

    if name:
        conn.execute('''
            UPDATE parking_lots
            SET prime_location_name = ?, price = ?, address = ?, pin_code = ?, maximum_number_of_spots = ?
            WHERE id = ?
        ''', (name, price, address, pincode, max_spots, lot_id))

        current_spots_count = conn.execute('SELECT COUNT(*) as count FROM parking_spots WHERE lot_id = ?', (lot_id,)).fetchone()['count']
        if max_spots > current_spots_count:
            prefix = name[:1].upper() if name else 'L'
            for i in range(current_spots_count + 1, max_spots + 1):
                s_num = f"{prefix}{lot_id}{i:02d}"
                conn.execute('''
                    INSERT OR IGNORE INTO parking_spots (lot_id, spot_number, zone, spot_type, status)
                    VALUES (?, ?, ?, 'Car', 'A')
                ''', (lot_id, s_num, name))

        conn.commit()
        flash(f'Parking Lot "{name}" updated successfully.', 'success')

    conn.close()
    return redirect(url_for('admin_parking_lots'))

@app.route('/admin/lots/delete/<int:lot_id>', methods=['GET', 'POST'])
def delete_parking_lot(lot_id):
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    occupied_count = conn.execute("SELECT COUNT(*) as count FROM parking_spots WHERE lot_id = ? AND status != 'A'", (lot_id,)).fetchone()['count']
    if occupied_count > 0:
        conn.close()
        flash('Cannot delete parking lot: all spots must be empty before deleting.', 'error')
        return redirect(url_for('admin_parking_lots'))

    conn.execute('DELETE FROM parking_spots WHERE lot_id = ?', (lot_id,))
    conn.execute('DELETE FROM parking_lots WHERE id = ?', (lot_id,))
    conn.commit()
    conn.close()
    flash('Parking lot and associated empty spots deleted successfully.', 'info')
    return redirect(url_for('admin_parking_lots'))

@app.route('/admin/users')
def admin_users():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    users = conn.execute('''
        SELECT u.*,
               (SELECT COUNT(*) FROM reservations WHERE user_id = u.id) as total_bookings,
               (SELECT COUNT(*) FROM reservations WHERE user_id = u.id AND status IN ('Active', 'Parked', 'Occupied')) as active_bookings
        FROM users u
        WHERE u.role = 'user'
        ORDER BY u.id DESC
    ''').fetchall()
    conn.close()

    return render_template('admin/users.html', active_page='admin_users', users=users)

@app.route('/admin/users/<int:user_id>')
def admin_user_details(user_id):
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))

    reservations = conn.execute('''
        SELECT r.*, pl.prime_location_name, ps.spot_number
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    ''', (user_id,)).fetchall()

    total_bookings = len(reservations)
    active_bookings = sum(1 for r in reservations if r['status'] in ('Active', 'Parked', 'Occupied'))
    completed_bookings = sum(1 for r in reservations if r['status'] == 'Completed')
    total_spent = sum(float(r['parking_cost'] or 0) for r in reservations if r['status'] == 'Completed')

    conn.close()
    return render_template('admin/user_details.html',
                           active_page='admin_users',
                           user=user,
                           reservations=reservations,
                           total_bookings=total_bookings,
                           active_bookings=active_bookings,
                           completed_bookings=completed_bookings,
                           total_spent=total_spent)

@app.route('/parking_slots')
def parking_slots_page():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    active_lot_id = session.get('active_lot_id', 0)
    lot_filter_sql = " WHERE ps.lot_id = ?" if active_lot_id > 0 else ""
    params = (active_lot_id,) if active_lot_id > 0 else ()

    spots = conn.execute(f'''
        SELECT ps.*, pl.prime_location_name,
               r.vehicle_number, r.vehicle_type, r.owner_name, r.parking_timestamp
        FROM parking_spots ps
        JOIN parking_lots pl ON ps.lot_id = pl.id
        LEFT JOIN reservations r ON r.id = (
            SELECT id FROM reservations
            WHERE spot_id = ps.id AND status IN ('Active', 'Parked', 'Occupied')
            ORDER BY id DESC LIMIT 1
        )
        {lot_filter_sql}
        ORDER BY ps.id ASC
    ''', params).fetchall()

    spots_list = []
    for s in spots:
        sd = dict(s)
        sd['duration_str'] = format_duration(sd['parking_timestamp']) if sd.get('parking_timestamp') else ''
        spots_list.append(sd)

    spots_by_zone = {}
    for s in spots_list:
        zone = s.get('zone') or 'General Zone'
        if zone not in spots_by_zone:
            spots_by_zone[zone] = []
        spots_by_zone[zone].append(s)

    total_count = len(spots_list)
    available_count = sum(1 for s in spots_list if s['status'] == 'A')
    occupied_count = sum(1 for s in spots_list if s['status'] == 'O')
    reserved_count = sum(1 for s in spots_list if s['status'] == 'R')
    maintenance_count = sum(1 for s in spots_list if s['status'] == 'M')

    conn.close()
    return render_template('parking_slots.html',
                           active_page='parking_slots',
                           spots=spots_list,
                           spots_by_zone=spots_by_zone,
                           total_spots=total_count,
                           available_spots=available_count,
                           occupied_spots=occupied_count,
                           reserved_spots=reserved_count,
                           maintenance_spots=maintenance_count)

@app.route('/edit_parking_slot', methods=['POST'])
def edit_parking_slot():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    spot_id = request.form.get('spot_id')
    spot_number = request.form.get('spot_number', '').strip()
    zone = request.form.get('zone', '').strip()
    spot_type = request.form.get('spot_type', 'Car').strip()
    status = request.form.get('status', 'A').strip()

    if spot_id and spot_number:
        conn = get_db_connection()
        conn.execute('''
            UPDATE parking_spots
            SET spot_number = ?, zone = ?, spot_type = ?, status = ?
            WHERE id = ?
        ''', (spot_number, zone, spot_type, status, spot_id))
        conn.commit()
        conn.close()
        flash(f'Parking slot "{spot_number}" updated successfully.', 'success')

    return redirect(request.referrer or url_for('parking_slots_page'))

@app.route('/history')
def history_page():
    user_id = session.get('user_id')
    is_admin = session.get('is_admin')
    conn = get_db_connection()

    active_lot_id = session.get('active_lot_id', 0)
    lot_filter = " AND pl.id = ?" if active_lot_id > 0 else ""
    lot_params = (active_lot_id,) if active_lot_id > 0 else ()

    if is_admin:
        history_rows = conn.execute(f'''
            SELECT r.*, ps.spot_number, pl.prime_location_name
            FROM reservations r
            JOIN parking_spots ps ON r.spot_id = ps.id
            JOIN parking_lots pl ON ps.lot_id = pl.id
            WHERE 1=1 {lot_filter}
            ORDER BY r.parking_timestamp DESC
        ''', lot_params).fetchall()
    else:
        history_rows = conn.execute(f'''
            SELECT r.*, ps.spot_number, pl.prime_location_name
            FROM reservations r
            JOIN parking_spots ps ON r.spot_id = ps.id
            JOIN parking_lots pl ON ps.lot_id = pl.id
            WHERE r.user_id = ? {lot_filter}
            ORDER BY r.parking_timestamp DESC
        ''', (user_id,) + lot_params).fetchall()

    history_list = []
    for h in history_rows:
        hd = dict(h)
        hd['duration_str'] = format_duration(hd['parking_timestamp'], hd.get('leaving_timestamp'))
        history_list.append(hd)

    conn.close()
    return render_template('history.html', active_page='history', history=history_list)

@app.route('/reports')
def reports_page():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    active_lot_id = session.get('active_lot_id', 0)
    lot_params = (active_lot_id,) if active_lot_id > 0 else ()

    total_lots = 1 if active_lot_id > 0 else conn.execute('SELECT COUNT(*) as count FROM parking_lots').fetchone()['count']
    total_spots = conn.execute(f'SELECT COUNT(*) as count FROM parking_spots{(" WHERE lot_id = ?" if active_lot_id > 0 else "")}', lot_params).fetchone()['count']
    total_reservations = conn.execute(f'''
        SELECT COUNT(*) as count FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        {(" WHERE ps.lot_id = ?" if active_lot_id > 0 else "")}
    ''', lot_params).fetchone()['count']
    total_revenue = conn.execute(f'''
        SELECT SUM(r.parking_cost) as total FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        WHERE r.status = "Completed" {(" AND ps.lot_id = ?" if active_lot_id > 0 else "")}
    ''', lot_params).fetchone()['total'] or 0.0

    lots_performance = conn.execute(f'''
        SELECT pl.prime_location_name,
               COUNT(r.id) as total_bookings,
               SUM(CASE WHEN r.status = 'Completed' THEN r.parking_cost ELSE 0 END) as total_revenue
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON ps.lot_id = pl.id
        LEFT JOIN reservations r ON r.spot_id = ps.id
        {(" WHERE pl.id = ?" if active_lot_id > 0 else "")}
        GROUP BY pl.id
    ''', lot_params).fetchall()

    conn.close()
    return render_template('reports.html',
                           active_page='reports',
                           total_lots=total_lots,
                           total_spots=total_spots,
                           total_reservations=total_reservations,
                           total_revenue=total_revenue,
                           lots_performance=lots_performance)

@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if not session.get('is_admin'):
        flash('Access restricted to administrators only.', 'error')
        return redirect(url_for('user_dashboard'))

    conn = get_db_connection()
    if request.method == 'POST':
        for key, val in request.form.items():
            if key.startswith('hourly_'):
                vtype = key.replace('hourly_', '')
                hourly = float(val)
                daily = float(request.form.get(f'daily_{vtype}', hourly * 7))
                custom = float(request.form.get(f'custom_{vtype}', hourly * 30))
                conn.execute('''
                    UPDATE tariffs
                    SET hourly_rate = ?, daily_rate = ?, custom_rate = ?
                    WHERE vehicle_type = ?
                ''', (hourly, daily, custom, vtype))
        conn.commit()
        flash('Tariff settings updated successfully.', 'success')

    tariffs_rows = conn.execute('SELECT * FROM tariffs').fetchall()
    tariffs = {row['vehicle_type']: dict(row) for row in tariffs_rows}
    conn.close()
    return render_template('settings.html', active_page='settings', tariffs=tariffs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit() or request.method == 'POST':
        email_or_user = (request.form.get('email') or '').strip()
        password = (request.form.get('password') or '').strip()

        if email_or_user == 'admin' and password == 'admin@123':
            session.clear()
            session['user_id'] = 1
            session['username'] = 'Admin'
            session['is_admin'] = True
            session['role'] = 'admin'
            session['active_lot_id'] = 0
            flash('Logged in successfully as Administrator!', 'success')
            return redirect(url_for('admin_dashboard'))

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? OR username = ?', (email_or_user, email_or_user)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role'] or 'user'
            session['active_lot_id'] = 0

            if user['role'] == 'admin':
                session['is_admin'] = True
                flash(f'Welcome back, Administrator {user["username"]}!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                session['is_admin'] = False
                flash(f'Welcome back, {user["username"]}!', 'success')
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username/email or password.', 'error')

    return render_template('login.html', form=form, active_page='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit() or request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = (request.form.get('password') or '').strip()
        address = (request.form.get('address') or '').strip()
        pincode = (request.form.get('pincode') or '').strip()

        if not username or not email or not password:
            flash('Please fill all required fields.', 'error')
            return render_template('register.html', form=form, active_page='register')

        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ? OR username = ?', (email, username)).fetchone()
        if existing:
            flash('Username or email is already registered! Please sign in.', 'error')
            conn.close()
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        conn.execute('''
            INSERT INTO users (username, email, password, address, pincode, role)
            VALUES (?, ?, ?, ?, ?, 'user')
        ''', (username, email, hashed_pw, address, pincode))
        conn.commit()
        conn.close()

        flash('Account registered successfully! You can now sign in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form, active_page='register')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
