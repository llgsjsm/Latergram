from .database import db
import datetime

class Comment(db.Model):
    __tablename__ = 'comment'

    commentId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    authorId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    postId = db.Column(db.Integer, db.ForeignKey('post.postId'), nullable=False)
    commentContent = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    edited_at = db.Column(db.DateTime, nullable=True)
    parentCommentId = db.Column(db.Integer, db.ForeignKey('comment.commentId'))
    
    # Relationships
    author = db.relationship('User', backref=db.backref('comments', lazy=True))
    post = db.relationship('Post', backref=db.backref('comments', lazy='dynamic'))

    def get_comment_id(self):
        return self.commentId

    def set_comment_id(self, comment_id):
        self.commentId = comment_id

    def get_comment_content(self):
        return self.commentContent

    def set_comment_content(self, content):
        self.commentContent = content

    def get_author(self):
        return self.author

    def set_author(self, author):
        self.author = author
        
    def get_post(self):
        return self.post
        
    def set_post(self, post):
        self.post = post

    def get_timestamp(self):
        return self.timestamp

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def get_edited_at(self):
        return self.edited_at

    def set_edited_at(self, edited_at):
        self.edited_at = edited_at

    def is_edited(self):
        """Check if the comment has been edited"""
        return self.edited_at is not None

    def mark_as_edited(self):
        """Mark the comment as edited with current timestamp"""
        self.edited_at = datetime.datetime.utcnow()

# Add self-referential relationship after class definition
Comment.replies = db.relationship('Comment', 
                                  backref=db.backref('parent', remote_side=[Comment.commentId]), 
                                  lazy='dynamic')