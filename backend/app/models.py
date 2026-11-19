import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """An anonymous user, identified only by the signed cookie on their browser."""

    __tablename__ = "users"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memories: Mapped[list["Memory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Memory(Base):
    """One remembered fact.

    The id is a short integer rather than a UUID because the model sees and repeats every id:
    with up to 200 facts in the session instructions, UUIDs would cost thousands of tokens.
    All access is scoped by user_id, so sequential ids reveal nothing.
    """

    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_user_id_updated_at", "user_id", "updated_at"),)
    # Fetch server-generated timestamps with RETURNING on insert and update, so they can be read
    # after a flush without an extra (async-unsafe) lazy load.
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="memories")
