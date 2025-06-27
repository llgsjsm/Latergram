from .database import db
from .enums import ReportStatus
import datetime

class Report(db.Model):
    __tablename__ = 'report'

    reportId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reportedBy = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    reviewedBy = db.Column(db.Integer, db.ForeignKey('moderator.modID'))
    status = db.Column(db.String(20), default='Pending', nullable=False)  # values from ReportStatus enum
    reason = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    targetType = db.Column(db.String(45), nullable=False)  # values from ReportTarget enum
    targetId = db.Column(db.Integer, nullable=False)  # ID of the post/comment/user being reported

    # Relationships
    reporter = db.relationship('User', foreign_keys=[reportedBy], backref='reports_made')
    reviewer = db.relationship('Moderator', foreign_keys=[reviewedBy], backref='reports_reviewed')

    def get_report_id(self):
        return self.reportId

    def set_report_id(self, report_id):
        self.reportId = report_id

    def get_reason(self):
        return self.reason

    def set_reason(self, reason):
        self.reason = reason

    def get_reported_by(self):
        return self.reporter

    def set_reported_by(self, user):
        self.reporter = user

    def get_timestamp(self):
        return self.timestamp

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def get_status(self):
        return self.status

    def set_status(self, status):
        self.status = status
        
    def get_reviewed_by(self):
        return self.reviewed_by
        
    def set_reviewed_by(self, moderator):
        self.reviewed_by = moderator 
    
    def get_target_type(self):
        return self.targetType
    
    def get_target_id(self):
        return self.targetId