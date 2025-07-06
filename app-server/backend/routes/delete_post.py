from flask import jsonify, Blueprint, session, flash
from models import db, User
from backend.splunk_utils import log_to_splunk
from managers import get_post_manager

delete_post_bp = Blueprint('delete_post', __name__)

post_manager = get_post_manager()

@delete_post_bp.route('/<int:post_id>', methods=['POST'])
def delete_post_route(post_id):
    print(f"Delete post route called for post_id: {post_id}")
    print(f"Session user_id: {session.get('user_id')}")
    
    if 'user_id' not in session:
        print("User not logged in")
        return jsonify({'success': False, 'error': 'Please log in'}), 401
    
    try:
        result = post_manager.delete_post(post_id, session['user_id'])
        print(f"Delete result: {result}")
        
        if result.get('success'):
            flash('Post deleted successfully', 'success')
            log_to_splunk("Delete Post", "Post deleted successfully", username=db.session.get(User, session['user_id']).username, content=[post_id])
            return jsonify({'success': True, 'message': result.get('message', 'Post deleted successfully')})
        else:
            error_message = result.get('error', 'Failed to delete post')
            print(f"Delete failed: {error_message}")
            flash(error_message, 'danger')
            log_to_splunk("Delete Post", "Post deleted successfully", username=db.session.get(User, session['user_id']).username, content=[post_id])

            return jsonify({'success': False, 'error': error_message}), 403
    except Exception as e:
        print(f"Exception in delete route: {e}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

