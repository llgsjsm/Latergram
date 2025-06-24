from .base_user import BaseUserMixin
from .database import db
from .enums import Role, VisibilityType
import datetime

class User(db.Model, BaseUserMixin):
    __tablename__ = 'user'
    
    userId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    profilePicture = db.Column(db.String(255), nullable=True, default='')
    visibility = db.Column(db.String(20), default='Public')
    bio = db.Column(db.Text, nullable=True, default='')
    followers = db.Column(db.Integer, default=0)  # Added missing followers field

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Implementation of abstract methods from BaseUserMixin
    def get_id(self):
        """Implementation of abstract method from BaseUserMixin"""
        return self.userId
    
    def set_id(self, user_id):
        """Implementation of abstract method from BaseUserMixin"""
        self.userId = user_id

    # User-specific getter and setter methods
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

# Follower relationship model  
class Follower(db.Model):
    __tablename__ = 'followers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    followerUserId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    followedUserId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20), default='accepted')  # 'pending', 'accepted', 'declined'
    
    # Relationships
    follower = db.relationship('User', foreign_keys=[followerUserId], backref='following_relationships')
    followed = db.relationship('User', foreign_keys=[followedUserId], backref='follower_relationships')