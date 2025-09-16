# iaai_service.py
import json
from typing import Optional, Any, Dict
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import aiosqlite

# =========================
# Хранилище сессий (SQLite) — как у тебя
# =========================
class SessionStore:
    def __init__(self, db_path: str = "sessions.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_sessions (
                username TEXT PRIMARY KEY,
                storage_state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
            await db.commit()

    async def get_storage_state(self, username: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT storage_state_json FROM bot_sessions WHERE username = ?", (username,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                try:
                    return json.loads(row[0])
                except Exception:
                    return None

    async def save_storage_state(self, username: str, storage_state: Dict[str, Any]):
        payload = json.dumps(storage_state, ensure_ascii=False)
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT INTO bot_sessions(username, storage_state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
              storage_state_json=excluded.storage_state_json,
              updated_at=excluded.updated_at
            """, (username, payload, now))
            await db.commit()


# ==============
# IAAI Bot (только авторизация и healthcheck)
# ==============
class IAAIBot:
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.headless = headless

        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    # ---------- lifecycle ----------
    async def start(self, storage_state: Optional[Dict[str, Any]] = None):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(storage_state=storage_state)
        self.page = await self.context.new_page()
        return self

    async def close(self):
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def storage_state(self) -> Dict[str, Any]:
        return await self.context.storage_state()

    # ---------- utils ----------
    async def _maybe_accept_cookies(self):
        """
        Неброский клик по возможным баннерам cookies/consent.
        """
        selectors = [
            "text=Accept", "text=I Accept", "text=Agree", "text=Got it",
            "button[aria-label*='Accept']", "button:has-text('Accept')",
            "#onetrust-accept-btn-handler", ".ot-pc-refuse-all-handler", ".accept-cookie"
        ]
        for sel in selectors:
            try:
                await self.page.locator(sel).first.click(timeout=1500)
                break
            except Exception:
                continue

    async def _click_any(self, selectors):
        for sel in selectors:
            try:
                await self.page.locator(sel).first.click(timeout=2500)
                return True
            except Exception:
                continue
        return False

    async def _fill_if_present(self, selectors, value):
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                await loc.fill(value, timeout=2500)
                return True
            except Exception:
                continue
        return False

    async def _visible_any(self, selectors, timeout=3000) -> bool:
        for sel in selectors:
            try:
                await self.page.locator(sel).first.wait_for(state="visible", timeout=timeout)
                return True
            except Exception:
                continue
        return False

    # ---------- auth ----------
    async def login_member(self) -> bool:
        """
        Пытается залогиниться на iaai.com, учитывая разные возможные разметки.
        Возвращает True при успехе.
        """
        try:
            await self.page.goto("https://www.iaai.com/", wait_until="domcontentloaded")
            await self._maybe_accept_cookies()

            # Открываем форму логина
            opened = await self._click_any([
                "a[href*='login']", "a:has-text('Sign In')", "a:has-text('Log In')",
                "button:has-text('Sign In')", "button[data-test='sign-in']",
                "a[aria-label*='Sign In']", "a[aria-label*='Log In']"
            ])
            if not opened:
                # Иногда форма на отдельном пути
                await self.page.goto("https://www.iaai.com/Login", wait_until="domcontentloaded")

            await self._maybe_accept_cookies()

            # Ждём инпуты логина/пароля (несколько вариантов)
            login_inputs = ["input#username", "input#email", "input[name='username']",
                            "input[name='email']", "input[type='email']"]
            pass_inputs  = ["input#password", "input[name='password']", "input[type='password']"]

            if not await self._visible_any(login_inputs, timeout=12000):
                # Иногда сначала нужно кликнуть "Member Login" таб
                await self._click_any(["button:has-text('Member Login')", "a:has-text('Member Login')"])
                await self._visible_any(login_inputs, timeout=8000)

            # Заполняем
            await self._fill_if_present(login_inputs, self.username)
            await self._fill_if_present(pass_inputs, self.password)

            # Сабмит
            submitted = await self._click_any([
                "button[type='submit']", "button:has-text('Sign In')", "button:has-text('Log In')",
                "input[type='submit']"
            ])
            if not submitted:
                # Нажмём Enter в поле пароля
                try:
                    await self.page.locator(pass_inputs[0]).press("Enter", timeout=1000)
                except Exception:
                    pass

            # Успешный вход: ждём редирект/признаки аккаунта
            try:
                await self.page.wait_for_url(r"**/myaccount**", timeout=25000)
            except PlaywrightTimeoutError:
                # Альтернатива: ищем элементы «My Account» / «Sign Out»
                ok = await self._visible_any([
                    "a:has-text('My Account')", "a:has-text('Sign Out')",
                    "button:has-text('Sign Out')", "[data-test='account-menu']"
                ], timeout=12000)
                if not ok:
                    raise

            print("✅ IAAI: авторизация успешна")
            return True

        except Exception as e:
            print(f"❌ IAAI: не удалось войти — {e}")
            return False

    # ---------- health ----------
    async def health_check(self) -> bool:
        """
        Быстрый пинг: открываем страницу аккаунта и проверяем наличие признаков авторизованного пользователя.
        """
        try:
            # Несколько возможных «домашних» страниц аккаунта
            for url in ("https://www.iaai.com/myaccount", "https://www.iaai.com/Dashboard", "https://www.iaai.com/"):
                try:
                    await self.page.goto(url, wait_until="domcontentloaded")
                    await self._maybe_accept_cookies()
                    ok = await self._visible_any([
                        "a:has-text('My Account')",
                        "a:has-text('Sign Out')",
                        "button:has-text('Sign Out')",
                        "[data-test='account-menu']"
                    ], timeout=6000)
                    if ok:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    async def ensure_session(self, store: SessionStore) -> bool:
        """
        Если сессия невалидна — логинимся и сохраняем storage_state.
        """
        if await self.health_check():
            return True
        print("🔐 IAAI: сессия невалидна — логин…")
        if not await self.login_member():
            return False
        state = await self.storage_state()
        await store.save_storage_state(self.username, state)
        return True


# ======================
# Пример использования (только проверка логина/здоровья)
# ======================
async def _demo():
    import os
    USER = os.getenv("IAAI_USER", "")
    PASS = os.getenv("IAAI_PASS", "")
    if not USER or not PASS:
        print("⛔ Укажи IAAI_USER и IAAI_PASS в переменных окружения")
        return

    store = SessionStore("sessions.db")
    await store.init()

    bot = IAAIBot(USER, PASS, headless=True)
    await bot.start(storage_state=await store.get_storage_state(USER))
    try:
        ok = await bot.ensure_session(store)
        print("health_check:", await bot.health_check(), "| ensure_session:", ok)
    finally:
        await bot.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
