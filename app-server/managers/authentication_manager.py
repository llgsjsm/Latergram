from typing import Optional, List, Dict, Any
from models import db, User, Moderator
from models.enums import VisibilityType
from flask_bcrypt import Bcrypt
from sqlalchemy import or_
from datetime import datetime
import re

bcrypt = Bcrypt()

class AuthenticationManager:
    def login(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """Authenticate user login - supports both username and email"""
        # Optimize: Single query using OR condition instead of two separate queries
        user = User.query.filter(
            or_(User.username == username_or_email, User.email == username_or_email)
        ).first()

        if user:
            if not bcrypt.check_password_hash(user.password, password):
                return {'success': False, 'error': 'Invalid password'}
            
            # enforce account disablement period
            if user.disabledUntil and user.disabledUntil > datetime.utcnow():
                return {
                    'success': False,
                    'error': f'Login failed. Your account is disabled until {user.disabledUntil.strftime("%Y-%m-%d %H:%M:%S")}.'
                }
            
            return {
                'success': True,
                'login_type': 'user',
                'user': {
                    'user_id': user.userId,
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.createdAt,
                    'profile_picture': user.profilePicture,
                    'bio': user.bio,
                    'visibility': user.visibility
                    },
                'message': 'Authentication successful'
            }
        # if user not found, check in moderators table
        else:
            moderator = Moderator.query.filter(
                or_(Moderator.username == username_or_email, Moderator.email == username_or_email)
            ).first()
            if moderator:
                if not bcrypt.check_password_hash(moderator.password, password):
                    return {'success': False, 'error': 'Invalid password'}
                return {
                    'success': True,
                    'login_type': 'moderator',
                    'moderator': {
                        'mod_id': moderator.modID,
                        'mod_level': moderator.modLevel,
                        'username': moderator.username,
                        'email': moderator.email,
                        'created_at': moderator.createdAt,
                        },
                    'message': 'Authentication successful'
                }        
            else:
                # not in user or moderator table
                return {
                    'success': False,
                    'error': 'User not found'
                }

    def logout(self):
        # In a session-based approach, this would clear the session
        pass

    def register(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Create a new user with validation"""
        # Validate input
        validation_result = self.validate_user_data(username, email, password)
        if not validation_result['valid']:
            return validation_result
        
        # Check if username or email already exists - single query optimization
        existing_user = User.query.filter(
            or_(User.username == username, User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                return {'success': False, 'error': 'Username already exists'}
            else:
                return {'success': False, 'error': 'Email already exists'}
        
        try:
            # Create user with profile information in the same table
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(
                username=username,
                email=email,
                password=hashed_password,
                profilePicture='',
                bio='',
                visibility=VisibilityType.PUBLIC.value
            )
            db.session.add(user)
            db.session.commit()
            
            return {
                'success': True,
                'user_id': user.userId,
                'message': 'User created successfully'
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to create user: {str(e)}'}

    def validate_session(self):
        # This would check if a user is logged in
        return False

    def reset_password(self, email):
        # This would handle password reset logic
        pass
    
    def validate_user_data(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Validate user registration data"""
        errors = []
        
        # Username validation
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        elif len(username) > 50:
            errors.append('Username must be less than 50 characters')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores')
        
        # Email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not email or not re.match(email_pattern, email):
            errors.append('Please enter a valid email address')
        
        # Password validation
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long')
        elif len(password) > 255:
            errors.append('Password must be less than 255 characters')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'success': len(errors) == 0
        } 