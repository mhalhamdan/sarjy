from fastapi import APIRouter, HTTPException, Response, status

from app.deps import CurrentUser, DbSession
from app.schemas import DeletedCount, MemoryOut
from app.services import memory as memory_service

router = APIRouter(prefix="/memories", tags=["memories"])

# The panel shows everything stored, not just what fits in the session instructions.
PANEL_LIMIT = 1000


@router.get("")
async def list_memories(user: CurrentUser, db: DbSession) -> list[MemoryOut]:
    memories = await memory_service.list_memories(db, user.id, PANEL_LIMIT)
    return [MemoryOut.model_validate(memory) for memory in memories]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(memory_id: int, user: CurrentUser, db: DbSession) -> Response:
    if not await memory_service.forget(db, user.id, memory_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("")
async def delete_all_memories(user: CurrentUser, db: DbSession) -> DeletedCount:
    return DeletedCount(deleted=await memory_service.forget_all(db, user.id))
