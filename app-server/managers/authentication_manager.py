from typing import Optional, List, Dict, Any
from models import db, User, Moderator
from models.enums import VisibilityType, ReportTarget, LogActionTypes
from flask_bcrypt import Bcrypt
from sqlalchemy import or_
from datetime import datetime, timedelta
import re
from sqlalchemy import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import random
import time

bcrypt = Bcrypt()

class AuthenticationManager:
    def __init__(self):
        # Email configuration for OTP
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.email_user = os.environ.get('EMAIL_USER', '')
        self.email_password = os.environ.get('EMAIL_PASSWORD', '')
    
    def _generate_otp(self) -> str:
        """Generate a 6-digit OTP"""
        return str(random.randint(100000, 999999)).zfill(6)
    
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
            "target_type": ReportTarget.USER.value
        })

    def login(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """Authenticate user login - supports both username and email"""
        # Optimize: Single query using OR condition instead of two separate queries
        user = User.query.filter(
            or_(User.username == username_or_email, User.email == username_or_email)
        ).first()

        if user:
            if not bcrypt.check_password_hash(user.password, password):
                return {'success': False, 'error': 'Error logging in. Try again.'}
            
            # enforce account disablement period
            if user.disabledUntil and user.disabledUntil > datetime.utcnow():
                return {
                    'success': False,
                    'error': f'Login failed. Your account is disabled until {user.disabledUntil.strftime("%Y-%m-%d %H:%M:%S")}.'
                }
            
            # Create a new log entry
            self.log_action(user.userId, LogActionTypes.LOGIN.value, None)
            db.session.commit()
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
                'message': 'Login successful'
            }
        # if user not found, check in moderators table
        else:
            moderator = Moderator.query.filter(
                or_(Moderator.username == username_or_email, Moderator.email == username_or_email)
            ).first()
            if moderator:
                if not bcrypt.check_password_hash(moderator.password, password):
                    return {'success': False, 'error': 'Error logging in. Try again.'}
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
                    'error': 'Error logging in. Try again.'
                }

    def logout(self):
        # In a session-based approach, this would clear the session
        pass

    def initiate_registration(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Validate data and prepare for registration OTP"""
        # Validate input
        validation_result = self.validate_user_data(username, email, password)
        if not validation_result['valid']:
            return validation_result
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            or_(User.username == username)
        ).first()

        if existing_user:
            if existing_user.username.lower() == username.lower():
                return {'success': False, 'errors': ['Username already exists']}
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        return {
            'success': True,
            'password_hash': hashed_password
        }

    def create_user(self, username: str, email: str, password_hash: str) -> Dict[str, Any]:
        """Creates a new user in the database."""
        try:
            user = User(
                username=username,
                email=email,
                password=password_hash,
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
            return {'success': False, 'errors': [f'Failed to create user: {str(e)}']}

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
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters long')
        elif len(password) > 64:
            errors.append('Password must be less than 64 characters')
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("Password must contain at least one special character")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'success': len(errors) == 0
        }
    
    def send_otp_email(self, email: str, otp_code: str, otp_type: str = 'login') -> bool:
        """Send OTP code via email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = email
            
            if otp_type == 'login':
                msg['Subject'] = 'LaterGram - Login Verification Code'
                body = f"""
                Hello,
                
                Your LaterGram login verification code is: {otp_code}
                
                This code will expire in 10 minutes.
                
                If you didn't request this code, please ignore this email.
                
                Best regards,
                LaterGram Team
                """
            elif otp_type == 'email_update':
                msg['Subject'] = 'LaterGram - Email Update Verification Code'
                body = f"""
                Hello,
                
                Your LaterGram email update verification code is: {otp_code}
                
                This code will expire in 10 minutes.
                
                If you didn't request this email update, please ignore this email.
                
                Best regards,
                LaterGram Team
                """
            elif otp_type == 'registration':
                msg['Subject'] = 'LaterGram - Account Verification Code'
                body = f"""
                Hello,
                
                Your LaterGram account verification code is: {otp_code}
                
                This code will expire in 10 minutes.
                
                If you didn't request this code, please ignore this email.
                
                Best regards,
                LaterGram Team
                """
            else:  # password_reset
                msg['Subject'] = 'LaterGram - Password Reset Code'
                body = f"""
                Hello,
                
                Your LaterGram password reset code is: {otp_code}
                
                This code will expire in 10 minutes.
                
                If you didn't request this password reset, please ignore this email.
                
                Best regards,
                LaterGram Team
                """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
    
    def generate_and_send_otp(self, email: str, otp_type: str = 'login') -> Dict[str, Any]:
        """Generate and send OTP to user's email"""
        try:
            if otp_type == 'registration':
                otp_code = self._generate_otp()
                if self.send_otp_email(email, otp_code, 'registration'):
                    return {'success': True, 'otp_code': otp_code, 'message': 'OTP sent to your email.'}
                else:
                    return {'success': False, 'error': 'Failed to send OTP email.'}

            user = User.query.filter_by(email=email).first()
            delay = 5 # Dummy delay against timing attacks :)
            if user:
                if user.last_otp_request:
                    # Bootleg rate limiting
                    time_since_last_request = datetime.utcnow() - user.last_otp_request
                    if time_since_last_request.total_seconds() < 60:  # 1 minute cooldown
                        time.sleep(delay)
                        return {'success': True, 'message': 'An OTP has been sent.'}
                otp_code = user.generate_otp()
                user.set_otp(otp_code, otp_type, expiry_minutes=10)
                db.session.commit()
                self.send_otp_email(email, otp_code, otp_type)
            else:
                time.sleep(delay)
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'An internal error occurred: {str(e)}'}

        return { 'success': True, 'message': 'An OTP has been sent.' }
    
    def generate_and_send_moderator_otp(self, email: str, otp_type: str = 'login') -> Dict[str, Any]:
        """Generate and send OTP to moderator's email"""
        # Find moderator by email
        moderator = Moderator.query.filter_by(email=email).first()
        if not moderator:
            return {'success': False, 'error': 'Moderator not found'}
        
        # Rate limiting: Check if moderator requested OTP recently
        if moderator.last_otp_request:
            time_since_last_request = datetime.utcnow() - moderator.last_otp_request
            if time_since_last_request.total_seconds() < 60:  # 1 minute cooldown
                return {'success': False, 'error': 'Please wait before requesting another OTP'}
        
        # Generate OTP
        otp_code = moderator.generate_otp()
        
        # Set OTP in database
        moderator.set_otp(otp_code, otp_type, expiry_minutes=10)
        
        try:
            db.session.commit()
            
            # Send OTP via email (using subject appropriate for moderators)
            if self.send_moderator_otp_email(email, otp_code, otp_type):
                return {'success': True, 'message': f'OTP sent to {email}'}
            else:
                # Rollback if email sending fails
                moderator.clear_otp()
                db.session.commit()
                return {'success': False, 'error': 'Failed to send OTP email'}
                
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Database error: {str(e)}'}
            
    def send_moderator_otp_email(self, email: str, otp_code: str, otp_type: str = 'login') -> bool:
        """Send OTP code via email to moderators"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = email
            
            if otp_type == 'login':
                msg['Subject'] = 'LaterGram Moderator - Login Verification Code'
                body = f"""
                Hello Moderator,
                
                Your LaterGram moderator login verification code is: {otp_code}
                
                This code will expire in 10 minutes.
                
                If you didn't request this code, please contact the system administrator immediately.
                
                Best regards,
                LaterGram Admin Team
                """
            else:  # password_reset
                msg['Subject'] = 'LaterGram Moderator - Password Reset Code'
                body = f"""
                Hello Moderator,
                
                Your LaterGram moderator password reset code is: {otp_code}
                
                This code will expire in 10 minutes.
                
                If you didn't request this password reset, please contact the system administrator immediately.
                
                Best regards,
                LaterGram Admin Team
                """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            print(f"Error sending moderator email: {str(e)}")
            return False
    
    def verify_otp(self, email: str, otp_code: str, otp_type: str = 'login') -> Dict[str, Any]:
        """Verify OTP code"""
        user = User.query.filter_by(email=email).first()
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Check if OTP is valid
        if not user.is_otp_valid(otp_code, otp_type):
            # Increment failed attempts
            if not user.login_attempts:
                user.login_attempts = 0
            user.login_attempts += 1
            
            # Lock account after 5 failed attempts for 15 minutes
            if user.login_attempts >= 5:
                user.disabledUntil = datetime.utcnow() + timedelta(minutes=15)
                user.clear_otp()
                db.session.commit()
                return {'success': False, 'error': 'Too many failed attempts. Account locked for 15 minutes.'}
            
            db.session.commit()
            return {'success': False, 'error': 'Invalid or expired OTP'}
        
        # OTP is valid - for login OTP, clear it immediately
        # For password reset OTP, keep it until password is actually reset
        if otp_type == 'login':
            user.clear_otp()
        user.login_attempts = 0
        db.session.commit()
        
        return {'success': True, 'user_id': user.userId, 'message': 'OTP verified successfully'}
    
    def verify_moderator_otp(self, email: str, otp_code: str, otp_type: str = 'login') -> Dict[str, Any]:
        """Verify moderator OTP code"""
        moderator = Moderator.query.filter_by(email=email).first()
        if not moderator:
            return {'success': False, 'error': 'Moderator not found'}
        
        # Check if OTP is valid
        if not moderator.is_otp_valid(otp_code, otp_type):
            # Increment failed attempts
            if not moderator.login_attempts:
                moderator.login_attempts = 0
            moderator.login_attempts += 1
            
            # Lock account after 5 failed attempts for 15 minutes
            if moderator.login_attempts >= 5:
                moderator.clear_otp()
                db.session.commit()
                return {'success': False, 'error': 'Too many failed attempts. Account locked for 15 minutes.'}
            
            db.session.commit()
            return {'success': False, 'error': 'Invalid or expired OTP'}
        
        # OTP is valid - for login OTP, clear it immediately
        # For password reset OTP, keep it until password is actually reset
        if otp_type == 'login':
            moderator.clear_otp()
        moderator.login_attempts = 0
        db.session.commit()
        
        return {'success': True, 'mod_id': moderator.modID, 'message': 'OTP verified successfully'}
    
    def login_with_otp(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """Initiate login process that requires OTP verification"""
        # First verify username/email and password
        user = User.query.filter(
            or_(User.username == username_or_email, User.email == username_or_email)
        ).first()

        if not user:
            return {'success': False, 'error': 'User not found'}

        if not bcrypt.check_password_hash(user.password, password):
            return {'success': False, 'error': 'Invalid password'}
        
        # Check if account is disabled
        if user.disabledUntil and user.disabledUntil > datetime.utcnow():
            return {
                'success': False,
                'error': f'Account is disabled until {user.disabledUntil.strftime("%Y-%m-%d %H:%M:%S")}.'
            }
        
        # Generate and send OTP
        otp_result = self.generate_and_send_otp(user.email, 'login')
        if not otp_result['success']:
            return otp_result
        
        return {
            'success': True,
            'requires_otp': True,
            'email': user.email,
            'message': 'OTP sent to your email. Please verify to complete login.'
        }
    
    def complete_login_with_otp(self, email: str, otp_code: str) -> Dict[str, Any]:
        """Complete login after OTP verification"""
        verify_result = self.verify_otp(email, otp_code, 'login')
        if not verify_result['success']:
            return verify_result
        
        user = User.query.filter_by(email=email).first()
        # Create a new log entry
        self.log_action(user.userId, LogActionTypes.LOGIN.value, None)
        db.session.commit()
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
            'message': 'Login successful'
        }
    
    def moderator_login_with_otp(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """Initiate moderator login process that requires OTP verification"""
        # First verify username/email and password
        moderator = Moderator.query.filter(
            or_(Moderator.username == username_or_email, Moderator.email == username_or_email)
        ).first()

        if not moderator:
            return {'success': False, 'error': 'Moderator not found'}

        if not bcrypt.check_password_hash(moderator.password, password):
            return {'success': False, 'error': 'Invalid password'}
        
        # Generate and send OTP
        otp_result = self.generate_and_send_moderator_otp(moderator.email, 'login')
        if not otp_result['success']:
            return otp_result
        
        return {
            'success': True,
            'requires_otp': True,
            'email': moderator.email,
            'mod_id': moderator.modID,
            'mod_level': moderator.modLevel,
            'message': 'OTP sent to your email. Please verify to complete login.'
        }
    
    def complete_moderator_login_with_otp(self, email: str, otp_code: str) -> Dict[str, Any]:
        """Complete moderator login after OTP verification"""
        verify_result = self.verify_moderator_otp(email, otp_code, 'login')
        if not verify_result['success']:
            return verify_result
        
        moderator = Moderator.query.filter_by(email=email).first()
        
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
            'message': 'Login successful'
        }
    
    def initiate_password_reset(self, email: str) -> Dict[str, Any]:
        """Initiate password reset by sending OTP"""
        return self.generate_and_send_otp(email, 'password_reset')
    
    def reset_password_with_otp(self, email: str, otp_code: str, new_password: str) -> Dict[str, Any]:
        """Reset password after OTP verification"""
        user = Moderator.query.filter_by(email=email).first()
        if not user:
            user = User.query.filter_by(email=email).first()
        else:
            return {'success': False, 'error': 'User not found'}
        
        # Verify OTP is still valid for password reset
        if not user.is_otp_valid(otp_code, 'password_reset'):
            return {'success': False, 'error': 'Invalid or expired OTP'}

        # Validate new password
        if len(new_password) < 8:
                return {'success': False, 'error': 'Password must be at least 8 characters long'}
        if not re.search(r"[A-Z]", new_password):
                return {'success': False, 'error': 'Password must contain at least one uppercase letter'}
        if not re.search(r"[a-z]", new_password):
                return {'success': False, 'error': 'Password must contain at least one uppercase letter'}
        if not re.search(r"[0-9]", new_password):
                return {'success': False, 'error': 'Password must contain at least one digit'}
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
                return {'success': False, 'error': 'Password must contain at least one special character'}
        
        try:
            # Update password
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            user.password = hashed_password
            user.login_attempts = 0  # Reset login attempts
            user.disabledUntil = None  # Remove any account locks
            
            # Clear OTP after successful password reset
            user.clear_otp()
            # Create a new log entry
            self.log_action(user.userId, LogActionTypes.RESET_PASSWORD.value, None)
            db.session.commit()
            
            return {'success': True, 'message': 'Password reset successfully'}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to reset password: {str(e)}'}
    
    def initiate_moderator_password_reset(self, email: str) -> Dict[str, Any]:
        """Initiate moderator password reset by sending OTP"""
        return self.generate_and_send_moderator_otp(email, 'password_reset')
    
    def reset_moderator_password_with_otp(self, email: str, otp_code: str, new_password: str) -> Dict[str, Any]:
        """Reset moderator password after OTP verification"""
        moderator = Moderator.query.filter_by(email=email).first()
        if not moderator:
            return {'success': False, 'error': 'Moderator not found'}
        
        # Verify OTP is still valid for password reset
        if not moderator.is_otp_valid(otp_code, 'password_reset'):
            return {'success': False, 'error': 'Invalid or expired OTP'}
        
        # Validate new password
        if len(new_password) < 8:
                return {'success': False, 'error': 'Password must be at least 8 characters long'}
        if not re.search(r"[A-Z]", new_password):
                return {'success': False, 'error': 'Password must contain at least one uppercase letter'}
        if not re.search(r"[a-z]", new_password):
                return {'success': False, 'error': 'Password must contain at least one uppercase letter'}
        if not re.search(r"[0-9]", new_password):
                return {'success': False, 'error': 'Password must contain at least one digit'}
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
                return {'success': False, 'error': 'Password must contain at least one special character'}
        
        try:
            # Update password
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            moderator.password = hashed_password
            moderator.login_attempts = 0  # Reset login attempts
            
            # Clear OTP after successful password reset
            moderator.clear_otp()
            
            db.session.commit()
            
            return {'success': True, 'message': 'Moderator password reset successfully'}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Failed to reset moderator password: {str(e)}'}
    
    def generate_and_send_email_update_otp(self, current_user_id: int, new_email: str) -> Dict[str, Any]:
        """Generate and send OTP to new email address for email update verification"""
        # Find the current user (who is requesting the email change)
        current_user = User.query.filter_by(userId=current_user_id).first()
        if not current_user:
            return {'success': False, 'error': 'User not found'}
        
        # Rate limiting: Check if user requested OTP recently
        if current_user.last_otp_request:
            time_since_last_request = datetime.utcnow() - current_user.last_otp_request
            if time_since_last_request.total_seconds() < 60:  # 1 minute cooldown
                return {'success': False, 'error': 'Please wait before requesting another OTP'}
        
        # Generate OTP
        otp_code = current_user.generate_otp()
        
        # Set OTP in current user's record (but for email_update type)
        # We store the new email temporarily in a way that can be validated later
        current_user.set_otp(otp_code, 'email_update', expiry_minutes=10)
        
        try:
            db.session.commit()
            
            # Send OTP via email to the NEW email address
            if self.send_otp_email(new_email, otp_code, 'email_update'):
                return {'success': True, 'message': f'OTP sent to {new_email}'}
            else:
                # Rollback if email sending fails
                current_user.clear_otp()
                db.session.commit()
                return {'success': False, 'error': 'Failed to send OTP email'}
                
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Database error: {str(e)}'}
    
    def verify_email_update_otp(self, current_user_id: int, new_email: str, otp_code: str) -> Dict[str, Any]:
        """Verify OTP for email update"""
        # Find the current user
        current_user = User.query.filter_by(userId=current_user_id).first()
        if not current_user:
            return {'success': False, 'error': 'User not found'}
        
        # Check if OTP is valid for email update
        if not current_user.is_otp_valid(otp_code, 'email_update'):
            # Increment failed attempts
            if not current_user.login_attempts:
                current_user.login_attempts = 0
            current_user.login_attempts += 1
            
            # Lock account after 5 failed attempts for 15 minutes
            if current_user.login_attempts >= 5:
                current_user.disabledUntil = datetime.utcnow() + timedelta(minutes=15)
                current_user.clear_otp()
                db.session.commit()
                return {'success': False, 'error': 'Too many failed attempts. Account locked for 15 minutes.'}
            
            db.session.commit()
            return {'success': False, 'error': 'Invalid or expired OTP'}
        
        # OTP is valid, clear it and reset attempts
        current_user.clear_otp()
        current_user.login_attempts = 0
        db.session.commit()
        
        return {'success': True, 'user_id': current_user.userId, 'message': 'OTP verified successfully'}
