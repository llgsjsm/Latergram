from models import db, Post, Comment, User
from typing import Dict, Any
from sqlalchemy import text
from datetime import datetime

class PostManager:
    def __init__(self):
        pass
        
    def create_post(self, title, content, user_id):
        new_post = Post(title=title, content=content, authorId=user_id)
        db.session.add(new_post)
        db.session.commit()
        return new_post

    def delete_post(self, post_id, user_id):
        try:
            post = Post.query.get(post_id)
            if not post:
                return {'success': False, 'error': 'Post not found'}
            
            if post.authorId != user_id:
                return {'success': False, 'error': 'You can only delete your own posts'}
            
            # Delete related comments first (if any)
            Comment.query.filter_by(postId=post_id).delete()
            
            # Delete related likes from junction table
            db.session.execute(
                text("DELETE FROM post_likes WHERE post_id = :post_id"),
                {"post_id": post_id}
            )
            
            # Delete the post
            db.session.delete(post)
            db.session.commit()
            
            return {'success': True, 'message': 'Post deleted successfully'}
            
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting post: {e}")
            return {'success': False, 'error': f'Failed to delete post: {str(e)}'}

    def like_post(self, user_id: int, post_id: int) -> Dict[str, Any]:
        """Like a post using a junction table approach - optimized version"""
        try:
            # Check if post exists and if user already liked it in a single query
            post = Post.query.get(post_id)
            if not post:
                return {'success': False, 'error': 'Post not found'}
            
            # Check if user already liked this post
            existing_like = db.session.execute(
                text("SELECT id FROM post_likes WHERE user_id = :user_id AND post_id = :post_id"),
                {"user_id": user_id, "post_id": post_id}
            ).first()
            
            if existing_like:
                return {'success': False, 'error': 'You have already liked this post', 'already_liked': True}
            
            # Create a new like in the likes table
            result = db.session.execute(
                text("INSERT INTO likes (user_userId, timestamp) VALUES (:user_id, NOW())"),
                {"user_id": user_id}
            )
            
            like_id = result.lastrowid
            
            # Create the junction record
            db.session.execute(
                text("INSERT INTO post_likes (post_id, user_id, like_id) VALUES (:post_id, :user_id, :like_id)"),
                {"post_id": post_id, "user_id": user_id, "like_id": like_id}
            )
            
            # Update post like count
            post.like = (post.like or 0) + 1
            
            db.session.commit()
            
            return {'success': True, 'message': 'Post liked successfully', 'new_count': post.like}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to like post: {str(e)}'}

    def unlike_post(self, user_id: int, post_id: int) -> Dict[str, Any]:
        """Unlike a post using the junction table approach - optimized version"""
        try:
            # Check if post exists
            post = Post.query.get(post_id)
            if not post:
                return {'success': False, 'error': 'Post not found'}
            
            # Check if user has liked this post
            like_record = db.session.execute(
                text("SELECT id, like_id FROM post_likes WHERE user_id = :user_id AND post_id = :post_id"),
                {"user_id": user_id, "post_id": post_id}
            ).first()
            
            if not like_record:
                return {'success': False, 'error': 'You have not liked this post', 'not_liked': True}
            
            # Remove the junction record
            db.session.execute(
                text("DELETE FROM post_likes WHERE user_id = :user_id AND post_id = :post_id"),
                {"user_id": user_id, "post_id": post_id}
            )
            
            # Update post like count
            post.like = max(0, (post.like or 0) - 1)
            
            # Don't touch post.likesId to avoid the NOT NULL constraint issue
            # The junction table is our source of truth for like tracking
            
            db.session.commit()
            
            # Clean up orphaned like records if they exist and are safe to delete
            if like_record.like_id:
                try:
                    # Only delete the like record if no posts reference it
                    posts_using_like = db.session.execute(
                        text("SELECT COUNT(*) FROM post WHERE likesId = :like_id"),
                        {"like_id": like_record.like_id}
                    ).scalar()
                    
                    if posts_using_like == 0:
                        db.session.execute(
                            text("DELETE FROM likes WHERE likesId = :like_id"),
                            {"like_id": like_record.like_id}
                        )
                        db.session.commit()
                except Exception as cleanup_error:
                    # If cleanup fails, that's okay - the main unlike operation succeeded
                    print(f"Cleanup warning: {cleanup_error}")
            
            return {'success': True, 'message': 'Post unliked successfully', 'new_count': post.like}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to unlike post: {str(e)}'}
    
    def is_post_liked_by_user(self, user_id: int, post_id: int) -> bool:
        """Check if a user has liked a specific post using junction table - optimized"""
        try:
            # Query the junction table (table already ensured during initialization)
            like_exists = db.session.execute(
                text("SELECT 1 FROM post_likes WHERE user_id = :user_id AND post_id = :post_id LIMIT 1"),
                {"user_id": user_id, "post_id": post_id}
            ).first()
            
            return like_exists is not None
        except Exception as e:
            print(f"Error checking if post is liked: {e}")
            return False

    def add_comment(self, post_id: int, user_id: int, content: str) -> Dict[str, Any]:
        """Create a new comment on a post"""
        # Verify post exists
        post = Post.query.get(post_id)
        if not post:
            return {'success': False, 'error': 'Post not found'}
        
        # Verify user exists
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        try:
            comment = Comment(postId=post_id, authorId=user_id, commentContent=content)
            db.session.add(comment)
            db.session.commit()
            
            return {
                'success': True,
                'comment_id': comment.commentId,
                'message': 'Comment created successfully'
            }
        except Exception as e:
            return {'success': False, 'error': f'Failed to create comment: {str(e)}'}

    def delete_comment(self, comment_id: int, user_id: int) -> Dict[str, Any]:
        """Delete a comment"""
        comment = Comment.query.get(comment_id)
        if not comment:
            return {'success': False, 'error': 'Comment not found'}
        
        # Check if user owns the comment or owns the post
        post = Post.query.get(comment.postId)
        if comment.authorId != user_id and (not post or post.authorId != user_id):
            return {'success': False, 'error': 'Unauthorized to delete this comment'}
        
        try:
            db.session.delete(comment)
            db.session.commit()
            return {
                'success': True,
                'message': 'Comment deleted successfully'
            }
        except Exception as e:
            return {'success': False, 'error': f'Failed to delete comment: {str(e)}'}

    def get_post_comments(self, post_id: int) -> Dict[str, Any]:
        """Get comments for a specific post"""
        post = Post.query.get(post_id)
        if not post:
            return {'success': False, 'error': 'Post not found'}
        
        comments = Comment.query.filter_by(postId=post_id).all()
        
        return {
            'success': True,
            'comments': [c.to_dict() for c in comments]
        }

    def share_post(self, post_id):
        # Share logic to be implemented
        pass

    def follow_user(self, follower_user_id, followed_user_id):
        if follower_user_id == followed_user_id:
            return {'success': False, 'error': 'Cannot follow yourself'}
        # Prevent double-follow
        sql = text("SELECT COUNT(*) FROM followers WHERE followerUserId = :follower AND followedUserId = :followed")
        result = db.session.execute(sql, {"follower": follower_user_id, "followed": followed_user_id}).scalar()
        if result > 0:
            return {'success': False, 'error': 'Already following this user'}
        # Insert follow
        db.session.execute(
            text("INSERT INTO followers (followerUserId, followedUserId, createdAt) VALUES (:follower, :followed, NOW())"),
            {"follower": follower_user_id, "followed": followed_user_id}
        )
        db.session.commit()
        return {'success': True}

    def get_user_liked_posts(self, user_id: int) -> set:
        """Get all post IDs that a user has liked using junction table - optimized"""
        try:
            # Query the junction table for all posts liked by this user (table already ensured)
            liked_posts = db.session.execute(
                text("SELECT post_id FROM post_likes WHERE user_id = :user_id"),
                {"user_id": user_id}
            ).fetchall()
            
            liked_post_ids = {row.post_id for row in liked_posts}
            return liked_post_ids
        except Exception as e:
            print(f"Error getting user liked posts: {e}")
            return set()

    def get_posts_with_likes_batch(self, post_ids: list, user_id: int) -> Dict[int, bool]:
        """Batch check which posts are liked by user - more efficient than individual checks"""
        if not post_ids:
            return {}
            
        try:
            # Convert list to comma-separated string for SQL IN clause
            post_ids_str = ','.join(map(str, post_ids))
            
            liked_posts = db.session.execute(
                text(f"SELECT post_id FROM post_likes WHERE user_id = :user_id AND post_id IN ({post_ids_str})"),
                {"user_id": user_id}
            ).fetchall()
            
            liked_set = {row.post_id for row in liked_posts}
            return {post_id: post_id in liked_set for post_id in post_ids}
        except Exception as e:
            print(f"Error getting posts likes batch: {e}")
            return {post_id: False for post_id in post_ids}