"""Minimal CRUD helpers for users and conversations."""
from sqlalchemy.orm import Session

from .config import settings
from .models import Conversation, User


def get_or_create_default_user(session: Session, name: str = "預設用戶") -> User:
    user = session.query(User).first()
    if user is None:
        user = User(name=name)
        session.add(user)
        session.commit()
    return user


def list_conversations(session: Session) -> list[Conversation]:
    user = get_or_create_default_user(session)
    return session.query(Conversation).filter_by(user_id=user.id).all()


def create_conversation(
    session: Session,
    body_part: str,
    icon: str = "🧴",
    cloud_analysis: bool | None = None,
) -> Conversation:
    user = get_or_create_default_user(session)
    # Privacy default comes from env (product default: off); the caller may
    # override per conversation once the UI toggle exists.
    conv = Conversation(
        user_id=user.id,
        body_part=body_part,
        icon=icon,
        cloud_analysis=settings.cloud_analysis_default if cloud_analysis is None else cloud_analysis,
    )
    session.add(conv)
    session.commit()
    return conv
