# src/backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from extensions import db, ma, bcrypt
from Database import users, area, areaCoordinates, areaImages, area_schema
import datetime

import jwt
import time
from functools import wraps

import os 
import base64 
from werkzeug.utils import secure_filename
import uuid 

from sqlalchemy.orm import joinedload


import dynamic_ip as dip

app = Flask(__name__)
CORS(app)

connection_string = "mysql+pymysql://root@localhost:3306/Capstone_DB"
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "pp5Z8iqjN7BuHfn"

BASE_UPLOAD_DIR = 'static/area_images'
app.config['BASE_UPLOAD_DIR'] = BASE_UPLOAD_DIR
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)

absolute_base_upload_dir = os.path.abspath(BASE_UPLOAD_DIR)
print(f"Backend: Absolute path for base upload directory: {absolute_base_upload_dir}")


db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

BLACKLISTED_TOKENS = []

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token is missing or malformed!'}), 401

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        if token in BLACKLISTED_TOKENS:
            return jsonify({'message': 'Token has been revoked.'}), 401

        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = decoded_token.get('user_id')

            if not current_user_id:
                return jsonify({'message': 'Token does not contain user ID!'}), 403

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
            return jsonify({'token': token, 'user_id': user.User_ID}), 200
        else:
            return jsonify({'error': 'Invalid Credentials'}), 401
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return jsonify({'error': 'An unexpected server error occurred during login.'}), 500

