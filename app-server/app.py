from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
import json
import os
from dotenv import load_dotenv  # Add this import
from models import db, Post, Comment, User
from managers.authentication_manager import bcrypt
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import text
import firebase_admin
from firebase_admin import credentials, storage
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Enable debug mode for development (auto-reload on code changes)
app.debug = True

# MySQL Database Configuration
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

db.init_app(app)
bcrypt.init_app(app)

# Use the optimized singleton managers
from managers import get_auth_manager, get_feed_manager, get_profile_manager, get_post_manager

auth_manager = get_auth_manager()
feed_manager = get_feed_manager()
profile_manager = get_profile_manager()
post_manager = get_post_manager()

# SPLUNK HEC Configuration
SPLUNK_HEC_URL = os.environ.get('SPLUNK_HEC_URL', '') 
SPLUNK_HEC_TOKEN = os.environ.get('SPLUNK_HEC_TOKEN', '') 

if not IS_TESTING:
    if FILE_LOCATION and BUCKET:
        cred = credentials.Certificate(FILE_LOCATION)
        firebase_admin.initialize_app(cred, {
            'storageBucket': BUCKET
        })
        bucket = storage.bucket()
    else:
        print("Firebase FILE_LOCATION or BUCKET not set — skipping Firebase init")
else:
    print("Skipping Firebase init — test mode enabled")

def get_real_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr

def log_to_splunk(event_data):
    client_ip = get_real_ip()
    payload = {
        "event": {
            "message": event_data,
            "path": request.path,
            "method": request.method,
            "ip": client_ip,
            "user_agent": request.headers.get("User-Agent")
        },
        "sourcetype": "flask-web",
        "host": client_ip
    }

    headers = {
        "Authorization": f"Splunk {SPLUNK_HEC_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(SPLUNK_HEC_URL, headers=headers, data=json.dumps(payload), verify=False)
        if response.status_code != 200:
            print(f"Splunk HEC error: {response.status_code} - {response.text}")
        else:
            print(f"Sent log to Splunk: {event_data}")
    except Exception as e:
        print(f"Failed to send log to Splunk: {e}")

@app.route('/home')
def home():
    # log_to_splunk("Visited /home")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        posts = feed_manager.generate_feed(session['user_id'])
    except Exception as e:
        print(f"Error getting posts: {e}")
        posts = []
    
    try:
        # Get user stats with caching
        user_stats = profile_manager.get_user_stats_cached(session['user_id'])
    except Exception as e:
        print(f"Error getting user stats: {e}")
        user_stats = {'posts_count': 0, 'followers_count': 0, 'following_count': 0}
    
    try:
        # Get suggested users (users not followed)
        suggested_users = profile_manager.get_suggested_users(session['user_id'])
    except Exception as e:
        print(f"Error getting suggested users: {e}")
        suggested_users = []
    
    try:
        # Get pending follow requests
        follow_requests = profile_manager.get_pending_follow_requests(session['user_id'])
        pending_requests = follow_requests.get('requests', []) if follow_requests.get('success') else []
    except Exception as e:
        print(f"Error getting follow requests: {e}")
        pending_requests = []
    
    # Check which posts the current user has liked (efficient single query)
    try:
        liked_post_ids = post_manager.get_user_liked_posts(session['user_id'])
        liked_posts = {post.postId: post.postId in liked_post_ids for post in posts}
    except Exception as e:
        print(f"Error getting liked posts: {e}")
        liked_posts = {post.postId: False for post in posts}

    return render_template('home.html', posts=posts, user_stats=user_stats, suggested_users=suggested_users, liked_posts=liked_posts, pending_requests=pending_requests)

@app.route('/')
def hello_world():
    # log_to_splunk("Visited /")
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        result = auth_manager.login(email, password)
        if result['success']:
            session['user_id'] = result['user']['user_id']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash(f'Login Unsuccessful. {result["error"]}', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        result = auth_manager.register(username, email, password)
        if result['success']:
            flash('Your account has been created! You are now able to log in', 'success')
            return redirect(url_for('login'))
        else:
            if 'errors' in result:
                for error in result['errors']:
                    flash(error, 'danger')
            else:
                flash(result['error'], 'danger')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))



@app.route('/create-post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        visibility = request.form.get('visibility', 'followers')

        image_url = "https://fastly.picsum.photos/id/404/200/300.jpg?hmac=..."  # default

        # Handle file upload
        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            blob = storage.bucket().blob(f'posts/{uuid.uuid4()}_{filename}')
            blob.upload_from_file(image_file, content_type=image_file.content_type)
            blob.make_public()
            image_url = blob.public_url

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
            timeOfPost=datetime.utcnow(),
            like=0,
            likesId=likes_id,
            image=image_url
        )

        db.session.add(new_post)
        db.session.commit()

        flash("Post created successfully!", "success")
        return redirect(url_for('home'))

    return render_template('create_post.html')

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
            timestamp=datetime.utcnow(),
            parentCommentId=parent_comment_id
        )
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('home'))

# Profile Routes
@app.route('/profile')
@app.route('/profile/<int:user_id>')
def profile(user_id=None):
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
        
        # Check which posts the current user has liked (efficient single query)
        liked_posts = {}
        if user_posts:
            try:
                liked_post_ids = post_manager.get_user_liked_posts(session['user_id'])
                liked_posts = {post.postId: post.postId in liked_post_ids for post in user_posts}
            except Exception as e:
                print(f"Error getting liked posts: {e}")
                liked_posts = {post.postId: False for post in user_posts}
        
        print(f"Profile data: user={user.username}, stats={user_stats}, posts_count={len(user_posts) if user_posts else 0}")
        
        return render_template('profile.html', 
                             user=user, 
                             user_stats=user_stats, 
                             user_posts=user_posts,
                             is_following=is_following,
                             follow_status=follow_status,
                             is_own_profile=is_own_profile,
                             liked_posts=liked_posts,
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
    return jsonify(result)

@app.route('/api/unfollow/<int:user_id>', methods=['POST'])
def unfollow_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = profile_manager.unfollow_user(session['user_id'], user_id)
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
    return jsonify(result)

@app.route('/api/unlike/<int:post_id>', methods=['POST'])
def unlike_post_api(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    result = post_manager.unlike_post(session['user_id'], post_id)
    return jsonify(result)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
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
        
        result = profile_manager.update_profile(
            session['user_id'], 
            display_name=display_name, 
            bio=bio, 
            visibility=visibility
        )
        
        if result['success']:
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash(f'Error updating profile: {result["error"]}', 'danger')
    
    return render_template('edit_profile.html', user=user)

@app.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'error': 'New passwords do not match'}), 400
    
    # Change the password
    result = profile_manager.change_password(session['user_id'], current_password, new_password)
    
    if result['success']:
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    else:
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
    return render_template('search.html', query=query, results=results)

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
    if not password:
        return jsonify({'success': False, 'error': 'Password is required for account deletion'}), 400
    
    if confirm_deletion != 'DELETE':
        return jsonify({'success': False, 'error': 'Please type DELETE to confirm account deletion'}), 400
    
    # Delete the account
    result = profile_manager.delete_account(session['user_id'], password)
    
    if result['success']:
        # Clear the session after successful deletion
        session.clear()
        return jsonify({'success': True, 'message': 'Account deleted successfully'})
    else:
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/remove-follower/<int:follower_user_id>', methods=['POST'])
def remove_follower_api(follower_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    result = profile_manager.remove_follower(session['user_id'], follower_user_id)
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("MySQL database tables created successfully!")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)



