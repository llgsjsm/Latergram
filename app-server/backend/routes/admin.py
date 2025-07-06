from flask import Flask, request, jsonify, Blueprint, render_template, redirect, url_for, session, flash
from models import db, Post, User, Report, Comment
from datetime import datetime, timezone
from models.enums import ReportStatus, ReportTarget, LogActionTypes
from backend.splunk_utils import log_to_splunk
from backend.profanity_helper import check_profanity
from backend.logging_utils import log_action
from managers import get_auth_manager, get_feed_manager, get_profile_manager, get_post_manager, get_moderator_manager
from sqlalchemy import text

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