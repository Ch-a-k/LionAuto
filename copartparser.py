# copartparser.py
import asyncio
import json
import re
from datetime import datetime, timezone, date
from typing import Optional, Any, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs
import os

import aiosqlite
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import time

load_dotenv()

# =========================
# Константы для локального API
# =========================
LOCAL_BATCH_URL = "http://37.60.253.236:89/lot/lots/batch"
LOCAL_AUTH = os.getenv("SECRET_KEY")

if not LOCAL_AUTH:
    raise RuntimeError("SECRET_KEY не найден в окружении (.env)")

# =========================
# Вспомогательные функции
# =========================
def _today_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _to_mmddyyyy_utc(dt: datetime) -> str:
    # ожидаем tz-aware в UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%m/%d/%Y")


def safe_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_odometer(odometer_str: str) -> Tuple[int, str]:
    """
    '0 mi (NOT ACTUAL)' → (0, 'NOT ACTUAL')
    '123,456 km (EXEMPT)' → (123456, 'EXEMPT')
    '123,456 mi' → (123456, '')
    '' → (0, '')
    """
    if not odometer_str:
        return 0, ""
    s = odometer_str.upper()

    # Бренд в скобках
    brand = ""
    m_brand = re.search(r"\(([^)]+)\)", s)
    if m_brand:
        brand = m_brand.group(1).strip()

    # Число
    m_num = re.search(r"(\d[\d,]*)", s)
    if m_num:
        num = m_num.group(1).replace(",", "")
        try:
            value = int(num)
        except ValueError:
            value = 0
    else:
        value = 0

    return value, brand


def parse_cylinders(cyl: str | None) -> Optional[int]:
    """
    '4 CYL' → 4
    'V6' → 6
    ''/None → None
    """
    if not cyl:
        return None
    m = re.search(r"\d+", str(cyl))
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def parse_title_for_year_make_model_body(title: str) -> Tuple[Optional[int], str, str, str]:
    """
    '2014 UTIL REEFER 53' - Refrigerated Van Trailer'
    → (2014, 'UTIL', "REEFER 53'", 'Refrigerated Van Trailer')
    """
    if not title:
        return None, "", "", ""

    year = None
    m_year = re.search(r"\b(19|20)\d{2}\b", title)
    if m_year:
        year = int(m_year.group(0))
        rest = title[m_year.end():].strip(" -")
    else:
        rest = title.strip()

    # Делим на 'левая часть - правая часть'
    body_type = ""
    if " - " in rest:
        left, right = rest.split(" - ", 1)
        name_part = left.strip()
        body_type = right.strip()
    else:
        name_part = rest

    parts = name_part.split()
    if parts:
        make = parts[0]
        model = " ".join(parts[1:]) if len(parts) > 1 else ""
    else:
        make, model = "", ""

    return year, make, model, body_type


def build_hd_and_thumb_images(images: List[str]) -> Tuple[List[str], List[str]]:
    """
    На входе thumbnails (_thb).
    На выходе: (hd_list, thumb_list)
    _thb -> _ful и _hrs.
    """
    thumbs = list(dict.fromkeys(images))  # unique, порядок
    hd: List[str] = []

    for url in thumbs:
        if "_thb" in url:
            hd_ful = url.replace("_thb", "_ful")
            hd_hrs = url.replace("_thb", "_hrs")
            hd.append(hd_ful)
            hd.append(hd_hrs)
        else:
            hd.append(url)

    # уникализируем hd также
    hd = list(dict.fromkeys(hd))
    return hd, thumbs


def parse_location_state_from_sale_href(sale_href: str) -> Tuple[str, str, str]:
    """
    Из href слота календаря:
    https://www.copart.com/saleListResult/23/2025-11-21?location=CT%20-%20Hartford&saleDate=...&yardNum=23
    → location='CT - Hartford', state='CT', country='USA' (по умолчанию)
    """
    try:
        p = urlparse(sale_href)
        qs = parse_qs(p.query)
        loc = qs.get("location", [""])[0]
        loc = loc.replace("+", " ")
        state = ""
        if " - " in loc:
            state = loc.split(" - ", 1)[0].strip()
        country = "USA"  # по умолчанию
        return loc, state, country
    except Exception:
        return "", "", ""


