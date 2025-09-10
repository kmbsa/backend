import datetime
from extensions import db, ma
from marshmallow import fields

class users(db.Model):
    __tablename__ = 'users'
    User_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Email = db.Column(db.String(50), unique=True, nullable=False)
    Password = db.Column(db.String(200), nullable=False)
    First_name = db.Column(db.String(255), nullable=False)
    Last_name = db.Column(db.String(255), nullable=False)
    Sex = db.Column(db.String(10), nullable=False)
    Contact_No = db.Column(db.String(50), nullable=True)
    User_Type = db.Column(db.String(50), nullable=False)

    areas = db.relationship('area', backref='author', lazy=True)

    def __repr__(self):
        return f"<User {self.User_ID} - {self.Email}>"


class area(db.Model):
    __tablename__ = 'area'
    Area_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    User_ID = db.Column(db.Integer, db.ForeignKey('users.User_ID'), nullable=False)
    Area_Name = db.Column(db.String(255), nullable=False)
    Region = db.Column(db.String(255), nullable=True)
    Province = db.Column(db.String(255), nullable=True)
    Organization = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)

    coordinates = db.relationship('areaCoordinates', backref='area_parent', lazy=True, cascade="all, delete-orphan")
    images = db.relationship('areaImages', backref='area_parent', lazy=True, cascade="all, delete-orphan")
    farm = db.relationship('areaFarm', backref='area_parent', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Area {self.Area_ID} - {self.Area_Name}>"

class areaCoordinates(db.Model):
    __tablename__ = 'area_coordinates'
    Area_Coordinate_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Area_ID = db.Column(db.Integer, db.ForeignKey('area.Area_ID'), nullable=False)

    Longitude = db.Column(db.Float, nullable=False)
    Latitude = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<AreaCoordinate (ID: {self.Area_Coordinate_ID}, Area: {self.Area_ID})>"
    
class areaImages(db.Model):
    __tablename__ = 'area_images'
    Image_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Area_ID = db.Column(db.Integer, db.ForeignKey('area.Area_ID'), nullable=False)
    Filepath = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<Image (ID: {self.Image_ID}, Filename: {self.Image_filename})>"
    
class soil(db.Model):
    __tablename__ = 'soil_type'
    Soil_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Soil_Type = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Soil (ID: {self.Soil_ID}, type: {self.Soil_Type})"

class areaFarm(db.Model):
    __tablename__ = 'area_farm'
    Farm_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Area_ID = db.Column(db.Integer, db.ForeignKey('area.Area_ID'), nullable=False)
    Soil = db.Column(db.Integer, db.ForeignKey('soil.Soil_ID'), nullable=True)
    Crop = db.Column(db.String(255), nullable=True)
    Hectares = db.Column(db.Numeric(10,2), nullable=False)

    soil = db.relationship("soil", backref="farms")

class userSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = users
        dump_only = ('User_ID',)
        load_instance = True
        exclude = ('Password',)

class areaImageSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaImages
        load_instance = True
        exclude = ('area_parent',) 

    Image_ID = fields.Int(required=True)
    Image_filename = fields.Str()

class areaCoordinateSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaCoordinates
        load_instance = True
        exclude = ('area_parent',) 

class areaSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = area
        load_instance = True
        exclude = ('author',) 

    coordinates = fields.Nested(areaCoordinateSchema, many=True)
    images = fields.Nested(areaImageSchema, many=True)

class soilSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = soil
        load_instance = True

class areaFarmSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaFarm
        load_instance = True
        exclude = ('area_parent', 'soil_parent',)

user_schema = userSchema()
users_schema = userSchema(many=True)

area_schema = areaSchema()
areas_schema = areaSchema(many=True)

area_coordinate_schema = areaCoordinateSchema()
area_coordinates_schema = areaCoordinateSchema(many=True)

image_schema = areaImageSchema()
images_schema = areaImageSchema(many=True)

soil_schema = soilSchema()
soils_schema = soilSchema(many=True)

farm_schema = areaFarmSchema()
farms_schema = areaFarmSchema(many=True)