"""HTTP boundary connecting MovieLens, recommendations, and SQLite."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from math import isfinite
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path as PathParameter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import database, recommender
from app.data import DEFAULT_DATA_DIR, load_movielens
from app.schemas import (
    GroupRequest, HealthResponse, MovieResponse, RatingRequest, RatingResponse,
    RecommendationResponse, UserResponse,
)


IdParameter = Annotated[int, PathParameter(gt=0, lt=2**63)]
Limit = Annotated[int, Query(ge=1, le=100)]
MinimumCount = Annotated[int, Query(ge=1)]
Decade = Annotated[int | None, Query(ge=1800, le=2090, multiple_of=10)]


def get_session(request: Request) -> Iterator[Session]:
    """Commit before sending success; roll back failures and always close."""
    with Session(request.app.state.engine) as session, session.begin():
        yield session


DatabaseSession = Annotated[Session, Depends(get_session, scope="function")]


def require_user(session: Session, user_id: int) -> UserResponse:
    user = database.get_user(session, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return UserResponse(id=user.id)


def movie_metadata(request: Request, movie_id: int) -> MovieResponse:
    movie = request.app.state.catalog.get(movie_id)
    if movie is None:
        raise HTTPException(404, "Movie not found")
    return movie


def recommendation_response(
    request: Request, results: list[recommender.RecommendationResult],
) -> list[RecommendationResponse]:
    return [
        RecommendationResponse(**movie_metadata(request, row.movie_id).model_dump(),
                               score=row.score, confidence=row.confidence, method=row.method)
        for row in results
    ]


def create_app(
    data_dir: Path = DEFAULT_DATA_DIR,
    database_path: Path = database.DEFAULT_DATABASE_PATH,
) -> FastAPI:
    """Allow tests to supply isolated CSVs and a temporary SQLite file."""
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        movies, ratings = load_movielens(data_dir)
        application.state.movies = movies
        application.state.historical_users = recommender.build_user_ratings(ratings)
        application.state.catalog = {
            int(row.movie_id): MovieResponse(
                movie_id=int(row.movie_id), title=row.title, genres=row.genres.split("|"),
            )
            for row in movies.itertuples(index=False)
        }
        application.state.release_years = {
            movie_id: recommender.release_year(movie.title)
            for movie_id, movie in application.state.catalog.items()
        }
        application.state.genres = {
            movie_id: movie.genres for movie_id, movie in application.state.catalog.items()
        }
        engine = database.create_database_engine(database_path)
        try:
            database.create_schema(engine)
            with Session(engine) as session, session.begin():
                database.register_movies(session, application.state.catalog)
            application.state.engine = engine
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Movie Recommender API", lifespan=lifespan)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Rejected inputs can contain infinity/NaN, which JSON cannot encode.
        details = jsonable_encoder(
            error.errors(),
            custom_encoder={float: lambda value: value if isfinite(value) else str(value)},
        )
        return JSONResponse(status_code=422, content={"detail": details})

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.get("/movies/search", response_model=list[MovieResponse])
    def search_movies(request: Request, q: str = "", limit: Limit = 20) -> list[MovieResponse]:
        query = q.strip().casefold()
        if not query:
            return []
        matches = []
        for movie in request.app.state.catalog.values():
            if query in movie.title.casefold():
                matches.append(movie)
                if len(matches) == limit:
                    break
        return matches

    @application.get("/movies/decades", response_model=list[int])
    def decades(request: Request) -> list[int]:
        return recommender.available_decades(request.app.state.release_years)

    @application.get("/movies/{movie_id}", response_model=MovieResponse)
    def get_movie(request: Request, movie_id: IdParameter) -> MovieResponse:
        return movie_metadata(request, movie_id)

    @application.get("/recommendations/popular", response_model=list[RecommendationResponse])
    def popular(
        request: Request, limit: Limit = 10, min_rating_count: MinimumCount = 20,
        decade: Decade = None,
    ) -> list[RecommendationResponse]:
        results = recommender.popular_recommendations(
            request.app.state.historical_users, limit=limit, min_rating_count=min_rating_count,
            allowed_movies=recommender.movie_ids_for_decade(request.app.state.release_years, decade),
        )
        return recommendation_response(request, [recommender.RecommendationResult(
            movie, score, None, "popularity",
        ) for movie, score in results])

    @application.get("/recommendations/genre/{genre}", response_model=list[RecommendationResponse])
    def genre_recommendations(
        request: Request, genre: str, limit: Limit = 10, min_rating_count: MinimumCount = 20,
        decade: Decade = None,
    ) -> list[RecommendationResponse]:
        results = recommender.genre_recommendations(
            genre, request.app.state.movies, request.app.state.historical_users,
            limit=limit, min_rating_count=min_rating_count,
            allowed_movies=recommender.movie_ids_for_decade(request.app.state.release_years, decade),
        )
        return recommendation_response(request, [recommender.RecommendationResult(
            movie, score, None, "popularity",
        ) for movie, score in results])

    @application.post("/users", status_code=201, response_model=UserResponse)
    def create_user(session: DatabaseSession) -> UserResponse:
        return UserResponse(id=database.create_user(session).id)

    @application.get("/users/{user_id}", response_model=UserResponse)
    def get_user(user_id: IdParameter, session: DatabaseSession) -> UserResponse:
        return require_user(session, user_id)

    @application.put("/users/{user_id}/ratings/{movie_id}", response_model=RatingResponse)
    def save_rating(
        request: Request, user_id: IdParameter, movie_id: IdParameter,
        body: RatingRequest, session: DatabaseSession,
    ) -> RatingResponse:
        require_user(session, user_id)
        movie_metadata(request, movie_id)
        row = database.save_rating(session, user_id, movie_id, body.rating)
        return RatingResponse(user_id=row.user_id, movie_id=row.movie_id, rating=row.rating)

    @application.get("/users/{user_id}/ratings", response_model=list[RatingResponse])
    def user_ratings(user_id: IdParameter, session: DatabaseSession) -> list[RatingResponse]:
        require_user(session, user_id)
        return [
            RatingResponse(user_id=row.user_id, movie_id=row.movie_id, rating=row.rating)
            for row in database.get_user_ratings(session, user_id)
        ]

    @application.get("/users/{user_id}/recommendations", response_model=list[RecommendationResponse])
    def personalized(
        request: Request, user_id: IdParameter, session: DatabaseSession,
        limit: Limit = 10, min_rating_count: MinimumCount = 20,
        decade: Decade = None,
    ) -> list[RecommendationResponse]:
        require_user(session, user_id)
        profile = database.get_user_profile(session, user_id)
        results = recommender.recommend_details(
            profile, request.app.state.historical_users,
            limit=limit, min_rating_count=min_rating_count,
            genres=request.app.state.genres,
            allowed_movies=recommender.movie_ids_for_decade(request.app.state.release_years, decade),
        )
        return recommendation_response(request, results)

    @application.post("/recommendations/group", response_model=list[RecommendationResponse])
    def group(
        request: Request, body: GroupRequest, session: DatabaseSession,
        limit: Limit = 10, min_rating_count: MinimumCount = 20,
        decade: Decade = None,
    ) -> list[RecommendationResponse]:
        profiles = []
        for user_id in body.user_ids:
            require_user(session, user_id)
            profiles.append(database.get_user_profile(session, user_id))
        results = recommender.recommend_details(
            recommender.combine_profiles(profiles), request.app.state.historical_users,
            limit=limit, min_rating_count=min_rating_count,
            genres=request.app.state.genres,
            allowed_movies=recommender.movie_ids_for_decade(request.app.state.release_years, decade),
        )
        return recommendation_response(request, results)

    return application


app = create_app()
