import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routers import users, products, prices, admin, alerts, settings, selectors, firefox_sites, push, messages, categories
from scheduler import start_scheduler
from database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        from database import engine, Base
        import models
        import app.taxonomy.models  # Register taxonomy models
        Base.metadata.create_all(bind=engine)

        from app.taxonomy.seed import seed_taxonomy_data
        try:
            seed_taxonomy_data(db)
        except Exception as e:
            logging.error(f"Error seeding taxonomy data: {e}")

        from app.collectors.service import schedule_market_collectors
        try:
            schedule_market_collectors()
        except Exception as e:
            logging.error(f"Error scheduling market collectors: {e}")

        from app.deal_hunter.bot_listener import bot_listener
        try:
            bot_listener.start()
        except Exception as e:
            logging.error(f"Error starting Telegram bot listener: {e}")

        from app.deal_hunter.ram_bot import ram_bot_listener
        try:
            ram_bot_listener.start()
        except Exception as e:
            logging.error(f"Error starting RAM Telegram bot listener: {e}")

        start_scheduler(db)
    finally:
        db.close()
    yield
    from app.deal_hunter.bot_listener import bot_listener
    from app.deal_hunter.ram_bot import ram_bot_listener
    bot_listener.stop()
    ram_bot_listener.stop()

app = FastAPI(title="Market Price Intelligence Platform", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://pt.zeolite"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(prices.router)
app.include_router(admin.router)
app.include_router(alerts.router)
app.include_router(settings.router)
app.include_router(selectors.router)
app.include_router(firefox_sites.router)
app.include_router(push.router)
app.include_router(messages.router)
app.include_router(categories.router)

from app.routers import taxonomy, collectors, normalization, market, deal_hunter
app.include_router(taxonomy.router)
app.include_router(collectors.router)
app.include_router(normalization.router)
app.include_router(market.router)
app.include_router(deal_hunter.router)

@app.get("/health")
def health():
    return {"status": "ok"}
