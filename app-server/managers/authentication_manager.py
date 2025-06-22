from typing import Optional, List, Dict, Any
from models import db, User
from flask_bcrypt import Bcrypt
import re

bcrypt = Bcrypt()

class AuthenticationManager:
    def login(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """Authenticate user login - supports both username and email"""
        # Try to find user by username or email
        user = User.query.filter_by(username=username_or_email).first()
        if not user:
            user = User.query.filter_by(email=username_or_email).first()
        
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        if not bcrypt.check_password_hash(user.password, password):
            return {'success': False, 'error': 'Invalid password'}
        
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
            'message': 'Authentication successful'
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
        
        # Check if username or email already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return {'success': False, 'error': 'Username already exists'}
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
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
                visibility='public'
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