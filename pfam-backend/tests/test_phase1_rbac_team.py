import unittest
from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.middleware.auth import verify_clerk_jwt
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User, UserRole


class Phase1RBACTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with self.session_factory() as session:
            org_a = Organization(name="Org A")
            org_b = Organization(name="Org B")
            session.add_all([org_a, org_b])
            await session.flush()

            self.owner_user = User(
                org_id=org_a.id,
                clerk_user_id="clerk-owner-a",
                role=UserRole.OWNER,
                is_active=True,
            )
            self.admin_user = User(
                org_id=org_a.id,
                clerk_user_id="clerk-admin-a",
                role=UserRole.ADMIN,
                is_active=True,
            )
            self.read_only_user = User(
                org_id=org_a.id,
                clerk_user_id="clerk-ro-a",
                role=UserRole.READ_ONLY,
                is_active=True,
            )
            self.other_org_user = User(
                org_id=org_b.id,
                clerk_user_id="clerk-owner-b",
                role=UserRole.OWNER,
                is_active=True,
            )
            session.add_all(
                [
                    self.owner_user,
                    self.admin_user,
                    self.read_only_user,
                    self.other_org_user,
                ]
            )
            await session.commit()

            self.org_a_id = org_a.id
            self.org_b_id = org_b.id
            self.owner_db_id = self.owner_user.id
            self.admin_db_id = self.admin_user.id
            self.read_only_db_id = self.read_only_user.id
            self.other_org_user_id = self.other_org_user.id

        self.jwt_payload = {"org_id": self.org_a_id, "sub": "clerk-owner-a"}

        async def override_verify_clerk_jwt():
            return self.jwt_payload

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[verify_clerk_jwt] = override_verify_clerk_jwt
        app.dependency_overrides[get_db_session] = override_get_db
        self.client = TestClient(app)

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def test_unauthorized_returns_401_when_user_not_provisioned(self) -> None:
        self.jwt_payload = {"org_id": self.org_a_id, "sub": "unknown-user"}
        response = self.client.get("/team/members")
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "USER_NOT_PROVISIONED")

    async def test_read_only_cannot_invite_member(self) -> None:
        self.jwt_payload = {"org_id": self.org_a_id, "sub": "clerk-ro-a"}
        response = self.client.post(
            "/team/invite",
            json={"clerk_user_id": "invitee-1", "role": "analyst"},
        )
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "ROLE_FORBIDDEN")

    async def test_org_scoping_excludes_other_org_members(self) -> None:
        self.jwt_payload = {"org_id": self.org_a_id, "sub": "clerk-owner-a"}
        response = self.client.get("/team/members")
        self.assertEqual(response.status_code, 200)
        member_ids = {item["id"] for item in response.json()["items"]}
        self.assertIn(self.owner_db_id, member_ids)
        self.assertNotIn(self.other_org_user_id, member_ids)

    async def test_role_update_writes_append_only_audit(self) -> None:
        self.jwt_payload = {"org_id": self.org_a_id, "sub": "clerk-owner-a"}
        response = self.client.patch(
            f"/team/members/{self.read_only_db_id}/role",
            json={"role": "analyst"},
        )
        self.assertEqual(response.status_code, 200)

        async with self.session_factory() as session:
            result = await session.execute(
                select(AuditLog).where(
                    AuditLog.org_id == self.org_a_id,
                    AuditLog.event_type == "team.member_role_updated",
                    AuditLog.target_user_id == self.read_only_db_id,
                )
            )
            event = result.scalar_one_or_none()
            self.assertIsNotNone(event)
            self.assertEqual(event.metadata_json["from_role"], "read_only")
            self.assertEqual(event.metadata_json["to_role"], "analyst")

    async def test_auth_success_writes_audit_event(self) -> None:
        self.jwt_payload = {"org_id": self.org_a_id, "sub": "clerk-owner-a"}
        response = self.client.get("/team/members")
        self.assertEqual(response.status_code, 200)

        async with self.session_factory() as session:
            result = await session.execute(
                select(AuditLog).where(
                    AuditLog.org_id == self.org_a_id,
                    AuditLog.event_type == "auth.user_authenticated",
                    AuditLog.actor_user_id == self.owner_db_id,
                )
            )
            self.assertIsNotNone(result.scalar_one_or_none())


if __name__ == "__main__":
    unittest.main()
