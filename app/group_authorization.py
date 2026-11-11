"""Dormant existing invitation capabilities; no persisted groups or member roles."""
import secrets

from sqlalchemy import and_, case, delete, literal, or_, select

from app import database, limits, recommender, security
from app.models import GroupInvitation, User, UserRating
from app.resource_authorization import _binding, _denied, _id, _scope, _storage
from app.supabase_auth import SupabaseAuthContext


def issue_invitation(session, principal: SupabaseAuthContext, user_id: int) -> tuple[str, int]:
    """Replace only the caller's capability, using the existing random-token format."""
    scope = _scope(principal, User.id, user_id)
    with _storage(session):
        token = secrets.token_urlsafe(32)
        digest = security.token_hash(token)
        expires = limits.database_now(session) + security.INVITATION_LIFETIME
        source = select(User.id, literal(digest), literal(expires)).where(scope)
        statement = database.conflict_insert(GroupInvitation, session.get_bind().dialect.name).from_select(
            ["user_id", "token_hash", "expires_at"], source)
        found = session.scalar(statement.on_conflict_do_update(index_elements=["user_id"],
            set_={"token_hash": digest, "expires_at": expires},
            where=_scope(principal, GroupInvitation.user_id, user_id)).returning(GroupInvitation.user_id))
        if found is None:
            raise _denied()
        return token, expires


def revoke_invitation(session, principal: SupabaseAuthContext, user_id: int) -> None:
    with _storage(session):
        found = session.scalar(delete(GroupInvitation).where(
            _scope(principal, GroupInvitation.user_id, user_id)).returning(GroupInvitation.user_id))
        if found is None:
            raise _denied()


def combined_group_profile(session, principal: SupabaseAuthContext, user_ids: list[int],
                           invitations: dict[int, str]) -> dict[int, float]:
    """Internal recommendation input only; never return raw/combined profiles over HTTP.

    Possession permits this computation, not private reads, writes or administration.
    Every participant must exist and every other participant must grant consent.
    """
    binding = _binding(principal)
    if type(user_ids) is not list or not 2 <= len(user_ids) <= limits.MAX_GROUP_MEMBERS:
        raise _denied()
    for identifier in user_ids:
        _id(identifier)
    if len(set(user_ids)) != len(user_ids) or principal.user_id not in user_ids:
        raise _denied()
    others = set(user_ids) - {principal.user_id}
    if (type(invitations) is not dict or any(type(key) is not int for key in invitations)
            or set(invitations) != others):
        raise _denied()
    expected = {}
    for identifier, token in invitations.items():
        if not isinstance(token, str) or not security.TOKEN_PATTERN.fullmatch(token):
            raise _denied()
        expected[identifier] = security.token_hash(token)
    with _storage(session):
        now = limits.database_now(session)
        permitted = or_(User.id == principal.user_id, and_(GroupInvitation.user_id == User.id,
            GroupInvitation.expires_at > now, GroupInvitation.token_hash == case(expected, value=User.id)))
        rows = session.execute(select(User.id, UserRating.movie_id, UserRating.rating, GroupInvitation.expires_at)
            .outerjoin(GroupInvitation, GroupInvitation.user_id == User.id)
            .outerjoin(UserRating, UserRating.user_id == User.id)
            .where(User.id.in_(user_ids), binding, permitted).order_by(User.id, UserRating.movie_id)
            .limit(limits.MAX_GROUP_MEMBERS * (limits.MAX_PROFILE_RATINGS + 1))).all()
        profiles = {identifier: {} for identifier in user_ids}
        seen, expiries = set(), []
        for identifier, movie, rating, expiry in rows:
            seen.add(identifier)
            if identifier != principal.user_id:
                if type(expiry) is not int:
                    raise _denied()
                expiries.append(expiry)
            if movie is not None:
                profiles[identifier][movie] = rating
        if seen != set(user_ids) or any(len(profile) > limits.MAX_PROFILE_RATINGS for profile in profiles.values()):
            raise _denied()
        if min(expiries) <= limits.database_now(session):
            raise _denied()
        combined = recommender.combine_profiles(list(profiles.values()))
        if len(combined) > limits.MAX_GROUP_RATINGS:
            raise _denied()
        return combined
