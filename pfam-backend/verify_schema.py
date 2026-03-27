import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from app.db import async_session_factory
from app.models.organization import Organization, BillingPlan
from app.models.connectors import Store, AdAccount, Platform, SyncStatus
from app.models.ads import Campaign, AdStatus

async def verify_phase2():
    print("🚀 Starting Phase 2 Manual Verification...")
    
    async with async_session_factory() as session:
        # 1. Check existing Organization (Phase 1)
        result = await session.execute(select(Organization).limit(1))
        org = result.scalars().first()
        
        if not org:
            print("⚠️ No organizations found. Creating a test organization...")
            org = Organization(
                id=str(uuid.uuid4()),
                name="Verification Test Org",
                billing_plan=BillingPlan.STARTER,
                base_currency="USD"
            )
            session.add(org)
            await session.commit()
            await session.refresh(org)
        
        print(f"✅ Organization: {org.name} (Plan: {org.billing_plan})")

        # 2. Test Phase 2 Connector: Store
        test_store = Store(
            id=str(uuid.uuid4()),
            org_id=org.id,
            shopify_store_id=f"verify-shop-{uuid.uuid4().hex[:6]}",
            access_token_enc="encrypted_val",
            access_token_iv="iv_val",
            sync_status=SyncStatus.PENDING
        )
        session.add(test_store)
        
        # 3. Test Phase 2 Ads: Campaign
        test_account = AdAccount(
            id=str(uuid.uuid4()),
            org_id=org.id,
            platform=Platform.META,
            account_id="act_verify_123",
            account_name="Verify Account",
            access_token_enc="encrypted_val",
            access_token_iv="iv_val",
            sync_status=SyncStatus.RUNNING
        )
        session.add(test_account)
        await session.flush() 

        test_campaign = Campaign(
            id=str(uuid.uuid4()),
            org_id=org.id,
            ad_account_id=test_account.id,
            platform_campaign_id=f"camp_{uuid.uuid4().hex[:6]}",
            name="Manual Verification Campaign",
            status=AdStatus.ACTIVE
        )
        session.add(test_campaign)
        
        try:
            await session.commit()
            print("✅ Database Mapping: Successfully committed Store, AdAccount, and Campaign.")
            
            # Cleanup
            await session.delete(test_campaign)
            await session.delete(test_account)
            await session.delete(test_store)
            await session.commit()
            print("✅ Cleanup: All test Phase-2 data removed.")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Verification Failed: {str(e)}")
            raise e

    print("\n🌟 Phase 2 Verification PASSED. Models and DB are in sync.")

if __name__ == "__main__":
    asyncio.run(verify_phase2())
