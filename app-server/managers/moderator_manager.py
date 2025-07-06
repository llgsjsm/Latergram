from datetime import datetime, timedelta
from models import db, Report, Post, Comment, User, Moderator
from models.enums import ReportStatus, UserDisableDays, ReportTarget
from sqlalchemy import text

class ModeratorManager:
    def __init__(self, moderator: Moderator = None):
        # if moderator.role != 'moderator':
        #     raise ValueError("User is not a moderator")
        self.moderator = moderator

    def review_report(self, report_id, mod_id, mod_level):
        report = Report.query.get(report_id)
        
        if report:
            if mod_level == 2 and report.targetType == ReportTarget.USER.value:
                return {'success': False, 'message': 'Only user moderators may manage user reports.'}
            elif mod_level == 1 and report.targetType != ReportTarget.USER.value:
                return {'success': False, 'message': 'Only content moderators may manage content reports.'}
            try:
                if report.status == ReportStatus.PENDING.value:
                    report.status = ReportStatus.UNDER_REVIEW.value
                    report.reviewedBy = mod_id
                    db.session.commit()
                    return {'success': True, 'message': 'Report marked as under review'}
                else:
                    return {'success': False, 'message': 'Report is not pending for review!'}
            except Exception as e:
                db.session.rollback()
                print(f"Error marking report as under review: {e}")
                return {'success': False, 'message': f'Failed to mark report as under review'}
        else:
            return {'success': False, 'message': 'Report not found'}

    def resolve_report(self, report_id, mod_id, mod_level):
        report = Report.query.get(report_id)
        
        if report:
            if mod_level == 2 and report.targetType == ReportTarget.USER.value:
                return {'success': False, 'message': 'Only user moderators may manage user reports.'}
            elif mod_level == 1 and report.targetType != ReportTarget.USER.value:
                return {'success': False, 'message': 'Only content moderators may manage content reports.'}
            try:
                if report.status == ReportStatus.UNDER_REVIEW.value:
                    report.status = ReportStatus.RESOLVED.value
                    db.session.commit()
                    return {'success': True, 'message': 'Report resolved'}
                else:
                    return {'success': False, 'message': 'Report is not under review!'}
            except Exception as e:
                db.session.rollback()
                print(f"Error marking report as resolved: {e}")
                return {'success': False, 'message': f'Failed to mark report as resolved'}
        else:
            return {'success': False, 'message': 'Report not found'}

    def reject_report(self, report_id, mod_id, mod_level):
        report = Report.query.get(report_id)
          
        if report:
            if mod_level == 2 and report.targetType == ReportTarget.USER.value:
                return {'success': False, 'message': 'Only user moderators may manage user reports.'}
            elif mod_level == 1 and report.targetType != ReportTarget.USER.value:
                return {'success': False, 'message': 'Only content moderators may manage content reports.'}
            try:
                if report.status == ReportStatus.UNDER_REVIEW.value or report.status == ReportStatus.PENDING.value:
                    report.status = ReportStatus.REJECTED.value
                    db.session.commit()
                    return {'success': True, 'message': 'Report rejected'}
                else:
                    return {'success': False, 'message': 'Report is not pending review or further action!'}
            except Exception as e:
                db.session.rollback()
                print(f"Error marking report as rejected: {e}")
                return {'success': False, 'message': f'Failed to mark report as rejected'}
        else:
            return {'success': False, 'message': 'Report not found'}

    def remove_reported_post(self, report_id, mod_level):
        if mod_level != 2:  # Only content moderators can remove posts
            return {'success': False, 'message': 'Only content moderators may remove reported posts.'}
        
        report = Report.query.get(report_id)
        if report:
            if report.status != ReportStatus.UNDER_REVIEW.value:
                return {'success': False, 'message': 'The associated report must be marked as under review!'}
            try:
                post = Post.query.get(report.targetId)
                if not post:
                    return {'success': False, 'error': 'Post not found'}
            
                # Delete related comments first (if any)
                Comment.query.filter_by(postId=report.targetId).delete()
                
                # Delete related likes from junction table
                db.session.execute(
                    text("DELETE FROM post_likes WHERE post_id = :post_id"),
                    {"post_id": report.targetId}
                )
            
                # Delete the post and auto-resolve the report
                db.session.delete(post)
                report.status = ReportStatus.RESOLVED.value

                db.session.commit()
                return {'success': True, 'message': 'Post deleted successfully'}    
            except Exception as e:
                db.session.rollback()
                print(f"Error deleting post: {e}")
                return {'success': False, 'error': f'Failed to delete post: {str(e)}'}
        else:
            return {'success': False, 'message': 'The associated report was not found'}
        
    def remove_reported_comment(self, report_id, mod_level):
        if mod_level != 2:  # Only content moderators can remove posts
            return {'success': False, 'message': 'Only content moderators may remove reported comments.'}
        
        report = Report.query.get(report_id)
        if report:
            if report.status != ReportStatus.UNDER_REVIEW.value:
                return {'success': False, 'message': 'The associated report must be marked as under review!'}
            try:
                comment = Comment.query.get_or_404(report.targetId)
                
                # Delete the comment and auto-resolve the report
                db.session.delete(comment)
                report.status = ReportStatus.RESOLVED.value

                db.session.commit()
                return {'success': True, 'message': 'Comment deleted successfully'}    

            except Exception as e:
                db.session.rollback()
                print(f"Error deleting comment: {e}")
                return {'success': False, 'error': 'Failed to delete comment'}
        else:
            return {'success': False, 'message': 'The associated report was not found'}

    def disable_user(self, report_id, user_id, disabled_days, mod_id, mod_level):
        """
        Disable a user account for a specified number of days.
        Sets the disabledUntil field to now + days.
        """
        if mod_level != 1:  # Only user moderators can disable users
            return {'success': False, 'message': 'Only user moderators may disable users.'}
        
        report = Report.query.get(report_id)
        if report:
            if report.status != ReportStatus.UNDER_REVIEW.value:
                return {'success': False, 'message': 'The associated report must be marked as under review!'}
            user = User.query.get(user_id)
            try:
                # Check if disabled_days is a valid enum value
                valid_days = [e.value for e in UserDisableDays]
                if disabled_days not in valid_days:
                    return {'success': False, 'message': 'Invalid user disable duration.'}
                if user:
                    user.disabledUntil = datetime.utcnow() + timedelta(days=disabled_days)
                    report.status = ReportStatus.RESOLVED.value
                    db.session.commit()
                    return {'success': True, 'message': f'User disabled for {disabled_days} day(s).'}
                else:
                    return {'success': False, 'message': 'User not found.'}
            except Exception as e:
                db.session.rollback()
                print(f"Error disabling user: {e}")
                return {'success': False, 'error': 'Failed to disable user'}
        else:
            return {'success': False, 'message': 'The associated report was not found.'}
        
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
            return Report.query.filter_by(reportId=report_id, targetType=ReportTarget.USER.value).first()
        elif mod_level == 2:
            return Report.query.filter(
                Report.reportId == report_id,
                Report.targetType.in_([ReportTarget.COMMENT.value, ReportTarget.POST.value])
            ).first()

    def mod_level_check(self, mod_level):
        # Logic to check moderator level
        pass 

    def get_application_log(self, page=1, per_page=20):
        sql = """
        SELECT
            l.*,
            u.username AS user_username,
            CASE
                WHEN l.target_type = 'Post' AND l.action IN ('like_post', 'unlike_post')
                THEN (SELECT p_author.username FROM post p
                      JOIN user p_author ON p.authorId = p_author.userId
                      WHERE p.postId = l.target_id)
                WHEN l.target_type = 'Comment' AND l.action IN ('create_comment', 'update_comment', 'delete_comment')
                THEN (SELECT p_author.username FROM post p
                      JOIN user p_author ON p.authorId = p_author.userId
                      WHERE p.postId = (SELECT c.postId FROM comment c 
                            WHERE c.commentId = l.target_id
                        )
                )
                ELSE NULL
            END AS target_author_username,
            tu.username AS target_username
        FROM application_log l
        JOIN user u ON l.user_id = u.userId
        LEFT JOIN user tu ON l.target_type = 'User' AND l.target_id IS NOT NULL AND tu.userId = l.target_id
        ORDER BY l.timestamp DESC
        LIMIT :limit OFFSET :offset
        """
        offset = (page - 1) * per_page
        result = db.session.execute(text(sql), {"limit": per_page, "offset": offset})
        logs = result.fetchall()

        # Get total count for pagination
        count_sql = "SELECT COUNT(*) FROM application_log"
        total = db.session.execute(text(count_sql)).scalar()
        total_pages = (total + per_page - 1) // per_page

        return {
            "items": logs,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_num": page - 1,
            "next_num": page + 1,
        }
