from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check():
    return {"code": 200, "status": "Healthy"}
