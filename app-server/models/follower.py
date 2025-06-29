from .database import db
import datetime

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
    
    
    def get_follower_id(self):
        return self.followerUserId
    
    def set_follower_id(self, follower_id):
        self.followerUserId = follower_id
        
    def get_followed_id(self):
        return self.followedUserId
    
    def set_followed_id(self, followed_id):
        self.followedUserId = followed_id
        
    def get_status(self):
        return self.status

    def set_status(self, status):
        self.status = status
        
    def get_created_at(self):
        return self.createdAt
    
    def set_created_at(self, created_at):
        self.createdAt = created_at
        
    def get_id(self):
        return self.id
