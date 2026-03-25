from sqlalchemy.orm import Session
from app.models import AuditLog


def write_audit_log(
    db: Session,
    workload_id: int,
    user_name: str,
    user_email: str,
    field_name: str,
    old_value,
    new_value,
):
    """Write an audit log entry. Call before updating the field — same transaction."""
    log = AuditLog(
        workload_id=workload_id,
        user_name=user_name,
        user_email=user_email,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
    )
    db.add(log)
    # Do not commit here — caller commits the whole transaction atomically.
