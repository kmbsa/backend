# src/backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from extensions import db, ma, bcrypt
from Database import users, area, areaCoordinates, areaImages, area_schema
import datetime

import jwt
import time
from functools import wraps

import dynamic_ip as dip

app = Flask(__name__)
CORS(app)

connection_string = "mysql+pymysql://root@localhost:3306/Capstone_DB"
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "pp5Z8iqjN7BuHfn" # KEEP THIS SECRET IN PRODUCTION! Use environment variables.

db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

# Token Blacklist (in-memory) - Note: This is for example, use a database/Redis for production
BLACKLISTED_TOKENS = []

# --- JWT Token Verification Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check for Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                # Expecting "Bearer <token>"
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token is missing or malformed!'}), 401

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        # Check if token is blacklisted
        if token in BLACKLISTED_TOKENS:
            return jsonify({'message': 'Token has been revoked.'}), 401

        try:
            # Decode the token using the secret key
            # Ensure the 'user_id' key in the payload matches what you store in generate_token
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = decoded_token.get('user_id') # Get user_id from token payload

            if not current_user_id:
                return jsonify({'message': 'Token does not contain user ID!'}), 403

            # Optionally, you can fetch the user from the database to ensure they still exist and are active
            # current_user = users.query.get(current_user_id)
            # if not current_user:
            #     return jsonify({'message': 'User associated with token not found!'}), 404

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
            app.logger.error(f"Token decoding error: {e}")
            return jsonify({'message': 'An error occurred during token verification.'}), 500

        return f(current_user_id, *args, **kwargs)
    return decorated


@app.route('/hello')
def hello():
    return "Hello World!"

@app.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Invalid or missing JSON data in request body'}), 400

        user_input = data.get('user')
        password = data.get('password')

        if not user_input or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        user = users.query.filter(users.Email.ilike(user_input)).first()

        if user and bcrypt.check_password_hash(user.Password, password):
            token = generate_token(user)
            # Send back the user_id from the database for the client to store
            return jsonify({'token': token, 'user_id': user.User_ID}), 200
        else:
            return jsonify({'error': 'Invalid Credentials'}), 401

    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return jsonify({'error': 'An unexpected server error occurred during login.'}), 500

def generate_token(user):
    token_payload = {
        'user_id': user.User_ID, # Store user_id in the token payload
        'email': user.Email,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1), # Token expires in 1 hour
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }
    # For PyJWT >= 2.0, encode returns bytes. Decode to string if needed for client.
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")
    return token

@app.route('/user', methods=['GET'])
@token_required # Apply token_required to secure this endpoint
def get_user_data(current_user_id): # The current_user_id is passed by the decorator
    start_time = time.time()
    # No need to get token from headers again, current_user_id is already available
    try:
        user = db.session.get(users, current_user_id)
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

    except Exception as e:
        app.logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/auth/logout', methods=['POST'])
