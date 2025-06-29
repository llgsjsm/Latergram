from typing import Optional, List, Dict, Any
from models import db, User
from models.enums import VisibilityType, LogActionTypes, ReportTarget
from sqlalchemy import text

class ProfileManager:
    def __init__(self, current_user: User = None):
        self.current_user = current_user
        # Simple in-memory cache for frequently accessed data
        self._user_stats_cache = {}
        self._suggested_users_cache = {}
        self._user_profile_cache = {}
        self._cache_timeout = 300  # 5 minutes cache timeout

    def log_action(self, user_id: int, action: str, target_id: int):
        """
        Logs an action to the application_log table.
        """
        sql = """
        INSERT INTO application_log 
        (user_id, action, target_id, target_type, timestamp)
        VALUES (:user_id, :action, :target_id, :target_type, NOW())
        """

        db.session.execute(text(sql), {
            "user_id": user_id,
            "action": action,
            "target_id": target_id,
            "target_type": ReportTarget.USER.value,
        })

    def _clear_user_cache(self, user_id: int):
        """Clear cache for a specific user"""
        if user_id in self._user_stats_cache:
            del self._user_stats_cache[user_id]
        if user_id in self._suggested_users_cache:
            del self._suggested_users_cache[user_id]
        if user_id in self._user_profile_cache:
            del self._user_profile_cache[user_id]
        if user_id in self._user_profile_cache:
            del self._user_profile_cache[user_id]

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
            # Create a new log entry
            self.log_action(user_id, LogActionTypes.UPDATE_PROFILE.value, user_id)
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

    def send_follow_request(self, requester_user_id: int, target_user_id: int) -> Dict[str, Any]:
        """Send a follow request to another user"""
        if requester_user_id == target_user_id:
            return {'success': False, 'error': 'Cannot send request to yourself'}
        
        # Check if both users exist and get target user's visibility
        result = db.session.execute(text("""
            SELECT 
                (SELECT COUNT(*) FROM user WHERE userId = :requester_id) as requester_exists,
                (SELECT COUNT(*) FROM user WHERE userId = :target_id) as target_exists,
                (SELECT visibility FROM user WHERE userId = :target_id) as target_visibility,
                (SELECT COUNT(*) FROM followers WHERE followerUserId = :requester_id AND followedUserId = :target_id) as existing_relationship
        """), {"requester_id": requester_user_id, "target_id": target_user_id}).fetchone()
        
        if not result.requester_exists or not result.target_exists:
            return {'success': False, 'error': 'One or both users not found'}
        
        if result.existing_relationship > 0:
            return {'success': False, 'error': 'Relationship already exists'}
        
        try:
            # If target user is public, auto-accept the follow
            # Handle both 'Public' and 'public' for backward compatibility
            if result.target_visibility and result.target_visibility.lower() == 'public':
                query = text("""
                    INSERT INTO followers (followerUserId, followedUserId, createdAt, status) 
                    VALUES (:requester_id, :target_id, NOW(), 'accepted')
                """)
                db.session.execute(query, {"requester_id": requester_user_id, "target_id": target_user_id})
                # Create a new log entry
                self.log_action(requester_user_id, LogActionTypes.FOLLOW_USER.value, target_user_id)
                message = 'Now following user'
            else:
                # For private or followers-only accounts, send pending request
                query = text("""
                    INSERT INTO followers (followerUserId, followedUserId, createdAt, status) 
                    VALUES (:requester_id, :target_id, NOW(), 'pending')
                """)
                db.session.execute(query, {"requester_id": requester_user_id, "target_id": target_user_id})
                # Create a new log entry
                self.log_action(requester_user_id, LogActionTypes.REQUEST_FOLLOW.value, target_user_id)
                message = 'Follow request sent'
            

            db.session.commit()
            
            # Clear cache for both users
            self._clear_user_cache(requester_user_id)
            self._clear_user_cache(target_user_id)
            
            return {
                'success': True,
                'message': message,
                'status': 'accepted' if result.target_visibility and result.target_visibility.lower() == 'public' else 'pending'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to send follow request: {str(e)}'}

    def respond_to_follow_request(self, target_user_id: int, requester_user_id: int, action: str) -> Dict[str, Any]:
        """Accept or decline a follow request"""
        if action not in ['accept', 'decline']:
            return {'success': False, 'error': 'Invalid action. Use "accept" or "decline"'}
        
        try:
            # Check if there's a pending request
            result = db.session.execute(text("""
                SELECT id FROM followers 
                WHERE followerUserId = :requester_id AND followedUserId = :target_id AND status = 'pending'
            """), {"requester_id": requester_user_id, "target_id": target_user_id}).fetchone()
            
            if not result:
                return {'success': False, 'error': 'No pending follow request found'}
            
            if action == 'accept':
                # Update status to accepted
                query = text("""
                    UPDATE followers SET status = 'accepted' 
                    WHERE followerUserId = :requester_id AND followedUserId = :target_id AND status = 'pending'
                """)
                db.session.execute(query, {"requester_id": requester_user_id, "target_id": target_user_id})
                # Create a new log entry
                self.log_action(target_user_id, LogActionTypes.ACCEPT_FOLLOW_REQUEST.value, requester_user_id)
                message = 'Follow request accepted'
            else:
                # Remove the pending request
                query = text("""
                    DELETE FROM followers 
                    WHERE followerUserId = :requester_id AND followedUserId = :target_id AND status = 'pending'
                """)
                # Create a new log entry
                self.log_action(target_user_id, LogActionTypes.REJECT_FOLLOW_REQUEST.value, requester_user_id)
                db.session.execute(query, {"requester_id": requester_user_id, "target_id": target_user_id})
                message = 'Follow request declined'
            
            db.session.commit()
            
            # Clear cache for both users
            self._clear_user_cache(requester_user_id)
            self._clear_user_cache(target_user_id)
            
            return {
                'success': True,
                'message': message,
                'action': action
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to respond to follow request: {str(e)}'}

    def get_pending_follow_requests(self, user_id: int) -> Dict[str, Any]:
        """Get all pending follow requests for a user"""
        try:
            # Get pending requests with requester details
            results = db.session.execute(text("""
                SELECT f.followerUserId, f.createdAt, u.username, u.profilePicture, u.bio
                FROM followers f
                JOIN user u ON f.followerUserId = u.userId
                WHERE f.followedUserId = :user_id AND f.status = 'pending'
                ORDER BY f.createdAt DESC
            """), {"user_id": user_id}).fetchall()
            
            requests = []
            for result in results:
                requests.append({
                    'requester_id': result.followerUserId,
                    'username': result.username,
                    'profile_picture': result.profilePicture or '',
                    'bio': result.bio or '',
                    'requested_at': result.createdAt
                })
            
            return {
                'success': True,
                'requests': requests,
                'count': len(requests)
            }
        except Exception as e:
            return {'success': False, 'error': f'Failed to get follow requests: {str(e)}'}

    def get_follow_status(self, requester_user_id: int, target_user_id: int) -> Dict[str, Any]:
        """Get the follow status between two users"""
        try:
            result = db.session.execute(text("""
                SELECT status FROM followers 
                WHERE followerUserId = :requester_id AND followedUserId = :target_id
            """), {"requester_id": requester_user_id, "target_id": target_user_id}).fetchone()
            
            if result:
                return {
                    'success': True,
                    'status': result.status,
                    'is_following': result.status == 'accepted',
                    'request_pending': result.status == 'pending'
                }
            else:
                return {
                    'success': True,
                    'status': 'none',
                    'is_following': False,
                    'request_pending': False
                }
        except Exception as e:
            return {'success': False, 'error': f'Failed to get follow status: {str(e)}'}

    def follow_user(self, follower_user_id: int, followed_user_id: int) -> Dict[str, Any]:
        """Follow another user - updated to handle friend requests"""
        # Use the new send_follow_request method instead
        return self.send_follow_request(follower_user_id, followed_user_id)
    
    def cancel_follow_request(self, requester_user_id: int, target_user_id: int) -> Dict[str, Any]:
        """Cancel a pending follow request"""
        try:
            # Check if there's a pending request
            result = db.session.execute(text("""
                SELECT id FROM followers 
                WHERE followerUserId = :requester_id AND followedUserId = :target_id AND status = 'pending'
            """), {"requester_id": requester_user_id, "target_id": target_user_id}).fetchone()
            
            if not result:
                return {'success': False, 'error': 'No pending follow request found'}
            
            # Remove the pending request
            query = text("""
                DELETE FROM followers 
                WHERE followerUserId = :requester_id AND followedUserId = :target_id AND status = 'pending'
            """)
            db.session.execute(query, {"requester_id": requester_user_id, "target_id": target_user_id})

            # Create a new log entry
            self.log_action(requester_user_id, LogActionTypes.CANCEL_PENDING_FOLLOW_REQUEST.value, target_user_id)
            db.session.commit()
            
            # Clear cache for both users
            self._clear_user_cache(requester_user_id)
            self._clear_user_cache(target_user_id)
            
            return {
                'success': True,
                'message': 'Follow request cancelled'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to cancel follow request: {str(e)}'}

    def unfollow_user(self, follower_user_id: int, followed_user_id: int) -> Dict[str, Any]:
        """Unfollow a user - updated to handle different statuses"""
        try:
            # Check current relationship status
            result = db.session.execute(text("""
                SELECT status FROM followers 
                WHERE followerUserId = :follower_id AND followedUserId = :followed_id
            """), {"follower_id": follower_user_id, "followed_id": followed_user_id}).fetchone()
            
            if not result:
                return {'success': False, 'error': 'Not following this user'}
            
            # Remove the relationship regardless of status
            query = text("DELETE FROM followers WHERE followerUserId = :follower_id AND followedUserId = :followed_id")
            db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id})

            # Create a new log entry
            self.log_action(follower_user_id, LogActionTypes.UNFOLLOW_USER.value, followed_user_id)
            db.session.commit()
            
            # Clear cache for both users
            self._clear_user_cache(follower_user_id)
            self._clear_user_cache(followed_user_id)
            
            message = 'Successfully unfollowed user' if result.status == 'accepted' else 'Follow request cancelled'
            
            return {
                'success': True,
                'message': message
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to unfollow user: {str(e)}'}
    
    def is_following(self, follower_user_id: int, followed_user_id: int) -> bool:
        """Check if one user follows another - updated to only check accepted follows"""
        try:
            query = text("""
                SELECT 1 FROM followers 
                WHERE followerUserId = :follower_id AND followedUserId = :followed_id AND status = 'accepted' 
                LIMIT 1
            """)
            result = db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id}).first()
            return result is not None
        except Exception:
            return False
    
    def get_followers(self, user_id: int, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get list of followers for a user - only accepted follows"""
        offset = (page - 1) * per_page
        
        try:
            # Get follower user IDs for accepted follows only
            query = text("""
                SELECT followerUserId, createdAt FROM followers 
                WHERE followedUserId = :user_id AND status = 'accepted'
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
        """Get list of users that this user follows - only accepted follows"""
        offset = (page - 1) * per_page
        
        try:
            # Get followed user IDs for accepted follows only
            query = text("""
                SELECT followedUserId, createdAt FROM followers 
                WHERE followerUserId = :user_id AND status = 'accepted'
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
        """Get total number of followers for a user - only accepted follows"""
        try:
            query = text("SELECT COUNT(*) as count FROM followers WHERE followedUserId = :user_id AND status = 'accepted'")
            result = db.session.execute(query, {"user_id": user_id}).fetchone()
            return result[0] if result else 0
        except Exception:
            return 0
    
    def get_following_count(self, user_id: int) -> int:
        """Get total number of users that this user follows - only accepted follows"""
        try:
            query = text("SELECT COUNT(*) as count FROM followers WHERE followerUserId = :user_id AND status = 'accepted'")
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
    
    def get_user_profile_cached(self, user_id: int) -> Dict:
        """Get user profile with caching for better performance"""
        import time
        
        # Check cache first
        if user_id in self._user_profile_cache:
            cached_data, timestamp = self._user_profile_cache[user_id]
            if time.time() - timestamp < self._cache_timeout:
                return cached_data
        
        # If not in cache or expired, fetch from database
        try:
            user = User.query.filter_by(userId=user_id).first()
            if user:
                profile_data = {
                    'userId': user.userId,
                    'username': user.username,
                    'profilePicture': user.profilePicture,
                    'bio': user.bio,
                    'visibility': user.visibility
                }
                # Cache the result
                self._user_profile_cache[user_id] = (profile_data, time.time())
                return profile_data
        except Exception as e:
            print(f"Error getting user profile: {e}")
        
        return None

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
        """Get user statistics with optimized single query - only count accepted follows"""
        try:
            # Single query to get all stats at once, counting only accepted follows
            result = db.session.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM post WHERE authorId = :user_id) as posts_count,
                    (SELECT COUNT(*) FROM followers WHERE followedUserId = :user_id AND status = 'accepted') as followers_count,
                    (SELECT COUNT(*) FROM followers WHERE followerUserId = :user_id AND status = 'accepted') as following_count
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
                ORDER BY u.createdAt DESC
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
    
    def get_suggested_users_cached(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Get suggested users with caching for better performance"""
        import time
        
        # Check cache first
        cache_key = f"{user_id}_{limit}"
        if cache_key in self._suggested_users_cache:
            cached_data, timestamp = self._suggested_users_cache[cache_key]
            if time.time() - timestamp < self._cache_timeout:
                return cached_data
        
        # If not in cache or expired, fetch from database
        suggested_users = self.get_suggested_users(user_id, limit)
        
        # Cache the result
        self._suggested_users_cache[cache_key] = (suggested_users, time.time())
        return suggested_users

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
            # Create a new log entry

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
        return {'can_view': True, 'can_see_posts': False, 'message': 'No posts available'}

    def remove_follower(self, user_id: int, follower_user_id: int) -> dict:
        """Remove a follower from the current user's followers list."""
        try:
            # Check if the follower relationship exists
            result = db.session.execute(text("""
                SELECT status FROM followers 
                WHERE followerUserId = :follower_id AND followedUserId = :user_id
            """), {"follower_id": follower_user_id, "user_id": user_id}).fetchone()

            if not result:
                return {'success': False, 'error': 'This user is not your follower.'}

            # Remove the follower relationship
            db.session.execute(text("""
                DELETE FROM followers WHERE followerUserId = :follower_id AND followedUserId = :user_id
            """), {"follower_id": follower_user_id, "user_id": user_id})
            # Create a new log entry
            self.log_action(user_id, LogActionTypes.REMOVE_FOLLOWER.value, follower_user_id)
            db.session.commit()

            # Clear cache for both users
            self._clear_user_cache(user_id)
            self._clear_user_cache(follower_user_id)

            return {'success': True, 'message': 'Follower removed successfully.'}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to remove follower: {str(e)}'}
    
    def prefetch_user_profiles(self, user_ids: List[int]) -> Dict[int, Dict]:
        """Prefetch multiple user profiles in a single query to warm the cache"""
        if not user_ids:
            return {}
        
        try:
            # Remove duplicates and get uncached users
            import time
            uncached_ids = []
            cached_profiles = {}
            
            for user_id in set(user_ids):
                if user_id in self._user_profile_cache:
                    cached_data, timestamp = self._user_profile_cache[user_id]
                    if time.time() - timestamp < self._cache_timeout:
                        cached_profiles[user_id] = cached_data
                        continue
                uncached_ids.append(user_id)
            
            # Fetch uncached profiles in batch
            if uncached_ids:
                users = User.query.filter(User.userId.in_(uncached_ids)).all()
                for user in users:
                    profile_data = {
                        'userId': user.userId,
                        'username': user.username,
                        'profilePicture': user.profilePicture,
                        'bio': user.bio,
                        'visibility': user.visibility
                    }
                    # Cache the result
                    self._user_profile_cache[user.userId] = (profile_data, time.time())
                    cached_profiles[user.userId] = profile_data
            
            return cached_profiles
        except Exception as e:
            print(f"Error prefetching user profiles: {e}")
            return {}
    
    def fix_visibility_case(self) -> Dict[str, Any]:
        """Fix visibility case for existing users - utility method for migration"""
        try:
            # Update all users with lowercase 'public' to uppercase 'Public'
            query = text("""
                UPDATE user SET visibility = 'Public' WHERE LOWER(visibility) = 'public'
            """)
            result = db.session.execute(query)
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Fixed visibility case for {result.rowcount} users',
                'updated_count': result.rowcount
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to fix visibility case: {str(e)}'}