def extract_auction_date_from_sale_href(sale_href: str) -> Optional[str]:
    """
    saleDate=epoch_ms → 'YYYY-MM-DD'
    """
    try:
        p = urlparse(sale_href)
        qs = parse_qs(p.query)
        if "saleDate" in qs and qs["saleDate"]:
            ms = int(qs["saleDate"][0])
            dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
            return dt.date().isoformat()
    except Exception:
        pass
    return None


# =========================
# map_factum_to_model
# =========================
def map_factum_to_model(item: Dict[str, Any]) -> Dict[str, Any]:
    """Приводим структуру Factum к VehicleModel / VehicleModelOther."""
    cylinders_raw = item.get("cylinders")
    if isinstance(cylinders_raw, str):
        cylinders_val = parse_cylinders(cylinders_raw)
    elif isinstance(cylinders_raw, int):
        cylinders_val = cylinders_raw
    else:
        cylinders_val = None

    return {
        "lot_id": item.get("lot_id"),
        "base_site": safe_str(item.get("base_site")),
        "odometer": item.get("odometer", 0),
        "price": item.get("price", 0),
        "reserve_price": item.get("reserve_price", 0),
        "bid": item.get("bid", 0),
        "auction_date": item.get("auction_date"),
        "cost_repair": item.get("cost_repair", 0),
        "year": item.get("year"),
        "cylinders": cylinders_val,
        "state": item.get("state"),

        "vehicle_type": safe_str(item.get("vehicle_type")),
        "make": safe_str(item.get("make")),
        "model": safe_str(item.get("model")),
        "damage_pr": safe_str(item.get("damage_pr")),
        "damage_sec": safe_str(item.get("damage_sec")),
        "keys": safe_str(item.get("keys")),
        "odobrand": safe_str(item.get("odobrand")),
        "fuel": safe_str(item.get("fuel")),
        "drive": safe_str(item.get("drive")),
        "transmission": safe_str(item.get("transmission")),
        "color": safe_str(item.get("color")),
        "status": safe_str(item.get("status")),
        "auction_status": safe_str(item.get("auction_status")) or "Not Sold",
        "body_type": safe_str(item.get("body_type")),
        "series": safe_str(item.get("series")),
        "title": safe_str(item.get("title")) or "",

        "vin": item.get("vin"),
        "engine": item.get("engine"),
        "engine_size": item.get("engine_size"),
        "location": item.get("location"),
        "location_old": item.get("location_old"),
        "country": item.get("country"),

        "document": safe_str(item.get("document")),
        "document_old": safe_str(item.get("document_old")),
        "seller": safe_str(item.get("seller")),

        "image_thubnail":
            (item["link_img_small"][0] if item.get("link_img_small") else None),

        "is_buynow": item.get("is_buynow", False),
        "link_img_hd": item.get("link_img_hd") or [],
        "link_img_small": item.get("link_img_small") or [],
        "link": item.get("link"),
        "seller_type": safe_str(item.get("seller_type")),

        "risk_index": item.get("risk_index"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "is_historical": item.get("is_historical", False),
    }


def map_copart_to_factum(
    sale_slot: Dict[str, Any],   # из get_auction_links
    lot_row: Dict[str, Any],    # из get_sale_lots
    details: Dict[str, Any],    # из get_lot_details
    base_site: str = "copart",
) -> Dict[str, Any]:
    """
    Мапим структуру Copart → «factum»-словарь, из которого потом
    идёт map_factum_to_model.
    """
    # базовые вещи
    lot_id = lot_row.get("lot_number") or details.get("lot_number")
    lot_link = details.get("lot_link") or lot_row.get("href")
    title = details.get("title") or lot_row.get("title") or ""

    # год / марка / модель / body_type
    year, make, model, body_type = parse_title_for_year_make_model_body(title)

    # одометр
    odo_val, odo_brand = parse_odometer(details.get("odometer", ""))

    # location / state / country из href слота
    location, state, country = parse_location_state_from_sale_href(sale_slot.get("href", ""))

    # дата аукциона
    auction_date = extract_auction_date_from_sale_href(sale_slot.get("href", ""))

    # картинки
    link_img_hd, link_img_small = build_hd_and_thumb_images(details.get("images") or [])

    now_iso = datetime.now(timezone.utc).isoformat()

    # цилиндры уже сразу приводим к int/None
    cylinders_val = parse_cylinders(details.get("cylinders"))

    return {
        "lot_id": lot_id,
        "base_site": base_site,
        "odometer": odo_val,
        "price": 0,
        "reserve_price": 0,
        "bid": 0,
        "auction_date": auction_date,
        "cost_repair": 0,
        "year": year,
        "cylinders": cylinders_val,
        "state": state,

        "vehicle_type": details.get("vehicle_type"),
        "make": make,
        "model": model,
        "damage_pr": details.get("primary_damage"),
        "damage_sec": None,
        "keys": details.get("keys"),
        "odobrand": odo_brand,
        "fuel": details.get("fuel"),
        "drive": details.get("drive"),
        "transmission": details.get("transmission"),
        "color": details.get("color"),
        "status": "",
        "auction_status": "Not Sold",
        "body_type": body_type,
        "series": "",
        "title": title,

        "vin": details.get("vin"),
        "engine": details.get("engine_type"),
        "engine_size": None,
        "location": location,
        "location_old": None,
        "country": country,

        "document": details.get("title_code"),
        "document_old": None,
        "seller": "",

        "link_img_small": link_img_small,
        "link_img_hd": link_img_hd,
        "image_thubnail": link_img_small[0] if link_img_small else None,

        "is_buynow": False,
        "link": lot_link,
        "seller_type": "",

        "risk_index": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "is_historical": False,
    }


# =========================
# Хранилище сессий (SQLite)
# =========================
class SessionStore:
    """
    Простейшее хранилище storage_state в SQLite.
    Ключом используем username (или любой другой ваш идентификатор аккаунта).
    """
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
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO bot_sessions(username, storage_state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                  storage_state_json=excluded.storage_state_json,
                  updated_at=excluded.updated_at
                """,
                (username, payload, now),
            )
            await db.commit()


# ==============
# Copart Bot
# ==============
class CopartBot:
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.headless = headless

        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    # ---------- lifecycle ----------
    async def start(self, storage_state=None):
        self._pw = await async_playwright().start()

        # CDP опционально через env
        expose_cdp = os.getenv("EXPOSE_CDP", "1") == "1"
        cdp_port = int(os.getenv("CDP_PORT", "9222"))

        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        if expose_cdp:
            launch_args += [
                f"--remote-debugging-port={cdp_port}",
                "--remote-debugging-address=0.0.0.0",
            ]

        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )
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

    # ---------- small utils ----------
    async def _maybe_accept_cookies(self):
        try:
            await self.page.locator("text=Accept").first.click(timeout=2000)
        except Exception:
            pass

    async def _scroll_to_bottom(self, step: int = 1500, max_iters: int = 20):
        prev_height = await self.page.evaluate("document.body.scrollHeight")
        iters = 0
        while iters < max_iters:
            iters += 1
            await self.page.mouse.wheel(0, step)
            await self.page.wait_for_timeout(250)
            cur_height = await self.page.evaluate("document.body.scrollHeight")
            if cur_height <= prev_height:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(300)
                cur_height = await self.page.evaluate("document.body.scrollHeight")
                if cur_height <= prev_height:
                    break
            prev_height = cur_height

    async def _wait_table_ready(self, hard_timeout: int = 20000):
        """
        Ждём загрузки таблицы lot-ов на странице saleListResult.
        """
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_selector("table#serverSideDataTable", timeout=hard_timeout)
        try:
            await self.page.wait_for_selector(
                "table#serverSideDataTable tbody tr a.search-results",
                timeout=2500,
            )
        except Exception:
            await self._scroll_to_bottom()
            await self.page.wait_for_selector(
                "table#serverSideDataTable tbody tr a.search-results",
                timeout=hard_timeout,
            )

    def _lot_id_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"/lot/(\d+)", urlparse(url).path)
        return m.group(1) if m else None

    # ---------- auth / health ----------
    async def login_member(self) -> bool:
        """
        Логин на copart.com как member.
        """
        await self.page.goto("https://www.copart.com", wait_until="domcontentloaded")
        await self._maybe_accept_cookies()

        # Кнопка Sign In на главной
        await self.page.click("button[data-uname='homePageSignIn']")
        await self.page.wait_for_selector(
            "a[data-uname='homePageMemberSignIn']",
            timeout=8000,
        )
        await self.page.click("a[data-uname='homePageMemberSignIn']")

        # Поля логина
        await self.page.wait_for_selector("input#username")
        await self.page.fill("input#username", self.username)
        await self.page.fill("input#password", self.password)

        await self.page.click("button[data-uname='loginSigninmemberbutton']")

        try:
            await self.page.wait_for_url("**/dashboard*", timeout=25000)
            await self.page.wait_for_selector("text=Hi,", timeout=20000)
            greet = await self.page.locator("text=Hi,").first.text_content()
            print(f"✅ Вошёл: {(greet or '').strip()}")
            return True
        except PlaywrightTimeoutError as e:
            print(f"❌ Не удалось подтвердить вход: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Быстрый пинг: пытаемся открыть dashboard и увидеть "Hi,".
        """
        try:
            await self.page.goto("https://www.copart.com/dashboard", wait_until="domcontentloaded")
            await self._maybe_accept_cookies()
            await self.page.wait_for_selector("text=Hi,", timeout=8000)
            return True
        except Exception:
            return False

    async def ensure_session(self, store: SessionStore) -> bool:
        """
        Проверяет, залогинен ли бот; если нет — делает логин и обновляет storage_state в БД.
        """
        ok = await self.health_check()
        if ok:
            return True

        print("🔐 Сессия невалидна — логинюсь заново…")
        ok = await self.login_member()
        if not ok:
            return False

        state = await self.storage_state()
        await store.save_storage_state(self.username, state)
        return True

    # ---------- календарь аукционов ----------
    async def goto_auction_calendar(self):
        """
        Просто открывает страницу календаря аукционов.
        """
        await self.page.goto("https://www.copart.com/auctionCalendar", wait_until="load")
        await self._maybe_accept_cookies()

    async def get_auction_links(self) -> List[Dict[str, str]]:
        """
        С /auctionCalendar — {date, time, title, href}
        href ведёт на saleListResult (список машин по площадке/дате).
        """
        await self.goto_auction_calendar()
        await self.page.wait_for_selector("a[data-url]", timeout=20000)

        items = await self.page.evaluate(r"""
        () => {
          const toAbs = (u) => new URL(u, window.location.origin).href;

          const sampleLink = document.querySelector("a[data-url]");
          if (!sampleLink) return [];
          const table = sampleLink.closest("table") || document.querySelector("table");
          if (!table) return [];

          const colDates = [];
          const headRow = table.querySelector("thead tr");
          if (headRow) {
            const headCells = Array.from(headRow.children);
            headCells.forEach((cell, idx) => {
              let txt = (cell.textContent || "").trim().replace(/\s*\n\s*/g, " ");
              const m = txt.match(/\b\d{2}\/\d{2}\/\d{4}\b/);
              if (m) txt = m[0];
              colDates[idx] = txt;
            });
          }

          const anchors = Array.from(table.querySelectorAll("a[data-url]"));
          const results = [];
          for (const a of anchors) {
            const cell = a.closest("td,th");
            if (!cell) continue;
            const row = cell.parentElement;
            if (!row) continue;

            const rowCells = Array.from(row.children);
            const colIndex = rowCells.indexOf(cell);

            let timeText = "";
            const firstCell = rowCells[0];
            if (firstCell) {
              const raw = (firstCell.textContent || "").trim();
              const m = raw.match(/\b\d{1,2}:\d{2}\s?(AM|PM)\b/i);
              timeText = m ? m[0] : raw;
            }

            const dateText = (colDates[colIndex] || "").trim();
            const title = (a.textContent || "").trim();
            const hrefAttr = a.getAttribute("href") || a.getAttribute("data-url") || "";
            const href = toAbs(hrefAttr);

            if (href && title) results.push({ date: dateText, time: timeText, title, href });
          }
          return results;
        }
        """)
        return items

    @staticmethod
    def _extract_date_from_href(href: str) -> Optional[str]:
        """
        Возвращает дату формата MM/DD/YYYY из href:
        - путь /YYYY-MM-DD
        - или query saleDate=epoch_ms (UTC)
        """
        if not href:
            return None

        # /YYYY-MM-DD
        m = re.search(r"/(\d{4}-\d{2}-\d{2})(?:[/?#]|$)", href)
        if m:
            iso = m.group(1)
            try:
                dt = datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                return _to_mmddyyyy_utc(dt)
            except ValueError:
                pass

        # saleDate=epoch_ms (UTC)
        try:
            qs = parse_qs(urlparse(href).query)
            if "saleDate" in qs and qs["saleDate"]:
                ms = int(qs["saleDate"][0])
                dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
                return _to_mmddyyyy_utc(dt)
        except Exception:
            pass

        return None

    async def get_regions_for_date(self, target: date | None = None) -> List[Dict[str, str]]:
        """
        Фильтрует ссылки календаря по конкретной дате.
        """
        if target is None:
            target = _today_utc_date()
        target_str = _to_mmddyyyy_utc(datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc))

        links = await self.get_auction_links()
        out: List[Dict[str, str]] = []
        for item in links:
            dt = (item.get("date") or "").strip()
            if not dt:
                dt = self._extract_date_from_href(item.get("href") or "") or ""
            if dt == target_str:
                out.append(item)
        return out

    # ---------- парсинг списка машин для конкретного аукциона ----------
    async def get_sale_lots(self, sale_url: str) -> List[Dict[str, Any]]:
        """
        Открывает saleListResult (href из календаря) и парсит таблицу машин.
        """
        await self.page.goto(sale_url, wait_until="domcontentloaded")
        await self._maybe_accept_cookies()

        await self._wait_table_ready(hard_timeout=30000)

        items: List[Dict[str, Any]] = await self.page.evaluate(r"""
        () => {
          const table = document.querySelector("table#serverSideDataTable");
          if (!table) return [];
          const rows = Array.from(table.querySelectorAll("tbody tr"));
          const results = [];

          const norm = (txt) => (txt || "").replace(/\s+/g, " ").trim();

          for (const tr of rows) {
            const cells = Array.from(tr.children);
            const data = cells.map(td => norm(td.textContent || ""));

            // ссылка на лот
            const a = tr.querySelector("a.search-results");
            const href = a ? a.href : "";
            const title = a ? norm(a.textContent || "") : "";

            // lot number
            let lotNumber = "";
            const lotCell = tr.querySelector("[data-uname='lotsearchLotnumber']");
            if (lotCell) {
              lotNumber = norm(lotCell.textContent || "");
            }
            if (!lotNumber && href) {
              const m = href.match(/\/lot\/(\d+)/);
              if (m) lotNumber = m[1];
            }

            results.push({
              lot_number: lotNumber,
              title,
              href,
              columns: data,
            });
          }

          return results;
        }
        """)
        return items

    # ---------- парсинг конкретного лота ----------
    async def _ensure_on_lot(self, expected_url: str, *, attempts: int = 3) -> bool:
        exp_lot = self._lot_id_from_url(expected_url)
        for i in range(1, attempts + 1):
            cur = self.page.url
            cur_lot = self._lot_id_from_url(cur)

            dom_lot = ""
            try:
                await self.page.wait_for_selector("h1.title, #LotNumber, .lot-detail-section", timeout=6000)
                try:
                    dom_lot = (await self.page.locator("#LotNumber").first.inner_text()).strip()
                except Exception:
                    dom_lot = ""
            except Exception:
                pass

            if cur_lot == exp_lot or (dom_lot and exp_lot and exp_lot in dom_lot):
                return True

            print(
                f"⚠️ Не та страница лота (got URL lot={cur_lot}, DOM lot={dom_lot or '—'}, need={exp_lot}) — "
                f"попытка {i}/{attempts}"
            )
            await self.page.goto(expected_url, wait_until="domcontentloaded")
            await self.page.wait_for_selector("h1.title, #LotNumber, .lot-detail-section", timeout=15000)
            await self._scroll_to_bottom(step=1200, max_iters=2)
        return False

    async def get_lot_details(self, lot_url: str) -> Dict[str, Any]:
        """
        Открывает страницу лота и вытягивает ключевые поля + ссылки на миниатюры.
        """
        await self.page.goto(lot_url, wait_until="domcontentloaded")
        ok = await self._ensure_on_lot(lot_url, attempts=3)
        if not ok:
            raise RuntimeError("Не удалось подтвердить корректный URL лота")

        await self.page.wait_for_selector("h1.title, #LotNumber, .lot-detail-section", timeout=20000)
        await self.page.wait_for_timeout(120)
        await self._scroll_to_bottom(step=1200, max_iters=2)

        try:
            await self.page.wait_for_selector(
                ".p-galleria-thumbnail-items img, .p-galleria-img-thumbnail",
                timeout=3000,
            )
        except Exception:
            pass

        details = await self.page.evaluate(r"""
        () => {
          const txt = (sel) => {
            const el = document.querySelector(sel);
            return el ? (el.textContent || "").replace(/\s+/g, " ").trim() : "";
          };
          const byLabel = (needle) => {
            const labs = Array.from(document.querySelectorAll("label"));
            for (const l of labs) {
              const t = (l.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
              if (!t) continue;
              if (t.startsWith(needle.toLowerCase())) {
                const parent = l.closest(".d-flex") || l.parentElement;
                const v = parent ? parent.querySelector(".lot-details-desc") : null;
                if (v) return (v.textContent || "").replace(/\s+/g, " ").trim();
              }
            }
            return "";
          };
          const uniq = (arr) => Array.from(new Set(arr.filter(Boolean)));

          // VIN
          const vinEl = document.querySelector("div[masking][number]");
          const vinAttr = vinEl ? vinEl.getAttribute("number") : "";
          const vin = vinAttr || txt("span[data-uname='lotdetailVinvalue']");

          // номера
          const lotFromPage = txt("#LotNumber");
          const lotFromUrl = (location.pathname.match(/\/lot\/(\d+)/) || [])[1] || "";

          // картинки (миниатюры галереи)
          const thumbImgs = Array.from(
            document.querySelectorAll(".p-galleria-thumbnail-items img, .p-galleria-img-thumbnail")
          ).map(img => (img.getAttribute("src") || "").trim());

          return {
            title: txt("h1.title"),
            lot_number: lotFromPage || lotFromUrl,
            vin,
            title_code: txt("span[data-uname='lotdetailTitledescriptionvalue']"),
            odometer: txt("span[data-uname='lotdetailOdometervalue']"),
            primary_damage: txt("span[data-uname='lotdetailPrimarydamagevalue']"),
            cylinders: txt("span[data-uname='lotdetailCylindervalue']"),
            color: txt("span[data-uname='lotdetailColorvalue']"),
            engine_type: txt("span[data-uname='lotdetailEnginetype']"),
            transmission: byLabel("transmission"),
            drive: txt("span[data-uname='DriverValue']"),
            vehicle_type: txt("span[data-uname='lotdetailvehicletype']"),
            fuel: txt("span[data-uname='lotdetailFuelvalue']"),
            keys: txt("span[data-uname='lotdetailKeyvalue']"),
            images: uniq(thumbImgs),
          };
        }
        """)
        details["lot_link"] = lot_url
        return details


# =========================
# Отправка батча в локальный API
# =========================
def send_batch(mapped_items: List[Dict[str, Any]]):
    """
    Отправка списка моделей на /lot/lots/batch.
    """
    if not mapped_items:
        print("⚠️ Пустой список для batch — отправка пропущена.")
        return

    headers = {
        "Authorization": LOCAL_AUTH,
        "content-type": "application/json",
    }
    print(f"➡️ Отправляю {len(mapped_items)} лотов в {LOCAL_BATCH_URL} ...")
    resp = requests.post(LOCAL_BATCH_URL, json=mapped_items, headers=headers)
    print("STATUS:", resp.status_code)
    try:
        print("RESPONSE JSON:", resp.json())
    except Exception:
        print("RESPONSE TEXT:", resp.text[:1000])


# ======================
# Пример использования
# ======================
async def main():
    # ENV:
    #   COPART_USER, COPART_PASS
    #   HEADLESS=1 (по умолчанию) или 0 — с окном браузера
    USERNAME = os.getenv("COPART_USER", "755554")
    PASSWORD = os.getenv("COPART_PASS", "newpass0408")
    HEADLESS = os.getenv("HEADLESS", "1") == "0"

    if not USERNAME or not PASSWORD:
        print("⛔ Укажи COPART_USER и COPART_PASS")
        return

    store = SessionStore("sessions.db")
    await store.init()

    bot = CopartBot(username=USERNAME, password=PASSWORD, headless=HEADLESS)
    await bot.start(storage_state=await store.get_storage_state(USERNAME))

    try:
        if not await bot.ensure_session(store):
            print("⛔ Авторизация не удалась")
            return
        print("✅ Сессия валидна")

        # 1) забираем все слоты из календаря
        links = await bot.get_auction_links()
        print(f"Найдено слотов в календаре: {len(links)}")
        for item in links[:5]:
            print(" ", item)

        if not links:
            return

        total_models = 0

        # === ИДЁМ ПО ВСЕМ ССЫЛКАМ КАЛЕНДАРЯ ===
        for slot_idx, sale_slot in enumerate(links, start=1):
            print(f"\n=== Слот {slot_idx}/{len(links)}: {sale_slot.get('time')} {sale_slot.get('title')} ===")
            try:
                lots = await bot.get_sale_lots(sale_slot["href"])
            except Exception as e:
                print(f"⚠️ Не удалось получить список лотов для слота: {e}")
                continue

            print(f"Найдено машин в этом слоте: {len(lots)}")
            if not lots:
                continue

            slot_models: List[Dict[str, Any]] = []

            for idx, lot_row in enumerate(lots, start=1):
                href = lot_row.get("href")
                if not href:
                    continue

                print(f"[{slot_idx}:{idx}/{len(lots)}] Тяну детали лота {lot_row.get('lot_number')}…")

                try:
                    details = await bot.get_lot_details(href)
                    time.sleep(1)
                except Exception as e:
                    print(f"⚠️ Не удалось получить детали лота {lot_row.get('lot_number')}: {e}")
                    continue

                factum_item = map_copart_to_factum(
                    sale_slot=sale_slot,
                    lot_row=lot_row,
                    details=details,
                    base_site="copart",
                )
                model_item = map_factum_to_model(factum_item)
                slot_models.append(model_item)

            print(f"Слот {slot_idx}: сконвертировано моделей: {len(slot_models)}")
            if slot_models:
                # отправляем этот слот батчем
                send_batch(slot_models)
                total_models += len(slot_models)

        print(f"\nГотово. Всего отправлено моделей: {total_models}")

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
