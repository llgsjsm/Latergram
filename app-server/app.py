from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import re, os, uuid
from dotenv import load_dotenv 
from models import db, Post, Comment, User, Report, Moderator
from managers.authentication_manager import bcrypt
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, or_
import firebase_admin
from firebase_admin import credentials, storage
from models.enums import ReportStatus, ReportTarget, LogActionTypes
from flask_limiter import Limiter

# Use the optimized singleton managers
from managers import get_auth_manager, get_feed_manager, get_profile_manager, get_post_manager, get_moderator_manager

# Backend imports
from backend.splunk_utils import get_real_ip, log_to_splunk
from backend.captcha_utils import verify_recaptcha
from backend.profanity_helper import check_profanity
# from backend.opennsfw import is_image_safe

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Enable debug mode for development (auto-reload on code changes)
app.debug = True

DB_USER = os.environ.get('DB_USER', '') 
DB_PASSWORD = os.environ.get('DB_PASSWORD', '') 
DB_HOST = os.environ.get('DB_HOST', '')
DB_PORT = os.environ.get('DB_PORT', '')
DB_NAME = os.environ.get('DB_NAME', '')
BUCKET = os.environ.get('BUCKET', '')
FILE_LOCATION = os.environ.get('FILE_LOCATION','')
IS_TESTING = os.getenv("IS_TESTING", "false").lower() == "true"

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Database connection pool optimizations
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'max_overflow': 20
}

db.init_app(app)
bcrypt.init_app(app)

auth_manager = get_auth_manager()
feed_manager = get_feed_manager()
profile_manager = get_profile_manager()
post_manager = get_post_manager()
moderator_manager = get_moderator_manager()

if not IS_TESTING:
    if FILE_LOCATION and BUCKET:
        cred = credentials.Certificate(FILE_LOCATION)
        firebase_admin.initialize_app(cred, {
            'storageBucket': BUCKET
        })
        bucket = storage.bucket()

# Redis Rate limiting
storage_uri = "redis://10.20.0.5:6379" if IS_TESTING else None
limiter = Limiter(
    key_func=get_real_ip,
    app=app,
    default_limits=[],
    storage_uri=storage_uri
)

def ensure_firebase_initialized():
    global bucket
    if not firebase_admin._apps:
        file_location = os.environ.get('FILE_LOCATION', '')
        bucket_name = os.environ.get('BUCKET', '')
        if file_location and bucket_name:
            cred = credentials.Certificate(file_location)
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
        else:
            raise RuntimeError('Firebase FILE_LOCATION or BUCKET not set in environment variables')
    bucket = storage.bucket()

def log_action(user_id: int, action: str, target_id: int, target_type: str):
        """
        Logs an action to the application_log table.
        """
        sql = """
        INSERT INTO application_log 
        (user_id, action, target_id, target_type, timestamp)
        VALUES (:user_id, :action, :target_id, :target_type, NOW())
        """

        db.session.execute(text(sql), {
            "user_id": user_id,
            "action": action,
            "target_id": target_id,
            "target_type": target_type,
        })

@app.route('/home')
def home():
    # log_to_splunk("Visited /home")
    if 'user_id' not in session and 'mod_id' not in session:
        return redirect(url_for('login'))
    
    # redirect moderators to their dashboard
    if 'mod_id' in session:
        return redirect(url_for('moderation'))
    
    try:
        posts = feed_manager.generate_feed(session['user_id'])
    except Exception as e:
        print(f"Error getting posts: {e}")
        posts = []
    
    # Get all required data in parallel to reduce sequential database calls
    user_stats = {'posts_count': 0, 'followers_count': 0, 'following_count': 0}
    suggested_users = []
    pending_requests = []
    liked_posts = {}
    
    try:
        # Get user stats with caching
        user_stats = profile_manager.get_user_stats_cached(session['user_id'])
    except Exception as e:
        print(f"Error getting user stats: {e}")
    
    try:
        # Get suggested users (users not followed) with caching
        suggested_users = profile_manager.get_suggested_users_cached(session['user_id'])
    except Exception as e:
        print(f"Error getting suggested users: {e}")
    
    try:
        # Get pending follow requests
        follow_requests = profile_manager.get_pending_follow_requests(session['user_id'])
        pending_requests = follow_requests.get('requests', []) if follow_requests.get('success') else []
    except Exception as e:
        print(f"Error getting follow requests: {e}")
    
    # Check which posts the current user has liked (optimized batch processing)
    try:
        if posts:
            post_ids = [post.postId for post in posts]
            liked_posts = post_manager.get_posts_with_likes_batch(post_ids, session['user_id'])
            # Also get comment counts for all posts
            comment_counts = feed_manager.get_comment_counts_batch(post_ids)
        else:
            liked_posts = {}
            comment_counts = {}
    except Exception as e:
        print(f"Error getting liked posts or comment counts: {e}")
        liked_posts = {post.postId: False for post in posts} if posts else {}
        comment_counts = {post.postId: 0 for post in posts} if posts else {}

    return render_template('home.html', posts=posts, user_stats=user_stats, suggested_users=suggested_users, liked_posts=liked_posts, pending_requests=pending_requests, comment_counts=comment_counts)

