from flask import Flask, request, jsonify, Blueprint, render_template, redirect, url_for, session, flash
from models import db, Post, User, Report, Comment
from datetime import datetime, timezone
from models.enums import ReportStatus, ReportTarget, LogActionTypes
from backend.splunk_utils import log_to_splunk
from backend.profanity_helper import check_profanity
from backend.logging_utils import log_action
from managers import get_auth_manager, get_feed_manager, get_profile_manager, get_post_manager, get_moderator_manager

delete_comment_bp = Blueprint('delete_comment', __name__)

@delete_comment_bp.route('/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        comment = Comment.query.get_or_404(comment_id)
        post = Post.query.get_or_404(comment.postId)
        
        # Check if user owns the comment OR owns the post
        is_comment_owner = comment.authorId == session['user_id']
        is_post_owner = post.authorId == session['user_id']
        
        if not (is_comment_owner or is_post_owner):
            log_to_splunk("Comment", "Comment delete failed - not owner", username=db.session.get(User, session['user_id']).username, content=[comment_id, comment.commentContent])
            return jsonify({'success': False, 'error': 'You can only delete your own comments or comments on your posts'}), 403
        
        post_id = comment.postId
        
        # Delete the comment
        db.session.delete(comment)
        # Create a new log entry
        log_action(session['user_id'], LogActionTypes.DELETE_COMMENT.value, comment.commentId, ReportTarget.COMMENT.value)
        db.session.commit()
        
        # Get updated comment count
        comment_count = Comment.query.filter_by(postId=post_id, parentCommentId=None).filter(~Comment.commentContent.like('__LIKE__%')).count()
        log_to_splunk("Comment", "Comment deleted", username=db.session.get(User, session['user_id']).username, content=[comment_id, comment.commentContent])
        return jsonify({
            'success': True, 
            'message': 'Comment deleted successfully',
            'is_post_owner_deletion': is_post_owner and not is_comment_owner,
            'comment_count': comment_count
        })
        
    except Exception as e:
        print(f"Error deleting comment: {e}")
        log_to_splunk("Comment", "Comment delete failed", username=db.session.get(User, session['user_id']).username, content=[comment_id, comment.commentContent])
        return jsonify({'success': False, 'error': 'Failed to delete comment'}), 500