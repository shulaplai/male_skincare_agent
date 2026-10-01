"""Minimal CRUD helpers for users and conversations."""
from sqlalchemy.orm import Session

from .config import settings
from .models import Conversation, User, utcnow


def get_or_create_default_user(session: Session, name: str = "預設用戶") -> User:
    user = session.query(User).first()
    if user is None:
        # Self-host default: consent counts as given (see `settings.require_photo_consent`).
        # A hosted deployment flips that flag and the same row starts ungranted.
        granted = not settings.require_photo_consent
        user = User(name=name, photo_cloud_consent=granted, consent_at=utcnow() if granted else None)
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
    # Cloud-only since 2026-10-01: every conversation is cloud-analysed; the only
    # gate is the one-time, user-level consent (`User.photo_cloud_consent`, read in
    # `service.run_consult` — never trust the UI alone). The `cloud_analysis`
    # argument stays so tests can build the legacy shapes, but no route passes it.
    conv = Conversation(
        user_id=user.id,
        body_part=body_part,
        icon=icon,
        cloud_analysis=True if cloud_analysis is None else cloud_analysis,
    )
    session.add(conv)
    session.commit()
    return conv


def consent_state(session: Session) -> dict:
    """Photo consent: what the UI needs to decide whether to show the consent screen.

    `required=False` means this deployment treats consent as already given
    (single-user self-host) — the frontend then never renders the gate.
    """
    user = get_or_create_default_user(session)
    return {
        "granted": bool(user.photo_cloud_consent),
        "at": user.consent_at.isoformat() if user.consent_at else None,
        "required": bool(settings.require_photo_consent),
    }


def set_consent(session: Session, granted: bool) -> dict:
    """Record (or withdraw) consent to send photo bytes to a cloud vision model.

    Withdrawing keeps `consent_at`: it is the record of when consent was first
    given, and its presence also tells `_normalise_consent_policy()` that this row
    has a consent *history* — so the self-host backfill will not silently re-grant
    a consent the user explicitly took back.
    """
    user = get_or_create_default_user(session)
    user.photo_cloud_consent = bool(granted)
    if granted:
        user.consent_at = utcnow()
    session.commit()
    return consent_state(session)
