#!/usr/bin/env python3
"""
Create a super_admins row (docs/rbac-redis-plan.md) -- operator-provisioned
only, deliberately: there is no self-service signup and no automatic seed
during init_db.py, the same "someone with database access has to actually
decide a real person gets platform-admin power" posture ADMIN_SECRET/
TENANTS_ADMIN_SECRET used to enforce via a shared secret only the team knew.
This is the replacement for typing that secret into a form -- run it once per
person who needs a super-admin login, not once per environment.

Usage:
    python -m scripts.seed_super_admin "Jane Doe" jane@example.com
The password is prompted for interactively (getpass, never a CLI arg or env
var) so it never lands in shell history or a process list.
"""
import getpass
import sys

import db.repository as db
from db.repositories.hospitals import hash_portal_password


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.seed_super_admin \"Full Name\" email@example.com", file=sys.stderr)
        sys.exit(1)
    name, email = sys.argv[1].strip(), sys.argv[2].strip()
    if not name or not email or "@" not in email:
        print("A non-empty name and a valid email are required.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)
    if password != getpass.getpass("Confirm password: "):
        print("Passwords did not match.", file=sys.stderr)
        sys.exit(1)

    try:
        super_admin = db.create_super_admin(email, hash_portal_password(password), name)
    except db.IntegrityError:
        print(f'A super admin with email "{email}" already exists.', file=sys.stderr)
        sys.exit(1)

    print(f"Created super admin #{super_admin['id']}: {super_admin['name']} <{super_admin['email']}>")
    print("Log in at /api/admin/super/login (the AdminSecretGate on any /admin/* page).")


if __name__ == "__main__":
    main()
