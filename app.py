from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import sqlite3
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
# This secret key is crucial for managing sessions (user logins)
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'

# --- Database Setup ---
DATABASE = 'mspa.db'

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Rides table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_email TEXT NOT NULL,
            driver_name TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            seats_available INTEGER NOT NULL,
            price_per_seat DECIMAL(10,2) DEFAULT 0.00,
            route_waypoints TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (driver_email) REFERENCES users (email)
        )
    ''')
    
    # Bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ride_id INTEGER NOT NULL,
            passenger_email TEXT NOT NULL,
            passenger_name TEXT NOT NULL,
            pickup_location TEXT,
            dropoff_location TEXT,
            amount_paid DECIMAL(10,2) DEFAULT 0.00,
            payment_status TEXT DEFAULT 'pending',
            booked_at TEXT NOT NULL,
            FOREIGN KEY (ride_id) REFERENCES rides (id),
            FOREIGN KEY (passenger_email) REFERENCES users (email)
        )
    ''')
    
    # Activity log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_name TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL
        )
    ''')
    
    # Add missing columns if they don't exist (migration)
    try:
        cursor.execute('ALTER TABLE rides ADD COLUMN price_per_seat DECIMAL(10,2) DEFAULT 0.00')
    except:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE rides ADD COLUMN route_waypoints TEXT')
    except:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE bookings ADD COLUMN pickup_location TEXT')
    except:
        pass
    
    try:
        cursor.execute('ALTER TABLE bookings ADD COLUMN dropoff_location TEXT')
    except:
        pass
    
    try:
        cursor.execute('ALTER TABLE bookings ADD COLUMN amount_paid DECIMAL(10,2) DEFAULT 0.00')
    except:
        pass
    
    try:
        cursor.execute('ALTER TABLE bookings ADD COLUMN payment_status TEXT DEFAULT "pending"')
    except:
        pass
    
    try:
        cursor.execute('ALTER TABLE rides ADD COLUMN ride_status TEXT DEFAULT "active"')
    except:
        pass
    
    try:
        cursor.execute('ALTER TABLE rides ADD COLUMN completed_at TEXT')
    except:
        pass
    
    try:
        cursor.execute('ALTER TABLE rides ADD COLUMN distance_km DECIMAL(5,2) DEFAULT 0.00')
    except:
        pass
    
    # Chat messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ride_id INTEGER NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (ride_id) REFERENCES rides (id),
            FOREIGN KEY (sender_email) REFERENCES users (email)
        )
    ''')
    
    # Insert default users if they don't exist
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO users (email, password, name, role) VALUES 
            (?, ?, ?, ?),
            (?, ?, ?, ?)
        ''', (
            'driver@college.edu', generate_password_hash('driver123'), 'Alex Driver', 'driver',
            'passenger@college.edu', generate_password_hash('pass123'), 'Sam Passenger', 'passenger'
        ))
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database
init_db()
# ---------------------


@app.route('/')
def index():
    """Serves the home page."""
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check if user exists and password is correct
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            # User is "logged in" by storing their email in the session
            session['email'] = email
            session['name'] = user['name']
            session['role'] = user['role']
            
            # Log the login
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO activity_log (timestamp, user_name, action, details)
                VALUES (?, ?, ?, ?)
            ''', (
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                user['name'],
                'LOGIN',
                f"User {user['name']} ({user['role']}) logged in"
            ))
            conn.commit()
            conn.close()
            logger.info(f"Login successful: {user['name']} ({user['role']})")
            
            flash(f'Welcome {user["role"].title()}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handles user registration."""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        # Validation
        if not email.endswith('.edu'):
            flash('Must use a valid college email address (e.g., .edu).', 'error')
            return redirect(url_for('signup'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('signup'))

        # Check if user already exists
        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            conn.close()
            flash('Email already registered.', 'error')
            return redirect(url_for('signup'))

        # Add new user to database
        conn.execute('''
            INSERT INTO users (email, password, name, role)
            VALUES (?, ?, ?, ?)
        ''', (email, generate_password_hash(password), name, role))
        
        # Log the registration
        conn.execute('''
            INSERT INTO activity_log (timestamp, user_name, action, details)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            name,
            'REGISTER',
            f"New {role} account created: {name}"
        ))
        conn.commit()
        conn.close()
        logger.info(f"New user registered: {name} ({role})")
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/dashboard')
def dashboard():
    """Shows the main dashboard after login."""
    if 'email' not in session:
        flash('You must be logged in to see this page.', 'error')
        return redirect(url_for('login'))

    # Get filter parameters
    search_from = request.args.get('search_from', '')
    search_to = request.args.get('search_to', '')
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    min_seats = request.args.get('min_seats', type=int)
    departure_date = request.args.get('departure_date', '')
    
    # Build query with filters
    query = '''
        SELECT r.*, COALESCE(COUNT(b.id), 0) as booked_seats
        FROM rides r
        LEFT JOIN bookings b ON r.id = b.ride_id
        WHERE (r.ride_status != 'completed' OR r.ride_status IS NULL)
    '''
    params = []
    
    if search_from:
        query += ' AND r.origin LIKE ?'
        params.append(f'%{search_from}%')
    if search_to:
        query += ' AND r.destination LIKE ?'
        params.append(f'%{search_to}%')
    if min_price:
        query += ' AND r.price_per_seat >= ?'
        params.append(min_price)
    if max_price:
        query += ' AND r.price_per_seat <= ?'
        params.append(max_price)
    if departure_date:
        query += ' AND DATE(r.departure_time) = ?'
        params.append(departure_date)
    
    query += ' GROUP BY r.id'
    
    if min_seats:
        query += ' HAVING (r.seats_available - COALESCE(COUNT(b.id), 0)) >= ?'
        params.append(min_seats)
    
    query += ' ORDER BY r.created_at DESC'
    
    # Fetch rides from database
    conn = get_db_connection()
    rides = conn.execute(query, params).fetchall()
    
    # Convert to list of dicts and add passenger info for drivers
    rides_list = []
    for ride in rides:
        ride_dict = dict(ride)
        ride_dict['available_seats'] = ride_dict['seats_available'] - ride_dict['booked_seats']
        
        # Parse waypoints if they exist
        waypoints = ride_dict.get('route_waypoints')
        if waypoints:
            import json
            try:
                ride_dict['route_waypoints'] = json.loads(waypoints)
            except:
                ride_dict['route_waypoints'] = []
        else:
            ride_dict['route_waypoints'] = []
        
        # Add passenger list for drivers
        if session.get('role') == 'driver' and ride_dict['driver_email'] == session['email']:
            passengers = conn.execute('''
                SELECT b.id as booking_id, passenger_name, passenger_email, pickup_location, dropoff_location, 
                       amount_paid, payment_status, booked_at
                FROM bookings b WHERE ride_id = ?
            ''', (ride_dict['id'],)).fetchall()
            ride_dict['passengers'] = [dict(p) for p in passengers]
        else:
            ride_dict['passengers'] = []
            
        rides_list.append(ride_dict)
    
    conn.close()
    
    return render_template('dashboard.html', 
                         name=session['name'], 
                         role=session.get('role', 'user'), 
                         rides=rides_list,
                         session=session)


@app.route('/logout')
def logout():
    """Logs the user out."""
    user_name = session.get('name', 'Unknown')
    session.pop('email', None)
    session.pop('name', None)
    session.pop('role', None)
    
    # Log the logout
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO activity_log (timestamp, user_name, action, details)
        VALUES (?, ?, ?, ?)
    ''', (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        user_name,
        'LOGOUT',
        f"User {user_name} logged out"
    ))
    conn.commit()
    conn.close()
    logger.info(f"User logged out: {user_name}")
    
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# -----------------------------------------------
# --- NEWLY ADDED FUNCTION FOR ADDING A RIDE ---
# -----------------------------------------------
@app.route('/add-ride', methods=['GET', 'POST'])
def add_ride():
    """Handles adding a new ride."""
    if 'email' not in session:
        flash('You must be logged in to post a ride.', 'error')
        return redirect(url_for('login'))
    
    if session.get('role') != 'driver':
        flash('Only drivers can post rides.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # --- This is the BACKEND part ---
        # Get data from the form
        origin = request.form['origin']
        destination = request.form['destination']
        departure_time = request.form['departure_time']
        seats = int(request.form['seats_available'])
        price_per_seat = float(request.form.get('price_per_seat', 0))
        route_waypoints = request.form.get('route_waypoints', '')
        
        # Validation
        if seats < 1 or seats > 8:
            flash('Seats must be between 1 and 8.', 'error')
            return render_template('add_ride.html')
        
        if price_per_seat < 0:
            flash('Price must be a positive number.', 'error')
            return render_template('add_ride.html')
        
        driver_name = session['name']
        
        # Calculate distance (simple estimation)
        distance_km = 10.0  # Default distance
        if origin != destination:
            # Simple distance calculation based on location
            location_distances = {
                ('KK Wagh Institute of Engineering Education and Research', 'Nashik Central Bus Stand'): 8.5,
                ('Nashik Central Bus Stand', 'College Road'): 5.2,
                ('College Road', 'Gangapur Road'): 3.8,
                ('Mumbai Naka', 'Panchavati'): 12.0
            }
            distance_km = location_distances.get((origin, destination), 
                         location_distances.get((destination, origin), 10.0))
        
        # Calculate split fare based on distance
        base_fare = max(20, distance_km * 8)  # ₹8 per km, minimum ₹20
        suggested_price = base_fare if price_per_seat == 0 else price_per_seat
        
        # Add the new ride to database
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO rides (driver_email, driver_name, origin, destination, departure_time, 
                             seats_available, price_per_seat, route_waypoints, distance_km, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['email'],
            driver_name,
            origin,
            destination,
            departure_time,
            seats,
            suggested_price,
            route_waypoints,
            distance_km,
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ))
        
        # Log the ride creation
        conn.execute('''
            INSERT INTO activity_log (timestamp, user_name, action, details)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            driver_name,
            'CREATE_RIDE',
            f"Posted ride from {origin} to {destination} for ₹{price_per_seat}/seat"
        ))
        conn.commit()
        conn.close()
        logger.info(f"Ride created by {driver_name}: {origin} -> {destination}")
        
        flash('Your ride has been posted successfully!', 'success')
        
        # 5. Send the user back to the dashboard to see their new ride
        return redirect(url_for('dashboard'))

    # --- This is the FRONTEND part (GET request) ---
    # Show the "add ride" form page
    return render_template('add_ride.html')
# -----------------------------------------------
# --- END OF NEW FUNCTION ---
# -----------------------------------------------


@app.route('/book-ride/<int:ride_id>', methods=['GET', 'POST'])
def book_ride(ride_id):
    """Book a ride."""
    if 'email' not in session:
        flash('You must be logged in to book a ride.', 'error')
        return redirect(url_for('login'))
    
    if session.get('role') != 'passenger':
        flash('Only passengers can book rides.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    ride = conn.execute('SELECT * FROM rides WHERE id = ?', (ride_id,)).fetchone()
    if not ride:
        conn.close()
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))
    
    # Check available seats
    booked_count = conn.execute('SELECT COUNT(*) FROM bookings WHERE ride_id = ?', (ride_id,)).fetchone()[0]
    available_seats = ride['seats_available'] - booked_count
    
    if available_seats <= 0:
        conn.close()
        flash('No seats available.', 'error')
        return redirect(url_for('dashboard'))
    
    if ride['driver_email'] == session['email']:
        conn.close()
        flash('You cannot book your own ride.', 'error')
        return redirect(url_for('dashboard'))
    
    # Check if already booked
    existing_booking = conn.execute('''
        SELECT * FROM bookings WHERE ride_id = ? AND passenger_email = ?
    ''', (ride_id, session['email'])).fetchone()
    
    if existing_booking:
        conn.close()
        flash('You have already booked this ride.', 'error')
        return redirect(url_for('dashboard'))
    
    ride_dict = dict(ride)
    ride_dict['available_seats'] = available_seats
    
    # Parse waypoints if they exist
    waypoints = ride_dict.get('route_waypoints')
    if waypoints:
        import json
        try:
            ride_dict['route_waypoints'] = json.loads(waypoints)
        except:
            ride_dict['route_waypoints'] = []
    else:
        ride_dict['route_waypoints'] = []
    
    if request.method == 'POST':
        pickup_location = request.form['pickup_location']
        dropoff_location = request.form['dropoff_location']
        payment_method = request.form['payment_method']
        
        # Add booking
        conn.execute('''
            INSERT INTO bookings (ride_id, passenger_email, passenger_name, pickup_location, 
                                dropoff_location, amount_paid, payment_status, booked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ride_id,
            session['email'],
            session['name'],
            pickup_location,
            dropoff_location,
            ride['price_per_seat'],
            'pending',
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ))
        
        # Log the booking
        conn.execute('''
            INSERT INTO activity_log (timestamp, user_name, action, details)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            session['name'],
            'BOOK_RIDE',
            f"Booked ride from {pickup_location} to {dropoff_location} (₹{ride['price_per_seat']})"
        ))
        
        conn.commit()
        conn.close()
        
        flash('Ride booked successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('book_ride.html', ride=ride_dict)

@app.route('/cancel-ride/<int:ride_id>')
def cancel_ride(ride_id):
    """Cancel a ride (only by driver)."""
    if 'email' not in session:
        flash('You must be logged in.', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    ride = conn.execute('SELECT * FROM rides WHERE id = ?', (ride_id,)).fetchone()
    if not ride:
        conn.close()
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))
    
    if ride['driver_email'] != session['email']:
        conn.close()
        flash('You can only cancel your own rides.', 'error')
        return redirect(url_for('dashboard'))
    
    # Delete bookings first
    conn.execute('DELETE FROM bookings WHERE ride_id = ?', (ride_id,))
    # Delete the ride
    conn.execute('DELETE FROM rides WHERE id = ?', (ride_id,))
    
    # Log the cancellation
    conn.execute('''
        INSERT INTO activity_log (timestamp, user_name, action, details)
        VALUES (?, ?, ?, ?)
    ''', (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        session['name'],
        'CANCEL_RIDE',
        f"Cancelled ride from {ride['origin']} to {ride['destination']}"
    ))
    
    conn.commit()
    conn.close()
    
    flash('Ride cancelled successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/login-driver')
def login_driver():
    """Driver login page."""
    return render_template('login.html', role='driver')

@app.route('/login-passenger')
def login_passenger():
    """Passenger login page."""
    return render_template('login.html', role='passenger')

@app.route('/ride-details/<int:ride_id>')
def ride_details(ride_id):
    """Show detailed ride information."""
    if 'email' not in session:
        flash('You must be logged in to view ride details.', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    ride = conn.execute('''
        SELECT r.*, COALESCE(COUNT(b.id), 0) as booked_seats
        FROM rides r
        LEFT JOIN bookings b ON r.id = b.ride_id
        WHERE r.id = ?
        GROUP BY r.id
    ''', (ride_id,)).fetchone()
    
    if not ride:
        conn.close()
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))
    
    ride_dict = dict(ride)
    ride_dict['available_seats'] = ride_dict['seats_available'] - ride_dict['booked_seats']
    
    # Get passenger list
    passengers = conn.execute('''
        SELECT passenger_name, passenger_email, booked_at
        FROM bookings WHERE ride_id = ?
    ''', (ride_id,)).fetchall()
    ride_dict['passengers'] = [dict(p) for p in passengers]
    
    conn.close()
    
    # Parse waypoints if they exist
    waypoints = ride_dict.get('route_waypoints')
    if waypoints:
        import json
        try:
            ride_dict['route_waypoints'] = json.loads(waypoints)
        except:
            ride_dict['route_waypoints'] = []
    else:
        ride_dict['route_waypoints'] = []
    
    return render_template('ride_details.html', 
                         ride=ride_dict, 
                         role=session.get('role'), 
                         email=session.get('email'))

@app.route('/complete-ride/<int:ride_id>', methods=['POST'])
def complete_ride(ride_id):
    """Mark a ride as completed."""
    if 'email' not in session or session.get('role') != 'driver':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    ride = conn.execute('SELECT * FROM rides WHERE id = ? AND driver_email = ?', 
                       (ride_id, session['email'])).fetchone()
    
    if not ride:
        conn.close()
        flash('Ride not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    
    # Update ride status
    conn.execute('''
        UPDATE rides SET ride_status = ?, completed_at = ? WHERE id = ?
    ''', ('completed', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ride_id))
    
    # Log the activity
    conn.execute('''
        INSERT INTO activity_log (timestamp, user_name, action, details)
        VALUES (?, ?, ?, ?)
    ''', (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        session['name'],
        'COMPLETE_RIDE',
        f"Completed ride from {ride['origin']} to {ride['destination']}"
    ))
    conn.commit()
    conn.close()
    
    flash('Ride marked as completed!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update-payment/<int:booking_id>', methods=['POST'])
def update_payment(booking_id):
    """Update payment status for a booking."""
    if 'email' not in session or session.get('role') != 'driver':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard'))
    
    payment_status = request.form['payment_status']
    
    conn = get_db_connection()
    # Verify the booking belongs to driver's ride
    booking = conn.execute('''
        SELECT b.*, r.driver_email FROM bookings b
        JOIN rides r ON b.ride_id = r.id
        WHERE b.id = ? AND r.driver_email = ?
    ''', (booking_id, session['email'])).fetchone()
    
    if not booking:
        conn.close()
        flash('Booking not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    
    # Update payment status
    conn.execute('UPDATE bookings SET payment_status = ? WHERE id = ?', 
                (payment_status, booking_id))
    
    # Log the activity
    conn.execute('''
        INSERT INTO activity_log (timestamp, user_name, action, details)
        VALUES (?, ?, ?, ?)
    ''', (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        session['name'],
        'UPDATE_PAYMENT',
        f"Updated payment status to {payment_status} for booking #{booking_id}"
    ))
    conn.commit()
    conn.close()
    
    flash(f'Payment status updated to {payment_status}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/chat/<int:ride_id>')
def chat(ride_id):
    """Chat for a specific ride."""
    if 'email' not in session:
        flash('You must be logged in to chat.', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    ride = conn.execute('SELECT * FROM rides WHERE id = ?', (ride_id,)).fetchone()
    if not ride:
        conn.close()
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))
    
    # Check if user is part of this ride
    is_driver = ride['driver_email'] == session['email']
    is_passenger = conn.execute('SELECT * FROM bookings WHERE ride_id = ? AND passenger_email = ?', 
                               (ride_id, session['email'])).fetchone() is not None
    
    if not (is_driver or is_passenger):
        conn.close()
        flash('You are not part of this ride.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get chat messages
    messages = conn.execute('''
        SELECT * FROM chat_messages WHERE ride_id = ? ORDER BY timestamp ASC
    ''', (ride_id,)).fetchall()
    
    conn.close()
    return render_template('chat.html', ride=dict(ride), messages=[dict(m) for m in messages])

@app.route('/send-message/<int:ride_id>', methods=['POST'])
def send_message(ride_id):
    """Send a chat message."""
    if 'email' not in session:
        return {'success': False, 'error': 'Not logged in'}
    
    message = request.form.get('message', '').strip()
    if not message:
        return {'success': False, 'error': 'Empty message'}
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO chat_messages (ride_id, sender_email, sender_name, message, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (ride_id, session['email'], session['name'], message, 
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chat', ride_id=ride_id))

if __name__ == '__main__':
    app.run(debug=True)