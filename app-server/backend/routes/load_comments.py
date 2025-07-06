from flask import jsonify, Blueprint, session
from models import db, Post
from sqlalchemy import text

load_comment_bp = Blueprint('load_comments', __name__)

@load_comment_bp.route('/<int:post_id>')
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