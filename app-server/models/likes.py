from .database import db
import datetime

class Likes(db.Model):
    __tablename__ = 'likes'
    
    likesId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_userId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('likes', lazy=True))
    
    def get_likes_id(self):
        return self.likesId
        
    def get_user_id(self):
        return self.user_userId
        
    def get_timestamp(self):
        return self.timestamp
