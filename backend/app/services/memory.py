import uuid
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Memory


class MemoryNotFoundError(Exception):
    pass


async def list_memories(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[Memory]:
    """The user's facts, most recently updated first."""
    result = await db.scalars(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.updated_at.desc(), Memory.id.desc())
        .limit(limit)
    )
    return list(result)


async def remember(
    db: AsyncSession, user_id: uuid.UUID, content: str, replaces_id: int | None = None
) -> tuple[Literal["saved", "updated"], Memory]:
    """Save a new fact, or replace the content of an existing one by id."""
    content = " ".join(content.split())
    if replaces_id is not None:
        memory = await _get_owned(db, user_id, replaces_id)
        if memory is None:
            raise MemoryNotFoundError(replaces_id)
        memory.content = content
        await db.commit()
        return "updated", memory

    memory = Memory(user_id=user_id, content=content)
    db.add(memory)
    await db.commit()
    return "saved", memory


async def forget(db: AsyncSession, user_id: uuid.UUID, memory_id: int) -> bool:
    result = await db.execute(
        delete(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    )
    await db.commit()
    return result.rowcount > 0


async def forget_all(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(delete(Memory).where(Memory.user_id == user_id))
    await db.commit()
    return result.rowcount


async def _get_owned(db: AsyncSession, user_id: uuid.UUID, memory_id: int) -> Memory | None:
    return await db.scalar(select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id))
