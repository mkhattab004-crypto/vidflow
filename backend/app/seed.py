"""
Database seed script.
Run once after first migration: python -m app.seed
Seeds the 5 channels defined in the V1 spec.
"""
import asyncio
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, create_tables
from app.models.channel import Channel, ChannelHook, ChannelCTA

logger = logging.getLogger(__name__)

CHANNELS = [
    {
        "id": str(uuid.uuid4()),
        "name": "CurioBuzz",
        "niche": "curiobuzz",
        "language": "en",
        "voice_id": "af_bella",
        "primary_color": "#f59e0b",
        "secondary_color": "#1e293b",
        "script_tone": "dramatic",
        "safety_level": "normal",
        "is_islamic": False,
        "extra_config": {"youtube_handle": "@CurioBuzz"},
        "hooks": [
            "Did you know that this place doesn't officially exist on any map?",
            "Scientists were completely baffled when they discovered this.",
            "This is the most bizarre fact you'll hear today.",
        ],
        "ctas": [
            "Subscribe and hit the bell so you never miss a mind-blowing fact!",
            "Drop a comment below — which fact surprised you most?",
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Islamic Wisdom EN",
        "niche": "islamic",
        "language": "en",
        "voice_id": "am_adam",
        "primary_color": "#15803d",
        "secondary_color": "#fef9c3",
        "script_tone": "inspirational",
        "safety_level": "strict",
        "is_islamic": True,
        "extra_config": {"youtube_handle": "@IslamicWisdomEN"},
        "hooks": [
            "The Prophet ﷺ said something that changed the way millions live their lives.",
            "This verse from the Quran holds a secret most people overlook.",
            "What Allah told us about this topic will surprise you.",
        ],
        "ctas": [
            "May Allah bless you. Subscribe to continue this journey of knowledge.",
            "Share this video — spread the benefit and earn rewards in sha Allah.",
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "الحكمة الإسلامية",
        "niche": "islamic",
        "language": "ar",
        "voice_id": "ar_hamza",
        "primary_color": "#15803d",
        "secondary_color": "#fef9c3",
        "script_tone": "formal",
        "safety_level": "strict",
        "is_islamic": True,
        "extra_config": {"youtube_handle": "@HikmaIslamiyya"},
        "hooks": [
            "قال رسول الله ﷺ كلمة غيّرت حياة الملايين.",
            "هذه الآية الكريمة تحمل سراً يغفل عنه كثيرون.",
            "ما قاله الله تعالى عن هذا الأمر سيدهشك.",
        ],
        "ctas": [
            "اشترك في القناة ليصلك كل جديد من العلم النافع.",
            "انشر الفيديو وشارك الأجر — من دلّ على خير فله مثل أجر فاعله.",
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "İslami Hikmet TR",
        "niche": "islamic",
        "language": "tr",
        "voice_id": "tr_ali",
        "primary_color": "#15803d",
        "secondary_color": "#fef9c3",
        "script_tone": "inspirational",
        "safety_level": "strict",
        "is_islamic": True,
        "extra_config": {"youtube_handle": "@IslamiHikmetTR"},
        "hooks": [
            "Hz. Peygamber ﷺ milyonların hayatını değiştiren bir söz söyledi.",
            "Bu ayet çoğu kişinin gözden kaçırdığı bir sır taşıyor.",
        ],
        "ctas": [
            "Abone olun, faydalı bilgilerle dolu içerikler için bildirimleri açın.",
            "Bu videoyu paylaşın — hayır yoluna vesile olun.",
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "WealthMind",
        "niche": "finance",
        "language": "en",
        "voice_id": "am_michael",
        "primary_color": "#0ea5e9",
        "secondary_color": "#0f172a",
        "script_tone": "educational",
        "safety_level": "normal",
        "is_islamic": False,
        "extra_config": {"youtube_handle": "@WealthMindChannel"},
        "hooks": [
            "The top 1% use this financial strategy — and most people have never heard of it.",
            "I analyzed 100 millionaires and found one thing they all had in common.",
            "This mistake is costing the average person $50,000 a year.",
        ],
        "ctas": [
            "Subscribe for weekly strategies to build and protect your wealth.",
            "Drop your biggest money question in the comments — I read every one.",
        ],
    },
]


async def seed_channels(db: AsyncSession):
    for ch_data in CHANNELS:
        hooks = ch_data.pop("hooks", [])
        ctas = ch_data.pop("ctas", [])

        existing = await db.get(Channel, ch_data["id"])
        if existing:
            logger.info(f"Channel '{ch_data['name']}' already exists, skipping.")
            continue

        channel = Channel(**ch_data)
        db.add(channel)
        await db.flush()

        for text in hooks:
            db.add(ChannelHook(channel_id=channel.id, text=text, category="hook"))
        for text in ctas:
            db.add(ChannelCTA(channel_id=channel.id, text=text, cta_type="subscribe"))

        logger.info(f"Seeded channel: {ch_data['name']}")

    await db.commit()


async def run():
    logging.basicConfig(level=logging.INFO)
    await create_tables()
    async with AsyncSessionLocal() as db:
        await seed_channels(db)
    print("✓ Seed complete")


if __name__ == "__main__":
    asyncio.run(run())
