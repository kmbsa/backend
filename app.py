import datetime
import os
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate
from functools import wraps
from extensions import db, ma, bcrypt
from Database import users, area, areaCoordinates, areaImages, area_schema, areaTopography, areaFarm
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity, get_jwt
)

import base64
import uuid
import jwt as pyjwt
import time
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

from dotenv import load_dotenv

import dynamic_ip as dip 

app = Flask(__name__)
CORS(app)

load_dotenv(os.path.join(app.root_path, '.env')) 

connection_string = "mysql+pymysql://root@localhost:3306/Capstone_DB"
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

app.config['JWT_BLACKLIST_ENABLED'] = True
app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']
app.config["JWT_SECRET_KEY"] = app.config['SECRET_KEY']
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=30)
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_CSRF_IN_PAYLOAD'] = False

BASE_UPLOAD_DIR = 'static/area_images' 
app.config['BASE_UPLOAD_DIR'] = BASE_UPLOAD_DIR

os.makedirs(os.path.join(app.root_path, BASE_UPLOAD_DIR), exist_ok=True)

absolute_base_upload_dir = os.path.abspath(os.path.join(app.root_path, BASE_UPLOAD_DIR))
print(f"Backend: Absolute path for base upload directory: {absolute_base_upload_dir}")

app.config['EXTERNAL_BASE_URL'] = os.getenv('EXTERNAL_BASE_URL') 

if not app.config['EXTERNAL_BASE_URL']:
    print("WARNING: EXTERNAL_BASE_URL is NOT set in src/backend/.env! Images and API calls may fail.")
    print("Please create/update src/backend/.env with: EXTERNAL_BASE_URL=http://YOUR_MACHINE_IP:5000")


db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

migrate = Migrate(app, db)


jwt = JWTManager(app)
BLACKLISTED_JTIS = set()

@jwt.token_in_blocklist_loader
def is_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in BLACKLISTED_JTIS

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
            access_token = create_access_token(identity=str(user.User_ID))
            return jsonify({
                'access_token': access_token,
                'user_id': user.User_ID,
            }), 200
        else:
            return jsonify({'error': 'Invalid Credentials'}), 401
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return jsonify({'error': 'An unexpected server error occurred during login.'}), 500

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity()
    try:
        current_user_id = int(current_user_id)
    except Exception as e:
        print(f"Error converting JWT identity to int: {e}")
        return jsonify({'error': 'Invalid user id in token'}), 400
    return jsonify(logged_in_as=current_user_id), 200

