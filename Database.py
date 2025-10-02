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
    Contact_No = db.Column(db.String(50), nullable=False)
    User_Type = db.Column(db.String(50), nullable=False, default="User")

    areas = db.relationship('area', backref='author', lazy=True)
    approval = db.relationship('areaApproval', backref='moderator', lazy=True)

    def __repr__(self):
        return f"<User {self.User_ID} - {self.Email}>"


class area(db.Model):
    __tablename__ = 'area'
    Area_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    User_ID = db.Column(db.Integer, db.ForeignKey('users.User_ID'), nullable=False)
    Area_Name = db.Column(db.String(255), nullable=False)
    Region = db.Column(db.String(255), nullable=False)
    Province = db.Column(db.String(255), nullable=False)
    Organization = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)

    coordinates = db.relationship('areaCoordinates', backref='area_parent', lazy=True, cascade="all, delete-orphan")
    images = db.relationship('areaImages', backref='area_parent', lazy=True, cascade="all, delete-orphan")
    farm = db.relationship('areaFarm', backref='area_parent', lazy=True, cascade="all, delete-orphan")
    approval = db.relationship('areaApproval', backref='area_parent', lazy=True, cascade="all, delete-orphan")
    topography = db.relationship('areaTopography', backref='area_parent', lazy=True, cascade="all, delete-orphan")

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
        return f"<Image (ID: {self.Image_ID}, Filename: {self.Filepath})>"
class areaFarm(db.Model):
    __tablename__ = 'area_farm'
    Farm_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Area_ID = db.Column(db.Integer, db.ForeignKey('area.Area_ID'), nullable=False)
    Soil = db.Column(db.String(75), nullable=True)
    Soil_Suitability = db.Column(db.String(75), nullable=True)
    Hectares = db.Column(db.Numeric(10,4), nullable=False)
    Status = db.Column(db.String(20), nullable=False, default="Inactive")

    harvest = db.relationship('farmHarvestData', backref='farm', lazy=True)

class areaApproval(db.Model):
    __tablename__ = 'area_approval'
    Approval_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Area_ID = db.Column(db.Integer, db.ForeignKey('area.Area_ID'), nullable=False)
    User_ID = db.Column(db.Integer, db.ForeignKey('users.User_ID'), nullable=False)
    Status = db.Column(db.String(20), nullable=True, default="Pending")
    Time_Of_Checking = db.Column(db.DateTime, nullable=True)

class areaTopography(db.Model):
    __tablename__ = 'area_topography'
    Area_Topography_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Area_ID = db.Column(db.Integer, db.ForeignKey('area.Area_ID'), nullable=False)
    Slope = db.Column(db.Integer, nullable=True)
    Mean_Average_Sea_Level = db.Column(db.Float, nullable=True)

class farmHarvestData(db.Model):
    __tablename__ = 'farm_harvest_data'
    Harvest_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Farm_ID = db.Column(db.Integer, db.ForeignKey('area_farm.Farm_ID'), nullable=False)
    Crop = db.Column(db.String(50), nullable=False)
    Sow_Date = db.Column(db.DateTime, nullable=False)
    Harvest_Date = db.Column(db.DateTime, nullable=False)

class userSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = users
        dump_only = ('User_ID', 'Password',)
        load_instance = True

class areaImageSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaImages
        load_instance = True
        exclude = ('area_parent',) 

    Image_ID = fields.Int(required=True)

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

class areaFarmSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaFarm
        load_instance = True
        exclude = ('area_parent',)

class areaApprovalSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaApproval
        load_instance = True
        exclude = ('area_parent', 'moderator',)

class areaTopographySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = areaTopography
        load_instance = True
        exclude = ('area_parent',)

class farmHarvestDataSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = farmHarvestData
        load_instance = True
        exclude = ('farm',)




user_schema = userSchema()
users_schema = userSchema(many=True)

area_schema = areaSchema()
areas_schema = areaSchema(many=True)

area_coordinate_schema = areaCoordinateSchema()
area_coordinates_schema = areaCoordinateSchema(many=True)

image_schema = areaImageSchema()
images_schema = areaImageSchema(many=True)

farm_schema = areaFarmSchema()
farms_schema = areaFarmSchema(many=True)

approval_schema = areaApprovalSchema()
approvals_schema = areaApprovalSchema(many=True)

topography_schema = areaTopographySchema()
topographies_schema = areaTopographySchema(many=True)

harvest_schema = farmHarvestDataSchema()
harvests_schema = farmHarvestDataSchema(many=True)