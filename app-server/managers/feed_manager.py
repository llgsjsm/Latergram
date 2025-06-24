from models import Post, User, db
from models.enums import VisibilityType
from sqlalchemy import text

class FeedManager:
    def __init__(self):
        self.default_page_size = 20  # Load only 20 posts at a time
    
    def _can_view_user_posts(self, viewer_user_id, post_author_id):
        """Check if a user can view posts from another user based on visibility settings"""
        # If viewing own posts, always allow
        if viewer_user_id == post_author_id:
            return True
        
        # Get the post author's visibility setting
        author = User.query.filter_by(userId=post_author_id).first()
        if not author:
            return False
        
        # If author's profile is public, allow viewing
        if author.visibility == VisibilityType.PUBLIC.value:
            return True
        
        # If author's profile is private, deny viewing
        if author.visibility == VisibilityType.PRIVATE.value:
            return False
        
        # If author's profile is followers only, check if viewer follows the author
        if author.visibility == VisibilityType.FOLLOWERS_ONLY.value:
            # Check if viewer follows the author
            follow_check = text("""
                SELECT 1 FROM followers 
                WHERE followerUserId = :viewer_id AND followedUserId = :author_id 
                LIMIT 1
            """)
            result = db.session.execute(follow_check, {
                "viewer_id": viewer_user_id, 
                "author_id": post_author_id
            }).first()
            return result is not None
        
        # Default to deny if visibility setting is unknown
        return False
    
    def generate_feed(self, user_id, page=1, per_page=None):
        """Generate feed with pagination and visibility filtering for better performance"""
        if per_page is None:
            per_page = self.default_page_size
            
        # Calculate offset for manual pagination
        offset = (page - 1) * per_page
        
        # Query posts with user info and filter based on visibility
        posts_query = text("""
            SELECT p.postId, p.authorId, p.title, p.timeOfPost, p.like, p.likesId, p.image, p.content,
                   u.username, u.profilePicture, u.visibility
            FROM post p
            JOIN user u ON p.authorId = u.userId
            WHERE 
                u.visibility = 'Public'
                OR p.authorId = :current_user_id
                OR (u.visibility = 'FollowersOnly' AND EXISTS (
                    SELECT 1 FROM followers f 
                    WHERE f.followerUserId = :current_user_id 
                    AND f.followedUserId = p.authorId
                ))
            ORDER BY p.timeOfPost DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.session.execute(posts_query, {
            "current_user_id": user_id,
            "limit": per_page,
            "offset": offset
        }).fetchall()
        
        # Convert results to Post objects
        posts = []
        for row in result:
            post = Post.query.filter_by(postId=row[0]).first()
            if post:
                posts.append(post)
        
        return posts

    def refresh_feed(self, user_id=None, page=1):
        """Refresh feed with pagination"""
        return self.generate_feed(user_id, page)

    def load_more_posts(self, user_id, page):
        """Load more posts for infinite scroll"""
        return self.generate_feed(user_id, page)

    def filter_by_following(self, user_id, page=1):
        """Filter feed to show only posts from followed users with visibility filtering"""
        per_page = self.default_page_size
        offset = (page - 1) * per_page
        
        # Query posts only from users that the current user follows, respecting visibility
        posts_query = text("""
            SELECT p.postId, p.authorId, p.title, p.timeOfPost, p.like, p.likesId, p.image, p.content,
                   u.username, u.profilePicture, u.visibility
            FROM post p
            JOIN user u ON p.authorId = u.userId
            JOIN followers f ON f.followedUserId = p.authorId
            WHERE f.followerUserId = :current_user_id
                AND (
                    u.visibility = 'Public'
                    OR u.visibility = 'FollowersOnly'
                    OR p.authorId = :current_user_id
                )
            ORDER BY p.timeOfPost DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.session.execute(posts_query, {
            "current_user_id": user_id,
            "limit": per_page,
            "offset": offset
        }).fetchall()
        
        # Convert results to Post objects
        posts = []
        for row in result:
            post = Post.query.filter_by(postId=row[0]).first()
            if post:
                posts.append(post)
        
        return posts 