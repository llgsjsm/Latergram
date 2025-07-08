from flask import Flask, app, render_template, request, jsonify, flash
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
from backend.limiter import init_limiter

import os
from dotenv import load_dotenv 
from models import db
from managers.authentication_manager import bcrypt

import firebase_admin
from firebase_admin import credentials, storage, _DEFAULT_APP_NAME
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

csrf = CSRFProtect()

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['SESSION_COOKIE_SECURE'] = True     # Only send cookies thru HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Prevent CSRF attacks w SameSite (doubled with WTF)
    if test_config:
        app.config.update(test_config)
        IS_TESTING = app.config.get("TESTING", os.getenv("IS_TESTING", "false").lower() == "true")

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
    # if not IS_TESTING:
    #     csrf.init_app(app)

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
        csrf.init_app(app)
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

    # Register blueprints
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
    
    # Redis Rate limiting (uncommented and fixed)
    storage_uri = "redis://10.20.0.5:6379" if IS_TESTING else None
    init_limiter(app, storage_uri=storage_uri)
    return app


# Create the app instance
app = create_app()

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    # HTML
    if request.accept_mimetypes.accept_html:
        flash('Security token mismatch. Please refresh and try again.', 'danger')
        return render_template('login.html'), 400

    # JSON/AJAX 
    return jsonify({'success': False, 'error': 'CSRF token missing or invalid'}), 400



if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)