from typing import Optional, List, Dict, Any
from models import db, User
from sqlalchemy import text

class ProfileManager:
    def __init__(self, current_user: User = None):
        self.current_user = current_user
        # Simple in-memory cache for frequently accessed data
        self._user_stats_cache = {}
        self._cache_timeout = 300  # 5 minutes cache timeout

    def _clear_user_cache(self, user_id: int):
        """Clear cache for a specific user"""
        if user_id in self._user_stats_cache:
            del self._user_stats_cache[user_id]

    def get_user_stats_cached(self, user_id: int) -> Dict[str, int]:
        """Get user stats with caching for better performance"""
        import time
        
        # Check cache first
        if user_id in self._user_stats_cache:
            cached_data, timestamp = self._user_stats_cache[user_id]
            if time.time() - timestamp < self._cache_timeout:
                return cached_data
        
        # If not in cache or expired, fetch from database
        stats = self.get_user_stats(user_id)
        
        # Cache the result
        self._user_stats_cache[user_id] = (stats, time.time())
        return stats

    def update_profile(self, user_id: int, display_name: str = None, 
                      bio: str = None, profile_picture_url: str = None, 
                      visibility: str = None) -> Dict[str, Any]:
        """Update user profile information"""
        user = User.query.filter_by(userId=user_id).first()
        
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Update provided fields (note: display_name maps to username in current schema)
        if display_name is not None:
            user.username = display_name
        if bio is not None:
            user.bio = bio
        if profile_picture_url is not None:
            user.profilePicture = profile_picture_url
        if visibility is not None:
            user.visibility = visibility
        
        try:
            db.session.commit()
            return {
                'success': True,
                'message': 'Profile updated successfully',
                'profile': {
                    'user_id': user.userId,
                    'username': user.username,
                    'bio': user.bio,
                    'profile_picture': user.profilePicture,
                    'visibility': user.visibility
                }
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to update profile: {str(e)}'}

    def change_visibility(self, user_id: int, visibility_type: str) -> Dict[str, Any]:
        """Change visibility of a user"""
        return self.update_profile(user_id, visibility=visibility_type)

    def follow_user(self, follower_user_id: int, followed_user_id: int) -> Dict[str, Any]:
        """Follow another user - optimized with cache clearing"""
        if follower_user_id == followed_user_id:
            return {'success': False, 'error': 'Cannot follow yourself'}
        
        # Single query to check if both users exist and if already following
        result = db.session.execute(text("""
            SELECT 
                (SELECT COUNT(*) FROM user WHERE userId = :follower_id) as follower_exists,
                (SELECT COUNT(*) FROM user WHERE userId = :followed_id) as followed_exists,
                (SELECT COUNT(*) FROM followers WHERE followerUserId = :follower_id AND followedUserId = :followed_id) as already_following
        """), {"follower_id": follower_user_id, "followed_id": followed_user_id}).fetchone()
        
        if not result.follower_exists or not result.followed_exists:
            return {'success': False, 'error': 'One or both users not found'}
        
        if result.already_following > 0:
            return {'success': False, 'error': 'Already following this user'}
        
        try:
            # Insert follow relationship
            query = text("INSERT INTO followers (followerUserId, followedUserId, createdAt) VALUES (:follower_id, :followed_id, NOW())")
            db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id})
            db.session.commit()
            
            # Clear cache for both users
            self._clear_user_cache(follower_user_id)
            self._clear_user_cache(followed_user_id)
            
            return {
                'success': True,
                'message': 'Successfully followed user'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to follow user: {str(e)}'}
    
    def unfollow_user(self, follower_user_id: int, followed_user_id: int) -> Dict[str, Any]:
        """Unfollow a user - optimized with cache clearing"""
        if not self.is_following(follower_user_id, followed_user_id):
            return {'success': False, 'error': 'Not following this user'}
        
        try:
            query = text("DELETE FROM followers WHERE followerUserId = :follower_id AND followedUserId = :followed_id")
            db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id})
            db.session.commit()
            
            # Clear cache for both users
            self._clear_user_cache(follower_user_id)
            self._clear_user_cache(followed_user_id)
            
            return {
                'success': True,
                'message': 'Successfully unfollowed user'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to unfollow user: {str(e)}'}
    
    def is_following(self, follower_user_id: int, followed_user_id: int) -> bool:
        """Check if one user follows another - optimized query"""
        try:
            query = text("SELECT 1 FROM followers WHERE followerUserId = :follower_id AND followedUserId = :followed_id LIMIT 1")
            result = db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id}).first()
            return result is not None
        except Exception:
            return False
    
    def get_followers(self, user_id: int, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get list of followers for a user"""
        offset = (page - 1) * per_page
        
        try:
            # Get follower user IDs
            query = text("""
                SELECT followerUserId, createdAt FROM followers 
                WHERE followedUserId = :user_id 
                ORDER BY createdAt DESC 
                LIMIT :limit OFFSET :offset
            """)
            results = db.session.execute(query, {"user_id": user_id, "limit": per_page, "offset": offset}).fetchall()
            
            # Get user details for each follower
            follower_users = []
            for result in results:
                user = User.query.filter_by(userId=result[0]).first()
                if user:
                    follower_users.append({
                        'user': {
                            'user_id': user.userId,
                            'username': user.username,
                            'email': user.email,
                            'created_at': user.createdAt,
                            'profile_picture': user.profilePicture,
                            'bio': user.bio,
                            'visibility': user.visibility
                        },
                        'followed_at': result[1]
                    })
            
            return {
                'success': True,
                'followers': follower_users,
                'total_count': self.get_follower_count(user_id)
            }
        except Exception as e:
            return {'success': False, 'error': f'Failed to get followers: {str(e)}'}
    
    def get_following(self, user_id: int, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get list of users that this user follows"""
        offset = (page - 1) * per_page
        
        try:
            # Get followed user IDs
            query = text("""
                SELECT followedUserId, createdAt FROM followers 
                WHERE followerUserId = :user_id 
                ORDER BY createdAt DESC 
                LIMIT :limit OFFSET :offset
            """)
            results = db.session.execute(query, {"user_id": user_id, "limit": per_page, "offset": offset}).fetchall()
            
            # Get user details for each followed user
            following_users = []
            for result in results:
                user = User.query.filter_by(userId=result[0]).first()
                if user:
                    following_users.append({
                        'user': {
                            'user_id': user.userId,
                            'username': user.username,
                            'email': user.email,
                            'created_at': user.createdAt,
                            'profile_picture': user.profilePicture,
                            'bio': user.bio,
                            'visibility': user.visibility
                        },
                        'followed_at': result[1]
                    })
            
            return {
                'success': True,
                'following': following_users,
                'total_count': self.get_following_count(user_id)
            }
        except Exception as e:
            return {'success': False, 'error': f'Failed to get following: {str(e)}'}
    
    def get_follower_count(self, user_id: int) -> int:
        """Get total number of followers for a user"""
        try:
            query = text("SELECT COUNT(*) as count FROM followers WHERE followedUserId = :user_id")
            result = db.session.execute(query, {"user_id": user_id}).fetchone()
            return result[0] if result else 0
        except Exception:
            return 0
    
    def get_following_count(self, user_id: int) -> int:
        """Get total number of users that this user follows"""
        try:
            query = text("SELECT COUNT(*) as count FROM followers WHERE followerUserId = :user_id")
            result = db.session.execute(query, {"user_id": user_id}).fetchone()
            return result[0] if result else 0
        except Exception:
            return 0
    
    def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Get complete user profile information"""
        user = User.query.filter_by(userId=user_id).first()
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        follower_count = self.get_follower_count(user_id)
        following_count = self.get_following_count(user_id)
        
        return {
            'success': True,
            'user': {
                'user_id': user.userId,
                'username': user.username,
                'email': user.email,
                'created_at': user.createdAt,
                'profile_picture': user.profilePicture,
                'bio': user.bio,
                'visibility': user.visibility
            },
            'follower_count': follower_count,
            'following_count': following_count
        }
    
    def search_users(self, query: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Search for users by username"""
        offset = (page - 1) * per_page
        
        search_term = f'%{query}%'
        users_query = User.query.filter(User.username.like(search_term)).offset(offset).limit(per_page)
        users = users_query.all()
        
        user_results = []
        for user in users:
            user_results.append({
                'user': {
                    'user_id': user.userId,
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.createdAt,
                    'profile_picture': user.profilePicture,
                    'bio': user.bio,
                    'visibility': user.visibility
                }
            })
        
        return {
            'success': True,
            'users': user_results,
            'query': query
        }

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """Get user statistics with optimized single query"""
        try:
            # Single query to get all stats at once
            result = db.session.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM post WHERE authorId = :user_id) as posts_count,
                    (SELECT COUNT(*) FROM followers WHERE followedUserId = :user_id) as followers_count,
                    (SELECT COUNT(*) FROM followers WHERE followerUserId = :user_id) as following_count
            """), {"user_id": user_id}).fetchone()
            
            if result:
                return {
                    'posts_count': result.posts_count or 0,
                    'followers_count': result.followers_count or 0,
                    'following_count': result.following_count or 0
                }
            return {'posts_count': 0, 'followers_count': 0, 'following_count': 0}
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {'posts_count': 0, 'followers_count': 0, 'following_count': 0}

    def get_suggested_users(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Get suggested users to follow with optimized query"""
        try:
            # Get users not being followed, excluding self, with efficient query
            result = db.session.execute(text("""
                SELECT u.userId, u.username, u.profilePicture, u.bio
                FROM user u
                WHERE u.userId != :user_id 
                AND u.userId NOT IN (
                    SELECT followedUserId FROM followers WHERE followerUserId = :user_id
                )
                AND u.visibility = 'public'
                ORDER BY u.followers DESC, u.createdAt DESC
                LIMIT :limit
            """), {"user_id": user_id, "limit": limit}).fetchall()
            
            suggestions = []
            for row in result:
                # Create a dict that matches the template expectations
                suggestions.append({
                    'userId': row.userId,  # Changed from user_id to userId for template compatibility
                    'username': row.username,
                    'profilePicture': row.profilePicture or '',
                    'bio': row.bio or ''
                })
            
            return suggestions
        except Exception as e:
            print(f"Error getting suggested users: {e}")
            return []
    
    def get_user_posts(self, user_id: int, viewer_user_id: int = None, page: int = 1, per_page: int = 20) -> List:
        """Get posts by a specific user with pagination and visibility filtering"""
        try:
            from models import Post
            
            # If no viewer specified, assume they're viewing their own profile
            if viewer_user_id is None:
                viewer_user_id = user_id
            
            # Check if viewer can see the user's posts
            if not self._can_view_user_posts(viewer_user_id, user_id):
                return []
            
            offset = (page - 1) * per_page
            
            # Get user's posts with pagination, ordered by most recent first
            posts = (Post.query
                    .filter_by(authorId=user_id)
                    .order_by(Post.timeOfPost.desc())
                    .offset(offset)
                    .limit(per_page)
                    .all())
            
            return posts
        except Exception as e:
            print(f"Error getting user posts: {e}")
            return []
    
    def _can_view_user_posts(self, viewer_user_id: int, profile_user_id: int) -> bool:
        """Check if a user can view another user's posts based on visibility settings"""
        # If viewing own posts, always allow
        if viewer_user_id == profile_user_id:
            return True
        
        # Get the profile user's visibility setting
        profile_user = User.query.filter_by(userId=profile_user_id).first()
        if not profile_user:
            return False
        
        # If profile is public, allow viewing
        if profile_user.visibility == 'Public':
            return True
        
        # If profile is private, deny viewing
        if profile_user.visibility == 'Private':
            return False
        
        # If profile is followers only, check if viewer follows the profile user
        if profile_user.visibility == 'FollowersOnly':
            return self.is_following(viewer_user_id, profile_user_id)
        
        # Default to deny if visibility setting is unknown
        return False

    def get_user_posts_count(self, user_id: int) -> int:
        """Get total count of user's posts"""
        try:
            from models import Post
            return Post.query.filter_by(authorId=user_id).count()
        except Exception as e:
            print(f"Error getting user posts count: {e}")
            return 0
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> Dict[str, Any]:
        """Change user password with validation"""
        try:
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt()
            
            # Get the user
            user = User.query.filter_by(userId=user_id).first()
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Verify current password
            if not bcrypt.check_password_hash(user.password, current_password):
                return {'success': False, 'error': 'Current password is incorrect'}
            
            # Validate new password (similar to registration)
            if len(new_password) < 6:
                return {'success': False, 'error': 'New password must be at least 6 characters long'}
            elif len(new_password) > 255:
                return {'success': False, 'error': 'New password must be less than 255 characters'}
            
            # Hash the new password
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            
            # Update the password
            user.password = hashed_password
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Password changed successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to change password: {str(e)}'}

    def delete_account(self, user_id: int, password: str) -> Dict[str, Any]:
        """Delete user account with password confirmation"""
        try:
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt()
            
            # Get the user
            user = User.query.filter_by(userId=user_id).first()
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Verify password before deletion
            if not bcrypt.check_password_hash(user.password, password):
                return {'success': False, 'error': 'Password is incorrect'}
            
            # Use a simpler approach: delete in order that respects foreign key constraints
            
            # 1. Delete user's post likes from junction table
            db.session.execute(text("DELETE FROM post_likes WHERE user_id = :user_id"), {"user_id": user_id})
            
            # 2. Delete user's comments
            db.session.execute(text("DELETE FROM comment WHERE authorId = :user_id"), {"user_id": user_id})
            
            # 3. Delete reports made by this user (using correct column name)
            db.session.execute(text("DELETE FROM report WHERE reportedBy = :user_id"), {"user_id": user_id})
            
            # 4. Delete follower relationships (both following and followers)
            db.session.execute(text("DELETE FROM followers WHERE followerUserId = :user_id OR followedUserId = :user_id"), {"user_id": user_id})
            
            # 5. Handle posts and likes carefully to avoid foreign key constraints
            # The challenge: other users' posts might reference likes created by this user
            
            # First, get all likes created by this user that are referenced by OTHER users' posts
            referenced_likes = db.session.execute(text("""
                SELECT DISTINCT l.likesId 
                FROM likes l 
                INNER JOIN post p ON p.likesId = l.likesId 
                WHERE l.user_userId = :user_id 
                AND p.authorId != :user_id
            """), {"user_id": user_id}).fetchall()
            
            # Create a placeholder/system like to replace references if needed
            placeholder_like_id = None
            if referenced_likes:
                # Create a system like (using user ID 1 as system user, or any existing user)
                # First, check if there's at least one other user to use as placeholder
                system_user = db.session.execute(text("SELECT userId FROM user WHERE userId != :user_id LIMIT 1"), {"user_id": user_id}).first()
                
                if system_user:
                    placeholder_result = db.session.execute(
                        text("INSERT INTO likes (user_userId, timestamp) VALUES (:system_user_id, NOW())"),
                        {"system_user_id": system_user.userId}
                    )
                    placeholder_like_id = placeholder_result.lastrowid
                
                    # Update other users' posts to use the placeholder like
                    for like_row in referenced_likes:
                        db.session.execute(text("""
                            UPDATE post SET likesId = :placeholder_id 
                            WHERE likesId = :old_like_id AND authorId != :user_id
                        """), {
                            "placeholder_id": placeholder_like_id,
                            "old_like_id": like_row.likesId,
                            "user_id": user_id
                        })
            
            # Now get all posts by this user and their associated like IDs
            user_posts = db.session.execute(text("""
                SELECT postId, likesId FROM post WHERE authorId = :user_id
            """), {"user_id": user_id}).fetchall()
            
            # Delete the user's posts (this removes the foreign key references from user's own posts)
            db.session.execute(text("DELETE FROM post WHERE authorId = :user_id"), {"user_id": user_id})
            
            # Now delete the likes that were associated with the user's posts
            for post in user_posts:
                if post.likesId:
                    try:
                        db.session.execute(text("DELETE FROM likes WHERE likesId = :like_id"), {"like_id": post.likesId})
                    except Exception as e:
                        # If we can't delete a like (maybe it's still referenced), that's okay
                        print(f"Could not delete like {post.likesId}: {e}")
            
            # Finally, delete any remaining likes created by this user
            # These should now be safe to delete since we've handled the references
            db.session.execute(text("DELETE FROM likes WHERE user_userId = :user_id"), {"user_id": user_id})
            
            # 6. Finally, delete the user account
            db.session.delete(user)
            db.session.commit()
            
            # Clear any cached data for this user
            self._clear_user_cache(user_id)
            
            return {
                'success': True,
                'message': 'Account deleted successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to delete account: {str(e)}'}
    
    def can_view_profile(self, viewer_user_id: int, profile_user_id: int) -> Dict[str, Any]:
        """Check if a user can view another user's profile based on visibility settings"""
        # If viewing own profile, always allow
        if viewer_user_id == profile_user_id:
            return {'can_view': True, 'can_see_posts': True}
        
        # Get the profile user's visibility setting
        profile_user = User.query.filter_by(userId=profile_user_id).first()
        if not profile_user:
            return {'can_view': False, 'can_see_posts': False, 'error': 'User not found'}
        
        # If profile is public, allow viewing everything
        if profile_user.visibility == 'Public':
            return {'can_view': True, 'can_see_posts': True}
        
        # If profile is private, can view basic info but not posts
        if profile_user.visibility == 'Private':
            return {'can_view': True, 'can_see_posts': False, 'message': 'This account is private'}
        
        # If profile is followers only, check if viewer follows the profile user
        if profile_user.visibility == 'FollowersOnly':
            is_following = self.is_following(viewer_user_id, profile_user_id)
            if is_following:
                return {'can_view': True, 'can_see_posts': True}
            else:
                return {'can_view': True, 'can_see_posts': False, 'message': 'Follow this user to see their posts'}
        
        # Default to basic view only
        return {'can_view': True, 'can_see_posts': False}