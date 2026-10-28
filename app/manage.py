"""Explicit operator commands; never called against production by tests."""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app import database, security
from app.migrations import migrate
from app.models import Credential
from app import config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["migrate", "recover-profile"])
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--output", type=Path, help="New private file for recovered credential; never stdout")
    args = parser.parse_args()
    try:
        config.validate()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    engine = database.create_database_engine()
    try:
        if args.command == "migrate":
            migrate(engine)
            print("Database schema is current")
        else:
            if not args.user_id or args.output is None:
                parser.error("Recovery requires --user-id and --output after verifying ownership out of band")
            # Exclusive file creation prevents accidentally overwriting an existing secret.
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                with Session(engine) as session, session.begin():
                    if database.get_user(session, args.user_id) is None or session.get(Credential, args.user_id) is not None:
                        raise ValueError("Only an existing unclaimed legacy profile may be recovered")
                    token, expires = security.issue_credential(session, args.user_id)
                    json.dump({"id": args.user_id, "token": token, "expires_at": expires}, output)
                    output.flush()
                    os.fsync(output.fileno())
            print("Recovery file created; protect it and transfer privately")
    except Exception:
        raise SystemExit("Operation failed; inspect configuration and private output file before retrying") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
