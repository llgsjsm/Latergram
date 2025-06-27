from datetime import timedelta
import datetime
from models import db, Report, Post, Comment, User, Moderator
from models.enums import ReportStatus, UserDisableDays

class ModeratorManager:
    def __init__(self, moderator: Moderator = None):
        # if moderator.role != 'moderator':
        #     raise ValueError("User is not a moderator")
        self.moderator = moderator

    def review_report(self, report_id, mod_id):
        report = Report.query.get(report_id)
        if report:
            if report.status == ReportStatus.PENDING.value:
                report.status = ReportStatus.UNDER_REVIEW.value
                report.reviewedBy = mod_id
                db.session.commit()
                return {'success': True, 'message': 'Report marked as under review'}
            else:
                return {'success': False, 'message': 'Report is not pending for review!'}


    def resolve_report(self, report_id, mod_id):
        report = Report.query.get(report_id)
        if report:
            if report.status == ReportStatus.UNDER_REVIEW.value:
                report.status = ReportStatus.RESOLVED.value
                db.session.commit()
                return {'success': True, 'message': 'Report resolved'}
            else:
                return {'success': False, 'message': 'Report is not under review!'}


    def reject_report(self, report_id, mod_id):
        report = Report.query.get(report_id)
        if report:
            if report.status == ReportStatus.UNDER_REVIEW.value:
                report.status = ReportStatus.REJECTED.value
                db.session.commit()
                return {'success': True, 'message': 'Report rejected'}
            else:
                return {'success': False, 'message': 'Report is not under review!'}


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

    def disable_user(self, user_id, disabled_days):
        """
        Disable a user account for a specified number of days.
        Sets the disabledUntil field to now + days.
        """
        user = User.query.get(user_id)
        # Check if disabled_days is a valid enum value
        valid_days = [e.value for e in UserDisableDays]
        if disabled_days not in valid_days:
            return {'success': False, 'message': 'Invalid user disable duration.'}
        if user:
            user.disabledUntil = datetime.datetime.utcnow() + timedelta(days=disabled_days)
            db.session.commit()
            return {'success': True, 'message': f'User disabled for {disabled_days} day(s).'}
        else:
            return {'success': False, 'message': 'User not found.'}

    def get_report_queue(self):
        return Report.query.filter_by(status=ReportStatus.PENDING.value).all()

    def get_all_reports_query(self):
        return Report.query.order_by(Report.timestamp.desc())
    
    def get_report_by_id(self, report_id):
        return Report.query.get(report_id)

    def mod_level_check(self, mod_level):
        # Logic to check moderator level
        pass 