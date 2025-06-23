from models import db, Post, Comment, User
from typing import Dict, Any
from sqlalchemy import text

class PostManager:
    def create_post(self, title, content, user_id):
        new_post = Post(title=title, content=content, authorId=user_id)
        db.session.add(new_post)
        db.session.commit()
        return new_post

    def delete_post(self, post_id, user_id):
        post = Post.query.get(post_id)
        if post and post.authorId == user_id:
            db.session.delete(post)
            db.session.commit()
            return True
        return False

    def like_post(self, post_id, user_id):
        # Prevent double-like - since we don't have postId in likes table,
        # we'll check if user already has any likes record (simplified approach)
        sql = text("SELECT COUNT(*) FROM likes WHERE user_userId = :user_id")
        result = db.session.execute(sql, {"user_id": user_id}).scalar()
        if result > 0:
            return {'success': False, 'error': 'User already has likes recorded'}
        # Insert like - only user and timestamp since no postId column
        db.session.execute(
            text("INSERT INTO likes (user_userId, timestamp) VALUES (:user_id, NOW())"),
            {"user_id": user_id}
        )
        # Optionally increment like count on Post
        post = Post.query.get(post_id)
        if post:
            post.like = (post.like or 0) + 1
            db.session.commit()
        return {'success': True}

    def unlike_post(self, post_id):
        post = Post.query.get(post_id)
        if post and post.likes > 0:
            post.likes -= 1
            db.session.commit()

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
        # Optionally increment followers count on User
        user = User.query.get(followed_user_id)
        if user:
            user.followers = (user.followers or 0) + 1
            db.session.commit()
        return {'success': True} 