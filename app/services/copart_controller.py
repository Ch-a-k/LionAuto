# app/services/copart_controller.py
import asyncio
from typing import Optional, Any, Dict, List
from loguru import logger
from datetime import timezone
from .copart import CopartBot, SessionStore  # импортируй свой файл с ботом

class CopartController:
    """
    Управляет жизненным циклом единственного экземпляра CopartBot,
    предоставляет потокобезопасные методы (через asyncio.Lock) и
    фонового "супервизора", который периодически проверяет сессию.
    """
    def __init__(self, username: str, password: str, headless: bool = True, session_db: str = "sessions.db"):
        self.username = username
        self.password = password
        self.headless = headless
        self.session_db = session_db

        self._bot: Optional[CopartBot] = None
        self._store: Optional[SessionStore] = None
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()
        self._stopped = asyncio.Event()
        self._supervisor_interval = 60  # сек. между health-проверками

    @property
    def is_started(self) -> bool:
        return self._bot is not None and not self._stopped.is_set()

    async def start(self) -> None:
        """Создаёт и запускает бота (idempotent)."""
        async with self._lock:
            if self._bot:
                return
            logger.info("Starting CopartBot...")
            self._store = SessionStore(self.session_db)
            await self._store.init()
            self._bot = CopartBot(self.username, self.password, headless=self.headless)
            await self._bot.start(storage_state=await self._store.get_storage_state(self.username))

            # Первая проверка/логин и сохранение стейта
            ok = await self._bot.ensure_session(self._store)
            if not ok:
                logger.warning("Copart session not valid on start()")

            # Запускаем супервизор
            self._stopped.clear()
            self._running.set()
            self._task = asyncio.create_task(self._supervisor_loop(), name="copart_supervisor")
            logger.info("CopartBot started.")

    async def stop(self) -> None:
        """Останавливает бота и супервизор (idempotent)."""
        async with self._lock:
            if not self._bot:
                return
            logger.info("Stopping CopartBot...")
            self._running.clear()
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None
            try:
                await self._bot.close()
            finally:
                self._bot = None
                self._stopped.set()
            logger.info("CopartBot stopped.")

    async def _supervisor_loop(self):
        """Периодически проверяет здоровье сессии и обновляет storage_state."""
        assert self._bot and self._store
        try:
            while self._running.is_set():
                try:
                    ok = await self._bot.ensure_session(self._store)
                    if not ok:
                        logger.warning("ensure_session failed in supervisor")
                except Exception as e:
                    logger.exception(f"Supervisor tick failed: {e}")
                await asyncio.sleep(self._supervisor_interval)
        except asyncio.CancelledError:
            pass

    # -----------------------
    # Методы управления ботом
    # -----------------------
    async def status(self) -> Dict[str, Any]:
        """Возвращает краткий статус бота."""
        async with self._lock:
            present = self._bot is not None
            healthy = False
            try:
                if self._bot:
                    healthy = await self._bot.health_check()
            except Exception:
                healthy = False
            return {
                "running": present and not self._stopped.is_set(),
                "healthy": healthy,
                "headless": self.headless,
                "username": self.username,
            }

    async def join_live(self, title_like: str) -> bool:
        """Join в live-аукцион по части названия модального слота."""
        async with self._lock:
            if not self._bot:
                raise RuntimeError("Bot is not started")
            return await self._bot.join_live_from_calendar_by_title(title_like)

    async def bid(self, amount: Optional[str | int] = None, times: int = 1, spacing_sec: float = 0.35) -> bool:
        """Сделать ставку (опционально с суммой) на текущем live виджете."""
        async with self._lock:
            if not self._bot:
                raise RuntimeError("Bot is not started")
            return await self._bot.bid_current_lot(amount=amount, times=times, spacing_sec=spacing_sec)

    async def lot_details(self, url: str) -> Dict[str, Any]:
        """Собрать детали лота по ссылке."""
        async with self._lock:
            if not self._bot:
                raise RuntimeError("Bot is not started")
            return await self._bot.get_lot_details(url)

    async def ensure_session(self) -> bool:
        """Ручной пинок ensure_session()."""
        async with self._lock:
            if not self._bot or not self._store:
                raise RuntimeError("Bot is not started")
            return await self._bot.ensure_session(self._store)

    async def health(self) -> bool:
        """Hand-check health без статуса."""
        async with self._lock:
            if not self._bot:
                return False
            return await self._bot.health_check()
