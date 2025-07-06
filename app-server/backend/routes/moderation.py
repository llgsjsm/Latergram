from flask import request, Blueprint, render_template, redirect, url_for, session, flash
from models import Post, User, Comment
from datetime import datetime, timezone
from backend.splunk_utils import log_to_splunk
from managers import get_moderator_manager

moderation_bp = Blueprint('moderation', __name__)
moderator_manager = get_moderator_manager()

# Moderator routes
@moderation_bp.route('/moderation')
def moderation():
    # moderator check
    if 'mod_id' not in session:
        return redirect(url_for('login'))

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    log_page = request.args.get('log_page', 1, type=int)
    per_page = 20

    try:
        # Pending reports for the first table
        reports = moderator_manager.get_report_queue(session['mod_level'])
        # All reports for history table, paginated
        all_reports_query = moderator_manager.get_all_reports_query(session['mod_level'])
        paginated_reports = all_reports_query.paginate(page=page, per_page=per_page, error_out=False)
        # Application user log for the log table
        application_log = moderator_manager.get_application_log(page=log_page, per_page=per_page)

    except Exception as e:
        print(f"Error getting reports: {e}")
        reports = []
        paginated_reports = None

    return render_template(
        'moderation.html',
        reports=reports,
        paginated_reports=paginated_reports,
        application_log=application_log,
    )

@moderation_bp.route('/moderation/report/<int:report_id>')
def report_detail(report_id):
    # moderator check
    if 'mod_id' not in session:
        return redirect(url_for('login'))

    report = moderator_manager.get_report_by_id(report_id, session['mod_level'])
    if report is None:
        flash('Report not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('moderation'))
    referenced = None
    referenced_type = None

    # Determine referenced object
    if report.targetType == "Post":
        referenced = Post.query.get(report.targetId)
        referenced_type = "post"
    elif report.targetType == "Comment":
        referenced = Comment.query.get(report.targetId)
        referenced_type = "comment"
    elif report.targetType == "User":
        referenced = User.query.get(report.targetId)
        referenced_type = "user"

    return render_template(
        'report_detail.html',
        report=report,
        referenced=referenced,
        referenced_type=referenced_type,
        now=datetime.now(timezone.utc)
    )

@moderation_bp.route('/moderation/action/<action>/<int:report_id>', methods=['POST'])
def moderation_action(action, report_id):
    # moderator check
    if 'mod_id' not in session:
        return redirect(url_for('login'))

    result = None
    if action == 'review':
        result = moderator_manager.review_report(report_id, session['mod_id'], session['mod_level'])
    elif action == 'resolve':
        result = moderator_manager.resolve_report(report_id, session['mod_id'], session['mod_level'])
    elif action == 'reject':
        result = moderator_manager.reject_report(report_id, session['mod_id'], session['mod_level'])
    elif action == 'disable_user':
        days = int(request.form.get('disable_days', 1))
        # Get the referenced user from the report
        report = moderator_manager.get_report_by_id(report_id, session['mod_level'])
        if report and report.targetType == "User":
            result = moderator_manager.disable_user(report.targetId, days, session['mod_id'], session['mod_level'])
    elif action == 'delete_post':
        result = moderator_manager.remove_reported_post(report_id, session['mod_level'])
    elif action == 'delete_comment':
        result = moderator_manager.remove_reported_comment(report_id, session['mod_level'])
    else:
        flash('Invalid action.', 'danger')
        return redirect(url_for('moderation'))

    if result and result.get('success'):
        log_to_splunk("Moderation Action", f"Report {report_id} action: {action}",
                      username=session.get('username'), content=[report_id, action])
        flash(result.get('message', 'Action completed.'), 'success')
    else:
        log_to_splunk("Moderation Action", f"Report {report_id} action: {action} failed",
                      username=session.get('username'), content=[report_id, action])
        flash(result.get('message', 'Action failed.'), 'danger')
    return redirect(url_for('moderation'))