from flask import request, jsonify, Blueprint, redirect, url_for, session, flash
from models import db, Post, User, Report, Comment
from datetime import datetime, timezone
from models.enums import ReportStatus, ReportTarget, LogActionTypes
from backend.splunk_utils import log_to_splunk
from backend.profanity_helper import check_profanity
from backend.logging_utils import log_action
from managers import get_auth_manager, get_profile_manager, get_post_manager
from backend.limiter import limiter

api_bp = Blueprint('api', __name__)

profile_manager = get_profile_manager()
post_manager = get_post_manager()
auth_manager = get_auth_manager()

@api_bp.route('/report_post/<int:post_id>', methods=['POST'])
def api_report_post(post_id):
    if 'user_id' not in session:
        flash('Please log in to report posts', 'warning')
        return redirect(url_for('main.login'))
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User not logged in.'}), 401

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'success': False, 'error': 'Post not found.'}), 404

    if post.authorId == user_id:
        return jsonify({'success': False, 'error': 'Cannot report your own post.'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing JSON data.'}), 400

    reason = data.get('reason', '').strip()
    target_type_raw = data.get('targetType', '').strip()

    if not reason:
        return jsonify({'success': False, 'error': 'Report reason cannot be empty.'}), 400

    if not target_type_raw:
        return jsonify({'success': False, 'error': 'Report target type is required.'}), 400

    # Normalize input to match enum values (case insensitive)
    # This matches target_type_raw ignoring case to enum values
    target_type_map = {e.value.lower(): e for e in ReportTarget}
    target_type_enum = target_type_map.get(target_type_raw.lower())
    if not target_type_enum:
        return jsonify({'success': False, 'error': f'Invalid report target type: {target_type_raw}'}), 400

    # Prevent reporting yourself if target is User
    if target_type_enum == ReportTarget.USER and post.authorId == user_id:
        return jsonify({'success': False, 'error': 'Cannot report yourself.'}), 400

    existing_report = Report.query.filter_by(
        reportedBy=user_id,
        targetType=target_type_enum.value,  # Store string e.g. "Post"
        targetId=post_id
    ).first()

    if existing_report:
        return jsonify({'success': False, 'error': 'You have already reported this target.'}), 409

    try:
        print(f"Creating report: user_id={user_id}, post_id={post_id}, reason={reason}, target_type={target_type_enum.value}")
        new_report = Report(
            reportedBy=user_id,
            reason=reason,
            timestamp=datetime.now(timezone.utc),
            targetType=target_type_enum.value,
            targetId=post_id,
            status=ReportStatus.PENDING.value
        )

        db.session.add(new_report)
        db.session.commit()
        print(f"Report created successfully with ID: {new_report.reportId}")
        log_to_splunk("Report", "Post reported successfully", username=db.session.get(User, user_id).username, content=[post_id, reason, target_type_enum.value])
        return jsonify({'success': True, 'message': f'{target_type_enum.value} reported successfully.'})
    except Exception as e:
        db.session.rollback()
        print(f"Error creating report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

@api_bp.route('/follow/<int:user_id>', methods=['POST'])
def follow_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.send_follow_request(session['user_id'], user_id)
    log_to_splunk("Follow User", "User followed another user", username=db.session.get(User, session['user_id']).username, content=[db.session.get(User, user_id).username])
    return jsonify(result)

@api_bp.route('/unfollow/<int:user_id>', methods=['POST'])
def unfollow_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.unfollow_user(session['user_id'], user_id)
    log_to_splunk("Unfollow User", "User unfollowed another user", username=db.session.get(User, session['user_id']).username, content=[db.session.get(User, user_id).username])
    return jsonify(result)

@api_bp.route('/follow-request/cancel/<int:target_user_id>', methods=['POST'])
def cancel_follow_request(target_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.cancel_follow_request(session['user_id'], target_user_id)
    return jsonify(result)

@api_bp.route('/follow-request/respond/<int:requester_id>', methods=['POST'])
def respond_to_follow_request(requester_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    action = data.get('action')  # 'accept' or 'decline'
    
    if not action or action not in ['accept', 'decline']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    result = profile_manager.respond_to_follow_request(session['user_id'], requester_id, action)
    return jsonify(result)

@api_bp.route('/follow-requests')
def get_follow_requests():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.get_pending_follow_requests(session['user_id'])
    return jsonify(result)

@api_bp.route('/follow-status/<int:target_user_id>')
def get_follow_status(target_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.get_follow_status(session['user_id'], target_user_id)
    return jsonify(result)

@api_bp.route('/like/<int:post_id>', methods=['POST'])
def like_post_api(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = post_manager.like_post(session['user_id'], post_id)
    log_to_splunk("Like Post", "Post liked", username=db.session.get(User, session['user_id']).username, content=[post_id])
    return jsonify(result)

@api_bp.route('/unlike/<int:post_id>', methods=['POST'])
def unlike_post_api(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = post_manager.unlike_post(session['user_id'], post_id)
    log_to_splunk("Unlike Post", "Post unliked", username=db.session.get(User, session['user_id']).username, content=[post_id])
    return jsonify(result)

@api_bp.route('/followers/<int:user_id>')
def get_followers(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    followers = profile_manager.get_followers(user_id)
    # Flatten the user info for the frontend
    if followers.get('success'):
        followers_list = [
            {
                'userId': f['user']['user_id'],
                'username': f['user']['username'],
                'profilePicture': f['user']['profile_picture'],
                'bio': f['user']['bio'],
            } for f in followers['followers']
        ]
        return jsonify({'success': True, 'followers': followers_list})
    else:
        return jsonify({'success': False, 'error': followers.get('error', 'Unknown error')})

@api_bp.route('/following/<int:user_id>')
def get_following(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    following = profile_manager.get_following(user_id)
    if following.get('success'):
        following_list = [
            {
                'userId': f['user']['user_id'],
                'username': f['user']['username'],
                'profilePicture': f['user']['profile_picture'],
                'bio': f['user']['bio'],
            } for f in following['following']
        ]
        return jsonify({'success': True, 'following': following_list})
    else:
        return jsonify({'success': False, 'error': following.get('error', 'Unknown error')})

@api_bp.route('/profile/<int:user_id>', methods=['GET'])
def api_get_profile(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        'username': user.username,
        'email': user.email,
        'bio': user.bio,
        'location': user.location,
        'website': user.website
    })

@api_bp.route('/profile/<int:user_id>', methods=['PUT'])
def api_update_profile(user_id):
    user = User.query.get_or_404(user_id)

    data = request.get_json()
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    user.bio = data.get('bio', user.bio)
    user.location = data.get('location', user.location)
    user.website = data.get('website', user.website)

    db.session.commit()
    return jsonify({'message': 'Profile updated successfully'})

@api_bp.route('/posts', methods=['GET'])
def api_get_posts():
    posts = Post.query.all()
    return jsonify([{
        'postId': post.postId,
        'authorId': post.authorId,
        'title': post.title,
        'content': post.content,
        'timeOfPost': post.timeOfPost,
        'like': post.like,
        'image': post.image
    } for post in posts])

@api_bp.route('/comments/<int:post_id>', methods=['GET'])
def api_get_comments(post_id):
    comments = Comment.query.filter_by(postId=post_id).all()
    return jsonify([{
        'commentId': comment.commentId,
        'postId': comment.postId,
        'authorId': comment.authorId,
        'commentContent': comment.commentContent,
        'timestamp': comment.timestamp,
        'edited_at': comment.edited_at,
        'is_edited': comment.is_edited(),
        'parentCommentId': comment.parentCommentId
    } for comment in comments])

@api_bp.route('/search_users')
def api_search_users():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    query = request.args.get('q', '')
    if not query:
        return jsonify({'success': True, 'users': []})
    search_result = profile_manager.search_users(query, per_page=5)
    if search_result['success']:
        users = [
            {
                'user_id': u['user']['user_id'],
                'username': u['user']['username'],
                'profile_picture': u['user']['profile_picture']
            } for u in search_result['users']
        ]
        return jsonify({'success': True, 'users': users})
    else:
        return jsonify({'success': False, 'error': 'Search failed'})

@api_bp.route('/remove-follower/<int:follower_user_id>', methods=['POST'])
def remove_follower_api(follower_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    result = profile_manager.remove_follower(session['user_id'], follower_user_id)
    return jsonify(result)

@api_bp.route('/edit-post/<int:post_id>', methods=['POST'])
def api_edit_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    post = Post.query.get_or_404(post_id)
    if post.authorId != session['user_id']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()

    if not title or not content:
        return jsonify({'success': False, 'error': 'Title and caption required'}), 400
    
    if check_profanity(title) or check_profanity(content):
        return jsonify({'success': False, 'error': 'Watch your profanity'}), 400

    post.title = title
    post.content = content
    post.updatedAt = datetime.now(timezone.utc)
    # Create a new log entry
    log_action(session['user_id'], LogActionTypes.UPDATE_POST.value, post.postId, ReportTarget.POST.value)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Post updated', 'title': post.title, 'content': post.content, 'updatedAt': post.updatedAt.isoformat() if post.updatedAt else None})

@api_bp.route('/send-email-update-otp', methods=['POST'])
@limiter.limit('5 per minute')
def send_email_update_otp():
    """Send OTP to new email address for email update verification"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    new_email = data.get('new_email', '').strip()
    
    if not new_email:
        return jsonify({'success': False, 'error': 'New email is required'}), 400

    # Get current user
    current_user = User.query.filter_by(userId=session['user_id']).first()
    if not current_user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Check if new email is the same as current email
    if new_email.lower() == current_user.email.lower():
        return jsonify({'success': False, 'error': 'Cannot be same as current email'}), 400

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, new_email):
        return jsonify({'success': False, 'error': 'Invalid email format'}), 400

    # Check if email is already in use
    existing = User.query.filter(User.email == new_email).first()
    
    if not existing:
        try:
            auth_manager.generate_and_send_email_update_otp(session['user_id'], new_email)
        except Exception:
            log_to_splunk("Edit Profile", "Failed to send OTP for email update", username=db.session.get(User, session['user_id']).username, content=[new_email])
            pass

    return jsonify({'success': True, 'message': 'OTP sent if email is valid'})

@api_bp.route('/verify-email-update-otp', methods=['POST'])
@limiter.limit('5 per minute')
def verify_email_update_otp():
    """Verify OTP and update email address"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    new_email = data.get('new_email', '').strip()
    otp_code = data.get('otp_code', '').strip()
    
    if not new_email or not otp_code:
        return jsonify({'success': False, 'error': 'New email and OTP code are required'}), 400

    # Verify OTP for email update
    verify_result = auth_manager.verify_email_update_otp(session['user_id'], new_email, otp_code)
    if not verify_result['success']:
        return jsonify(verify_result), 400

    # Check if email is still available
    existing = User.query.filter(User.email == new_email).first()
    if existing:
        return jsonify({'success': False, 'error': 'Email already in use'}), 409

    # Update user's email
    user = User.query.filter_by(userId=session['user_id']).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    old_email = user.email
    user.email = new_email
    
    try:
        db.session.commit()
        log_to_splunk("Edit Profile", "Email updated successfully", username=user.username, content=[old_email, new_email])
        return jsonify({
            'success': True, 
            'message': 'Email updated successfully', 
            'old_email': old_email,
            'new_email': new_email
        })
    except Exception as e:
        db.session.rollback()
        log_to_splunk("Edit Profile", "Failed to update email", username=user.username, content=[old_email, new_email])
        return jsonify({'success': False, 'error': f'Failed to update email: {str(e)}'}), 500

@api_bp.route('/update-email', methods=['POST'])
def api_update_email():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    new_email = data.get('new_email', '').strip()
    if not new_email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, new_email):
        return jsonify({'success': False, 'error': 'Invalid email format'}), 400

    # Check uniqueness
    from models import User
    existing = User.query.filter(User.email == new_email).first()
    if existing:
        return jsonify({'success': False, 'error': 'Email already in use'}), 409

    user = User.query.filter_by(userId=session['user_id']).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    user.email = new_email
    try:
        log_action(session['user_id'], LogActionTypes.UPDATE_EMAIL.value, user.userId, None)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Email updated successfully', 'email': new_email})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Failed to update email: {str(e)}'}), 500

@api_bp.route('/send-password-change-otp', methods=['POST'])
@limiter.limit('5 per minute')
def send_password_change_otp():
    """Send OTP for password change verification"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    user = User.query.filter_by(userId=session['user_id']).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Only send OTP if user has OTP enabled
    if not user.otp_enabled:
        return jsonify({'success': False, 'error': 'OTP not enabled for this account'}), 400

    try:
        otp_result = auth_manager.generate_and_send_otp(user.email, 'password_change')
        if otp_result['success']:
            log_to_splunk("Edit Profile", "OTP sent for password change", username=user.username)
            return jsonify({'success': True, 'message': 'OTP sent to your email'})
        else:
            log_to_splunk("Edit Profile", "Failed to send OTP for password change", username=user.username)
            return jsonify({'success': False, 'error': 'Failed to send OTP'}), 500
    except Exception as e:
        log_to_splunk("Edit Profile", "Exception sending OTP for password change", username=user.username)
        return jsonify({'success': False, 'error': 'Failed to send OTP'}), 500




