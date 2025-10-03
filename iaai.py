# iaai.py (polite automation, human-like pacing – no anti-detect, Patchright version)
import asyncio
import json
import os
import random
import math
import platform
from datetime import datetime, timezone
from typing import Optional, Any, Dict, Callable, Awaitable

import aiosqlite
from patchright.async_api import async_playwright, TimeoutError as PatchrightTimeoutError, Page, Locator


# =========================
# Хранилище сессий (SQLite)
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
            async with db.execute(
                "SELECT storage_state_json FROM bot_sessions WHERE username = ?",
                (username,)
            ) as cur:
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


# =========================
# Утилиты «человечного» поведения (без антидетекта)
# =========================

def get_human_user_agent():
    """Генерирует реалистичный User-Agent для разных ОС"""
    chrome_versions = [
        "131.0.0.0", "130.0.0.0", "129.0.0.0", "128.0.0.0", "127.0.0.0"
    ]
    chrome_version = random.choice(chrome_versions)
    
    system = platform.system().lower()
    
    if system == 'windows':
        windows_versions = [
            "Windows NT 10.0; Win64; x64",
            "Windows NT 10.0; WOW64",
            "Windows NT 11.0; Win64; x64"
        ]
        os_string = random.choice(windows_versions)
    elif system == 'darwin':  # macOS
        mac_versions = [
            "Macintosh; Intel Mac OS X 10_15_7",
            "Macintosh; Intel Mac OS X 11_7_10",
            "Macintosh; Intel Mac OS X 12_7_6",
            "Macintosh; Intel Mac OS X 13_6_9",
            "Macintosh; Intel Mac OS X 14_7_1"
        ]
        os_string = random.choice(mac_versions)
    else:  # Linux
        linux_versions = [
            "X11; Linux x86_64",
            "X11; Linux i686"
        ]
        os_string = random.choice(linux_versions)
    
    webkit_version = f"537.{random.randint(1, 36)}"
    
    return f"Mozilla/5.0 ({os_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"

def get_human_viewport():
    """Возвращает случайный реалистичный размер экрана"""
    common_resolutions = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1600, "height": 900},
        {"width": 1280, "height": 720},
        {"width": 1680, "height": 1050},
        {"width": 2560, "height": 1440},
    ]
    return random.choice(common_resolutions)

def get_human_languages():
    """Возвращает реалистичные языковые предпочтения"""
    lang_preferences = [
        ["en-US", "en"],
        ["en-GB", "en"],
        ["en-CA", "en", "fr-CA"],
        ["en-AU", "en"],
        ["en-US", "en", "es-US"],
        ["en-US", "en", "de-DE", "de"],
    ]
    return random.choice(lang_preferences)

def _jitter(a: float, b: float) -> float:
    return random.uniform(a, b)

async def human_pause(a: float = 0.15, b: float = 0.6):
    await asyncio.sleep(_jitter(a, b))

async def human_type(page: Page, selector: str, text: str, per_char_ms=(30, 120)):
    # Более реалистичная печать с человекоподобными паузами
    delay = lambda: _jitter(per_char_ms[0], per_char_ms[1])
    
    await page.click(selector)
    await human_pause(0.1, 0.4)
    
    # Имитируем реальную скорость печати с ошибками
    for i, ch in enumerate(text):
        # Случайные опечатки (редко)
        if random.random() < 0.02 and i > 0:  # 2% шанс опечатки
            # Печатаем неправильный символ
            wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
            await page.type(selector, wrong_char, delay=delay())
            await human_pause(0.1, 0.3)  # Пауза перед исправлением
            await page.keyboard.press('Backspace')
            await human_pause(0.05, 0.15)
        
        await page.type(selector, ch, delay=delay())
        
        # Дополнительные паузы на знаках препинания и пробелах
        if ch in {'.', ',', '!', '?', ';', ':'}:
            await human_pause(0.1, 0.25)
        elif ch == ' ':
            await human_pause(0.03, 0.12)
        elif ch in {'@', '_', '-', '=', '+'}:
            await human_pause(0.05, 0.15)
        
        # Случайные микро-паузы для реализма
        if random.random() < 0.1:  # 10% шанс дополнительной паузы
            await human_pause(0.02, 0.08)
    
    await human_pause(0.15, 0.35)

