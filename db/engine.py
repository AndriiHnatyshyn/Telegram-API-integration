import logging
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DB_URL")

Base = declarative_base()
engine = create_async_engine(DB_URL, echo=False)

async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
