from models import AuditLog

def audit(db, action, user=None, detail=None):
    db.add(AuditLog(
        user_id=user.id if user else None,
        entity_id=user.entity_id if user else None,
        action=action,
        detail=detail
    ))
    db.commit()
