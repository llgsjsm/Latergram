class BaseUserMixin:
    """
    Base mixin class for all user types in the system.
    Provides common methods that all user types should have.
    This is a mixin, not a database model, so it doesn't create tables.
    """
    
    # Methods that subclasses should implement
    def get_id(self):
        """Return the unique identifier for this user"""
        raise NotImplementedError("Subclasses must implement get_id()")
    
    def set_id(self, user_id):
        """Set the unique identifier for this user"""
        raise NotImplementedError("Subclasses must implement set_id()")
    
    def get_username(self):
        """Return the username for this user"""
        raise NotImplementedError("Subclasses must implement get_username()")

    def set_username(self, username):
        """Set the username for this user"""
        raise NotImplementedError("Subclasses must implement set_username()")

    def get_email(self):
        """Return the email for this user"""
        raise NotImplementedError("Subclasses must implement get_email()")

    def set_email(self, email):
        """Set the email for this user"""
        raise NotImplementedError("Subclasses must implement set_email()")

    def get_password(self):
        """Return the password for this user"""
        raise NotImplementedError("Subclasses must implement get_password()")

    def set_password(self, password):
        """Set the password for this user"""
        raise NotImplementedError("Subclasses must implement set_password()")
        
    def get_created_at(self):
        """Return the creation timestamp for this user"""
        raise NotImplementedError("Subclasses must implement get_created_at()")
    
    # Common utility methods that can be shared
    def is_valid_email(self, email):
        """Check if email format is valid"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def is_valid_username(self, username):
        """Check if username format is valid"""
        if not username or len(username) < 3 or len(username) > 50:
            return False
        # Only allow alphanumeric characters and underscores
        import re
        return re.match(r'^[a-zA-Z0-9_]+$', username) is not None
    
    def get_display_name(self):
        """Return a display-friendly name (username by default)"""
        return self.get_username()
    
    # OTP-related methods
    def generate_otp(self):
        """Generate a 6-digit OTP code"""
        import random
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    def is_otp_valid(self, otp_code, otp_type=None):
        """Check if the provided OTP is valid and not expired"""
        from datetime import datetime
        
        if not hasattr(self, 'otp_code') or not hasattr(self, 'otp_expires_at'):
            return False
            
        if not self.otp_code or not self.otp_expires_at:
            return False
            
        # Check if OTP has expired
        if datetime.utcnow() > self.otp_expires_at:
            return False
            
        # Check if OTP matches
        if self.otp_code != otp_code:
            return False
            
        # Check OTP type if specified
        if otp_type and hasattr(self, 'otp_type') and self.otp_type != otp_type:
            return False
            
        return True
    
    def clear_otp(self):
        """Clear OTP data after successful verification"""
        if hasattr(self, 'otp_code'):
            self.otp_code = None
        if hasattr(self, 'otp_expires_at'):
            self.otp_expires_at = None
        if hasattr(self, 'otp_type'):
            self.otp_type = None
    
    def set_otp(self, otp_code, otp_type, expiry_minutes=10):
        """Set OTP code with expiry time"""
        from datetime import datetime, timedelta
        
        if hasattr(self, 'otp_code'):
            self.otp_code = otp_code
        if hasattr(self, 'otp_expires_at'):
            self.otp_expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
        if hasattr(self, 'otp_type'):
            self.otp_type = otp_type
        if hasattr(self, 'last_otp_request'):
            self.last_otp_request = datetime.utcnow()
    
    def __str__(self):
        """String representation of the user"""
        return f"{self.__class__.__name__}(username={self.get_username()})"
    
    def __repr__(self):
        """Developer representation of the user"""
        return f"{self.__class__.__name__}(id={self.get_id()}, username={self.get_username()})"
