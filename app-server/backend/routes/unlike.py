from flask import Blueprint, redirect, url_for
from flask import session, flash
from managers import get_post_manager

post_manager = get_post_manager()

unlike_bp = Blueprint('unlike', __name__)

@unlike_bp.route('/<int:post_id>', methods=['POST'])
def unlike_post(post_id):
    if 'user_id' not in session:
        flash('Please log in to unlike posts', 'warning')
        return redirect(url_for('main.login'))
    
    result = post_manager.unlike_post(session['user_id'], post_id)
    if result['success']:
        flash('Post unliked successfully!', 'success')
    else:
        if result.get('not_liked'):
            flash('You have not liked this post', 'info')
        else:
            flash(result.get('error', 'Failed to unlike post'), 'danger')
    return redirect(url_for('main.home'))
