"""POST /contact — the site's contact form. Separate from /gap: a gap report
is the bot noticing a topic it can't cover; a contact submission is a human
choosing to reach out directly, and it's the one place in this service that
touches a real visitor's own name and email, so it gets its own light
validation (a honeypot field, basic email shape) rather than reusing the
guardrail gates built for chat questions.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from ..deps import AppState, get_state
from ..notify import send_contact_email
from ..schemas import ContactRequest, ContactResponse

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/contact", response_model=ContactResponse)
async def contact(body: ContactRequest, request: Request, background: BackgroundTasks, state: AppState = Depends(get_state)):
    state.rate_limiter.check(request)

    if body.honeypot.strip():
        # A real visitor never fills this field in — it's hidden by CSS in
        # the frontend form. Report success without sending anything, so a
        # bot filling every field gets no signal that it was caught.
        return ContactResponse(ok=True)

    if not body.name.strip() or not body.message.strip():
        raise HTTPException(422, "Name and message are required.")
    if not _EMAIL_RE.match(body.email.strip()):
        raise HTTPException(422, "That doesn't look like a valid email address.")

    background.add_task(send_contact_email, state.settings, body.name.strip(), body.email.strip(), body.message.strip())
    return ContactResponse(ok=True, detail="Thanks — that's on its way.")
