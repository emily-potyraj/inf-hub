from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_auth
from app.database import get_db
from app.models import Comment, Workload
from app.schemas import CommentCreate, CommentReply, CommentResolve, CommentRow

router = APIRouter(tags=["comments"])


def _to_row(c: Comment, replies: list) -> CommentRow:
    return CommentRow(
        id=c.id,
        workload_id=c.workload_id,
        field=c.field,
        body=c.body,
        author=c.author,
        parent_id=c.parent_id,
        resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
        resolved_by=c.resolved_by,
        created_at=c.created_at.isoformat() if c.created_at else None,
        replies=[_to_row(r, []) for r in replies],
    )


def _build_reply_map(comments: list) -> dict:
    reply_map: dict[int, list] = {}
    for c in comments:
        if c.parent_id is not None:
            reply_map.setdefault(c.parent_id, []).append(c)
    return reply_map


@router.get("/workloads/{workload_id}/comments", response_model=list[CommentRow])
def list_comments(workload_id: int, db: Session = Depends(get_db)):
    if db.get(Workload, workload_id) is None:
        raise HTTPException(status_code=404, detail="Workload not found")
    all_comments = (
        db.query(Comment)
        .filter(Comment.workload_id == workload_id)
        .order_by(Comment.created_at)
        .all()
    )
    reply_map = _build_reply_map(all_comments)
    return [
        _to_row(c, reply_map.get(c.id, []))
        for c in all_comments
        if c.parent_id is None
    ]


@router.post("/workloads/{workload_id}/comments")
def create_comment(
    workload_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if db.get(Workload, workload_id) is None:
        raise HTTPException(status_code=404, detail="Workload not found")
    author = user["name"] if user else body.author
    c = Comment(workload_id=workload_id, field=body.field, body=body.body, author=author)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id}


@router.post("/comments/{comment_id}/replies")
def add_reply(
    comment_id: int,
    body: CommentReply,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    parent = db.get(Comment, comment_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    author = user["name"] if user else body.author
    reply = Comment(
        workload_id=parent.workload_id,
        field=parent.field,
        body=body.body,
        author=author,
        parent_id=comment_id,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return {"id": reply.id}


@router.patch("/comments/{comment_id}/resolve")
def resolve_comment(
    comment_id: int,
    body: CommentResolve,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    c = db.get(Comment, comment_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    c.resolved_at = datetime.now(timezone.utc)
    c.resolved_by = body.resolved_by or (user["name"] if user else None)
    db.commit()
    return {"ok": True}


@router.get("/comments", response_model=list[CommentRow])
def list_all_open_comments(
    resolved: str = "false",
    db: Session = Depends(get_db),
):
    q = db.query(Comment).filter(Comment.parent_id.is_(None))
    if resolved == "false":
        q = q.filter(Comment.resolved_at.is_(None))
    roots = q.order_by(Comment.workload_id, Comment.created_at).all()

    all_replies = (
        db.query(Comment)
        .filter(Comment.parent_id.isnot(None))
        .order_by(Comment.created_at)
        .all()
    )
    reply_map = _build_reply_map(all_replies)
    return [_to_row(r, reply_map.get(r.id, [])) for r in roots]
