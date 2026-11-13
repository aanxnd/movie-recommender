"""Local-only staging database boundary; never falls back to production DATABASE_URL."""
import os
import re
from ipaddress import ip_address

from sqlalchemy.engine import make_url


def local_staging_url(value):
    try:
        url = make_url(value)
        address = ip_address('127.0.0.1' if url.host == 'localhost' else url.host)
        if (url.drivername not in {'postgresql', 'postgresql+psycopg'} or not address.is_loopback
                or not url.username or not url.database
                or set(url.query) - {'sslmode', 'connect_timeout', 'application_name', 'options', 'hostaddr'}
                or url.query.get('hostaddr', str(address)) != str(address)
                or any(os.environ.get(k) for k in ('PGSERVICE', 'PGSERVICEFILE'))):
            raise ValueError
        options = url.query.get('options', '')
        # CI fixtures have an independent random schema in the disposable DB.
        isolated_test = url.database == 'disposable' and re.fullmatch(r'-c search_path=verify_[0-9a-f]{32}', options)
        if not (re.fullmatch(r'movelle_staging_[a-z0-9_]+', url.database) or isolated_test):
            raise ValueError
        if options and not isolated_test:
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        return url.set(port=url.port or 5432, query={**url.query, 'hostaddr': str(address)})
    except Exception:
        raise ValueError('Explicit disposable loopback staging PostgreSQL required') from None
