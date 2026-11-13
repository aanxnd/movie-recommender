"""Staging-only resource HTTP composition, using existing verified ownership helpers."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import database, group_authorization, limits, resource_authorization as owners
from app.main import IdParameter, Limit, get_session, saved_movie
from app.models import UserRating
from app.schemas import InvitationResponse, RatingLookup, RatingRequest, RatingResponse, RatingsPage, UserResponse


def profile_router(authenticate):
    router = APIRouter()
    Principal = Annotated[object, Depends(authenticate)]
    Storage = Annotated[Session, Depends(get_session, scope='function')]

    @router.get('/users/me', response_model=UserResponse)
    def me(principal: Principal):
        return UserResponse(id=principal.user_id)

    @router.get('/users/{user_id}', response_model=UserResponse)
    def profile(user_id: IdParameter, principal: Principal, session: Storage):
        return UserResponse(id=owners.require_profile_owner(session, principal, user_id))

    @router.put('/users/{user_id}/ratings/{movie_id}', response_model=RatingResponse)
    def rate(user_id: IdParameter, movie_id: IdParameter, body: RatingRequest, principal: Principal, session: Storage):
        limits.owner_admission(session, principal.user_id, 'write', 60)
        value = owners.put_rating(session, principal, user_id, movie_id, body.rating)
        return RatingResponse(user_id=principal.user_id, movie_id=movie_id, rating=value)

    @router.get('/users/{user_id}/ratings', response_model=list[RatingResponse])
    def ratings(user_id: IdParameter, principal: Principal, session: Storage, limit: Limit = 100,
                after: Annotated[int, Query(ge=0, lt=2**63)] = 0):
        values = owners.read_ratings(session, principal, user_id, after=after, limit=limit)
        return [RatingResponse(user_id=principal.user_id, movie_id=mid, rating=value) for mid, value in values.items()]

    @router.get('/users/{user_id}/ratings/details', response_model=RatingsPage)
    def details(request: Request, user_id: IdParameter, principal: Principal, session: Storage, limit: Limit = 100,
                after: Annotated[int, Query(ge=0, lt=2**63)] = 0):
        owners.require_profile_owner(session, principal, user_id)
        rows = list(session.scalars(select(UserRating).where(UserRating.user_id == principal.user_id,
            UserRating.movie_id > after).order_by(UserRating.movie_id).limit(limit + 1)))
        total = session.scalar(select(func.count()).select_from(UserRating).where(UserRating.user_id == principal.user_id))
        return RatingsPage(items=[saved_movie(request, r) for r in rows[:limit]], total=total,
                           next_after=rows[limit - 1].movie_id if len(rows) > limit else None)

    @router.post('/users/{user_id}/ratings/lookup')
    def lookup(request: Request, user_id: IdParameter, body: RatingLookup, principal: Principal, session: Storage):
        owners.require_profile_owner(session, principal, user_id)
        return [saved_movie(request, r) for r in session.scalars(select(UserRating).where(
            UserRating.user_id == principal.user_id, UserRating.movie_id.in_(body.movie_ids)).order_by(UserRating.movie_id))]

    @router.post('/users/{user_id}/group-invitation', response_model=InvitationResponse)
    def invitation(user_id: IdParameter, principal: Principal, session: Storage):
        limits.owner_admission(session, principal.user_id, 'invitation', 10)
        token, expiry = group_authorization.issue_invitation(session, principal, user_id)
        return InvitationResponse(code=f'{principal.user_id}:{token}', expires_at=expiry)

    @router.delete('/users/{user_id}/group-invitation', status_code=204)
    def revoke(user_id: IdParameter, principal: Principal, session: Storage):
        group_authorization.revoke_invitation(session, principal, user_id)

    return router
