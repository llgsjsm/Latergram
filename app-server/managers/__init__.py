from .authentication_manager import AuthenticationManager
from .feed_manager import FeedManager
from .moderator_manager import ModeratorManager
from .post_manager import PostManager
from .profile_manager import ProfileManager

# Create singleton instances for better performance
_auth_manager = None
_feed_manager = None
_post_manager = None
_profile_manager = None

def get_auth_manager():
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthenticationManager()
    return _auth_manager

def get_feed_manager():
    global _feed_manager
    if _feed_manager is None:
        _feed_manager = FeedManager()
    return _feed_manager

def get_post_manager():
    global _post_manager
    if _post_manager is None:
        _post_manager = PostManager()
    return _post_manager

def get_profile_manager():
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager

__all__ = [
    "AuthenticationManager",
    "FeedManager", 
    "ModeratorManager",
    "PostManager",
    "ProfileManager",
    "get_auth_manager",
    "get_feed_manager", 
    "get_post_manager",
    "get_profile_manager"
] 