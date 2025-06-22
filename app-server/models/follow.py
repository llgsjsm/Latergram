from .database import db
from sqlalchemy.sql import func

class Follow(db.Model):
    """
    Represents the relationship of one user following another.
    This is a direct mapping to the 'followers' table in the database.
    """
    __tablename__ = 'followers'

    id = db.Column(db.Integer, primary_key=True)
    
    # The user who is doing the following
    follower_user_id = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    
    # The user who is being followed
    followed_user_id = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    
    created_at = db.Column(db.DateTime, server_default=func.now())

    # Define relationships to the User model
    # This allows us to easily access the User object from a Follow object
    follower = db.relationship('User', foreign_keys=[follower_user_id], backref='following')
    followed = db.relationship('User', foreign_keys=[followed_user_id], backref='followers')

    # Add a unique constraint to ensure a user cannot follow another user more than once.
    __table_args__ = (
        db.UniqueConstraint('follower_user_id', 'followed_user_id', name='_user_follows_uc'),
    )

    def __repr__(self):
        return f'<Follow {self.follower_user_id} follows {self.followed_user_id}>'
