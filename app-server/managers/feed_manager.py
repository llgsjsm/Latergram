from models import Post, User

class FeedManager:
    def __init__(self):
        self.default_page_size = 20  # Load only 20 posts at a time
    
    def generate_feed(self, user_id, page=1, per_page=None):
        """Generate feed with pagination for better performance"""
        if per_page is None:
            per_page = self.default_page_size
            
        # Optimize: Use pagination and join with User to avoid N+1 queries
        # Calculate offset for manual pagination
        offset = (page - 1) * per_page
        
        posts = (Post.query
                .join(User, Post.authorId == User.userId)
                .order_by(Post.timeOfPost.desc())
                .offset(offset)
                .limit(per_page)
                .all())
        
        return posts

    def refresh_feed(self, user_id=None, page=1):
        """Refresh feed with pagination"""
        return self.generate_feed(user_id, page)

    def load_more_posts(self, user_id, page):
        """Load more posts for infinite scroll"""
        return self.generate_feed(user_id, page)

    def filter_by_following(self, user_id, page=1):
        """Filter feed to show only posts from followed users"""
        # This would filter the feed to show only posts from followed users.
        # For now, return all posts but this can be enhanced later
        return self.generate_feed(user_id, page) 