from enum import Enum

class Role(Enum):
    STUDENT = "student"
    MODERATOR = "moderator"

class ReportStatus(Enum):
    PENDING = "Pending"
    UNDER_REVIEW = "UnderReview"
    RESOLVED = "Resolved"
    REJECTED = "Rejected"

class VisibilityType(Enum):
    PUBLIC = "Public"
    PRIVATE = "Private"
    FOLLOWERS_ONLY = "FollowersOnly" 

class ReportTarget(Enum):
    POST = "Post"
    COMMENT = "Comment"
    USER = "User"

class UserDisableDays(Enum):
    ONE = 1
    THREE = 3
    SEVEN = 7
    THIRTY = 30
    SIXTY = 60
    NINETY = 90

class LogActionTypes(Enum):
    CREATE_POST = "create_post"
    DELETE_POST = "delete_post"
    UPDATE_POST = "update_post"
    CREATE_COMMENT = "create_comment"
    DELETE_COMMENT = "delete_comment"
    UPDATE_COMMENT = "update_comment"
    FOLLOW_USER = "follow_user"
    REQUEST_FOLLOW = "request_follow"
    ACCEPT_FOLLOW_REQUEST = "accept_follow_request"
    UNFOLLOW_USER = "unfollow_user"
    CANCEL_PENDING_FOLLOW_REQUEST = "cancel_pending_follow_request"
    REJECT_FOLLOW_REQUEST = "reject_follow_request"
    REMOVE_FOLLOWER = "remove_follower"
    LIKE_POST = "like_post"
    UNLIKE_POST = "unlike_post"
    LOGIN = "login"
    LOGOUT = "logout"
    UPDATE_PROFILE = "update_profile"
    UPDATE_EMAIL = "update_email"
    CHANGE_PASSWORD = "change_password"
    RESET_PASSWORD = "reset_password"