from flask import Blueprint, redirect, url_for
from flask import session, flash
from managers import get_post_manager

post_manager = get_post_manager()

like_bp = Blueprint('like', __name__)

@like_bp.route('/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        flash('Please log in to like posts', 'warning')
        return redirect(url_for('login'))
    
    result = post_manager.like_post(session['user_id'], post_id)
    if result['success']:
        flash('Post liked successfully!', 'success')
    else:
        if result.get('already_liked'):
            flash('You have already liked this post', 'info')
        else:
            flash(result.get('error', 'Failed to like post'), 'danger')
    return redirect(url_for('home'))
