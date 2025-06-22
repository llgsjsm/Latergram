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