"""Central role guards for FastAPI routes.

Use these as dependencies on every protected route. Resource scope (which
classes, subjects and students a teacher may see) is checked separately by
`services/access.py`, using the guarded user.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from .config import get_settings
from .models import Profile
from .security import get_current_user


def require_roles(*roles: str) -> Callable[[Profile], Profile]:
    allowed = set(roles)

    def guard(user: Profile = Depends(get_current_user)) -> Profile:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this")
        return user

    guard.__name__ = f"require_{'_or_'.join(sorted(allowed))}"
    return guard


require_admin = require_roles("admin")
require_teacher = require_roles("teacher")
require_student = require_roles("student")
require_staff = require_roles("admin", "teacher")


def require_ai_enabled() -> None:
    if not get_settings().ai_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI features are not enabled")
