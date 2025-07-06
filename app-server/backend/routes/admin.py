from flask import jsonify, Blueprint, session
from managers import get_profile_manager

admin_bp = Blueprint('admin', __name__)

profile_manager = get_profile_manager()

@admin_bp.route('/fix-visibility', methods=['POST'])
def fix_visibility_case():
    """Admin endpoint to fix visibility case for existing users"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    # Add admin check here if needed
    result = profile_manager.fix_visibility_case()
    return jsonify(result)