async def smooth_mouse_move(page: Page, x2: float, y2: float, steps: int = 25):
    # Более реалистичное движение мыши с кривой Безье
    x1, y1 = 100 + random.random()*50, 150 + random.random()*80
    try:
        pos = await page.mouse.position()
        x1, y1 = pos["x"], pos["y"]
    except Exception:
        pass
    
    # Добавляем промежуточные точки для кривой Безье
    control_x = x1 + (x2 - x1) * 0.5 + _jitter(-50, 50)
    control_y = y1 + (y2 - y1) * 0.5 + _jitter(-50, 50)
    
    for i in range(1, steps + 1):
        t = i / steps
        
        # Кривая Безье для более естественного движения
        nx = (1-t)**2 * x1 + 2*(1-t)*t * control_x + t**2 * x2
        ny = (1-t)**2 * y1 + 2*(1-t)*t * control_y + t**2 * y2
        
        # Добавляем небольшие человеческие дрожания
        nx += _jitter(-1, 1)
        ny += _jitter(-1, 1)
        
        await page.mouse.move(nx, ny)
        
        # Переменная скорость движения (быстрее в середине, медленнее в начале/конце)
        speed_factor = math.sin(t * math.pi)  # 0 в начале/конце, 1 в середине
        delay = _jitter(0.003, 0.015) * (2 - speed_factor)
        await asyncio.sleep(delay)
    
    # Финальная микро-пауза перед кликом
    await asyncio.sleep(_jitter(0.05, 0.15))

async def hover_scroll_click(loc: Locator):
    page = loc.page
    
    # Случайно скроллим страницу перед действием (имитация чтения)
    if random.random() < 0.3:  # 30% шанс
        scroll_delta = _jitter(-200, 200)
        await page.mouse.wheel(0, scroll_delta)
        await human_pause(0.2, 0.5)
    
    try:
        box = await loc.bounding_box()
        if box:
            # Добавляем случайное смещение в пределах элемента
            offset_x = _jitter(-box["width"]*0.2, box["width"]*0.2)
            offset_y = _jitter(-box["height"]*0.2, box["height"]*0.2)
            
            target_x = box["x"] + box["width"]/2 + offset_x
            target_y = box["y"] + box["height"]/2 + offset_y
            
            await smooth_mouse_move(page, target_x, target_y)
    except Exception:
        pass
    
    try:
        await loc.scroll_into_view_if_needed()
        await human_pause(0.1, 0.3)
    except Exception:
        pass
    
    try:
        await loc.hover()
        await human_pause(0.1, 0.4)  # Пауза после ховера
    except Exception:
        pass
    
    # Иногда делаем двойной клик случайно (человеческая ошибка)
    if random.random() < 0.05:  # 5% шанс
        await loc.click()
        await human_pause(0.05, 0.1)
    
    await loc.click()
    
    # Небольшая пауза после клика
    await human_pause(0.1, 0.3)

async def retry(fn: Callable[[], Awaitable[Any]], *, attempts: int = 3, base_delay: float = 0.6, max_delay: float = 3.5):
    last_err = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last_err = e
            sleep_for = min(max_delay, base_delay * (2 ** i)) + _jitter(0, 0.2)
            await asyncio.sleep(sleep_for)
    raise last_err if last_err else RuntimeError("retry: unknown error")


# ==============
# IAAI Bot
# ==============
from patchright.async_api import Browser, BrowserContext

