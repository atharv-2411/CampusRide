from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))

# --- Database Configuration ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///mspa.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Ride(db.Model):
    __tablename__ = 'rides'
    id = db.Column(db.Integer, primary_key=True)
    driver_email = db.Column(db.String(255), db.ForeignKey('users.email'), nullable=False)
    driver_name = db.Column(db.String(255), nullable=False)
    origin = db.Column(db.Text, nullable=False)
    destination = db.Column(db.Text, nullable=False)
    departure_time = db.Column(db.String(50), nullable=False)
    seats_available = db.Column(db.Integer, nullable=False)
    price_per_seat = db.Column(db.Numeric(10, 2), default=0.00)
    route_waypoints = db.Column(db.Text)
    ride_status = db.Column(db.String(50), default='active')
    completed_at = db.Column(db.String(50))
    distance_km = db.Column(db.Numeric(5, 2), default=0.00)
    created_at = db.Column(db.String(50), nullable=False)
    bookings = db.relationship('Booking', backref='ride', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('ChatMessage', backref='ride', lazy=True, cascade='all, delete-orphan')

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('rides.id'), nullable=False)
    passenger_email = db.Column(db.String(255), db.ForeignKey('users.email'), nullable=False)
    passenger_name = db.Column(db.String(255), nullable=False)
    pickup_location = db.Column(db.Text)
    dropoff_location = db.Column(db.Text)
    amount_paid = db.Column(db.Numeric(10, 2), default=0.00)
    payment_status = db.Column(db.String(50), default='pending')
    booked_at = db.Column(db.String(50), nullable=False)

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(50), nullable=False)
    user_name = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=False)

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('rides.id'), nullable=False)
    sender_email = db.Column(db.String(255), db.ForeignKey('users.email'), nullable=False)
    sender_name = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.String(50), nullable=False)

# --- Helpers ---
def log_activity(user_name, action, details):
    db.session.add(ActivityLog(
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        user_name=user_name, action=action, details=details
    ))

def parse_waypoints(ride_dict):
    wp = ride_dict.get('route_waypoints')
    if wp:
        try:
            ride_dict['route_waypoints'] = json.loads(wp)
        except (json.JSONDecodeError, TypeError):
            ride_dict['route_waypoints'] = []
    else:
        ride_dict['route_waypoints'] = []
    return ride_dict

def ride_to_dict(ride):
    d = {c.name: getattr(ride, c.name) for c in ride.__table__.columns}
    d['price_per_seat'] = float(d['price_per_seat'] or 0)
    d['distance_km'] = float(d['distance_km'] or 0)
    d['amount_paid'] = float(d.get('amount_paid') or 0) if 'amount_paid' in d else 0
    return d

