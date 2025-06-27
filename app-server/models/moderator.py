from .base_user import BaseUserMixin
from .database import db
import datetime

class Moderator(db.Model, BaseUserMixin):
    """
    Moderator user class that inherits from BaseUserMixin.
    Represents moderators in the system with additional moderation capabilities.
    Uses the existing database table structure.
    """
    __tablename__ = 'moderator'
    
    modID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    modLevel = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # OTP fields
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    otp_type = db.Column(db.String(20), nullable=True)  # 'login' or 'password_reset'
    login_attempts = db.Column(db.Integer, default=0)
    last_otp_request = db.Column(db.DateTime, nullable=True)
    otp_enabled = db.Column(db.Boolean, default=True)  # Moderator preference for OTP login (enabled by default)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Implementation of abstract methods from BaseUserMixin
    def get_id(self):
        """Implementation of abstract method from BaseUserMixin"""
        return self.modID
    
    def set_id(self, user_id):
        """Implementation of abstract method from BaseUserMixin"""
        self.modID = user_id
        
    def get_username(self):
        """Implementation of abstract method from BaseUserMixin"""
        return self.username

    def set_username(self, username):
        """Implementation of abstract method from BaseUserMixin"""
        self.username = username

    def get_email(self):
        """Implementation of abstract method from BaseUserMixin"""
        return self.email

    def set_email(self, email):
        """Implementation of abstract method from BaseUserMixin"""
        self.email = email

    def get_password(self):
        """Implementation of abstract method from BaseUserMixin"""
        return self.password

    def set_password(self, password):
        """Implementation of abstract method from BaseUserMixin"""
        self.password = password
        
    def get_created_at(self):
        """Implementation of abstract method from BaseUserMixin"""
        return self.createdAt
        
    # Moderator-specific methods
    def get_mod_id(self):
        return self.modID
        
    def get_mod_level(self):
        return self.modLevel
        
    def set_mod_level(self, level):
        self.modLevel = level
        
    def can_moderate_level(self, target_level):
        """Check if this moderator can moderate content at the target level"""
        return self.modLevel >= target_level
    
    def get_role(self):
        """Return the role for compatibility with ModeratorManager"""
        return "moderator"
