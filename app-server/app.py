from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import json
import os
from dotenv import load_dotenv  # Add this import
from models import db, Post, Likes
from managers import AuthenticationManager, FeedManager
from managers.authentication_manager import bcrypt
from werkzeug.utils import secure_filename
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# MySQL Database Configuration
DB_USER = os.environ.get('DB_USER', '') 
DB_PASSWORD = os.environ.get('DB_PASSWORD', '') 
DB_HOST = os.environ.get('DB_HOST', '')
DB_PORT = os.environ.get('DB_PORT', '')
DB_NAME = os.environ.get('DB_NAME', '')

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt.init_app(app)

auth_manager = AuthenticationManager()
feed_manager = FeedManager()

# SPLUNK HEC Configuration
SPLUNK_HEC_URL = "https://10.20.0.100:8088/services/collector"
# Please remind me to hide this
SPLUNK_HEC_TOKEN = "e4e0bbe8-2549-4a8e-bafa-28d0eb22244b"

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
    posts = feed_manager.generate_feed(session['user_id'])
    return render_template('home.html', posts=posts)

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
        visibility = request.form.get('visibility', 'followers')  # You can handle visibility if you want

        new_likes = Likes(
            user_userId=session['user_id'],  # must NOT be None
            timestamp=datetime.utcnow()
        )
        db.session.add(new_likes)
        db.session.flush()

        # Create the post record first
        new_post = Post(
            authorId=session['user_id'],  # use session user id
            title=title,
            content=content,
            timeOfPost=datetime.utcnow(),
            like=0,
            likesId=new_likes.likesId,  # You can update this if Likes is linked
            image="https://fastly.picsum.photos/id/404/200/300.jpg?hmac=1i6ra6DJN9kJ9AQVfSf3VD1w08FkegBgXuz9lNDk1OM"  # No image for now
        )

        db.session.add(new_post)
        # db.session.flush()  # Flush to get new_post.id before commit

        # # Now create a Likes record linked to the post (optional)
        # # Assuming Likes has a post_id field linking to Post
        # new_like = Likes(post_id=new_post.id, user_id=session['user_id'])  # Adjust fields as per your model
        # db.session.add(new_like)

        # # Update the post with likesId if needed (optional)
        # new_post.likesId = new_like.id

        db.session.commit()

        flash("Post created successfully!", "success")
        return redirect(url_for('home'))

    return render_template('create_post.html')




if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("MySQL database tables created successfully!")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    app.run(host='0.0.0.0', port=8080)