def generate_token(user):
    token_payload = {
        'user_id': user.User_ID,
        'email': user.Email,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")
    return token

@app.route('/user', methods=['GET'])
@token_required
def get_user_data(current_user_id):
    start_time = time.time()
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
@token_required
def logout(current_user_id):
    token = request.headers.get('Authorization')
    if token:
        token = token.split("Bearer ")[1]
        if token not in BLACKLISTED_TOKENS:
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

@app.route('/api/area/<int:area_id>', methods=['GET'])
@token_required
def get_area_details(current_user_id, area_id):
    try:
        # Assuming your Area model has relationships named 'coordinates_rel' and 'images_rel'
        current_area = area.query.options(
            joinedload(area.coordinates_rel),
            joinedload(area.images_rel)
        ).filter_by(Area_ID=area_id).first()

        if not current_area:
            return jsonify({"message": "Area not found."}), 404

        # Optional: Check if the requesting user owns this area (or has permission to view it)
        # if current_area.User_ID != current_user_id:
        #     return jsonify({"message": "Unauthorized to view this area."}), 403

        result = area_schema.dump(current_area)
        return jsonify({"area": result}), 200

    except Exception as e:
        app.logger.error(f"Error fetching area details for Area ID {area_id}: {e}")
        return jsonify({"message": "An error occurred while fetching area details.", "error": str(e)}), 500


@app.route('/area', methods=['POST'])
@token_required
def submitArea(current_user_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({"message": "Invalid JSON data"}), 400

        name = data.get('name')
        region = data.get('region')
        province = data.get('province')
        coordinates_data = data.get('coordinates', [])
        photos_data = data.get('photos', []) # <--- Check this list!

        print(f"Received photos_data: {photos_data}") # DEBUG LINE 1
        print(f"Number of photos received: {len(photos_data)}") # DEBUG LINE 2

        payload_user_id = data.get('user_id')
        if payload_user_id is None:
            return jsonify({"message": "Missing 'user_id' in payload."}), 400
        try:
            payload_user_id = int(payload_user_id)
        except ValueError:
            return jsonify({"message": "'user_id' in payload must be an integer."}), 400

        if payload_user_id != current_user_id:
            app.logger.warning(f"Attempted area submission for user_id {payload_user_id} by authenticated user {current_user_id}.")
            return jsonify({"message": "User ID in payload does not match authenticated user."}), 403

        if not name:
            return jsonify({"message": "Area 'name' is required"}), 400

        user_id_from_token = current_user_id

        new_area = area(
            User_ID=user_id_from_token,
            Area_Name=name,
            Region=region,
            Province=province,
            created_at=datetime.datetime.now()
        )
        db.session.add(new_area)
        db.session.flush()

        if not coordinates_data:
            db.session.rollback()
            return jsonify({"message": "At least one coordinate is required for an area"}), 400

        for coord_item in coordinates_data:
            latitude = coord_item.get('latitude')
            longitude = coord_item.get('longitude')

            if latitude is None or longitude is None:
                db.session.rollback()
                return jsonify({"message": "Invalid coordinate data: 'latitude' and 'longitude' are required"}), 400
            
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
        
        # --- Handle Images (Photos) - MODIFIED FOR AREA-SPECIFIC FOLDERS ---
        sanitized_area_name = secure_filename(name.lower().replace(" ", "_"))
        area_upload_dir = os.path.join(app.config['BASE_UPLOAD_DIR'], sanitized_area_name)
        
        # This will only create the folder if photos_data is not empty and the loop runs
        # Consider making this happen unconditionally if you want the folder even without photos
        # Or add a print statement here to see if it's reached
        print(f"Attempting to create directory: {area_upload_dir}") # DEBUG LINE 3
        os.makedirs(area_upload_dir, exist_ok=True)


        for photo_item in photos_data:
            print(f"Processing photo_item: {photo_item.keys()}") # DEBUG LINE 4
            base64_data = photo_item.get('base64')
            mime_type = photo_item.get('mimeType')
            original_filename = photo_item.get('filename', 'untitled_image')

            if not base64_data:
                app.logger.warning(f"Skipping photo with missing base64 data for area {new_area.Area_ID}.")
                print("base64_data is empty or None. Skipping this photo.") # DEBUG LINE 5
                continue

            try:
                # IMPORTANT: Remove the "data:image/jpeg;base64," prefix if it's present!
                # Expo's ImagePicker and Camera sometimes return the full data URI.
                if ',' in base64_data and base64_data.startswith('data:'):
                    base64_data = base64_data.split(',')[1]
                    print("Removed data URI prefix from base64 data.") # DEBUG LINE 6

                image_binary = base64.b64decode(base64_data)

                extension = ""
                if mime_type and '/' in mime_type:
                    extension = "." + mime_type.split('/')[-1]
                elif '.' in original_filename:
                    extension = "." + original_filename.split('.')[-1]
                else:
                    extension = ".jpg" # Default if no info available

                unique_filename = secure_filename(f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex}{extension}")
                
                file_path_on_server = os.path.join(area_upload_dir, unique_filename)

                print(f"Saving image to: {file_path_on_server}") # DEBUG LINE 7
                with open(file_path_on_server, 'wb') as f:
                    f.write(image_binary)

                public_url = f"{request.url_root.rstrip('/')}/{app.config['BASE_UPLOAD_DIR']}/{sanitized_area_name}/{unique_filename}"
                
                new_image = areaImages(
                    Area_ID=new_area.Area_ID,
                    Image_filename=original_filename, 
                    Filepath=public_url
                )
                db.session.add(new_image)
                print(f"Added image entry to DB for {new_area.Area_ID}: {public_url}") # DEBUG LINE 8

            except Exception as img_e:
                app.logger.error(f"Error processing and saving image for area {new_area.Area_ID}: {img_e}")
                print(f"Detailed image saving error: {img_e}") # DEBUG LINE 9
                continue

        db.session.commit()

        result = area_schema.dump(new_area)
        return jsonify({
            "message": "Area submitted successfully!",
            "area": result
        }), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error submitting area for user {current_user_id}: {e}")
        print(f"Overall submission error: {e}") # DEBUG LINE 10
        return jsonify({"message": "An error occurred while submitting the area.", "error": str(e)}), 500
        
with app.app_context():
    print("Ensuring database tables exist...")
    db.create_all()
    print("Database table check complete.")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')