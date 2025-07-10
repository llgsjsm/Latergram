from flask import Flask, app, abort, request, jsonify, flash, session, redirect, url_for
from backend.routes.main import main_bp
from backend.routes.profile import profile_bp
from backend.routes.comment import comment_bp
from backend.routes.like import like_bp
from backend.routes.unlike import unlike_bp
from backend.routes.api import api_bp
from backend.routes.edit_comment import edit_comment_bp
from backend.routes.delete_post import delete_post_bp
from backend.routes.delete_comment import delete_comment_bp
from backend.routes.load_comments import load_comment_bp
from backend.routes.admin import admin_bp
from backend.routes.moderation import moderation_bp
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv 
from models import db
from managers.authentication_manager import bcrypt

import firebase_admin
from firebase_admin import credentials, storage, _DEFAULT_APP_NAME

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['SESSION_COOKIE_SECURE'] = True     # Only send cookies thru HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Prevent CSRF attacks w SameSite

    if test_config:
        app.config.update(test_config)
    app.config['IS_TESTING'] = app.config.get("IS_TESTING", os.getenv("IS_TESTING", "false").lower() == "true")


    # Enable debug mode for development (auto-reload on code changes)
    app.debug = True
    DB_USER = os.environ.get('DB_USER', '') 
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '') 
    DB_HOST = os.environ.get('DB_HOST', '')
    DB_PORT = os.environ.get('DB_PORT', '')
    DB_NAME = os.environ.get('DB_NAME', '')
    BUCKET = os.environ.get('BUCKET', '')
    FILE_LOCATION = os.environ.get('FILE_LOCATION','')
    # Default to false if not set. Set IS_TESTING to true for testing environments
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
    if not IS_TESTING:
        if FILE_LOCATION and BUCKET:
            try:
                if _DEFAULT_APP_NAME not in firebase_admin._apps:
                    cred = credentials.Certificate(FILE_LOCATION)
                    firebase_admin.initialize_app(cred, {
                        'storageBucket': BUCKET
                    })
                bucket = storage.bucket()
            except Exception as e:
                print(f"Error initializing Firebase: {e}")

    app.register_blueprint(main_bp)    
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(comment_bp, url_prefix='/comment')
    app.register_blueprint(like_bp, url_prefix='/like')
    app.register_blueprint(unlike_bp, url_prefix='/unlike')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(edit_comment_bp, url_prefix='/edit_comment')
    app.register_blueprint(delete_post_bp, url_prefix='/delete-post')
    app.register_blueprint(delete_comment_bp, url_prefix='/delete_comment')
    app.register_blueprint(load_comment_bp, url_prefix='/load_comments')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(moderation_bp, url_prefix='/moderation')
    
    # Redis Rate limiting
    # storage_uri = "redis://10.20.0.5:6379" if IS_TESTING else None
    # init_limiter(app, storage_uri=storage_uri)
    return app

app = create_app()

@app.before_request
def csrf_protect():
    if request.method in ["GET", "OPTIONS"]:
        return
    csrf_token_from_request = request.form.get('csrf_token') or request.headers.get('X-CSRF-TOKEN')    
    # Debugging: Print the CSRF tokens
    print(f"Session CSRF Token: {session.get('csrf_token')}")
    print(f"Submitted CSRF Token: {csrf_token_from_request}")
    if not csrf_token_from_request or csrf_token_from_request != session.get('csrf_token'):
        return jsonify({'success': False, 'error': 'CSRF token missing or invalid'}), 400

@app.before_request
def session_inactivity_check():
    now = datetime.now(timezone.utc)
    # mod timeout (10 minutes)
    if 'mod_id' in session:
        last_activity = session.get('last_activity_mod')
        if last_activity:
            last_active_time = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            if now - last_active_time > timedelta(minutes=10):
                session.clear()
                return redirect(url_for('main.login'))  # Redirect to login
        session['last_activity_mod'] = now.strftime('%Y-%m-%d %H:%M:%S')
    # user timeout (30 minutes)
    elif 'user_id' in session:
        last_activity = session.get('last_activity')
        if last_activity:
            last_active_time = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            if now - last_active_time > timedelta(minutes=30):
                session.clear()
                return redirect(url_for('main.login'))
        session['last_activity'] = now.strftime('%Y-%m-%d %H:%M:%S')

@app.after_request
def apply_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)