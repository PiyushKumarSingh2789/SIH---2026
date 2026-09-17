"""
Creates a handful of test users covering different roles/scopes, so RBAC can actually be
tested end to end. Passwords are simple ON PURPOSE for local dev/demo only -- never reuse
this pattern anywhere real. Run after generate_synthetic_data.py:

    python3 -m app.seeds.seed_users
"""
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User, Role, UserScope, RoleName, ScopeLevel

TEST_USERS = [
    {
        "email": "admin@sih26102.gov.in", "full_name": "System Administrator",
        "password": "Admin@123", "role": RoleName.SYSTEM_ADMIN, "scope_level": ScopeLevel.NATIONAL, "scope_value": None,
    },
    {
        "email": "ministry@sih26102.gov.in", "full_name": "Ministry Administrator",
        "password": "Ministry@123", "role": RoleName.MINISTRY_ADMIN, "scope_level": ScopeLevel.NATIONAL, "scope_value": None,
    },
    {
        "email": "state.up@sih26102.gov.in", "full_name": "UP State Officer",
        "password": "State@123", "role": RoleName.STATE_OFFICER, "scope_level": ScopeLevel.STATE, "scope_value": "Uttar Pradesh",
    },
    {
        "email": "district.lucknow@sih26102.gov.in", "full_name": "Lucknow District Reviewer",
        "password": "District@123", "role": RoleName.DISTRICT_REVIEWER, "scope_level": ScopeLevel.DISTRICT, "scope_value": "Lucknow",
    },
    {
        "email": "auditor@sih26102.gov.in", "full_name": "National Auditor",
        "password": "Auditor@123", "role": RoleName.AUDITOR, "scope_level": ScopeLevel.NATIONAL, "scope_value": None,
    },
]


def run() -> None:
    db = SessionLocal()
    try:
        created = 0
        for u in TEST_USERS:
            if db.query(User).filter(User.email == u["email"]).first():
                continue  # idempotent -- safe to re-run
            user = User(email=u["email"], full_name=u["full_name"], hashed_password=hash_password(u["password"]))
            db.add(user)
            db.flush()
            db.add(Role(user_id=user.id, role_name=u["role"]))
            db.add(UserScope(user_id=user.id, scope_level=u["scope_level"], scope_value=u["scope_value"]))
            created += 1
        db.commit()
        print(f"Seeded {created} test users (skipped {len(TEST_USERS) - created} already present).")
        print("Login with any of these emails + the password shown above -- e.g.:")
        print("  district.lucknow@sih26102.gov.in / District@123")
    finally:
        db.close()


if __name__ == "__main__":
    run()
