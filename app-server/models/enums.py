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