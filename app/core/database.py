"""
Database configuration and session management for the application.
Provides async database connectivity with connection pooling and health checks.
"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class DatabaseManager:
    """Manages database connections and sessions with proper lifecycle management."""
    
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    
    def initialize(self, database_url: Optional[str] = None) -> None:
        """Initialize database engine and session factory."""
        url = database_url or settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
        
        # Engine configuration for optimal performance
        engine_kwargs = {
            "url": url,
            "echo": settings.debug,
            "pool_pre_ping": settings.database_pool_pre_ping,
            "pool_recycle": settings.database_pool_recycle,
        }
        
        # Configure connection pool based on environment
        if settings.debug:
            # Development: Use NullPool for easier debugging
            engine_kwargs["poolclass"] = NullPool
        else:
            # Production: Use QueuePool with configured sizes
            engine_kwargs.update({
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "poolclass": QueuePool,
            })
        
        self._engine = create_async_engine(**engine_kwargs)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        
        logger.info("Database manager initialized successfully")
    
    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """Check database connectivity and health."""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._engine


# Global database manager instance
db_manager = DatabaseManager()


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    return db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session."""
    async with db_manager.get_session() as session:
        yield session


async def create_tables() -> None:
    """Create all database tables."""
    if not db_manager._engine:
        raise RuntimeError("Database not initialized")
    
    async with db_manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")


async def drop_tables() -> None:
    """Drop all database tables (use with caution)."""
    if not db_manager._engine:
        raise RuntimeError("Database not initialized")
    
    async with db_manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("Database tables dropped successfully")


@asynccontextmanager
async def database_lifespan():
    """Context manager for application database lifespan."""
    try:
        # Initialize database
        db_manager.initialize()
        await create_tables()
        
        # Perform health check
        is_healthy = await db_manager.health_check()
        if not is_healthy:
            raise RuntimeError("Database health check failed during startup")
        
        logger.info("Database startup completed successfully")
        yield
        
    except Exception as e:
        logger.error(f"Database startup failed: {e}")
        raise
    finally:
        # Cleanup
        await db_manager.close()
        logger.info("Database shutdown completed")


# Connection URL helper for synchronous tools (like Alembic)
def get_sync_database_url() -> str:
    """Get synchronous database URL for tools like Alembic."""
    return settings.database_url