from flask import request, jsonify, Blueprint, session
from models import db, User, Comment
from models.enums import ReportTarget, LogActionTypes
from backend.splunk_utils import log_to_splunk
from backend.profanity_helper import check_profanity
from backend.logging_utils import log_action

edit_comment_bp = Blueprint('edit_comment', __name__)

@edit_comment_bp.route('/<int:comment_id>', methods=['POST'])
def edit_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        comment = Comment.query.get_or_404(comment_id)
        if comment.authorId != session['user_id']:
            return jsonify({'success': False, 'error': 'You can only edit your own comments'}), 403
        
        data = request.get_json()
        new_content = data.get('content', '').strip()
        
        if not new_content:
            return jsonify({'success': False, 'error': 'Comment cannot be empty'}), 400
        
        if check_profanity(new_content):
            log_to_splunk("Comment", "Comment edit failed - profanity detected", username=db.session.get(User, session['user_id']).username, content=[new_content[:64], comment_id])
            return jsonify({'success': False, 'error': 'Profanity detected in comment'}), 400
        
        if len(new_content) > 500:
            log_to_splunk("Comment", "Comment edit failed - too long", username=db.session.get(User, session['user_id']).username, content=[new_content[:64], comment_id])
            return jsonify({'success': False, 'error': 'Comment too long (max 500 characters)'}), 400
        
        # Update comment
        comment.commentContent = new_content
        comment.mark_as_edited()  # Set edited_at timestamp
        
        # Create a new log entry
        log_action(session['user_id'], LogActionTypes.UPDATE_COMMENT.value, comment.commentId, ReportTarget.COMMENT.value)
        log_to_splunk("Comment", "Comment edited", username=db.session.get(User, session['user_id']).username, content=[new_content, comment_id])
        db.session.commit()
        return jsonify({'success': True, 'message': 'Comment updated successfully'})
        
    except Exception as e:
        print(f"Error editing comment: {e}")
        return jsonify({'success': False, 'error': 'Failed to edit comment'}), 500