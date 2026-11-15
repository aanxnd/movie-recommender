"""Dormant deletion journal. Separate metadata: no startup migration or production import."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, Uuid, CheckConstraint, delete, select, update

from app.limits import database_now
from app.models import Credential, GroupInvitation, User, UserIdentity, UserRating
from app.provisioning_principal import ProvisioningPrincipal
from app.supabase_identity import resolve_verified_subject


metadata = MetaData()
intents = Table('account_deletion_intents', metadata,
    Column('request_id', Uuid, primary_key=True), Column('subject', Uuid, unique=True, nullable=False),
    Column('user_id', BigInteger, unique=True, nullable=False), Column('issuer', String(255), nullable=False),
    Column('created_at', BigInteger, nullable=False), Column('authorized_until', BigInteger, nullable=False),
    Column('authorization_tag', String(64), nullable=False), Column('phase', String(24), nullable=False),
    Column('worker', Uuid), Column('lease_until', BigInteger, nullable=False, server_default='0'),
    CheckConstraint("phase IN ('pending','provider_absent','complete')"))
events = Table('account_deletion_events', metadata,
    Column('id', BigInteger().with_variant(Integer, 'sqlite'), primary_key=True),
    Column('request_id', Uuid, nullable=False), Column('event', String(24), nullable=False),
    Column('observed_at', BigInteger, nullable=False))


class DeletionUnavailable(RuntimeError):
    def __init__(self):
        super().__init__('Account deletion unavailable')


@dataclass(frozen=True, slots=True, repr=False)
class DeletionJob:
    request_id: UUID
    subject: UUID
    user_id: int
    worker: UUID
    phase: str
    authorized_until: int


class DeletionStore:
    """Trusted server/worker only. Keys never come from requests or the browser."""
    def __init__(self, sessions, issuer, signing_key):
        if (not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co/auth/v1', issuer)
                or type(signing_key) is not bytes or not 32 <= len(signing_key) <= 64):
            raise DeletionUnavailable()
        self.sessions, self.issuer, self._key = sessions, issuer, signing_key

    def _tag(self, row):
        fields = {k: str(row[k]) for k in ('request_id', 'subject', 'user_id', 'issuer', 'created_at', 'authorized_until', 'phase')}
        return hmac.new(self._key, json.dumps(fields, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _event(session, request_id, event):
        session.execute(events.insert().values(request_id=request_id, event=event, observed_at=database_now(session)))

    def blocked(self, subject):
        with self.sessions() as session, session.begin():
            return session.scalar(select(intents.c.request_id).where(intents.c.subject == subject)) is not None

    def request(self, principal, request_id, confirmation):
        # Call only AFTER the server-side password authorizer, never from a request model.
        if (type(principal) is not ProvisioningPrincipal or type(request_id) is not UUID or not request_id.int
                or confirmation != 'PERMANENTLY DELETE MY ACCOUNT'):
            raise DeletionUnavailable()
        principal.require_fresh()
        with self.sessions() as session, session.begin():
            identity = resolve_verified_subject(session, principal.subject)
            session.execute(update(User).where(User.id == identity.user_id).values(id=User.id))
            previous = session.execute(select(intents).where(intents.c.subject == principal.subject)).mappings().one_or_none()
            if previous:
                if previous['user_id'] != identity.user_id or previous['issuer'] != self.issuer:
                    raise DeletionUnavailable()
                return previous['request_id']
            row = dict(request_id=request_id, subject=principal.subject, user_id=identity.user_id,
                issuer=self.issuer, created_at=database_now(session), authorized_until=principal.expires_at, phase='pending')
            row['authorization_tag'] = self._tag(row)
            principal.require_fresh()
            session.execute(intents.insert().values(**row))
            self._event(session, request_id, 'requested')
        return request_id

    def claim(self, request_id):
        worker = uuid4()
        with self.sessions() as session, session.begin():
            now = database_now(session)
            row = session.execute(update(intents).where(intents.c.request_id == request_id,
                intents.c.phase != 'complete', intents.c.lease_until < now).values(worker=worker, lease_until=now+60)
                .returning(*intents.c)).mappings().one_or_none()
            if row is None:
                return None
            if row['issuer'] != self.issuer or not hmac.compare_digest(row['authorization_tag'], self._tag(row)):
                raise DeletionUnavailable()
            self._event(session, request_id, 'claimed')
            return DeletionJob(row['request_id'], row['subject'], row['user_id'], worker, row['phase'], row['authorized_until'])

    def _advance(self, session, job, before, after):
        changed = session.execute(update(intents).where(intents.c.request_id == job.request_id,
            intents.c.subject == job.subject, intents.c.user_id == job.user_id, intents.c.worker == job.worker,
            intents.c.phase == before, intents.c.lease_until >= database_now(session)).values(phase=after)
            .returning(*intents.c)).mappings().one_or_none()
        if changed is None:
            raise DeletionUnavailable()
        original = {**changed, 'phase': before}
        if not hmac.compare_digest(changed['authorization_tag'], self._tag(original)):
            raise DeletionUnavailable()
        session.execute(update(intents).where(intents.c.request_id == job.request_id).values(authorization_tag=self._tag(changed)))
        self._event(session, job.request_id, after)

    def provider_absent(self, job):
        with self.sessions() as session, session.begin():
            self._advance(session, job, 'pending', 'provider_absent')

    def finish(self, job):
        with self.sessions() as session, session.begin():
            self._advance(session, job, 'provider_absent', 'complete')
            row = session.execute(select(UserIdentity.supabase_subject).where(UserIdentity.user_id == job.user_id)).one_or_none()
            if row is None or row[0] != job.subject:
                raise DeletionUnavailable()
            # Never cascade an unknown dependency or delete a reference MovieLens row.
            for model in (UserRating, GroupInvitation, Credential, UserIdentity):
                session.execute(delete(model).where(model.user_id == job.user_id))
            session.execute(delete(User).where(User.id == job.user_id))

    def release(self, job):
        with self.sessions() as session, session.begin():
            session.execute(update(intents).where(intents.c.request_id == job.request_id,
                intents.c.worker == job.worker).values(worker=None, lease_until=0))
