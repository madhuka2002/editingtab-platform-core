from fastapi import APIRouter

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get(
    "",
    summary="Health check",
)
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "editingtab-platform-core",
    }