# Authentication & Rate Limiting

ArchiMind now includes a complete authentication system with rate limiting for anonymous users.

## Features

### For Anonymous Users
- **5 Free Generations**: Try ArchiMind with up to 5 repository analyses without creating an account
- **Session Tracking**: Your generation count is tied to your browser session
- **Login Prompt**: After 5 generations, a beautiful modal prompts you to sign up or login

### For Authenticated Users
- **Unlimited Generations**: No limits on repository analysis
- **Persistent History**: All your analyses are tracked in your account
- **Secure Authentication**: Passwords are hashed using industry-standard PBKDF2-SHA256

## User Flow

1. **First Visit (Anonymous)**
   - User can analyze up to 5 repositories
   - Each analysis is logged with a session ID
   - Generation count is displayed (optional)

2. **After 5 Generations**
   - Modal popup appears when attempting 6th generation
   - User can:
     - **Sign Up**: Create a new account for unlimited access
     - **Login**: Sign in to existing account
     - **Close**: Cancel the current generation

3. **After Login/Signup**
   - Welcome message shows user's first name
   - Logout button available in header
   - Unlimited repository analysis

## Implementation Details

### Backend (`main.py`)
```python
@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    # Check rate limiting for anonymous users
    if not current_user.is_authenticated:
        count = AnalysisLog.query.filter_by(session_id=session_id).count()
        if count >= 5:
            return jsonify({...}), 403  # Forbidden
```

### Frontend (`static/script.js`)
```javascript
if (response.status === 403) {
    // Show login modal
    document.getElementById('loginModal').style.display = 'flex';
}
```

### Database Schema
- **Users**: Email, password, first_name, created_at
- **AnalysisLog**: Tracks every analysis with user_id or session_id

## API Endpoints

### Authentication Routes
- `GET/POST /login` - User login
- `GET/POST /sign-up` - User registration
- `GET /logout` - User logout (requires login)

### Analysis Routes
- `POST /api/analyze` - Start analysis (enforces rate limit)
- `GET /api/status` - Check analysis status
- `GET /api/check-limit` - Check current generation count

## Security Features

1. **Password Hashing**: PBKDF2-SHA256 with salt
2. **Session Management**: Flask-Login with remember me
3. **CSRF Protection**: Flask secret key
4. **SQL Injection Prevention**: SQLAlchemy ORM
5. **Environment Variables**: Sensitive data in `.env`

## Database Migration

If upgrading from a previous version:

```bash
# Backup existing data first!

# Install new dependencies
pip install -r requirements.txt

# Set up PostgreSQL (see DATABASE_SETUP.md)

# Update .env with DATABASE_URL and SECRET_KEY

# Start app (tables created automatically)
python3 main.py
```

## Customization

### Change Rate Limit
Edit `main.py`, line 71:
```python
if count >= 5:  # Change 5 to your desired limit
```

### Modify Modal Design
Edit `templates/index.html`, search for `id="loginModal"`

### Add Password Requirements
Edit `auth.py`, modify validation in `sign_up()` function

## Troubleshooting

### "Generation limit reached" but I haven't used 5
- Clear browser cookies/session
- Check if session ID is being properly set
- Verify database connection

### Login doesn't work
- Ensure DATABASE_URL is correct in `.env`
- Check PostgreSQL is running
- Verify user exists: `SELECT * FROM users;`

### Modal doesn't show
- Check browser console for JavaScript errors
- Ensure `loginModal` div exists in index.html
- Verify script.js is loaded properly


# Database Setup Guide

ArchiMind uses PostgreSQL for user authentication and rate limiting.

## Quick Setup

### 1. Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**macOS (using Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Windows:**
Download and install from [postgresql.org](https://www.postgresql.org/download/windows/)

### 2. Create Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE archimind;
CREATE USER archimind_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE archimind TO archimind_user;
\q
```

### 3. Configure Environment

Update your `.env` file:

```env
# PostgreSQL Database
DATABASE_URL=postgresql://archimind_user:your_secure_password@localhost/archimind

# Flask Secret Key (generate a secure random key)
SECRET_KEY=your-secret-key-here

# Gemini API
GEMINI_API_KEY=your-gemini-api-key
```

**Generate a secure SECRET_KEY:**
```python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Initialize Tables

The application will automatically create all required tables on first run. Just start the server:

```bash
python3 main.py
```

## Database Schema

### Users Table
- `id`: Primary key
- `email`: Unique user email (indexed)
- `password`: Hashed password
- `first_name`: User's first name
- `created_at`: Registration timestamp

### Analysis Logs Table
- `id`: Primary key
- `user_id`: Foreign key to users (nullable for anonymous)
- `session_id`: Session ID for anonymous users (indexed)
- `repo_url`: Repository URL analyzed
- `status`: Analysis status (pending, processing, completed, failed)
- `created_at`: Analysis start time
- `completed_at`: Analysis completion time

## Rate Limiting

- **Anonymous users**: 5 free generations per session
- **Authenticated users**: Unlimited generations

## Troubleshooting

### Connection Error
```
psycopg2.OperationalError: could not connect to server
```
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Verify DATABASE_URL in `.env` matches your PostgreSQL credentials

### Permission Denied
```
FATAL: permission denied for database
```
- Re-run the GRANT command in the database setup step

### Tables Not Created
- Check application logs for errors
- Manually create tables: See `models.py` for schema
- Ensure the user has CREATE TABLE permissions
