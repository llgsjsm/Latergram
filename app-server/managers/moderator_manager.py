from models import db, Report, Post, Comment, User
from models.enums import ReportStatus

class ModeratorManager:
    def __init__(self, moderator: User):
        if moderator.role != 'moderator':
            raise ValueError("User is not a moderator")
        self.moderator = moderator

    def review_report(self, report_id):
        # Logic to review a report
        pass

    def remove_post(self, post_id):
        post = Post.query.get(post_id)
        if post:
            db.session.delete(post)
            db.session.commit()

    def remove_comment(self, comment_id):
        comment = Comment.query.get(comment_id)
        if comment:
            db.session.delete(comment)
            db.session.commit()

    def disable_user(self, user_id):
        # Logic to disable a user account
        pass

    def get_report_queue(self):
        return Report.query.filter_by(status=ReportStatus.PENDING).all()

    def mod_level_check(self, mod_level):
        # Logic to check moderator level
        pass 