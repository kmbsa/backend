# src/backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from extensions import db, ma, bcrypt
# Ensure all models are imported for db.create_all()
from Database import Users, Area, AreaCoordinates, Images

import jwt
import time

import dynamic_ip as dip

app = Flask(__name__)
CORS(app)

# Configurations
connection_string = "mysql+pymysql://root@localhost:3306/Capstone_DB"
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "pp5Z8iqjN7BuHfn"

# Initialize extensions
db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

# Token Blacklist (in-memory) - Note: This is for example, use a database for production
BLACKLISTED_TOKENS = []

@app.route('/hello')
def hello():
    return "Hello World!"

@app.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        # --- Explicitly handle missing data or invalid JSON ---
        if not data:
            return jsonify({'error': 'Invalid or missing JSON data in request body'}), 400

        user_input = data.get('user') # Should be the email now
        password = data.get('password')

        # --- Basic input validation ---
        if not user_input or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        user = Users.query.filter(Users.Email.ilike(user_input)).first()


        # --- Check if user was found and password is correct ---
        if user and bcrypt.check_password_hash(user.Password, password):
            token = generate_token(user)
            return jsonify({'token': token, 'user_id': user.User_ID}), 200
        else:
            # User not found OR password incorrect
            return jsonify({'error': 'Invalid Credentials'}), 401

    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return jsonify({'error': 'An unexpected server error occurred during login.'}), 500

def generate_token(user):
    token_payload = {
        'user_id': user.User_ID, # Use user.User_ID
        'email': user.Email, # Use user.Email
        # Optional: Add other non-sensitive user data to token if needed on frontend
        # 'first_name': user.First_name,
        # 'last_name': user.Last_name,
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")
    return token

# --- Get User Route
@app.route('/user', methods=['GET'])
def get_user():
    start_time = time.time()
    # Assuming token validation middleware would go here in a larger app
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        token = token.split("Bearer ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])

        # Use the User_ID from the token to fetch the user
        user = db.session.get(Users, decoded_token['user_id']) # Use Users model and decoded user_id
        if not user:
            return jsonify({'error': 'User not found'}), 404

        end_time = time.time()
        print(f"🕒 API Execution Time: {end_time - start_time:.4f} seconds")

        return jsonify({
            'user_id': user.User_ID,
            'email': user.Email,
            'first_name': user.First_name,
            'last_name': user.Last_name,
            'sex': user.Sex,
            'contact_no': user.Contact_No,
            'user_type': user.User_Type
        }), 200

    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        app.logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Server error'}), 500

# --- Logout Route (Keep as is for now) ---
@app.route('/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')

    if token:
        token = token.split("Bearer ")[1]
        BLACKLISTED_TOKENS.append(token) # Note: In-memory blacklist is not persistent

    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/user', methods=['POST'])
def register():
    try:
        data = request.get_json()

        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        sex = data.get('sex')
        contact_no = data.get('contact_no')

        if not email or not password or not first_name or not last_name or not sex or not contact_no:
            return jsonify({'error': 'Missing required fields'}), 400

        # Hash password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # --- Check if email already exists (since email is unique now) ---
        if Users.query.filter_by(Email=email).first(): # Check against Users.Email
            return jsonify({'error': 'Email address already registered'}), 409

        # --- Create new user object matching DB schema column names ---
        new_user = Users(
            Email=email.lower(), 
            Password=hashed_password,
            First_name=first_name,
            Last_name=last_name, 
            Sex=sex,
            Contact_No=contact_no,
            User_Type="User"
        )

        db.session.add(new_user)
        db.session.commit()

        return jsonify({'message': 'User registered successfully', 'user_id': new_user.User_ID}), 201 # Use new_user.User_ID

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Server error during registration'}), 500


with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created.")

if __name__ == "__main__":
    # Use the correct IP address from dynamic_ip if needed, otherwise remove dip.get_ip()
    # app.run(debug=True, host=dip.get_ip()) # If you need to run on a specific IP
    app.run(debug=True, host='0.0.0.0') # Or run on 0.0.0.0 to be accessible externally