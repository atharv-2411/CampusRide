# 🚗 CampusRide

**CampusRide** is a web-based **Carpooling Service for College or Company** that allows users to share rides easily.  
It helps reduce travel costs, traffic congestion, and fuel usage by connecting riders going in the same direction.

This project is built using **Python Flask**, **Flask-SQLAlchemy**, **HTML**, **CSS**, and **PostgreSQL** (SQLite for local development).

🔗 **Live Demo:** https://campusride-d6t4.onrender.com/

---

## 🌟 Features

- 🔐 User Signup and Login System
- 🚗 Add, View, and Manage Rides
- 📅 Book Available Rides
- 💬 Chat Feature Between Users
- 🏠 Dashboard for Viewing Ride Details
- 💰 Payment Status Tracking
- 🗂️ PostgreSQL Database (SQLite fallback for local dev)

---

## 🧰 Tech Stack

| Component | Technology |
|------------|-------------|
| **Frontend** | HTML, CSS, Bootstrap 5 |
| **Backend** | Python (Flask Framework) |
| **ORM** | Flask-SQLAlchemy |
| **Database** | PostgreSQL (Production) / SQLite (Local) |
| **Server** | Gunicorn (Production) / Flask Dev Server (Local) |
| **Hosting** | Render |

---

## 🚀 Local Development Setup

### 1️⃣ Prerequisites

Make sure the following are installed:

- **Python 3.8+** → [Download here](https://www.python.org/downloads/)
- **pip** → comes with Python by default
- **Git** → [Download here](https://git-scm.com/downloads)

```bash
python --version
pip --version
git --version
```

### 2️⃣ Clone the Repository

```bash
git clone https://github.com/atharv-2411/CampusRide.git
cd CampusRide
```

### 3️⃣ Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

- **Windows:** `venv\Scripts\activate`
- **macOS/Linux:** `source venv/bin/activate`

### 4️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 5️⃣ Run the Application

```bash
python app.py
```

Visit: [http://127.0.0.1:5000](http://127.0.0.1:5000)

> SQLite database (`mspa.db`) is created automatically on first run.

---

## 🌐 Production Deployment (Render)

### Environment Variables

Set these in your Render Web Service settings:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | PostgreSQL Internal URL from Render |
| `SECRET_KEY` | Any long random secret string |

### Deploy Steps

1. Push code to GitHub
2. Create a **PostgreSQL** database on Render
3. Create a **Web Service** on Render connected to this repo
4. Set the environment variables above
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `gunicorn app:app`

Every push to `main` triggers an automatic redeploy.

---

## 🔑 Default Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Driver | `driver@college.edu` | `driver123` |
| Passenger | `passenger@college.edu` | `pass123` |

> These are seeded automatically on first boot if no users exist.

---

## 📁 Project Structure

```
CampusRide/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── Procfile            # Render/Gunicorn start command
├── static/
│   └── style.css       # Custom styles
└── templates/
    ├── layout.html
    ├── index.html
    ├── login.html
    ├── signup.html
    ├── dashboard.html
    ├── add_ride.html
    ├── book_ride.html
    ├── ride_details.html
    └── chat.html
```
