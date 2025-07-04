from .base_user import BaseUserModel
from .database import db
import datetime

class Moderator(BaseUserModel):
    """
    Moderator user class that inherits from BaseUserModel.
    Represents moderators in the system with additional moderation capabilities.
    Uses the existing database table structure.
    """
    __tablename__ = 'moderator'
    
    modID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    modLevel = db.Column(db.Integer, nullable=False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Implementation of abstract methods from BaseUserModel
    def get_id(self):
        """Implementation of abstract method from BaseUserModel"""
        return self.modID
    
    def set_id(self, user_id):
        """Implementation of abstract method from BaseUserModel"""
        self.modID = user_id
        
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