@app.route('/auth/user', methods=['GET'])
@jwt_required()
def get_user_data():
    print("/auth/user called")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Authorization header value: {request.headers.get('Authorization')}")
    current_user_id = get_jwt_identity()
    print(f"JWT identity (user id): {current_user_id}")
    try:
        current_user_id = int(current_user_id)
    except Exception as e:
        print(f"Error converting JWT identity to int: {e}")
        return jsonify({'error': 'Invalid user id in token'}), 400
    try:
        user = db.session.get(users, current_user_id)
        print(f"User lookup result: {user}")
        if not user:
            print("User not found for id:", current_user_id)
            return jsonify({'error': 'User not found'}), 404
        user_json = {
            'user_id': user.User_ID,
            'email': user.Email,
            'first_name': user.First_name,
            'last_name': user.Last_name,
            'sex': user.Sex,
            'contact_no': user.Contact_No,
            'user_type': user.User_Type
        }
        print(f"Returning user JSON: {user_json}")
        return jsonify(user_json), 200
    except Exception as e:
        app.logger.error(f"Get user error: {e}")
        print(f"Exception in /auth/user: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        jti = get_jwt()['jti']
        BLACKLISTED_JTIS.add(jti)
        app.logger.info(f"User logged out. Token with jti {jti} blacklisted.")
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        app.logger.error(f"Logout error: {e}")



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
    
@app.route('/areas', methods=['GET'])
@jwt_required()
def get_all_areas():
    try:
        current_user_id = get_jwt_identity()
        try:
            current_user_id = int(current_user_id)
        except Exception as e:
            print(f"Error converting JWT identity to int: {e}")
            return jsonify({'error': 'Invalid user id in token'}), 400
        print(f"--- API Endpoint /areas hit by user {current_user_id} ---")
        
        current_page = request.args.get('page', 1, type=int)
        items_per_page = request.args.get('per_page', 10, type=int)
        search_query = request.args.get('search', '')

        print(f"Fetching page {current_page} with {items_per_page} items per page.")
        if search_query:
            print(f"Searching for: '{search_query}'")

        if current_page < 1 or items_per_page < 1:
            print("Invalid pagination parameters received.")
            return jsonify({"message": "Pagination parameters must be positive integers."}), 400

        base_query = area.query.options(
            joinedload(area.coordinates),
            joinedload(area.images)
        )

        if search_query:
            search_pattern = f"%{search_query}%"
            base_query = base_query.filter(
                or_(
                    area.Area_Name.ilike(search_pattern),
                    area.Region.ilike(search_pattern),
                    area.Province.ilike(search_pattern)
                )
            )

        offset_value = (current_page - 1) * items_per_page

        paginated_area_entries = base_query.offset(offset_value).limit(items_per_page + 1).all()
        
        print(f"Database query successful. Found {len(paginated_area_entries)} entries.")

        has_more_entries = len(paginated_area_entries) > items_per_page

        if has_more_entries:
            paginated_area_entries = paginated_area_entries[:-1]

        serialized_entries = area_schema.dump(paginated_area_entries, many=True)
        
        print(f"Serialization successful. Returning {len(serialized_entries)} entries with has_more: {has_more_entries}")
        
        return jsonify({
            "entries": serialized_entries,
            "page": current_page,
            "per_page": items_per_page,
            "has_more": has_more_entries
        }), 200

    except Exception as e:
        app.logger.error(f"Error fetching paginated map entries for user {current_user_id}: {e}")
        print(f"An unexpected error occurred: {e}")
        return jsonify({"message": "An error occurred while fetching paginated map entries.", "error": str(e)}), 500


@app.route('/api/area/<int:area_id>', methods=['GET'])
@jwt_required()
def get_area_details(area_id):
    try:
        current_area = area.query.options(
            joinedload(area.coordinates),
            joinedload(area.images)
        ).filter_by(Area_ID=area_id).first()

        if not current_area:
            return jsonify({"message": "Area not found."}), 404
        
        result = area_schema.dump(current_area)
        return jsonify({"area": result}), 200

    except Exception as e:
        app.logger.error(f"Error fetching area details for Area ID {area_id}: {e}")
        return jsonify({"message": "An error occurred while fetching area details.", "error": str(e)}), 500


@app.route('/area', methods=['POST'])
@jwt_required()
def submitArea():
    try:
        current_user_id = get_jwt_identity()
        try:
            current_user_id = int(current_user_id)
        except Exception as e:
            print(f"Error converting JWT identity to int: {e}")
            return jsonify({'error': 'Invalid user id in token'}), 400
        data = request.get_json()

        if not data:
            return jsonify({"message": "Invalid JSON data"}), 400

        name_data = data.get('name')
        region_data = data.get('region')
        province_data = data.get('province')
        organization_data = data.get('organization')
        coordinates_data = data.get('coordinates', [])
        photos_data = data.get('photos', [])

        # print(f"Received photos_data: {photos_data}")
        print(f"Number of photos received: {len(photos_data)}")

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

        if not name_data:
            return jsonify({"message": "Area 'name' is required"}), 400

        user_id_from_token = current_user_id

        new_area = area(
            User_ID=user_id_from_token,
            Area_Name=name_data,
            Region=region_data,
            Organization=organization_data,
            Province=province_data,
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
        
        sanitized_area_name = secure_filename(name_data.lower().replace(" ", "_"))
        area_upload_dir = os.path.join(app.root_path, app.config['BASE_UPLOAD_DIR'], sanitized_area_name)
        
        print(f"Attempting to create directory: {area_upload_dir}")
        os.makedirs(area_upload_dir, exist_ok=True)


        for photo_item in photos_data:
            print(f"Processing photo_item: {photo_item.keys()}")
            base64_data = photo_item.get('base64')
            mime_type = photo_item.get('mimeType')

            if not base64_data:
                app.logger.warning(f"Skipping photo with missing base64 data for area {new_area.Area_ID}.")
                print("base64_data is empty or None. Skipping this photo.")
                continue

            try:
                if ',' in base64_data and base64_data.startswith('data:'):
                    base64_data = base64.b64decode(base64_data.split(',')[1])
                    print("Removed data URI prefix from base64 data.")

                # You need to re-decode the base64 data after splitting.
                # If the data comes without the prefix, this line will work correctly.
                image_binary = base64.b64decode(base64_data)

                extension = ""
                if mime_type and '/' in mime_type:
                    extension = "." + mime_type.split('/')[-1]
                else:
                    extension = ".jpg"

                unique_filename = secure_filename(f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex}{extension}")
                
                file_path_on_server = os.path.join(area_upload_dir, unique_filename)

                print(f"Saving image to: {file_path_on_server}")
                with open(file_path_on_server, 'wb') as f:
                    f.write(image_binary)

                relative_url = f"/{app.config['BASE_UPLOAD_DIR']}/{sanitized_area_name}/{unique_filename}"
                
                new_image = areaImages(
                    Area_ID=new_area.Area_ID,
                    Filepath=relative_url
                )
                db.session.add(new_image)
                print(f"Added image entry to DB for {new_area.Area_ID}: {relative_url}")

            except Exception as img_e:
                app.logger.error(f"Error processing and saving image for area {new_area.Area_ID}: {img_e}")
                print(f"Detailed image saving error: {img_e}")
                continue
        
        slope_data = data.get('slope')
        masl_data = data.get('masl')

        new_topography_data = areaTopography(
            Area_ID=new_area.Area_ID,
            Slope=slope_data,
            Mean_Average_Sea_Level=masl_data,
        )
        db.session.add(new_topography_data)

        soil_type_data = data.get('soil_type')
        suitability_data = data.get('suitability')

        new_farm_data = areaFarm(
            Area_ID=new_area.Area_ID,
            Soil_Type=soil_type_data,
            Soil_Suitability=suitability_data,
        )
        db.session.add(new_farm_data)

        db.session.commit()

        result = area_schema.dump(new_area)
        return jsonify({
            "message": "Area submitted successfully!",
            "area": result
        }), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error submitting area for user {current_user_id}: {e}")
        print(f"Overall submission error: {e}")
        return jsonify({"message": "An error occurred while submitting the area.", "error": str(e)}), 500

@app.route('/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def catch_all(path):
    print("[Catch-All] Incoming request:")
    print(f"  Method: {request.method}")
    print(f"  Path: /{path}")
    print(f"  Headers: {dict(request.headers)}")
    try:
        data = request.get_json(force=False, silent=True)
        print(f"  JSON Body: {data}")
    except Exception as e:
        print(f"  Could not parse JSON body: {e}")
    return jsonify({
        "message": "No matching route found.",
        "method": request.method,
        "path": f"/{path}",
        "headers": dict(request.headers),
    }), 404

with app.app_context():
    print("Ensuring database tables exist...")
    db.create_all()
    print("Database table check complete.")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
