"""Dormant single-job worker; no scheduler, credentials, environment switch or public endpoint."""
from app.deletion_provider import SupabaseIdentityEraser
from app.deletion_store import DeletionStore, DeletionUnavailable


class DeletionWorker:
    def __init__(self, store, provider, *, reviewed=False):
        if (reviewed is not True or type(store) is not DeletionStore or type(provider) is not SupabaseIdentityEraser
                or store.issuer != provider.issuer):
            raise DeletionUnavailable()
        self._store, self._provider = store, provider

    def run(self, request_id):
        job = None
        try:
            job = self._store.claim(request_id)
            if job is None:
                return 'unchanged'
            self._provider.ensure_absent(job.subject, job.provider_created_at, lambda: self._store.authorized(job))
            if job.phase == 'pending':
                self._store.provider_absent(job)
            self._store.finish(job)
            return 'complete'
        except Exception:
            raise DeletionUnavailable() from None
        finally:
            if job is not None:
                try:
                    self._store.release(job)
                except Exception:
                    raise DeletionUnavailable() from None