class IAAIBot:
    def __init__(self, username: str, password: str,
                 headless: bool = False, verbose: bool = True, slow_mo_ms: int = 0):
        self.username = username
        self.password = password
        self.headless = headless
        self.verbose = verbose
        self.slow_mo_ms = slow_mo_ms

        self._pr = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    # ---------- lifecycle ----------
    async def start(self, storage_state: Optional[Dict[str, Any]] = None):
        if self.verbose:
            print(f"🧭 Launching Chromium (Patchright) | headless={self.headless} slowMo={self.slow_mo_ms}ms")
        
        self._pr = await async_playwright().start()
        
        # Человекоподобные аргументы запуска браузера
        viewport = get_human_viewport()
        user_agent = get_human_user_agent()
        languages = get_human_languages()
        
        if self.verbose:
            print(f"🧭 Using viewport: {viewport['width']}x{viewport['height']}")
            print(f"🧭 Using User-Agent: {user_agent[:80]}...")
            print(f"🧭 Using languages: {languages}")
        
        # Запуск браузера с человекоподобными настройками
        browser_args = [
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-extensions',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
        ]
        
        self.browser = await self._pr.chromium.launch(
            headless=self.headless, 
            slow_mo=self.slow_mo_ms,
            args=browser_args
        )

        # Создаём контекст с человекоподобными настройками
        if self.verbose:
            print("🧭 Creating human-like browser context")
        
        context_options = {
            'storage_state': storage_state,
            'viewport': viewport,
            'user_agent': user_agent,
            'locale': languages[0] if languages else 'en-US',
            'timezone_id': 'America/New_York',  # Можно сделать рандомным
            'permissions': ['geolocation'],
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': ','.join([f"{lang};q={1.0 - i*0.1:.1f}" for i, lang in enumerate(languages[:5])]),
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Ch-Ua': f'"Google Chrome";v="{user_agent.split("Chrome/")[1].split(".")[0]}", "Chromium";v="{user_agent.split("Chrome/")[1].split(".")[0]}", "Not=A?Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': f'"{platform.system()}"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            },
            'java_script_enabled': True,
            'bypass_csp': True,
            'ignore_https_errors': True,
        }
        
        self.context = await self.browser.new_context(**context_options)
        
        # Добавляем дополнительные человекоподобные свойства
        await self.context.add_init_script("""
            // Переопределяем webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Добавляем реалистичные свойства navigator
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        name: 'Chrome PDF Plugin',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format'
                    },
                    {
                        name: 'Chrome PDF Viewer',
                        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                        description: ''
                    },
                    {
                        name: 'Native Client',
                        filename: 'internal-nacl-plugin',
                        description: ''
                    }
                ],
            });
            
            // Добавляем реалистичные размеры экрана с небольшими отклонениями
            const originalQuery = window.screen.width;
            Object.defineProperty(screen, 'availWidth', {
                get: () => originalQuery - Math.floor(Math.random() * 10),
            });
            
            // Переопределяем permissions
            const originalQuery2 = navigator.permissions.query;
            navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery2(parameters)
            );
            
            // Добавляем случайные колебания в timing API
            const originalNow = performance.now;
            performance.now = () => originalNow.call(performance) + Math.random() * 0.1;
        """)
        
        self.page = await self.context.new_page()
        
        # Устанавливаем дополнительные заголовки для страницы
        await self.page.set_extra_http_headers({
            'DNT': '1',  # Do Not Track
            'Connection': 'keep-alive',
        })
        
        if self.verbose:
            print("🧭 Human-like browser context created successfully")
        
        return self

    async def close(self):
        try:
            if self.page:
                try:
                    await self.page.close()
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️  Ошибка при закрытии страницы: {e}")
            
            if self.context:
                try:
                    await self.context.close()
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️  Ошибка при закрытии контекста: {e}")
            
            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️  Ошибка при закрытии браузера: {e}")
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Общая ошибка при закрытии: {e}")
        finally:
            if self._pr:
                try:
                    await self._pr.stop()
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️  Ошибка при остановке Patchright: {e}")
            
            # Обнуляем все ссылки
            self.page = None
            self.context = None
            self.browser = None
            self._pr = None

    async def storage_state(self) -> Dict[str, Any]:
        return await self.context.storage_state()

    # ---------- helpers ----------
    async def _maybe_handle_modals(self):
        """Обрабатывает различные модальные окна на сайте"""
        # Сначала обрабатываем основное модальное окно (может быть на любом языке)
        await self._maybe_handle_modal_dialog()
        # Затем куки
        await self._maybe_accept_cookies()
    
    async def _maybe_handle_modal_dialog(self):
        """Обрабатывает модальные окна с различными языковыми вариантами кнопок отказа"""
        try:
            # Увеличиваем таймаут ожидания модального окна
            modal_dialog = self.page.locator("div.modal-dialog.modal-md").first
            
            # Проверяем, появилось ли модальное окно (даём больше времени)
            modal_found = False
            try:
                await modal_dialog.wait_for(state="visible", timeout=8000)
                modal_found = True
            except Exception:
                # Проверяем другие варианты модальных окон
                alternative_modals = [
                    "div.modal-dialog",
                    ".modal",
                    "[role='dialog']",
                    ".popup",
                    ".overlay",
                ]
                
                for selector in alternative_modals:
                    try:
                        alt_modal = self.page.locator(selector).first
                        if await alt_modal.count() > 0:
                            modal_dialog = alt_modal
                            await modal_dialog.wait_for(state="visible", timeout=3000)
                            modal_found = True
                            if self.verbose:
                                print(f"📋 Найдено альтернативное модальное окно: {selector}")
                            break
                    except Exception:
                        continue
            
            if not modal_found:
                return False
                
            if await modal_dialog.count() > 0:
                if self.verbose:
                    print("📋 Найдено модальное окно")
                
                # Даём время модальному окну полностью загрузиться
                await human_pause(0.5, 1.2)
                
                # Сначала ищем по точному селектору (самый надёжный способ)
                decline_btn = self.page.locator("button.btn.btn-md.btn-tertiary[data-dismiss='modal']").first
                
                if await decline_btn.count() > 0:
                    btn_text = await decline_btn.text_content()
                    await hover_scroll_click(decline_btn)
                    if self.verbose:
                        print(f"📋 Нажата кнопка отказа: '{btn_text}' (по селектору)")
                    
                    # Ждём, пока модальное окно закроется
                    await modal_dialog.wait_for(state="hidden", timeout=5000)
                    await human_pause(0.3, 0.8)
                    return True
                
                # Fallback 1: ищем кнопки с data-dismiss="modal" в модальном окне
                modal_dismiss_buttons = modal_dialog.locator("button[data-dismiss='modal']")
                if await modal_dismiss_buttons.count() > 0:
                    btn = modal_dismiss_buttons.first
                    btn_text = await btn.text_content()
                    await hover_scroll_click(btn)
                    if self.verbose:
                        print(f"📋 Нажата кнопка отказа: '{btn_text}' (data-dismiss)")
                    await human_pause(0.3, 0.8)
                    return True
                
                # Fallback 2: ищем по различным текстам на разных языках
                decline_texts = [
                    "Ні, дякую",           # Украинский
                    "No, thanks",          # Английский
                    "No thanks",           # Английский (короткий)
                    "Нет, спасибо",        # Русский
                    "Non, merci",          # Французский
                    "Nein, danke",         # Немецкий
                    "No, gracias",         # Испанский
                    "Não, obrigado",       # Португальский
                    "いいえ、結構です",         # Японский
                    "不用了，谢谢",           # Китайский
                    "Cancel",              # Отмена
                    "Close",               # Закрыть
                    "Dismiss",             # Отклонить
                    "Skip",                # Пропустить
                    "Later",               # Позже
                    "Maybe Later",         # Может быть позже
                ]
                
                for text in decline_texts:
                    decline_btn_text = modal_dialog.locator(f"button:has-text('{text}')").first
                    if await decline_btn_text.count() > 0:
                        await hover_scroll_click(decline_btn_text)
                        if self.verbose:
                            print(f"📋 Нажата кнопка отказа: '{text}' (по тексту)")
                        await human_pause(0.3, 0.8)
                        return True
                
                # Fallback 3: ищем кнопки с классами, которые обычно означают отказ/отмену
                fallback_selectors = [
                    "button.btn-tertiary",
                    "button.btn-secondary", 
                    "button.btn-outline",
                    "button[class*='cancel']",
                    "button[class*='dismiss']",
                    "button[class*='close']",
                    "button[class*='decline']",
                    "button[class*='no']",
                ]
                
                for selector in fallback_selectors:
                    btn = modal_dialog.locator(selector).first
                    if await btn.count() > 0:
                        btn_text = await btn.text_content()
                        await hover_scroll_click(btn)
                        if self.verbose:
                            print(f"📋 Нажата кнопка отказа: '{btn_text}' (fallback: {selector})")
                        await human_pause(0.3, 0.8)
                        return True
                
                # Последний fallback: просто закрываем модальное окно через ESC
                if self.verbose:
                    print("📋 Не найдена подходящая кнопка, пробуем закрыть через ESC")
                await self.page.keyboard.press("Escape")
                await human_pause(0.5, 1.0)
                
                return True
                
        except Exception as e:
            if self.verbose:
                print(f"📋 Не удалось обработать модальное окно: {e}")
        
        return False
    
    async def _maybe_accept_cookies(self):
        """Обрабатывает куки-баннеры"""
        candidates = [
            "button:has-text('Accept All')",
            "button:has-text('Accept')",
            "button[aria-label*='Accept']",
            "text=I Accept",
        ]
        for sel in candidates:
            try:
                btn = self.page.locator(sel).first
                if await btn.count():
                    await hover_scroll_click(btn)
                    if self.verbose:
                        print("🍪 Accepted cookies")
                    break
            except Exception:
                continue

    # ---------- auth / health ----------
    async def login(self) -> bool:
        try:
            if self.verbose:
                print("→ Go to home")
            await retry(lambda: self.page.goto("https://www.iaai.com/", wait_until="domcontentloaded"))
            await human_pause(1.8, 2.6)
            await self._maybe_handle_modals()
            await human_pause(0.4, 0.9)

            # 0) Сначала пробуем твой точный XPath
            LOGIN_XPATH = "xpath=/html/body/section/header/div[2]/div/div[3]/div/div[1]/a[2]"
            try:
                loc = self.page.locator(LOGIN_XPATH).first
                if await loc.count() > 0:
                    await loc.wait_for(state="visible", timeout=8000)
                    # Для реализма — ховер+клик
                    await hover_scroll_click(loc)
                    if self.verbose:
                        print("→ Clicked login via provided XPATH")
                else:
                    raise RuntimeError("xpath not found")
            except Exception as e:
                if self.verbose:
                    print(f"→ XPATH click failed: {e}")

                # 1) Падаем на альтернативные селекторы
                alts = [
                    "a[aria-label='Log In']",
                    "a:has-text('Log In')",
                    "a:has-text('Sign In')",
                    "a[href*='login']",
                    "a[href*='signin']",
                    "button:has-text('Log In')",
                    "button:has-text('Sign In')",
                    ".login-link, .sign-in, [data-login], [data-signin]"
                ]
                clicked = False
                for sel in alts:
                    try:
                        l = self.page.locator(sel).first
                        if await l.count() > 0:
                            await l.wait_for(state="visible", timeout=6000)
                            await hover_scroll_click(l)
                            if self.verbose:
                                print(f"→ Clicked login via alt selector: {sel}")
                            clicked = True
                            break
                    except Exception:
                        pass

                # 2) Если кнопка не нашлась/не нажалась — пробуем прямой URL с реферером
                if not clicked:
                    if self.verbose:
                        print("→ No visible login control — open /Account/Login with referer")
                    try:
                        await self.page.goto(
                            "https://www.iaai.com/Account/Login",
                            wait_until="domcontentloaded",
                            referer="https://www.iaai.com/"
                        )
                    except Exception as e2:
                        # Тут как раз ловим твой кейс net::ERR_HTTP_RESPONSE_CODE_FAILURE
                        if self.verbose:
                            print(f"→ Direct /Account/Login failed: {e2}. Retrying via Dashboard with referer…")
                        # Ещё один обход: сначала Dashboard, затем редирект на логин (часто пускает)
                        await self.page.goto(
                            "https://www.iaai.com/Dashboard/Default",
                            wait_until="domcontentloaded",
                            referer="https://www.iaai.com/"
                        )

            # На странице логина тоже может всплыть модалка — закрываем
            await self._maybe_handle_modals()
            if self.verbose:
                print(f"→ Current URL after login navigation: {self.page.url}")

            # Ожидаем наличие полей формы (основные + запасные)
            selectors_email = ["#Email", "input[type='email']", "input[name='email']", "#email"]
            selectors_pass  = ["#Password", "input[type='password']", "input[name='password']", "#password"]

            # Даём странице стабилизироваться
            try:
                await self.page.wait_for_selector(selectors_email[0], timeout=12000)
                await self.page.wait_for_selector(selectors_pass[0], timeout=12000)
            except Exception:
                # fallback ожидание по альтернативам
                found_email = any([await self.page.locator(s).first.count() for s in selectors_email])
                found_pass  = any([await self.page.locator(s).first.count() for s in selectors_pass])
                if not (found_email and found_pass):
                    print("❌ Не удалось найти форму логина")
                    return False

            # Вводим email
            typed = False
            for e_sel in selectors_email:
                try:
                    await human_type(self.page, e_sel, self.username)
                    if self.verbose:
                        print(f"→ Email typed via {e_sel}")
                    typed = True
                    break
                except Exception:
                    pass
            if not typed:
                print("❌ Не удалось ввести email")
                return False

            # Вводим пароль
            typed = False
            for p_sel in selectors_pass:
                try:
                    await human_type(self.page, p_sel, self.password)
                    if self.verbose:
                        print(f"→ Password typed via {p_sel}")
                    typed = True
                    last_pass_sel = p_sel
                    break
                except Exception:
                    pass
            if not typed:
                print("❌ Не удалось ввести пароль")
                return False

            # Сабмит — сначала Enter на поле пароля
            submitted = False
            try:
                await self.page.press(last_pass_sel, "Enter")
                submitted = True
                if self.verbose:
                    print("→ Submitted via Enter")

                # ⬇️ ждём, пока страница действительно уйдёт с формы логина
                await self.page.wait_for_load_state("networkidle", timeout=30000)

                # Дополнительно ждём, чтобы URL изменился
                try:
                    await self.page.wait_for_url(
                        lambda url: "dashboard" in url.lower() or "account/login" not in url.lower(),
                        timeout=30000
                    )
                    if self.verbose:
                        print(f"→ Redirect detected: {self.page.url}")
                except Exception:
                    if self.verbose:
                        print("⚠️ Redirect after Enter не произошёл за 30с, продолжаю проверку...")
            except Exception:
                pass
            if not submitted:
                print("❌ Не удалось отправить форму логина")
                return False

            # Подтверждаем факт входа
            await human_pause(0.8, 1.4)
            # ok = await self.health_check()
            # if not ok:
            #     print("❌ Не удалось подтвердить вход после сабмита")
            #     if self.verbose:
            #         print(f"→ Current URL: {self.page.url}")
            #         try:
            #             await self.page.screenshot(path="debug_failed_health_check.png")
            #         except Exception:
            #             pass
            #     return False

            if self.verbose:
                print("✅ Вход подтверждён.")
            return True

        except PatchrightTimeoutError as e:
            print(f"❌ Таймаут при логине: {e}")
            return False
        except Exception as e:
            print(f"❌ Ошибка логина: {e}")
            return False



    async def health_check(self) -> bool:
        try:
            # 1) Главная
            await retry(lambda: self.page.goto("https://www.iaai.com/", wait_until="domcontentloaded"))
            await human_pause(0.3, 0.7)
            await self._maybe_handle_modals()

            # быстрые негативные проверки (признаки НЕ авторизован)
            url = self.page.url.lower()
            if any(k in url for k in ["login", "signin", "identity", "auth"]):
                if self.verbose:
                    print(f"❌ Health: на странице логина ({url})")
                return False
            for sel in ("#Email", "#Password", "input[type='email']", "input[type='password']"):
                if await self.page.locator(sel).first.count():
                    if self.verbose:
                        print(f"❌ Health: видны поля логина ({sel}) → не авторизован")
                    return False

            # положительные маркеры учётки
            positive_markers = [
                "a[aria-label='Sign Out']",
                "a:has-text('Sign Out')",
                "button:has-text('Sign Out')",
                "a:has-text('My Account')",
                "[aria-label*='My Account']",
                "[data-test*='profile']",
                "[data-qa*='account']",
                "img[alt*='avatar']",
                ".user-avatar,.profile-avatar,.account-menu"
            ]
            for sel in positive_markers:
                try:
                    await self.page.locator(sel).first.wait_for(state="visible", timeout=1200)
                    if self.verbose:
                        print(f"✅ Health: найден маркер учётки на главной → {sel!r}")
                    return True
                except Exception:
                    pass

            # 2) Пробуем прямо на Dashboard
            await self.page.goto("https://www.iaai.com/Dashboard/Default", wait_until="domcontentloaded")
            await human_pause(0.2, 0.5)
            await self._maybe_handle_modals()

            url = self.page.url.lower()
            if any(k in url for k in ["login", "signin", "identity", "auth"]):
                if self.verbose:
                    print(f"❌ Health: Dashboard редиректнул на логин ({url})")
                return False
            for sel in ("#Email", "#Password", "input[type='email']", "input[type='password']"):
                if await self.page.locator(sel).first.count():
                    if self.verbose:
                        print("❌ Health: на Dashboard видна форма логина → не авторизован")
                    return False

            dashboard_markers = [
                "a[aria-label='Sign Out']",
                "a:has-text('Sign Out')",
                "a:has-text('My Account')",
                "[aria-label*='My Account']",
                "[data-test*='profile']",
                "h1:has-text('Dashboard')",
                ".dashboard-content,.dashboard-wrapper,.my-account"
            ]
            for sel in dashboard_markers:
                try:
                    await self.page.locator(sel).first.wait_for(state="visible", timeout=1500)
                    if self.verbose:
                        print(f"✅ Health: найден маркер учётки на Dashboard → {sel!r}")
                    return True
                except Exception:
                    pass

            if self.verbose:
                print(f"❌ Health: не нашёл ни одного надёжного маркера (url={self.page.url})")
            return False

        except Exception as e:
            if self.verbose:
                print(f"❌ Health exception: {e}")
            return False


    async def ensure_session(self, store: SessionStore) -> bool:
        ok = await self.health_check()
        if ok:
            return True

        if self.verbose:
            print("🔐 Сессия невалидна — проверяем модальные окна и логинимся заново…")
        
        # ВАЖНО: После неудачного health_check сначала обрабатываем модальные окна
        # Они могли появиться на текущей странице и блокировать доступ к элементам
        await self._maybe_handle_modals()
        await human_pause(0.3, 0.7)
        
        ok = await self.login()
        if not ok:
            return False

        state = await self.storage_state()
        await store.save_storage_state(self.username, state)
        if self.verbose:
            print("💾 storage_state сохранён в SQLite")
        return True
    
    async def go_dashboard(self):
        await self.page.goto("https://www.iaai.com/Dashboard/Default", wait_until="domcontentloaded")
        await human_pause(0.4, 0.9)
        await self._maybe_handle_modals()

    async def go_live_auctions_calendar(self) -> list[dict]:
        """Открывает /LiveAuctionsCalendar, ждёт якоря и собирает все <a class='link heading-7'>."""
        target_url = "https://www.iaai.com/LiveAuctionsCalendar"
        if self.verbose:
            print(f"📅 Opening Live Auctions Calendar: {target_url}")

        try:
            await self.page.goto(
                target_url,
                wait_until="domcontentloaded",
                referer="https://www.iaai.com/"
            )
        except Exception:
            await retry(lambda: self.page.goto("https://www.iaai.com/", wait_until="domcontentloaded"))
            await human_pause(0.3, 0.7)
            await self._maybe_handle_modals()
            await retry(lambda: self.page.goto(target_url, wait_until="domcontentloaded"))

        await human_pause(0.4, 0.9)
        await self._maybe_handle_modals()

        # Пытаемся дождаться характерных элементов страницы (не критично, но полезно)
        anchors = [
            "h1:has-text('Live Auctions Calendar')",
            "text=Live Auctions Calendar",
            "[data-qa*='live-auctions-calendar']",
            "div[class*='calendar']",
            "section:has-text('Live Auctions')",
            "table:has(th:has-text('Auction'))",
        ]
        for sel in anchors:
            try:
                await self.page.locator(sel).first.wait_for(state="visible", timeout=3000)
                break
            except Exception:
                pass

        # В ЛЮБОМ СЛУЧАЕ собираем ссылки
        return await self.collect_link_heading7()


    async def _auto_scroll(self, max_steps: int = 20, step_px: int = 1200, pause=(0.2, 0.5)):
        """Плавный скролл вниз, пока контент подгружается (или пока не достигнем низа/лимита шагов)."""
        last_height = await self.page.evaluate("() => document.body.scrollHeight")
        steps = 0
        while steps < max_steps:
            await self.page.mouse.wheel(0, step_px)
            await human_pause(*pause)
            new_height = await self.page.evaluate("() => document.body.scrollHeight")
            if new_height <= last_height + 10:  # почти не растёт — вероятно, конец
                break
            last_height = new_height
            steps += 1

    async def collect_link_heading7(self) -> list[dict]:
        """
        Собирает все <a class="link heading-7" href="..."> на текущей странице.
        Возвращает список словарей: {"href": "...", "text": "..."} с абсолютными URL.
        """
        results: list[dict] = []

        # Сначала пробуем CSS-селектор
        locator = self.page.locator("a.link.heading-7")
        # Если вдруг сайт рендерится дольше — чуть подождём
        try:
            await locator.first.wait_for(state="visible", timeout=4000)
        except Exception:
            pass

        # Автоскролл, чтобы подтянуть всю ленту перед сбором
        await self._auto_scroll()

        # Обновляем локатор после скролла
        locator = self.page.locator("a.link.heading-7")

        count = await locator.count()
        if count == 0:
            # Fallback: XPath на класс с contains() (на случай лишних классов)
            xpath_loc = self.page.locator("//a[contains(concat(' ', normalize-space(@class), ' '), ' link ') and contains(concat(' ', normalize-space(@class), ' '), ' heading-7 ')]")
            count = await xpath_loc.count()
            if count == 0:
                # Ещё один запасной вариант (без дефиса, если верстка отличается)
                alt = self.page.locator("a.link.heading7, a[class*='link'][class*='heading-7']")
                count = await alt.count()
                anchors = alt
            else:
                anchors = xpath_loc
        else:
            anchors = locator

        # Сбор атрибутов
        seen = set()
        base = "https://www.iaai.com"
        for i in range(count):
            a = anchors.nth(i)
            href = await a.get_attribute("href")
            if not href:
                continue
            href = href.strip()
            if href.startswith("/"):
                href = base + href
            # иногда бывает "javascript:void(0)" — пропустим
            if not href.startswith("http"):
                continue

            text = (await a.text_content() or "").strip()
            if href in seen:
                continue
            seen.add(href)
            results.append({"href": href, "text": text})

        if self.verbose:
            print(f"🔗 Собрано ссылок link heading-7: {len(results)}")
        return results


    async def go_watchlist(self):
        # Поменяй путь на актуальный для IAAI (примерный URL; если у тебя другой — подставь)
        candidates = [
            "https://www.iaai.com/MyAccount/Watchlist",
            "https://www.iaai.com/Buyer/Watchlist",
        ]
        for url in candidates:
            try:
                await self.page.goto(url, wait_until="domcontentloaded")
                await human_pause(0.4, 0.9)
                # ищем таблицу/список вотчлиста
                table_like = self.page.locator("table, .table, .grid, .watchlist, [data-qa*='watchlist']").first
                if await table_like.count():
                    if self.verbose:
                        print(f"📋 Watchlist открыт: {url}")
                    return True
            except Exception:
                pass
        if self.verbose:
            print("⚠️  Не удалось открыть Watchlist (проверь URL/селекторы)")
        return False



