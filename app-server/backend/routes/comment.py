from flask import Blueprint, request, jsonify, redirect, url_for, session
from datetime import datetime, timezone
from models import db, Post, Comment, User
from managers.authentication_manager import LogActionTypes, ReportTarget
from backend.splunk_utils import log_to_splunk
from backend.logging_utils import log_action


comment_bp = Blueprint('comment', __name__)

@comment_bp.route('/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    post = Post.query.get_or_404(post_id)
    content = request.form.get('comment')

    parent_comment_id = request.form.get('parentCommentId')

    # Convert '0' to None (top-level comment)
    if parent_comment_id in (None, '0', 0):
        parent_comment_id = None

    if content:
        new_comment = Comment(
            commentContent=content,
            authorId=session['user_id'],
            postId=post.postId,
            timestamp=datetime.now(timezone.utc),
            parentCommentId=parent_comment_id
        )
        db.session.add(new_comment)
        db.session.flush()

        log_action(session['user_id'], LogActionTypes.CREATE_COMMENT.value, new_comment.commentId, ReportTarget.COMMENT.value)
        log_to_splunk("Comment", "Commented on post", username=db.session.get(User, session['user_id']).username, content=[content, post_id])
        db.session.commit()
        
        # Check if this is an AJAX request by looking for XMLHttpRequest header
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                  'application/x-www-form-urlencoded' in request.headers.get('Content-Type', '') and \
                  'HX-Request' not in request.headers  # Ensure it's our AJAX and not HTMX
        
        if is_ajax:
            return jsonify({
                'success': True, 
                'message': 'Comment added successfully',
                'comment_count': Comment.query.filter_by(postId=post_id, parentCommentId=None).filter(~Comment.commentContent.like('__LIKE__%')).count()
            })
    
    return redirect(url_for('home'))