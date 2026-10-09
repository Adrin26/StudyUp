from fastapi import APIRouter, Depends

from ..models import Profile
from ..security import get_current_user
from ..services.gamification import BADGES, XP_NOT_AWARDED, XP_PER_LEVEL, XP_RULES

router = APIRouter(prefix="/api/gamification", tags=["gamification"])


@router.get("/rules")
def rules(_: Profile = Depends(get_current_user)):
    """How XP is earned, for students and teachers alike."""
    return {
        "xp_per_level": XP_PER_LEVEL,
        "earning": XP_RULES,
        "not_awarded": XP_NOT_AWARDED,
        "badges": [{"code": c, "name": n, "description": d, "xp": xp} for c, n, d, _, xp in BADGES],
    }
