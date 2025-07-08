from flask import Flask, request, jsonify, Blueprint, redirect, url_for, render_template, session, flash
from managers import get_auth_manager, get_feed_manager, get_profile_manager, get_post_manager
from sqlalchemy import text, or_
from models import db, User, Moderator, Post, Comment, Report
from backend.splunk_utils import log_to_splunk
from backend.captcha_utils import IS_TESTING, verify_recaptcha
from backend.profanity_helper import check_profanity
from backend.logging_utils import log_action
from backend.firebase_utils import ensure_firebase_initialized
from datetime import datetime, timedelta, timezone
from models.enums import ReportTarget, LogActionTypes
from werkzeug.utils import secure_filename
import uuid, re, magic, os
from firebase_admin import storage
from backend.limiter import limiter
from flask_wtf.csrf import generate_csrf

main_bp = Blueprint('main', __name__)
auth_manager = get_auth_manager()
feed_manager = get_feed_manager()
profile_manager = get_profile_manager()
post_manager = get_post_manager()

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png'}
MAX_IMAGE_SIZE_MB = 5
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
# Check if Playwright is enabled, default to False
PLAYWRIGHT = os.getenv("PLAYWRIGHT", "false").lower() == "true"

######################
### Main functions ###
######################
@main_bp.route('/')
def hello_world():
    log_to_splunk("Landing","Browsed to landing page.")
    return redirect(url_for('main.home'))

@main_bp.route('/home')
def home():
    if 'user_id' not in session and 'mod_id' not in session:
        return redirect(url_for('main.login'))
    # redirect moderators to their dashboard
    if 'mod_id' in session:
        return redirect(url_for('moderation.moderation'))
    
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

    # Get current user for template context
    current_user = User.query.filter_by(userId=session['user_id']).first()

    return render_template('home.html', posts=posts, user_stats=user_stats, suggested_users=suggested_users, liked_posts=liked_posts, pending_requests=pending_requests, comment_counts=comment_counts, current_user=current_user)

@main_bp.route('/get-csrf-token', methods=['GET'])
def get_csrf_token():
    token = generate_csrf()
    return jsonify({'csrf_token': token})


@main_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('7 per minute')
def login():
    log_to_splunk("Login", "Visited login page")
    if request.method == 'POST':
        # Check if it's a JSON request (AJAX)
        if request.is_json:
            data = request.get_json()

            # Captcha JSON
            token = data.get('g-recaptcha-response', '')
            if not verify_recaptcha(token, request.remote_addr):
                if PLAYWRIGHT:
                    pass
                else:
                    return jsonify({'success': False, 'error': 'Captcha verification failed'}), 400
            
            if data.get('action') == 'login':
                email = data.get('email', '')
                password = data.get('password', '')

                if email and password:
                    if PLAYWRIGHT:
                        result = auth_manager.login(email, password)
                        if result['success']:
                            session['user_id'] = 999999
                            return jsonify(result)

                    # Check if user exists in User table first
                    user = User.query.filter(
                        or_(User.username == email, User.email == email)
                    ).first()
                    
                    if user:
                        # Use OTP login if user has it enabled, otherwise use normal login
                        if getattr(user, 'otp_enabled', True):  # Default to True (enabled)
                            result = auth_manager.login_with_otp(email, password)
                            if result['success']:
                                return jsonify(result)
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
                            log_to_splunk("Login", "Moderator logged in", username=result['moderator']['username'])
                            return redirect(url_for('moderation.moderation'))
                        else:
                            session['user_id'] = result['user']['user_id']
                            flash('Login successful!', 'success')
                            log_to_splunk("Login", "User logged in", username=result['user']['username'])
                            return redirect(url_for('main.home'))
                    else:
                        log_to_splunk("Login", "Failed login attempt", username=email)
                        flash(f'Login Unsuccessful. {result["error"]}', 'danger')
                else:
                    flash('Please enter both email and password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@main_bp.route('/reset_password_portal', methods=['GET', 'POST'])
def reset_password_portal():
    log_to_splunk("Reset Password", "Visited reset password portal")
    return render_template('reset_password.html')

@main_bp.route('/register', methods=['GET', 'POST'])
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

@main_bp.route('/logout')
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], LogActionTypes.LOGOUT.value, None, ReportTarget.USER.value)
        user = User.query.filter_by(userId=session['user_id']).first()
        log_to_splunk("Logout", "User logged out", username=user.username)
        session.pop('user_id', None)
        session.pop('_flashes', None) 
    else:
        try:
            mod = Moderator.query.filter_by(modID=session['mod_id']).first()
            log_to_splunk("Logout", "Moderator logged out", username=mod.username)
            session.pop('mod_id', None)
        except KeyError:
            log_to_splunk("Logout", "Weird logout attempt")
            return redirect(url_for('main.login'))
        
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))

