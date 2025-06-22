from typing import Optional, List, Dict, Any
from models import db, User
from sqlalchemy import text

class ProfileManager:
    def __init__(self, current_user: User = None):
        self.current_user = current_user

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
        """Follow another user"""
        if follower_user_id == followed_user_id:
            return {'success': False, 'error': 'Cannot follow yourself'}
        
        # Check if users exist
        follower_user = User.query.filter_by(userId=follower_user_id).first()
        followed_user = User.query.filter_by(userId=followed_user_id).first()
        
        if not follower_user or not followed_user:
            return {'success': False, 'error': 'One or both users not found'}
        
        # Check if already following
        if self.is_following(follower_user_id, followed_user_id):
            return {'success': False, 'error': 'Already following this user'}
        
        try:
            # Insert follow relationship
            query = text("INSERT INTO followers (followerUserId, followedUserId) VALUES (:follower_id, :followed_id)")
            db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id})
            db.session.commit()
            return {
                'success': True,
                'message': 'Successfully followed user'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to follow user: {str(e)}'}
    
    def unfollow_user(self, follower_user_id: int, followed_user_id: int) -> Dict[str, Any]:
        """Unfollow a user"""
        if not self.is_following(follower_user_id, followed_user_id):
            return {'success': False, 'error': 'Not following this user'}
        
        try:
            query = text("DELETE FROM followers WHERE followerUserId = :follower_id AND followedUserId = :followed_id")
            db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id})
            db.session.commit()
            return {
                'success': True,
                'message': 'Successfully unfollowed user'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to unfollow user: {str(e)}'}
    
    def is_following(self, follower_user_id: int, followed_user_id: int) -> bool:
        """Check if one user follows another"""
        try:
            query = text("SELECT COUNT(*) as count FROM followers WHERE followerUserId = :follower_id AND followedUserId = :followed_id")
            result = db.session.execute(query, {"follower_id": follower_user_id, "followed_id": followed_user_id}).fetchone()
            return result[0] > 0 if result else False
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