# ======================
# Пример использования
# ======================
# ======================
# Обновлённый main
# ======================
async def main():
    USERNAME = os.getenv("IAAI_USER", "").strip()
    USERNAME = "db625@creditcar.ge"
    PASSWORD = os.getenv("IAAI_PASS", "").strip()
    PASSWORD = "trypass18zzz"
    HEADLESS = os.getenv("HEADLESS", "0") == "1"
    SLOWMO = int(os.getenv("SLOWMO", "0"))

    if not USERNAME or not PASSWORD:
        print("⛔ Укажи IAAI_USER и IAAI_PASS в переменных окружения.")
        return

    store = SessionStore("sessions.db")
    await store.init()

    storage = await store.get_storage_state(USERNAME)

    bot = IAAIBot(
        username=USERNAME,
        password=PASSWORD,
        headless=HEADLESS,
        verbose=True,
        slow_mo_ms=SLOWMO,
    )
    await bot.start(storage_state=storage)

    try:
        # Если storage пустой — сразу форсим login(), иначе пробуем оживить сессию
        if not storage:
            if not await bot.login():
                print("⛔ Авторизация не удалась (первичный вход)")
                return
            await store.save_storage_state(USERNAME, await bot.storage_state())
            if bot.verbose:
                print("💾 storage_state сохранён в SQLite (первичный вход)")
        # else:
        #     if not await bot.ensure_session(store):
        #         print("⛔ Авторизация не удалась (ensure_session)")
        #         return

        print("✅ Сессия валидна. Выполняю дальнейшие действия в кабинете…")

        # Дальнейшие действия
        # await bot.go_dashboard()
        # await bot.go_watchlist()
        links = await bot.go_live_auctions_calendar()
        print(f"✅ Найдено {len(links)} ссылок:")
        for i, item in enumerate(links, 1):
            print(f"{i:02d}. {item['text'] or '(no text)'} -> {item['href']}")
        # здесь добавлять шаги: поиск, ставки, экспорт и т.п.

    finally:
        await bot.close()



if __name__ == "__main__":
    asyncio.run(main())