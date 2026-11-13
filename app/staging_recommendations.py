"""Native staging authorization around the unchanged recommendation computation."""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import database, group_authorization, limits, recommender, resource_authorization
from app.main import (Decade, IdParameter, Limit, MinimumCount, RecommendationSlot,
                      compute_recommendations, recommendation_response)
from app.schemas import GroupRequest, RecommendationResponse


def recommendation_router(authenticate):
    router = APIRouter()
    Principal = Annotated[object, Depends(authenticate)]

    def compute(request, profile, limit, minimum, decade):
        return recommendation_response(request, compute_recommendations(profile, request.app.state.historical_users,
            limit=limit, min_rating_count=minimum, genres=request.app.state.genres,
            allowed_movies=recommender.movie_ids_for_decade(request.app.state.release_years, decade)))

    @router.get('/users/{user_id}/recommendations', response_model=list[RecommendationResponse])
    def personal(request: Request, user_id: IdParameter, principal: Principal, slot: RecommendationSlot,
                 limit: Limit = 10, min_rating_count: MinimumCount = 20, decade: Decade = None):
        with Session(request.app.state.engine) as session, session.begin():
            resource_authorization.require_profile_owner(session, principal, user_id)
            limits.owner_admission(session, principal.user_id, 'recommend', 6)
            profile = database.bounded_profile(session, principal.user_id, limits.MAX_PROFILE_RATINGS)
        # Neither database transaction nor a second connection stays open during CPU work.
        return compute(request, profile, limit, min_rating_count, decade)

    @router.post('/recommendations/group', response_model=list[RecommendationResponse])
    def group(request: Request, body: GroupRequest, principal: Principal, slot: RecommendationSlot,
              limit: Limit = 10, min_rating_count: MinimumCount = 20, decade: Decade = None):
        with Session(request.app.state.engine) as session, session.begin():
            profile = group_authorization.combined_group_profile(session, principal, body.user_ids, body.invitations)
            limits.owner_admission(session, principal.user_id, 'recommend', 6)
        return compute(request, profile, limit, min_rating_count, decade)

    return router
