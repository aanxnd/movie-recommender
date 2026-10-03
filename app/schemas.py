"""Explicit JSON contracts for the REST API."""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator


UserId = Annotated[int, Field(strict=True, gt=0, lt=2**63)]


class HealthResponse(BaseModel):
    status: str


class MovieResponse(BaseModel):
    movie_id: int
    title: str
    genres: list[str]


class RecommendationResponse(MovieResponse):
    score: float


class UserResponse(BaseModel):
    id: int


class RatingRequest(BaseModel):
    rating: float = Field(strict=True, ge=0.5, le=5.0, allow_inf_nan=False)


class RatingResponse(BaseModel):
    user_id: int
    movie_id: int
    rating: float


class GroupRequest(BaseModel):
    user_ids: list[UserId] = Field(min_length=2, max_length=100)

    @field_validator("user_ids")
    @classmethod
    def distinct_users(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("user_ids must be distinct")
        return value
