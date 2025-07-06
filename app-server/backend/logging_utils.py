from sqlalchemy import text
from models import db

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
