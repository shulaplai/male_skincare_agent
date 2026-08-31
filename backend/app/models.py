"""SQLAlchemy ORM models for SkinCoach.

Key design point: every record is scoped by a Conversation, which represents a
body part (面部 / 頭皮 / 背部 / 手腳…). One user -> many conversations -> each
with its own entries, photos, insights (long-term memory) and timeline events.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime.datetime:
    # Naive UTC so SQLite round-trips datetimes without tz offset drift.
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body_part: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(16), default="🧴")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="conversations")
    entries: Mapped[list[Entry]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    insights: Mapped[list[Insight]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Entry(Base):
    """A daily check-in (one per conversation per day, upsert by date)."""

    __tablename__ = "entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[list] = mapped_column(JSON, default=list)  # [{"key","value","dir"}]
    diet: Mapped[list] = mapped_column(JSON, default=list)  # ["打邊爐·辣底", ...]
    products: Mapped[list] = mapped_column(JSON, default=list)  # ["水楊酸 toner", ...]
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="entries")
    photos: Mapped[list[Photo]] = relationship(back_populates="entry", cascade="all, delete-orphan")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entry_id: Mapped[str] = mapped_column(ForeignKey("entries.id"), index=True)
    path: Mapped[str] = mapped_column(String(500))  # relative to data dir
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    entry: Mapped[Entry] = relationship(back_populates="photos")


class Insight(Base):
    """Long-term memory.

    kind: fact (ground truth) | derived (AI inference, decays) | preference (stable).
    Derived insights expire after 30 days and get superseded (versioned) on
    contradiction — see `memory.py` for the rules.
    """

    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # fact | derived | preference
    tag: Mapped[str] = mapped_column(String(120), default="")  # e.g. "skin_type", "product_reaction"
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(ForeignKey("insights.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="insights")


class TimelineEvent(Base):
    """A causal event on the conversation timeline (product change, diet, outcome)."""

    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="events")


class Chunk(Base):
    """A RAG corpus chunk (global beauty knowledge, not per-user)."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(300), index=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
