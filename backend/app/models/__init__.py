"""Import every model module so tables register on Base.metadata."""

import app.models.auth_tokens  # noqa: F401
import app.models.calendar  # noqa: F401
import app.models.course  # noqa: F401
import app.models.file_vault  # noqa: F401
import app.models.planner  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.video  # noqa: F401
