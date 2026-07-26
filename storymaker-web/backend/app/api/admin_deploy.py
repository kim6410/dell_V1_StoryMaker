# -*- coding: utf-8 -*-
"""StoryMaker V1 isolation guard.

The V2 frontend deployment endpoint is intentionally disabled in the isolated
V1 environment.  app.api.admin imports ``router`` from this module, so the
module remains as a harmless empty router rather than being deleted.
"""

from fastapi import APIRouter

router = APIRouter()

V1_DEPLOY_ROUTE_DISABLED = True
