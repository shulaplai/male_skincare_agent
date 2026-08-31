"""Minimal CRUD helpers for users and conversations."""
from sqlalchemy.orm import Session

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


def create_conversation(session: Session, body_part: str, icon: str = "🧴") -> Conversation:
    user = get_or_create_default_user(session)
    conv = Conversation(user_id=user.id, body_part=body_part, icon=icon)
    session.add(conv)
    session.commit()
    return conv
