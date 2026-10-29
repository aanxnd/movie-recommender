"""Application database models, separate from MovieLens reference users."""

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


ID_TYPE = BigInteger().with_variant(Integer(), "sqlite")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True)


class Movie(Base):
    """Reference IDs only; MovieLens CSVs own titles and genres."""

    __tablename__ = "movies"
    __table_args__ = (CheckConstraint("movie_id > 0"),)

    movie_id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=False)


class UserRating(Base):
    __tablename__ = "user_ratings"
    __table_args__ = (CheckConstraint("rating >= 0.5 AND rating <= 5.0"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.movie_id"), primary_key=True)
    rating: Mapped[float] = mapped_column(Float, nullable=False)


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class Credential(Base):
    __tablename__ = "profile_credentials"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class GroupInvitation(Base):
    __tablename__ = "group_invitations"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