@app.route('/')
def hello_world():
    log_to_splunk("Landing","Browsed to landing page")
    return redirect(url_for('home'))

@app.route('/reset_password_portal', methods=['GET', 'POST'])
def reset_password_portal():
    log_to_splunk("Reset Password", "Visited reset password portal")
    return render_template('reset_password.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    log_to_splunk("Login", "Visited login page")
    if request.method == 'POST':
        # Check if it's a JSON request (AJAX)
        if request.is_json:
            data = request.get_json()

            # Captcha JSON
            token = data.get('g-recaptcha-response', '')
            if not verify_recaptcha(token, request.remote_addr):
                return jsonify({'success': False, 'error': 'Captcha verification failed'}), 400
            
            if data.get('action') == 'login':
                email = data.get('email', '')
                password = data.get('password', '')
                
                if email and password:
                    # Check if user exists in User table first
                    user = User.query.filter(
                        or_(User.username == email, User.email == email)
                    ).first()
                    
                    if user:
                        # Use OTP login if user has it enabled, otherwise use normal login
                        if getattr(user, 'otp_enabled', True):  # Default to True (enabled)
                            result = auth_manager.login_with_otp(email, password)
                            if not result['success']:
                                log_to_splunk("Login", "Failed valid user login attempt", username=email)
                        else:
                            # Use normal login for user
                            result = auth_manager.login(email, password)
                            if result['success']:
                                session['user_id'] = result['user']['user_id']
                                log_to_splunk("Login", "User logged in", username=result['user']['username'])
                            else:
                                log_to_splunk("Login", "Failed valid user login attempt", username=email)
                        return jsonify(result)
                    else:
                        # Check if it's a moderator
                        moderator = Moderator.query.filter(
                            or_(Moderator.username == email, Moderator.email == email)
                        ).first()
                        
                        if moderator:
                            # Use OTP login for moderators (always enabled for moderators)
                            result = auth_manager.moderator_login_with_otp(email, password)
                            if result['success']:
                                session['mod_id'] = result['mod_id']
                                session['mod_level'] = result['mod_level']
                                log_to_splunk("Moderator", "Moderator logged in with OTP", username=moderator.username)
                            else:
                                log_to_splunk("Moderator", "Failed valid moderator login attempt", username=email)
                            return jsonify(result)
                        else:
                            log_to_splunk("Login", "Failed login attempt", username=email)
                            return jsonify({'success': False, 'error': 'Error logging in. Try again.'})
                else:
                    return jsonify({'success': False, 'error': 'Please enter both email and password'})
        else:
            # Traditional form submission (fallback)
            if request.form.get('login-btn') is not None:
                email = request.form.get('email', '')
                password = request.form.get('password', '')

                # Captcha Form 
                token = request.form.get('g-recaptcha-response', '')
                if not verify_recaptcha(token, request.remote_addr):
                    flash('Captcha verification failed.', 'danger')
                    return render_template('login.html')
                
                if email and password:
                    result = auth_manager.login(email, password)
                    if result['success']:
                        if result['login_type'] == 'moderator':
                            session['mod_id'] = result['moderator']['mod_id']
                            session['mod_level'] = result['moderator']['mod_level']
                            flash('Login successful!', 'success')
                            log_to_splunk("Login", "Moderator logged in", username=result['user']['username'])
                            return redirect(url_for('moderation'))
                        else:
                            session['user_id'] = result['user']['user_id']
                            flash('Login successful!', 'success')
                            log_to_splunk("Login", "User logged in", username=result['user']['username'])
                            return redirect(url_for('home'))
                    else:
                        log_to_splunk("Login", "Failed login attempt", username=email)
                        flash(f'Login Unsuccessful. {result["error"]}', 'danger')
                else:
                    flash('Please enter both email and password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    log_to_splunk("Register", "Visited registration page")
    if request.method == 'POST':
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
    
        if not username or not email or not password:
            return jsonify({'success': False, 'error': 'Username, email, and password are required.'}), 400

        if check_profanity(username):
            return jsonify({'success': False, 'error': 'Watch your profanity'}), 400

        token = data.get('g-recaptcha-response', '')
        if not verify_recaptcha(token, request.remote_addr):
            return jsonify({'success': False, 'error': 'Captcha verification failed'}), 400

        init_result = auth_manager.initiate_registration(username, email, password)
        if not init_result.get('success'):
            return jsonify({'success': False, 'errors': init_result.get('errors', ['An unknown error occurred.'])}), 400
        
        otp_result = auth_manager.generate_and_send_otp(email, otp_type='registration')
        if not otp_result.get('success'):
            return jsonify({'success': False, 'error': otp_result.get('error', 'Failed to send OTP.')})

        session['registration_data'] = {
            'username': username,
            'email': email,
            'password_hash': init_result['password_hash'],
            'otp': otp_result['otp_code'], 
            'otp_expiry': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        }
        
        return jsonify({'success': True, 'email': email})
    return render_template('register.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], LogActionTypes.LOGOUT.value, None, ReportTarget.USER.value)
        user = User.query.filter_by(userId=session['user_id']).first()
        log_to_splunk("Logout", "User logged out", username=user.username)
        session.pop('user_id', None)
    else:
        try:
            mod = Moderator.query.filter_by(modID=session['mod_id']).first()
            log_to_splunk("Logout", "Moderator logged out", username=mod.username)
            session.pop('mod_id', None)
        except KeyError:
            log_to_splunk("Logout", "Weird logout attempt")
            return redirect(url_for('login'))
        
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/create-post', methods=['GET', 'POST'])
def create_post():
    ensure_firebase_initialized()
    # moderators cannot create posts
    if 'mod_id' in session:
        return redirect(url_for('moderator'))
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        # visibility = request.form.get('visibility', 'followers')

        if not title or not content:
            log_to_splunk("Create Post", "Post creation failed - missing title or content", username=db.session.get(User, session['user_id']).username)
            return jsonify({'success': False, 'error': 'Title and content are required.'}), 400

        if check_profanity(title) or check_profanity(content):
            log_to_splunk("Create Post", "Post creation failed - profanity detected", username=db.session.get(User, session['user_id']).username)
            return jsonify({'success': False, 'error': 'Profanity detected in title or content.'}), 400

        image_url = "https://fastly.picsum.photos/id/404/200/300.jpg?hmac=..."  #default 

        # Handle file upload
        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            blob = storage.bucket().blob(f'posts/{uuid.uuid4()}_{filename}')
            blob.upload_from_file(image_file, content_type=image_file.content_type)
            blob.make_public()
            image_url = blob.public_url
        else:
            log_to_splunk("Create Post", "Post created failed", username=db.session.get(User, session['user_id']).username)
            return jsonify({'success': False, 'error': 'Image upload failed or no image provided.'}), 400

        # Check if image is safe
        # is_image_safe_result = is_image_safe(image_url)
        # if not is_image_safe_result:
        #     log_to_splunk("Create Post", "Post creation failed - unsafe image", username=db.session.get(User, session['user_id']).username)
        #     return jsonify({'success': False, 'error': 'Image is not safe.'}), 400

        # Create likes record
        result = db.session.execute(
            text("INSERT INTO likes (user_userId, timestamp) VALUES (:user_id, NOW())"),
            {"user_id": session['user_id']}
        )

        db.session.flush()
        likes_id = result.lastrowid

        new_post = Post(
            authorId=session['user_id'],
            title=title,
            content=content,
            timeOfPost=datetime.now(timezone.utc),
            like=0,
            likesId=likes_id,
            image=image_url
        )

        db.session.add(new_post)
        db.session.flush()

        # Create a new log entry
        log_action(session['user_id'], LogActionTypes.CREATE_POST.value, new_post.postId, ReportTarget.POST.value)
        db.session.commit()
        log_to_splunk("Create Post", "Post created successfully", username=db.session.get(User, session['user_id']).username, content=[title, content, image_url])
        flash("Post created successfully!", "success")
        return redirect(url_for('home'))
    return render_template('create_post.html')

@app.route('/api/report_post/<int:post_id>', methods=['POST'])
def api_report_post(post_id):
    if 'user_id' not in session:
        flash('Please log in to report posts', 'warning')
        return redirect(url_for('login'))
    
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
    log_to_splunk("Report", "Post reported successfully", username=db.session.get(User, user_id).username, content=[post_id, reason, target_type_enum.value])
    return jsonify({'success': True, 'message': f'{target_type_enum.value} reported successfully.'})

@app.route('/like/<int:post_id>', methods=['POST'])
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

@app.route('/unlike/<int:post_id>', methods=['POST'])
def unlike_post(post_id):
    if 'user_id' not in session:
        flash('Please log in to unlike posts', 'warning')
        return redirect(url_for('login'))
    
    result = post_manager.unlike_post(session['user_id'], post_id)
    if result['success']:
        flash('Post unliked successfully!', 'success')
    else:
        if result.get('not_liked'):
            flash('You have not liked this post', 'info')
        else:
            flash(result.get('error', 'Failed to unlike post'), 'danger')
    return redirect(url_for('home'))

@app.route('/comment/<int:post_id>', methods=['POST'])
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

@app.route('/edit_comment/<int:comment_id>', methods=['POST'])
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

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
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

@app.route('/delete-post/<int:post_id>', methods=['POST'])
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

# Profile Routes
@app.route('/profile')
@app.route('/profile/<int:user_id>')
def profile(user_id=None):
    if 'mod_id' in session:
        return redirect(url_for('moderation'))
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # If no user_id provided, show current user's profile
    if user_id is None:
        user_id = session['user_id']
    
    try:
        # Get user info
        user = User.query.filter_by(userId=user_id).first()
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('home'))
        
        # Check if current user can view this profile

        visibility_check = profile_manager.can_view_profile(session['user_id'], user_id)
        if not visibility_check['can_view']:
            flash('Profile not found', 'danger')
            return redirect(url_for('home'))
        
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
        return redirect(url_for('home'))

@app.route('/api/follow/<int:user_id>', methods=['POST'])
def follow_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.send_follow_request(session['user_id'], user_id)
    log_to_splunk("Follow User", "User followed another user", username=db.session.get(User, session['user_id']).username, content=[db.session.get(User, user_id).username])
    return jsonify(result)

@app.route('/api/unfollow/<int:user_id>', methods=['POST'])
def unfollow_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.unfollow_user(session['user_id'], user_id)
    log_to_splunk("Unfollow User", "User unfollowed another user", username=db.session.get(User, session['user_id']).username, content=[db.session.get(User, user_id).username])
    return jsonify(result)

@app.route('/api/follow-request/cancel/<int:target_user_id>', methods=['POST'])
def cancel_follow_request(target_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.cancel_follow_request(session['user_id'], target_user_id)
    return jsonify(result)

@app.route('/api/follow-request/respond/<int:requester_id>', methods=['POST'])
def respond_to_follow_request(requester_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    action = data.get('action')  # 'accept' or 'decline'
    
    if not action or action not in ['accept', 'decline']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    result = profile_manager.respond_to_follow_request(session['user_id'], requester_id, action)
    return jsonify(result)

@app.route('/api/follow-requests')
def get_follow_requests():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.get_pending_follow_requests(session['user_id'])
    return jsonify(result)

@app.route('/api/follow-status/<int:target_user_id>')
def get_follow_status(target_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.get_follow_status(session['user_id'], target_user_id)
    return jsonify(result)

@app.route('/api/like/<int:post_id>', methods=['POST'])
def like_post_api(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = post_manager.like_post(session['user_id'], post_id)
    log_to_splunk("Like Post", "Post liked", username=db.session.get(User, session['user_id']).username, content=[post_id])
    return jsonify(result)

@app.route('/api/unlike/<int:post_id>', methods=['POST'])
def unlike_post_api(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = post_manager.unlike_post(session['user_id'], post_id)
    log_to_splunk("Unlike Post", "Post unliked", username=db.session.get(User, session['user_id']).username, content=[post_id])
    return jsonify(result)

@app.route('/update-otp-setting', methods=['POST'])
def update_otp_setting():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user = User.query.filter_by(userId=session['user_id']).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    try:
        data = request.get_json()
        otp_enabled = data.get('otp_enabled', True)
        confirmation = data.get('confirmation', False)
        
        # If disabling OTP, require explicit confirmation
        if not otp_enabled and user.otp_enabled and not confirmation:
            return jsonify({
                'success': False, 
                'error': 'Confirmation required to disable MFA',
                'requires_confirmation': True
            }), 400
        
        # Update the user's OTP preference
        user.otp_enabled = bool(otp_enabled)
        db.session.commit()
        log_to_splunk("Edit Profile", "Updated OTP setting", username=user.username)
        return jsonify({
            'success': True, 
            'message': f'OTP authentication {"enabled" if otp_enabled else "disabled"}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to update OTP setting'}), 500

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    ensure_firebase_initialized()
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(userId=session['user_id']).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        display_name = request.form.get('display_name')
        bio = request.form.get('bio')
        visibility = request.form.get('visibility')

        # Handle profile picture upload
        profile_pic_file = request.files.get('profile_picture')
        profile_pic_url = user.profilePicture  # Default to current
        if profile_pic_file and profile_pic_file.filename != '':
            filename = secure_filename(profile_pic_file.filename)
            blob = storage.bucket().blob(f'profile_pics/{uuid.uuid4()}_{filename}')
            blob.upload_from_file(profile_pic_file, content_type=profile_pic_file.content_type)
            blob.make_public()
            profile_pic_url = blob.public_url

        result = profile_manager.update_profile(
            session['user_id'], 
            display_name=display_name, 
            bio=bio, 
            visibility=visibility,
            profile_picture_url=profile_pic_url
        )
        
        if result['success']:
            flash('Profile updated successfully!', 'success')
            log_to_splunk("Edit Profile", "Profile updated successfully", username=user.username, content=[display_name, bio, visibility, profile_pic_url])
            return redirect(url_for('profile'))
        else:
            log_to_splunk("Edit Profile", "Failed to update profile" + result['error'], username=user.username)
            flash(f'Error updating profile: {result["error"]}', 'danger')
    
    return render_template('edit_profile.html', user=user)

@app.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    otp_code = request.form.get('otp_code')
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'error': 'New passwords do not match'}), 400
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Verify OTP if user has OTP enabled
    if user.otp_enabled:
        if not otp_code:
            return jsonify({'success': False, 'error': 'OTP code is required for password change'}), 400
        
        otp_result = auth_manager.verify_otp(user.email, otp_code, 'password_change')
        if not otp_result['success']:
            log_to_splunk("Edit Profile", "Failed OTP verification for password change", username=user.username)
            return jsonify({'success': False, 'error': 'Invalid OTP code'}), 400

    # Change the password
    result = profile_manager.change_password(session['user_id'], current_password, new_password)
    if (not result['success']):
        log_to_splunk("Edit Profile", "Failed to change password", username=user.username)
        return jsonify({'success': False, 'error': result['error']}), 400

    
    if result['success']:
        log_to_splunk("Edit Profile", "Password changed successfully", username=user.username)
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    else:
        log_to_splunk("Edit Profile", "Failed to change password", username=user.username)
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/followers/<int:user_id>')
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

@app.route('/api/following/<int:user_id>')
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

@app.route('/api/profile/<int:user_id>', methods=['GET'])
def api_get_profile(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        'username': user.username,
        'email': user.email,
        'bio': user.bio,
        'location': user.location,
        'website': user.website
    })

@app.route('/api/profile/<int:user_id>', methods=['PUT'])
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

@app.route('/api/posts', methods=['GET'])
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

@app.route('/api/comments/<int:post_id>', methods=['GET'])
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

@app.route('/search', methods=['GET'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    query = request.args.get('q', '')
    results = []
    if query:
        search_result = profile_manager.search_users(query)
        if search_result['success']:
            results = search_result['users']
    return redirect(url_for('home'))

@app.route('/api/search_users')
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

@app.route('/delete-account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    password = request.form.get('password')
    confirm_deletion = request.form.get('confirm_deletion')
    
    # Validate inputs
    if not password or not confirm_deletion or confirm_deletion.strip() != 'DELETE':
        log_to_splunk("Delete Account", "Failed to delete account due to incorrect fields", username=session.get('user_id', 'Unknown'))
        return jsonify({'success': False, 'error': 'All correct fields required for account deletion'}), 400
    
    # if confirm_deletion != 'DELETE':
        return jsonify({'success': False, 'error': 'Please type DELETE to confirm account deletion'}), 400
    
    # Delete the account
    result = profile_manager.delete_account(session['user_id'], password)
    
    if result['success']:
        log_to_splunk("Delete Account", "Account deleted successfully", username=session.get['user_id', 'Unknown'])

        # Clear the session after successful deletion
        session.clear()
        return jsonify({'success': True, 'message': 'Account deleted successfully'})
    else:
        log_to_splunk("Delete Account", "Failed to delete account", username=session.get('user_id', 'Unknown'))
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/remove-follower/<int:follower_user_id>', methods=['POST'])
def remove_follower_api(follower_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    result = profile_manager.remove_follower(session['user_id'], follower_user_id)
    return jsonify(result)

@app.route('/remove-profile-picture', methods=['POST'])
def remove_profile_picture():
    ensure_firebase_initialized()
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message='Not logged in'), 401
        return redirect(url_for('login'))

    user = User.query.filter_by(userId=session['user_id']).first()
    if not user or not user.profilePicture:
        msg = 'No profile picture to remove.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg)
        flash(msg, 'warning')
        return redirect(url_for('edit_profile'))

    # Delete from Firebase Storage if exists and is a Firebase URL
    if user.profilePicture and 'appspot.com' in user.profilePicture:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(user.profilePicture)
            blob_name = parsed.path.lstrip('/')
            blob = storage.bucket().blob(blob_name)
            blob.delete()
        except Exception as e:
            print(f"Error deleting profile picture from storage: {e}")

    # Remove from user profile and commit
    user.profilePicture = ''  # Set to empty string, not None
    try:
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=True)
        flash('Profile picture removed.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error committing profile picture removal: {e}")

        # if 'NOT NULL' in str(e):
        #     print("\n\nYour profilePicture column is NOT NULL. Run this SQL in MySQL Workbench to fix it:\nALTER TABLE user MODIFY profilePicture varchar(255) DEFAULT NULL;\n")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message='Database error')
        flash('Error removing profile picture.', 'danger')
    return redirect(url_for('edit_profile'))

@app.route('/load_comments/<int:post_id>')
def load_comments(post_id):
    """AJAX endpoint to load comments for a specific post"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Get post information to check ownership
        post = Post.query.get_or_404(post_id)
        
        # Get comments for the post with author information
        comments_query = text("""
            SELECT c.commentId, c.commentContent, c.timestamp, c.edited_at, c.parentCommentId,
                   u.username, u.profilePicture
            FROM comment c
            JOIN user u ON c.authorId = u.userId
            WHERE c.postId = :post_id
            AND c.parentCommentId IS NULL
            AND NOT c.commentContent LIKE '__LIKE__%'
            ORDER BY c.timestamp DESC
            LIMIT 10
        """)
        
        result = db.session.execute(comments_query, {"post_id": post_id}).fetchall()
        
        comments = []
        for row in result:
            # Format timestamps
            timestamp_str = row.timestamp.strftime('%b %d, %Y at %I:%M %p') if row.timestamp else ''
            edited_at_str = row.edited_at.strftime('%b %d, %Y at %I:%M %p') if row.edited_at else None
            
            comments.append({
                'commentId': row.commentId,
                'content': row.commentContent,
                'timestamp': timestamp_str,
                'edited_at': edited_at_str,
                'is_edited': row.edited_at is not None,
                'author': {
                    'username': row.username,
                    'profilePicture': row.profilePicture or ''
                }
            })
        
        return jsonify({
            'success': True, 
            'comments': comments,
            'post_owner_id': post.authorId,
            'current_user_id': session['user_id']
        })
    except Exception as e:
        print(f"Error loading comments: {e}")
        return jsonify({'error': 'Failed to load comments'}), 500

@app.route('/admin/fix-visibility', methods=['POST'])
def fix_visibility_case():
    """Admin endpoint to fix visibility case for existing users"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    # Add admin check here if needed
    result = profile_manager.fix_visibility_case()
    return jsonify(result)

# Moderator routes
@app.route('/moderation')
def moderation():
    # moderator check
    if 'mod_id' not in session:
        return redirect(url_for('login'))

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    log_page = request.args.get('log_page', 1, type=int)
    per_page = 10

    try:
        # Pending reports for the first table
        reports = moderator_manager.get_report_queue(session['mod_level'])
        # All reports for history table, paginated
        all_reports_query = moderator_manager.get_all_reports_query(session['mod_level'])
        paginated_reports = all_reports_query.paginate(page=page, per_page=per_page, error_out=False)
        # Application user log for the log table
        moderation_log = moderator_manager.get_moderation_log(page=log_page, per_page=per_page)

    except Exception as e:
        print(f"Error getting reports: {e}")
        reports = []
        paginated_reports = None

    return render_template(
        'moderation.html',
        reports=reports,
        paginated_reports=paginated_reports,
        moderation_log=moderation_log,
    )

@app.route('/moderation/report/<int:report_id>')
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

@app.route('/moderation/action/<action>/<int:report_id>', methods=['POST'])
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

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.filter_by(userId=session['user_id']).first()
    return dict(user=user)

@app.route('/api/edit-post/<int:post_id>', methods=['POST'])
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

@app.route('/api/send-email-update-otp', methods=['POST'])
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

@app.route('/api/verify-email-update-otp', methods=['POST'])
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

@app.route('/api/update-email', methods=['POST'])
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

@app.route('/forgot-password', methods=['POST'])
@limiter.limit('5 per minute')
def forgot_password():
    data = request.get_json()
    email = data.get('email', '')
    # Backend email validation -- remove if already has existing validation somewhere...
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    if not email:
        return jsonify({'success': False, 'error': 'Email is required'})

    if not email_regex.match(email):
        log_to_splunk("Reset Password", "Invalid email input", username=email)
        return jsonify({'success': False, 'error': 'Invalid email. Please enter a valid email address.'})

    # Try Moderator first
    user = Moderator.query.filter_by(email=email).first()
    if user:
        auth_manager.initiate_moderator_password_reset(email)
    else:
        # Try regular User
        user = User.query.filter_by(email=email).first()
        if user:
            auth_manager.initiate_password_reset(email)
    log_to_splunk("Reset Password", "Password reset initiated", username=email)
    return jsonify({'success': True, 'message': 'If an account with that email exists, an OTP has been sent.'
    })

@app.route('/resend-login-otp', methods=['POST'])
@limiter.limit('5 per minute')
def resend_login_otp():
    data = request.get_json()
    email = data.get('email', '')
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'})
    
    # Try Moderator first
    user = Moderator.query.filter_by(email=email).first()
    if user:
        result = auth_manager.generate_and_send_moderator_otp(email)
    else:
        # Try regular User
        user = User.query.filter_by(email=email).first()
        if user:
            result = auth_manager.generate_and_send_otp(email)
    if result['success']:
        log_to_splunk("Login", "OTP resent successfully", username=email)
    else:
        log_to_splunk("Login OTP", "Failed to resend OTP", username=email)
    return jsonify({'success': True, 'message': 'If an account with that email exists, a reset link has been sent.'
    })

@app.route('/verify-reset-otp', methods=['POST'])
@limiter.limit('5 per minute')
def verify_reset_otp():
    data = request.get_json()
    email = data.get('email', '')
    otp_code = data.get('otp_code', '')
    
    if not email or not otp_code:
        return jsonify({'success': False, 'error': 'Email and OTP code are required'})
    
    user = Moderator.query.filter_by(email=email).first()
    if user:
        result = auth_manager.verify_moderator_otp(email, otp_code, 'password_reset')
    else:
        user = User.query.filter_by(email=email).first()
        if user:
            result = auth_manager.verify_otp(email, otp_code, 'password_reset')

    if result['success']:
        log_to_splunk("Reset Password", "Succesful OTP verification for password reset", username=email)
    else:
        log_to_splunk("Reset Password", "Failed OTP verification for password reset", username=email)
    return jsonify(result)

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email', '')
    otp_code = data.get('otp_code', '')
    new_password = data.get('new_password', '')
    
    if not email or not otp_code or not new_password:
        return jsonify({'success': False, 'error': 'Email, OTP code, and new password are required'})
    
    user = Moderator.query.filter_by(email=email).first()
    if user:
        result = auth_manager.reset_moderator_password_with_otp(email, otp_code, new_password)
    else:
        user = User.query.filter_by(email=email).first()
        if user:
            result = auth_manager.reset_password_with_otp(email, otp_code, new_password)
    
    if result['success']:
        log_to_splunk("Reset Password", "Password reset successful", username=email)
    else:
        log_to_splunk("Reset Password", "Password reset failed - " + result['error'], username=email)
    return jsonify(result)

@app.route('/verify-login-otp', methods=['POST'])
@limiter.limit('5 per minute')
def verify_login_otp():
    data = request.get_json()
    email = data.get('email', '')
    otp_code = data.get('otp_code', '')

    if not email or not otp_code:
        return jsonify({'success': False, 'error': 'Email and OTP code are required'})
    
    user = Moderator.query.filter_by(email=email).first()
    if user:
        result = auth_manager.complete_moderator_login_with_otp(email, otp_code)
    else:
        user = User.query.filter_by(email=email).first()
        if user:
            result = auth_manager.complete_login_with_otp(email, otp_code)

    if result['success'] and result['login_type'] == 'user':
        if (result['user']['user_id']):
            session['user_id'] = result['user']['user_id']
            result['redirect'] = '/home'
            log_to_splunk("Login", "User logged in with OTP", username=result['user']['username'])
    elif result['success'] and result['login_type'] == 'moderator':
        if(result['moderator']['mod_id']):
            session['mod_id'] = result['moderator']['mod_id']
            session['mod_level'] = result['moderator']['mod_level']
            result['redirect'] = '/moderation'
            log_to_splunk("Login", "Moderator logged in", username=result['moderator']['username'])
    else:     
        log_to_splunk("Login", "Failed OTP verification", username=email)

    return jsonify(result)

@app.route('/verify-register-otp', methods=['POST'])
@limiter.limit('5 per minute')
def verify_register_otp():
    data = request.get_json()
    email = data.get('email')
    otp_code = data.get('otp_code')
    reg_data = session.get('registration_data')

    # Input Tampering
    if not reg_data or reg_data.get('email') != email:
        log_to_splunk("Register", "Attempted registration with invalid inputs", username=email)
        return jsonify({'success': False, 'error': 'Error registering with email address.'})

    # OTP expiry
    if datetime.fromisoformat(reg_data.get('otp_expiry')) < datetime.now(timezone.utc):
        log_to_splunk("Register", "OTP expired during registration", username=email)
        session.pop('registration_data', None)
        return jsonify({'success': False, 'error': 'OTP Expired. Please try again.'}), 500

    # OTP mismatch
    if reg_data.get('otp') != otp_code:
        log_to_splunk("Register", "Invalid OTP during registration", username=email)
        return jsonify({'success': False, 'error': 'Invalid OTP. Please try again.'}), 500
    
    # Multi-account creation check
    if User.query.filter(User.email == email).first() or Moderator.query.filter(Moderator.email == email).first():
        log_to_splunk("Register", "Attempted creation of multi-accounts", username=email)
        return jsonify({'success': False, 'error': 'Email already registered.'})

    create_result = auth_manager.create_user(
        username=reg_data['username'],
        email=reg_data['email'],
        password_hash=reg_data['password_hash']
    )

    if not create_result.get('success'):
        log_to_splunk("Register", "Failed to create user", username=email)
        session.pop('registration_data', None)
        return jsonify({'success': False, 'error': create_result.get('errors', ['Failed to create user.'])})

    session.pop('registration_data', None)
    
    user = User.query.filter_by(email=email).first()
    if user:
        session['user_id'] = user.userId
        log_to_splunk("Register", "User registered an account", username=user.username)
        return jsonify({'success': True, 'redirect': url_for('home')})
    else:
        log_to_splunk("Register", "Failed to register user after OTP verification", username=email)
        return jsonify({'success': False, 'error': 'Login failed after OTP verification.'})

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="Too many requests, slow down!"), 429

@app.route('/api/send-password-change-otp', methods=['POST'])
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

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)