def is_allowed_file_secure(file):
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    return mime in ALLOWED_MIME_TYPES

@main_bp.route('/create-post', methods=['GET', 'POST'])
def create_post():
    if not IS_TESTING:
        ensure_firebase_initialized()
    
    # moderators cannot create posts
    if 'mod_id' in session:
        return redirect(url_for('moderation.moderator'))
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

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
            image_file.seek(0, 2)  # move to end
            if image_file.tell() > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                image_file.seek(0)
                log_to_splunk("Create Post", "Post creation failed - image too large", username=db.session.get(User, session['user_id']).username)
                return jsonify({'success': False, 'error': f'Image is too large. Max size is {MAX_IMAGE_SIZE_MB}MB'}), 400
            image_file.seek(0)

            if not is_allowed_file_secure(image_file):
                log_to_splunk("Create Post", "Post creation failed - invalid image type", username=db.session.get(User, session['user_id']).username)
                return jsonify({'success': False, 'error': 'Invalid image format. Allowed: jpg, png'}), 400
            
            filename = secure_filename(image_file.filename)
            blob = storage.bucket().blob(f'posts/{uuid.uuid4()}_{filename}')
            blob.upload_from_file(image_file, content_type=image_file.content_type)
            blob.make_public()
            image_url = blob.public_url
        else:
            log_to_splunk("Create Post", "Post created failed", username=db.session.get(User, session['user_id']).username)
            return jsonify({'success': False, 'error': 'Image upload failed or no image provided.'}), 400

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
        return redirect(url_for('main.home'))
    return render_template('create_post.html')

@main_bp.route('/search', methods=['GET'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    query = request.args.get('q', '')
    results = []
    if query:
        search_result = profile_manager.search_users(query)
        if search_result['success']:
            results = search_result['users']
    return redirect(url_for('main.home'))

@main_bp.route('/remove-profile-picture', methods=['POST'])
def remove_profile_picture():
    ensure_firebase_initialized()
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message='Not logged in'), 401
        return redirect(url_for('main.login'))

    user = User.query.filter_by(userId=session['user_id']).first()
    if not user or not user.profilePicture:
        msg = 'No profile picture to remove.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg)
        flash(msg, 'warning')
        return redirect(url_for('main.edit_profile'))

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
    return redirect(url_for('main.edit_profile'))

@main_bp.route('/delete-account', methods=['POST'])
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

@main_bp.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    ensure_firebase_initialized()
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    user = User.query.filter_by(userId=session['user_id']).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('main.home'))
    
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
            return redirect(url_for('profile.profile'))
        else:
            log_to_splunk("Edit Profile", "Failed to update profile" + result['error'], username=user.username)
            flash(f'Error updating profile: {result["error"]}', 'danger')
    
    return render_template('edit_profile.html', user=user, current_user=user)

########################
### Password helpers ###
########################
@main_bp.route('/reset-password', methods=['POST'])
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

@main_bp.route('/forgot-password', methods=['POST'])
@limiter.limit('5 per minute')
def forgot_password():
    data = request.get_json()
    email = data.get('email', '')
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    if not email:
        return jsonify({'success': False, 'error': 'Email is required'})

    if not email_regex.match(email):
        log_to_splunk("Reset Password", "Invalid email input", username=email)
        return jsonify({'success': False, 'error': 'Invalid email. Please enter a valid email address.'})

    if PLAYWRIGHT:
        auth_manager.initiate_password_reset(email)
        log_to_splunk("Reset Password", "Password reset initiated for Playwright test", username=email)
        return jsonify({'success': True, 'message': 'If an account with that email exists, an OTP has been sent.'})
    
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

@main_bp.route('/change-password', methods=['POST'])
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

######################
### OTP helpers ###
######################
@main_bp.route('/verify-login-otp', methods=['POST'])
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

@main_bp.route('/verify-register-otp', methods=['POST'])
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
        return jsonify({'success': True, 'redirect': url_for('main.home')})
    else:
        log_to_splunk("Register", "Failed to register user after OTP verification", username=email)
        return jsonify({'success': False, 'error': 'Login failed after OTP verification.'})
    
@main_bp.route('/verify-reset-otp', methods=['POST'])
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

@main_bp.route('/update-otp-setting', methods=['POST'])
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

@main_bp.route('/resend-login-otp', methods=['POST'])
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