# --- Routes ---
@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['email'] = email
            session['name'] = user.name
            session['role'] = user.role
            log_activity(user.name, 'LOGIN', f"User {user.name} ({user.role}) logged in")
            db.session.commit()
            logger.info(f"Login successful: {user.name} ({user.role})")
            flash(f'Welcome {user.role.title()}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if role not in ('driver', 'passenger'):
            flash('Invalid role selected.', 'error')
            return redirect(url_for('signup'))
        if not email.endswith('.edu'):
            flash('Must use a valid college email address (e.g., .edu).', 'error')
            return redirect(url_for('signup'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('signup'))

        db.session.add(User(email=email, password=generate_password_hash(password), name=name, role=role))
        log_activity(name, 'REGISTER', f"New {role} account created: {name}")
        db.session.commit()
        logger.info(f"New user registered: {name} ({role})")
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        flash('You must be logged in to see this page.', 'error')
        return redirect(url_for('login'))

    search_from = request.args.get('search_from', '')
    search_to = request.args.get('search_to', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    min_seats = request.args.get('min_seats', type=int)
    departure_date = request.args.get('departure_date', '')

    query = Ride.query.filter(
        (Ride.ride_status != 'completed') | (Ride.ride_status == None)
    )
    if search_from:
        query = query.filter(Ride.origin.ilike(f'%{search_from}%'))
    if search_to:
        query = query.filter(Ride.destination.ilike(f'%{search_to}%'))
    if min_price is not None:
        query = query.filter(Ride.price_per_seat >= min_price)
    if max_price is not None:
        query = query.filter(Ride.price_per_seat <= max_price)
    if departure_date:
        query = query.filter(Ride.departure_time.like(f'{departure_date}%'))

    rides = query.order_by(Ride.created_at.desc()).all()

    rides_list = []
    for ride in rides:
        ride_dict = ride_to_dict(ride)
        booked_seats = len(ride.bookings)
        ride_dict['booked_seats'] = booked_seats
        ride_dict['available_seats'] = ride_dict['seats_available'] - booked_seats
        ride_dict = parse_waypoints(ride_dict)

        if min_seats and ride_dict['available_seats'] < min_seats:
            continue

        if session.get('role') == 'driver' and ride_dict['driver_email'] == session['email']:
            ride_dict['passengers'] = [{
                'booking_id': b.id,
                'passenger_name': b.passenger_name,
                'passenger_email': b.passenger_email,
                'pickup_location': b.pickup_location,
                'dropoff_location': b.dropoff_location,
                'amount_paid': float(b.amount_paid or 0),
                'payment_status': b.payment_status,
                'booked_at': b.booked_at
            } for b in ride.bookings]
        else:
            ride_dict['passengers'] = []

        rides_list.append(ride_dict)

    return render_template('dashboard.html',
                           name=session['name'],
                           role=session.get('role', 'user'),
                           rides=rides_list,
                           session=session)


@app.route('/logout')
def logout():
    user_name = session.get('name', 'Unknown')
    session.pop('email', None)
    session.pop('name', None)
    session.pop('role', None)
    log_activity(user_name, 'LOGOUT', f"User {user_name} logged out")
    db.session.commit()
    logger.info(f"User logged out: {user_name}")
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/add-ride', methods=['GET', 'POST'])
def add_ride():
    if 'email' not in session:
        flash('You must be logged in to post a ride.', 'error')
        return redirect(url_for('login'))
    if session.get('role') != 'driver':
        flash('Only drivers can post rides.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        origin = request.form['origin']
        destination = request.form['destination']
        departure_time = request.form['departure_time']
        seats = int(request.form['seats_available'])
        price_per_seat = float(request.form.get('price_per_seat', 0))
        route_waypoints = request.form.get('route_waypoints', '')

        if seats < 1 or seats > 8:
            flash('Seats must be between 1 and 8.', 'error')
            return render_template('add_ride.html')
        if price_per_seat < 0:
            flash('Price must be a positive number.', 'error')
            return render_template('add_ride.html')

        location_distances = {
            ('KK Wagh Institute of Engineering Education and Research', 'Nashik Central Bus Stand'): 8.5,
            ('Nashik Central Bus Stand', 'College Road'): 5.2,
            ('College Road', 'Gangapur Road'): 3.8,
            ('Mumbai Naka', 'Panchavati'): 12.0
        }
        distance_km = location_distances.get((origin, destination),
                      location_distances.get((destination, origin), 10.0))
        base_fare = max(20, distance_km * 8)
        suggested_price = base_fare if price_per_seat == 0 else price_per_seat

        db.session.add(Ride(
            driver_email=session['email'],
            driver_name=session['name'],
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            seats_available=seats,
            price_per_seat=suggested_price,
            route_waypoints=route_waypoints,
            distance_km=distance_km,
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M')
        ))
        log_activity(session['name'], 'CREATE_RIDE',
                     f"Posted ride from {origin} to {destination} for ₹{price_per_seat}/seat")
        db.session.commit()
        logger.info(f"Ride created by {session['name']}: {origin} -> {destination}")
        flash('Your ride has been posted successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_ride.html')


@app.route('/book-ride/<int:ride_id>', methods=['GET', 'POST'])
def book_ride(ride_id):
    if 'email' not in session:
        flash('You must be logged in to book a ride.', 'error')
        return redirect(url_for('login'))
    if session.get('role') != 'passenger':
        flash('Only passengers can book rides.', 'error')
        return redirect(url_for('dashboard'))

    ride = Ride.query.get(ride_id)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))

    booked_count = len(ride.bookings)
    available_seats = ride.seats_available - booked_count

    if available_seats <= 0:
        flash('No seats available.', 'error')
        return redirect(url_for('dashboard'))
    if ride.driver_email == session['email']:
        flash('You cannot book your own ride.', 'error')
        return redirect(url_for('dashboard'))
    if Booking.query.filter_by(ride_id=ride_id, passenger_email=session['email']).first():
        flash('You have already booked this ride.', 'error')
        return redirect(url_for('dashboard'))

    ride_dict = ride_to_dict(ride)
    ride_dict['available_seats'] = available_seats
    ride_dict = parse_waypoints(ride_dict)

    if request.method == 'POST':
        pickup_location = request.form['pickup_location']
        dropoff_location = request.form['dropoff_location']
        db.session.add(Booking(
            ride_id=ride_id,
            passenger_email=session['email'],
            passenger_name=session['name'],
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            amount_paid=ride.price_per_seat,
            payment_status='pending',
            booked_at=datetime.now().strftime('%Y-%m-%d %H:%M')
        ))
        log_activity(session['name'], 'BOOK_RIDE',
                     f"Booked ride from {pickup_location} to {dropoff_location} (₹{ride.price_per_seat})")
        db.session.commit()
        flash('Ride booked successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('book_ride.html', ride=ride_dict)


@app.route('/cancel-ride/<int:ride_id>')
def cancel_ride(ride_id):
    if 'email' not in session:
        flash('You must be logged in.', 'error')
        return redirect(url_for('login'))

    ride = Ride.query.get(ride_id)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))
    if ride.driver_email != session['email']:
        flash('You can only cancel your own rides.', 'error')
        return redirect(url_for('dashboard'))

    log_activity(session['name'], 'CANCEL_RIDE',
                 f"Cancelled ride from {ride.origin} to {ride.destination}")
    db.session.delete(ride)
    db.session.commit()
    flash('Ride cancelled successfully.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/login-driver')
def login_driver():
    return render_template('login.html', role='driver')


@app.route('/login-passenger')
def login_passenger():
    return render_template('login.html', role='passenger')


@app.route('/ride-details/<int:ride_id>')
def ride_details(ride_id):
    if 'email' not in session:
        flash('You must be logged in to view ride details.', 'error')
        return redirect(url_for('login'))

    ride = Ride.query.get(ride_id)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))

    ride_dict = ride_to_dict(ride)
    booked_seats = len(ride.bookings)
    ride_dict['booked_seats'] = booked_seats
    ride_dict['available_seats'] = ride_dict['seats_available'] - booked_seats
    ride_dict['passengers'] = [
        {'passenger_name': b.passenger_name, 'passenger_email': b.passenger_email, 'booked_at': b.booked_at}
        for b in ride.bookings
    ]
    ride_dict = parse_waypoints(ride_dict)

    return render_template('ride_details.html',
                           ride=ride_dict,
                           role=session.get('role'),
                           email=session.get('email'))


