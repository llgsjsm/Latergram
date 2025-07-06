from flask import Flask, request, jsonify, Blueprint, render_template, redirect, url_for
from flask import session, flash
from models import db, User
from managers import get_auth_manager, get_feed_manager, get_profile_manager, get_post_manager, get_moderator_manager


profile_bp = Blueprint('profile', __name__)

auth_manager = get_auth_manager()
feed_manager = get_feed_manager()
profile_manager = get_profile_manager()
post_manager = get_post_manager()
moderator_manager = get_moderator_manager()

@profile_bp.route('/')
@profile_bp.route('/<int:user_id>')
def profile(user_id=None):
    if 'mod_id' in session:
        return redirect(url_for('moderation.moderation'))
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # If no user_id provided, show current user's profile
    if user_id is None:
        user_id = session['user_id']
    
    try:
        # Get user info
        user = User.query.filter_by(userId=user_id).first()
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('main.home'))
        
        # Check if current user can view this profile

        visibility_check = profile_manager.can_view_profile(session['user_id'], user_id)
        if not visibility_check['can_view']:
            flash('Profile not found', 'danger')
            return redirect(url_for('main.home'))
        
        # Get user stats
        user_stats = profile_manager.get_user_stats(user_id)
        
        # Get user's posts only if visibility allows
        user_posts = []
        visibility_message = None
        if visibility_check['can_see_posts']:
            user_posts = profile_manager.get_user_posts(user_id, session['user_id'])
        else:
            if 'message' in visibility_check:
                visibility_message = visibility_check['message']
        
        # Check if current user is following this user and get follow status
        is_following = False
        follow_status = {'status': 'none', 'is_following': False, 'request_pending': False}
        if user_id != session['user_id']:
            follow_status_result = profile_manager.get_follow_status(session['user_id'], user_id)
            if follow_status_result.get('success'):
                follow_status = follow_status_result
                is_following = follow_status.get('is_following', False)
        
        # Check if this is the current user's profile
        is_own_profile = (user_id == session['user_id'])
        
        # Check which posts the current user has liked (optimized batch processing)
        liked_posts = {}
        comment_counts = {}
        if user_posts:
            try:
                post_ids = [post.postId for post in user_posts]
                liked_posts = post_manager.get_posts_with_likes_batch(post_ids, session['user_id'])
                comment_counts = feed_manager.get_comment_counts_batch(post_ids)
            except Exception as e:
                print(f"Error getting liked posts or comment counts: {e}")
                liked_posts = {post.postId: False for post in user_posts}
                comment_counts = {post.postId: 0 for post in user_posts}
        
        print(f"Profile data: user={user.username}, visibility={user.visibility}, stats={user_stats}, posts_count={len(user_posts) if user_posts else 0}")
        print(f"Visibility check: can_view={visibility_check['can_view']}, can_see_posts={visibility_check['can_see_posts']}, message={visibility_message}")
        
        # Get current logged-in user for navbar
        current_user = User.query.filter_by(userId=session['user_id']).first()
        
        return render_template('profile.html', 
                             profile_user=user,  # Change user to profile_user
                             current_user=current_user,  # Add current_user for navbar
                             user_stats=user_stats, 
                             user_posts=user_posts,
                             is_following=is_following,
                             follow_status=follow_status,
                             is_own_profile=is_own_profile,
                             liked_posts=liked_posts,
                             comment_counts=comment_counts,
                             visibility_message=visibility_message,
                             can_see_posts=visibility_check['can_see_posts'])
    
    except Exception as e:
        print(f"Error in profile route: {e}")
        flash('Error loading profile', 'danger')
        return redirect(url_for('main.home'))


