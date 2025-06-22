from .database import db
from .enums import Role, VisibilityType
import datetime

class User(db.Model):
    __tablename__ = 'user'
    
    userId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    profilePicture = db.Column(db.String(255), nullable=True, default='')
    visibility = db.Column(db.String(20), default='public')
    bio = db.Column(db.Text, nullable=True, default='')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_user_id(self):
        return self.userId

    def set_user_id(self, user_id):
        self.userId = user_id

    def get_username(self):
        return self.username

    def set_username(self, username):
        self.username = username

    def get_email(self):
        return self.email

    def set_email(self, email):
        self.email = email

    def get_password(self):
        return self.password

    def set_password(self, password):
        self.password = password
        
    def get_created_at(self):
        return self.createdAt
        
    def get_profile_picture(self):
        return self.profilePicture
        
    def set_profile_picture(self, profile_picture):
        self.profilePicture = profile_picture
        
    def get_visibility(self):
        return self.visibility
        
    def set_visibility(self, visibility):
        self.visibility = visibility
        
    def get_bio(self):
        return self.bio
        
    def set_bio(self, bio):
        self.bio = bio

# Moderator model as separate table
class Moderator(db.Model):
    __tablename__ = 'moderator'
    
    modID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    modLevel = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(45), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def get_mod_id(self):
        return self.modID
        
    def get_mod_level(self):
        return self.modLevel
        
    def set_mod_level(self, level):
        self.modLevel = level 