from .base_user import BaseUserModel
from .database import db
import datetime

class User(BaseUserModel):
    __tablename__ = 'user'
    
    userId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    profilePicture = db.Column(db.String(255), nullable=True, default='')
    visibility = db.Column(db.String(20), default='Public')
    bio = db.Column(db.Text, nullable=True, default='')
    disabledUntil = db.Column(db.DateTime, nullable=True)  # add missing field for disabling user accounts
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Implementation of abstract methods from BaseUserModel
    def get_id(self):
        """Implementation of abstract method from BaseUserModel"""
        return self.userId
    
    def set_id(self, user_id):
        """Implementation of abstract method from BaseUserModel"""
        self.userId = user_id

    # User-specific getter and setter methods
    def get_user_id(self):
        return self.userId

    def set_user_id(self, user_id):
        self.userId = user_id

    def set_user_id(self, user_id):
        self.userId = user_id
        
    # User-specific getter and setter methods for additional fields
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
        
    def get_followers(self):
        return self.followers
        
    def set_followers(self, followers):
        self.followers = followers

    def get_role(self):
        """Return the role for compatibility with ModeratorManager"""
        return "student"  # Default role for regular users
    
    @property
    def role(self):
        """Property accessor for role to maintain compatibility"""
        return self.get_role()