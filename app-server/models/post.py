from .database import db
import datetime

class Post(db.Model):
    __tablename__ = 'post'

    postId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    authorId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    likesId = db.Column(db.Integer, db.ForeignKey('likes.likesId'))
    title = db.Column(db.String(255), nullable=False)
    timeOfPost = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    like = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255))
    content = db.Column(db.Text, nullable=False)
    
    # Relationships
    author = db.relationship('User', backref=db.backref('posts', lazy=True))
    likes_rel = db.relationship('Likes', backref=db.backref('post', lazy=True))

    def get_post_id(self):
        return self.postId

    def set_post_id(self, post_id):
        self.postId = post_id

    def get_title(self):
        return self.title

    def set_title(self, title):
        self.title = title

    def get_content(self):
        return self.content

    def set_content(self, content):
        self.content = content

    def get_author(self):
        return self.author

    def set_author(self, author):
        self.author = author

    def get_time_of_post(self):
        return self.timeOfPost

    def set_time_of_post(self, time_of_post):
        self.timeOfPost = time_of_post

    def get_likes(self):
        return self.like

    def set_likes(self, likes):
        self.like = likes

    def get_image(self):
        return self.image

    def set_image(self, image):
        self.image = image

    def set_images(self, image_paths):
        self.images = ','.join(image_paths) 