@app.route('/complete-ride/<int:ride_id>', methods=['POST'])
def complete_ride(ride_id):
    if 'email' not in session or session.get('role') != 'driver':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard'))

    ride = Ride.query.filter_by(id=ride_id, driver_email=session['email']).first()
    if not ride:
        flash('Ride not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    ride.ride_status = 'completed'
    ride.completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_activity(session['name'], 'COMPLETE_RIDE',
                 f"Completed ride from {ride.origin} to {ride.destination}")
    db.session.commit()
    flash('Ride marked as completed!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update-payment/<int:booking_id>', methods=['POST'])
def update_payment(booking_id):
    if 'email' not in session or session.get('role') != 'driver':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard'))

    booking = Booking.query.join(Ride).filter(
        Booking.id == booking_id,
        Ride.driver_email == session['email']
    ).first()

    if not booking:
        flash('Booking not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    payment_status = request.form['payment_status']
    booking.payment_status = payment_status
    log_activity(session['name'], 'UPDATE_PAYMENT',
                 f"Updated payment status to {payment_status} for booking #{booking_id}")
    db.session.commit()
    flash(f'Payment status updated to {payment_status}!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/chat/<int:ride_id>')
def chat(ride_id):
    if 'email' not in session:
        flash('You must be logged in to chat.', 'error')
        return redirect(url_for('login'))

    ride = Ride.query.get(ride_id)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))

    is_driver = ride.driver_email == session['email']
    is_passenger = Booking.query.filter_by(ride_id=ride_id, passenger_email=session['email']).first() is not None

    if not (is_driver or is_passenger):
        flash('You are not part of this ride.', 'error')
        return redirect(url_for('dashboard'))

    messages = ChatMessage.query.filter_by(ride_id=ride_id).order_by(ChatMessage.timestamp.asc()).all()
    return render_template('chat.html',
                           ride=ride_to_dict(ride),
                           messages=[{c.name: getattr(m, c.name) for c in m.__table__.columns} for m in messages])


@app.route('/send-message/<int:ride_id>', methods=['POST'])
def send_message(ride_id):
    if 'email' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    message = request.form.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Empty message'}), 400

    db.session.add(ChatMessage(
        ride_id=ride_id,
        sender_email=session['email'],
        sender_name=session['name'],
        message=message,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    db.session.commit()
    return redirect(url_for('chat', ride_id=ride_id))


with app.app_context():
    db.create_all()
    if not User.query.first():
        db.session.add_all([
            User(email='driver@college.edu', password=generate_password_hash('driver123'),
                 name='Alex Driver', role='driver'),
            User(email='passenger@college.edu', password=generate_password_hash('pass123'),
                 name='Sam Passenger', role='passenger'),
        ])
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        pass  # already initialized above
        # Seed default users if table is empty
        if not User.query.first():
            db.session.add_all([
                User(email='driver@college.edu', password=generate_password_hash('driver123'),
                     name='Alex Driver', role='driver'),
                User(email='passenger@college.edu', password=generate_password_hash('pass123'),
                     name='Sam Passenger', role='passenger'),
            ])
            db.session.commit()
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
