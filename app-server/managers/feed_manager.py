from models import Post

class FeedManager:
    def generate_feed(self, user_id):
        # For now, return all posts. Later this can be personalized.
        return Post.query.order_by(Post.timeOfPost.desc()).all()

    def refresh_feed(self):
        # In a real application, this might involve checking for new posts
        # since the last fetch.
        return self.generate_feed(None)

    def load_more_posts(self):
        # This would implement pagination.
        pass

    def filter_by_following(self):
        # This would filter the feed to show only posts from followed users.
        pass 