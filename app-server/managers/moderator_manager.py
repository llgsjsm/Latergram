from datetime import datetime, timedelta
from models import db, Report, Post, Comment, User, Moderator
from models.enums import ReportStatus, UserDisableDays, ReportTarget

class ModeratorManager:
    def __init__(self, moderator: Moderator = None):
        # if moderator.role != 'moderator':
        #     raise ValueError("User is not a moderator")
        self.moderator = moderator

    def review_report(self, report_id, mod_id, mod_level):
        report = Report.query.get(report_id)
        if mod_level == 2 and report.targetType == ReportTarget.USER.value:
            return {'success': False, 'message': 'Only user moderators may manage user reports.'}
        elif mod_level == 1 and report.targetType != ReportTarget.USER.value:
            return {'success': False, 'message': 'Only content moderators may manage content reports.'}
        
        if report:
            if report.status == ReportStatus.PENDING.value:
                report.status = ReportStatus.UNDER_REVIEW.value
                report.reviewedBy = mod_id
                db.session.commit()
                return {'success': True, 'message': 'Report marked as under review'}
            else:
                return {'success': False, 'message': 'Report is not pending for review!'}


    def resolve_report(self, report_id, mod_id, mod_level):
        report = Report.query.get(report_id)
        if mod_level == 2 and report.targetType == ReportTarget.USER.value:
            return {'success': False, 'message': 'Only user moderators may manage user reports.'}
        elif mod_level == 1 and report.targetType != ReportTarget.USER.value:
            return {'success': False, 'message': 'Only content moderators may manage content reports.'}
        
        if report:
            if report.status == ReportStatus.UNDER_REVIEW.value:
                report.status = ReportStatus.RESOLVED.value
                db.session.commit()
                return {'success': True, 'message': 'Report resolved'}
            else:
                return {'success': False, 'message': 'Report is not under review!'}


    def reject_report(self, report_id, mod_id, mod_level):
        report = Report.query.get(report_id)
        if mod_level == 2 and report.targetType == ReportTarget.USER.value:
            return {'success': False, 'message': 'Only user moderators may manage user reports.'}
        elif mod_level == 1 and report.targetType != ReportTarget.USER.value:
            return {'success': False, 'message': 'Only content moderators may manage content reports.'}
          
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

    def disable_user(self, user_id, disabled_days, mod_id, mod_level):
        """
        Disable a user account for a specified number of days.
        Sets the disabledUntil field to now + days.
        """
        if mod_level != 1:  # Only user moderators can disable users
            return {'success': False, 'message': 'Only user moderators may disable users.'}
        user = User.query.get(user_id)
        # Check if disabled_days is a valid enum value
        valid_days = [e.value for e in UserDisableDays]
        if disabled_days not in valid_days:
            return {'success': False, 'message': 'Invalid user disable duration.'}
        if user:
            user.disabledUntil = datetime.utcnow() + timedelta(days=disabled_days)
            db.session.commit()
            return {'success': True, 'message': f'User disabled for {disabled_days} day(s).'}
        else:
            return {'success': False, 'message': 'User not found.'}

    def get_report_queue(self, mod_level):
        if mod_level == 1: # user moderator
            return Report.query.filter_by(status=ReportStatus.PENDING.value, targetType=ReportTarget.USER.value).all()
        elif mod_level == 2: # content moderator
            return Report.query.filter(
                Report.status == ReportStatus.PENDING.value,
                Report.targetType.in_([ReportTarget.COMMENT.value, ReportTarget.POST.value])
            ).all()

    def get_all_reports_query(self, mod_level):
        if mod_level == 1: # user moderator
            return Report.query.filter_by(targetType=ReportTarget.USER.value).order_by(Report.timestamp.desc())
        elif mod_level == 2: # content moderator
            return Report.query.filter(
                Report.targetType.in_([ReportTarget.COMMENT.value, ReportTarget.POST.value])
            ).order_by(Report.timestamp.desc())
    
    def get_report_by_id(self, report_id, mod_level):
        if mod_level == 1:
            return Report.query.filter_by(id=report_id, targetType=ReportTarget.USER.value).first()
        elif mod_level == 2:
            return Report.query.filter(
                Report.id == report_id,
                Report.targetType.in_([ReportTarget.COMMENT.value, ReportTarget.POST.value])
            ).first()

    def mod_level_check(self, mod_level):
        # Logic to check moderator level
        pass 