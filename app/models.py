"""SQLite models for application data, separate from MovieLens users."""

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class Movie(Base):
    """Reference IDs only; MovieLens CSVs own titles and genres."""

    __tablename__ = "movies"
    __table_args__ = (CheckConstraint("movie_id > 0"),)

    movie_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)


class UserRating(Base):
    __tablename__ = "user_ratings"
    __table_args__ = (CheckConstraint("rating >= 0.5 AND rating <= 5.0"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.movie_id"), primary_key=True)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
