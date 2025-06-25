from models import Post, User, db
from models.enums import VisibilityType
from sqlalchemy import text
from typing import Dict

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
        
        try:
            # Query posts with user info and filter based on visibility - optimized with indexes
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
            
        except Exception as e:
            print(f"Error with optimized query, falling back to simple query: {e}")
            # Fallback to simpler query without complex visibility logic
            try:
                fallback_query = text("""
                    SELECT p.postId, p.authorId, p.title, p.timeOfPost, p.like, p.likesId, p.image, p.content,
                           u.username, u.profilePicture, u.visibility
                    FROM post p
                    JOIN user u ON p.authorId = u.userId
                    WHERE u.visibility = 'Public' OR p.authorId = :current_user_id
                    ORDER BY p.timeOfPost DESC
                    LIMIT :limit OFFSET :offset
                """)
                
                result = db.session.execute(fallback_query, {
                    "current_user_id": user_id,
                    "limit": per_page,
                    "offset": offset
                }).fetchall()
            except Exception as fallback_error:
                print(f"Fallback query also failed: {fallback_error}")
                return []
        
        # Convert results to Post objects efficiently using bulk query
        if not result:
            return []
        
        post_ids = [row[0] for row in result]
        posts = Post.query.filter(Post.postId.in_(post_ids)).order_by(Post.timeOfPost.desc()).all()
        
        # Prefetch user profiles for better performance
        try:
            from managers import get_profile_manager
            profile_manager = get_profile_manager()
            author_ids = list(set([post.authorId for post in posts]))
            profile_manager.prefetch_user_profiles(author_ids)
        except Exception as e:
            print(f"Error prefetching profiles: {e}")
            # Continue without prefetching if it fails
        
        # Maintain the original order from the query
        post_dict = {post.postId: post for post in posts}
        ordered_posts = [post_dict[post_id] for post_id in post_ids if post_id in post_dict]
        
        return ordered_posts

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
        
        try:
            # Query posts only from users that the current user follows, respecting visibility - optimized
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
            
        except Exception as e:
            print(f"Error with following query, falling back to simple query: {e}")
            # Fallback to simpler query
            try:
                fallback_query = text("""
                    SELECT p.postId, p.authorId, p.title, p.timeOfPost, p.like, p.likesId, p.image, p.content,
                           u.username, u.profilePicture, u.visibility
                    FROM post p
                    JOIN user u ON p.authorId = u.userId
                    JOIN followers f ON f.followedUserId = p.authorId
                    WHERE f.followerUserId = :current_user_id
                    ORDER BY p.timeOfPost DESC
                    LIMIT :limit OFFSET :offset
                """)
                
                result = db.session.execute(fallback_query, {
                    "current_user_id": user_id,
                    "limit": per_page,
                    "offset": offset
                }).fetchall()
            except Exception as fallback_error:
                print(f"Fallback following query also failed: {fallback_error}")
                return []
        
        # Convert results to Post objects efficiently using bulk query
        if not result:
            return []
        
        post_ids = [row[0] for row in result]
        posts = Post.query.filter(Post.postId.in_(post_ids)).order_by(Post.timeOfPost.desc()).all()
        
        # Prefetch user profiles for better performance
        try:
            from managers import get_profile_manager
            profile_manager = get_profile_manager()
            author_ids = list(set([post.authorId for post in posts]))
            profile_manager.prefetch_user_profiles(author_ids)
        except Exception as e:
            print(f"Error prefetching profiles: {e}")
            # Continue without prefetching if it fails
        
        # Maintain the original order from the query  
        post_dict = {post.postId: post for post in posts}
        ordered_posts = [post_dict[post_id] for post_id in post_ids if post_id in post_dict]
        
        return ordered_posts
    
    def get_comment_counts_batch(self, post_ids: list) -> Dict[int, int]:
        """Get comment counts for multiple posts in a single query"""
        if not post_ids:
            return {}
        
        try:
            # Convert list to comma-separated string for SQL IN clause
            post_ids_str = ','.join(map(str, post_ids))
            
            comment_counts = db.session.execute(
                text(f"SELECT postId, COUNT(*) as count FROM comment WHERE postId IN ({post_ids_str}) GROUP BY postId")
            ).fetchall()
            
            counts = {row.postId: row.count for row in comment_counts}
            # Ensure all posts have a count (0 if no comments)
            return {post_id: counts.get(post_id, 0) for post_id in post_ids}
        except Exception as e:
            print(f"Error getting comment counts: {e}")
            return {post_id: 0 for post_id in post_ids}