@token_required # Secure the logout endpoint too
def logout(current_user_id): # Accept current_user_id (though not strictly used here)
    token = request.headers.get('Authorization')

    if token:
        token = token.split("Bearer ")[1]
        if token not in BLACKLISTED_TOKENS: # Prevent double blacklisting
            BLACKLISTED_TOKENS.append(token)
            app.logger.info(f"User {current_user_id} logged out. Token blacklisted.")

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

        if not all([email, password, first_name, last_name, sex, contact_no]):
            return jsonify({'error': 'Missing required fields'}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if users.query.filter_by(Email=email).first():
            return jsonify({'error': 'Email address already registered'}), 409

        new_user = users(
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

        return jsonify({'message': 'User registered successfully', 'user_id': new_user.User_ID}), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Server error during registration'}), 500

@app.route('/area', methods=['POST'])
@token_required # Apply the token_required decorator
def submitArea(current_user_id): # The authenticated user's ID will be passed here
    try:
        data = request.get_json()

        # --- 1. Basic Input Validation ---
        if not data:
            return jsonify({"message": "Invalid JSON data"}), 400

        name = data.get('name')
        region = data.get('region')
        province = data.get('province')
        coordinates_data = data.get('coordinates', []) # Ensure it's a list, default to empty
        photos_data = data.get('photos', [])           # Ensure it's a list, default to empty
        
        # Validate that the user_id in the payload matches the authenticated user_id
        # This is an important security check to prevent a user from submitting data for another user
        payload_user_id = data.get('user_id')
        if payload_user_id is None: # Check for None as 0 could be a valid ID
            return jsonify({"message": "Missing 'user_id' in payload."}), 400
        
        # Ensure payload_user_id is an integer for comparison
        try:
            payload_user_id = int(payload_user_id)
        except ValueError:
            return jsonify({"message": "'user_id' in payload must be an integer."}), 400

        if payload_user_id != current_user_id:
            app.logger.warning(f"Attempted area submission for user_id {payload_user_id} by authenticated user {current_user_id}.")
            return jsonify({"message": "User ID in payload does not match authenticated user."}), 403

        # Check for mandatory fields from the frontend
        if not name:
            return jsonify({"message": "Area 'name' is required"}), 400
        # region and province are nullable in your schema, so not strictly required here
        
        # --- 2. Use Authenticated User ID ---
        # The user_id is now retrieved directly from the JWT token via `current_user_id`
        user_id_from_token = current_user_id

        # Verify if the user actually exists (optional, but good practice if not always fetching user)
        # user_exists = users.query.get(user_id_from_token)
        # if not user_exists:
        #     return jsonify({"message": f"User with ID {user_id_from_token} not found. Cannot associate area."}), 404


        # --- 3. Create the Area Entry ---
        new_area = area(
            User_ID=user_id_from_token, # Assign the User_ID from the authenticated token
            Area_Name=name,
            Region=region,
            Province=province,
            created_at=datetime.datetime.now() # Explicitly set timestamp, though default handles it
        )
        db.session.add(new_area)
        db.session.flush() # Use flush to get new_area.Area_ID before committing

        # --- 4. Handle Coordinates ---
        if not coordinates_data:
            db.session.rollback() # Rollback if coordinates are missing
            return jsonify({"message": "At least one coordinate is required for an area"}), 400

        for coord_item in coordinates_data:
            latitude = coord_item.get('latitude')
            longitude = coord_item.get('longitude')

            if latitude is None or longitude is None:
                db.session.rollback() # Rollback if coordinates are malformed
                return jsonify({"message": "Invalid coordinate data: 'latitude' and 'longitude' are required"}), 400
            
            # Type conversion and validation for float types
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except ValueError:
                db.session.rollback()
                return jsonify({"message": "Invalid coordinate data: latitude and longitude must be numbers"}), 400
            
            new_coordinate = areaCoordinates(
                Area_ID=new_area.Area_ID,
                Latitude=latitude,
                Longitude=longitude
            )
            db.session.add(new_coordinate)
        
        # --- 5. Handle Images (Photos) ---
        # Your frontend sends 'uri'. Your backend expects 'Filepath'.
        # We'll store the `uri` directly into `Filepath` for now.
        # If you were actually uploading files, this part would be much more complex.
        for photo_item in photos_data:
            # Assuming photo_item looks like { id: '...', uri: 'file://path/to/image.jpg' }
            photo_uri = photo_item.get('uri')
            
            if not photo_uri:
                # Optionally rollback or just log and skip malformed photo entries
                print(f"Skipping photo with missing URI: {photo_item}")
                continue
            
            # It's good practice to derive a filename from the URI or generate a unique one
            # For simplicity, let's just use a placeholder for Image_filename if not directly provided
            image_filename = f"photo_{photo_item.get('id') or datetime.datetime.now().timestamp()}.jpg"
            if photo_uri and photo_uri.startswith('file:///'):
                # Extracting just the filename from a file URI (e.g., for display purposes)
                # This is a basic example; you might need a more robust path parsing if actual files are involved
                image_filename = photo_uri.split('/')[-1]


            new_image = areaImages(
                Area_ID=new_area.Area_ID,
                Image_filename=image_filename, # This might be null or a derived name
                Filepath=photo_uri # Store the URI provided by the frontend
            )
            db.session.add(new_image)

        # --- 6. Commit the Transaction ---
        db.session.commit()

        # --- 7. Return Success Response ---
        # Optionally, you can return the full, newly created area object using its Marshmallow schema
        result = area_schema.dump(new_area)
        return jsonify({
            "message": "Area submitted successfully!",
            "area": result
        }), 201 # 201 Created

    except Exception as e:
        # --- 8. Robust Error Handling ---
        db.session.rollback() # Rollback any changes in case of an error
        app.logger.error(f"Error submitting area for user {current_user_id}: {e}") # Log the error for debugging
        return jsonify({"message": "An error occurred while submitting the area.", "error": str(e)}), 500

with app.app_context():
    # Only create tables if they don't exist
    print("Ensuring database tables exist...")
    db.create_all()
    print("Database table check complete.")

if __name__ == "__main__":
    # Use the correct IP address from dynamic_ip if needed, otherwise remove dip.get_ip()
    # app.run(debug=True, host=dip.get_ip()) # If you need to run on a specific IP
    app.run(debug=True, host='0.0.0.0') # Or run on 0.0.0.0 to be accessible externally