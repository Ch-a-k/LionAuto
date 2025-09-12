# copart_service.py
import asyncio
import json
import re
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Any, Dict, List
from urllib.parse import urlparse, parse_qs, unquote
from pprint import pprint

import aiosqlite
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


ENG_WEEKDAYS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}



def _today_utc_date() -> date:
    return datetime.now(timezone.utc).date()

def _to_mmddyyyy_utc(dt: datetime) -> str:
    # ожидаем tz-aware в UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%m/%d/%Y")

def _mmddyyyy_today_utc() -> str:
    return _to_mmddyyyy_utc(datetime.now(timezone.utc))


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

    # ---------- auth / health ----------
    async def login_member(self) -> bool:
        await self.page.goto("https://www.copart.com", wait_until="domcontentloaded")
        await self._maybe_accept_cookies()

        await self.page.click("button[data-uname='homePageSignIn']")
        await self.page.wait_for_selector("a[data-uname='homePageMemberSignIn']", timeout=8000)
        await self.page.click("a[data-uname='homePageMemberSignIn']")

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

    # ---------- parsing helpers ----------
    async def _wait_table_ready(self, hard_timeout: int = 20000):
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_selector("table#serverSideDataTable", timeout=hard_timeout)
        try:
            await self.page.wait_for_selector("table#serverSideDataTable tbody tr a.search-results", timeout=2500)
        except Exception:
            await self._scroll_to_bottom()
            await self.page.wait_for_selector("table#serverSideDataTable tbody tr a.search-results", timeout=hard_timeout)

    def _lot_id_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"/lot/(\d+)", urlparse(url).path)
        return m.group(1) if m else None

    def _sale_keys(self, url: str):
        """
        Возвращает (yardNum, yyyy-mm-dd) из saleListResult URL.
        """
        p = urlparse(url)
        parts = [x for x in p.path.split("/") if x]
        yard = parts[1] if len(parts) > 1 and parts[0] == "saleListResult" else None
        date_path = parts[2] if len(parts) > 2 and parts[0] == "saleListResult" else None
        qs = parse_qs(p.query or "")
        yard_qs = (qs.get("yardNum") or [None])[0]
        return (yard or yard_qs, date_path)

    async def _ensure_on_sale_list(self, expected_url: str, *, attempts: int = 3) -> bool:
        exp_yard, exp_date = self._sale_keys(expected_url)
        for i in range(1, attempts + 1):
            cur = self.page.url
            cur_yard, cur_date = self._sale_keys(cur)
            ok = ("/saleListResult/" in urlparse(cur).path) and (cur_yard == exp_yard) and (cur_date == exp_date)
            if ok:
                return True

            print(f"⚠️ Не на нужной saleList (got: {cur_yard}/{cur_date}, need: {exp_yard}/{exp_date}) — попытка {i}/{attempts}")
            await self.page.goto(expected_url, wait_until="domcontentloaded")
            try:
                await self._wait_table_ready(hard_timeout=20000)
                await self._scroll_to_bottom()
            except Exception:
                pass
        return False

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

            print(f"⚠️ Не та страница лота (got URL lot={cur_lot}, DOM lot={dom_lot or '—'}, need={exp_lot}) — попытка {i}/{attempts}")
            await self.page.goto(expected_url, wait_until="domcontentloaded")
            await self.page.wait_for_selector("h1.title, #LotNumber, .lot-detail-section", timeout=15000)
            await self._scroll_to_bottom(step=1200, max_iters=2)
        return False

    # ---------- задачи ----------
    async def get_auction_links(self) -> List[Dict[str, str]]:
        """
        С /auctionCalendar — {date, time, title, href}
        """
        await self.page.goto("https://www.copart.com/auctionCalendar", wait_until="load")
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

    async def get_regions_for_date(self, target: Optional[date] = None) -> List[Dict[str, str]]:
        """
        Возвращает регионы (таймслот, название, ссылка) на указанную дату (UTC).
        По умолчанию — сегодня по UTC.
        """
        target = target or _today_utc_date()
        target_str = target.strftime("%m/%d/%Y")  # UTC-дата в формате календаря

        items = await self.get_auction_links()
        regions = []
        for it in items:
            raw_date = (it.get("date") or "").strip()
            if not raw_date:
                raw_date = self._extract_date_from_href(it.get("href") or "") or ""
            if raw_date == target_str:
                regions.append({
                    "time": (it.get("time") or "").strip(),
                    "title": (it.get("title") or "").strip(),
                    "link": (it.get("href") or "").strip(),
                })
        return regions


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
            await self.page.wait_for_selector(".p-galleria-thumbnail-items img, .p-galleria-img-thumbnail", timeout=3000)
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
          const thumbImgs = Array.from(document.querySelectorAll(".p-galleria-thumbnail-items img, .p-galleria-img-thumbnail"))
            .map(img => (img.getAttribute("src") || "").trim());

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

    # ---------- auctionsCalendar: live / inactive ----------
    async def get_calendar_live_status(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Собирает {active:[], inactive:[]} со структурой:
        { date:'MM/DD/YYYY', time:'HH:MM AM/PM', title:'CT - Hartford (Live)', href:'...', is_live:bool }
        Live определяем по наличию .fa-li-live поблизости И/ИЛИ по "(Live)" в тексте.
        """
        await self.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
        await self._maybe_accept_cookies()
        await self.page.wait_for_selector("a[data-url]", timeout=20000)
        await self._scroll_to_bottom(step=1200, max_iters=6)
        await self.page.wait_for_timeout(300)

        data = await self.page.evaluate(r"""
        () => {
        const toAbs = (u) => new URL(u, window.location.origin).href;

        // Карта дат из THEAD (столбцы)
        const headDates = [];
        const table = document.querySelector("a[data-url]")?.closest("table") || document.querySelector("table");
        if (table) {
            const headRow = table.querySelector("thead tr");
            if (headRow) {
            Array.from(headRow.children).forEach((cell, idx) => {
                let txt = (cell.textContent || "").trim().replace(/\s*\n\s*/g, " ");
                const m = txt.match(/\b\d{2}\/\d{2}\/\d{4}\b/);
                headDates[idx] = m ? m[0] : "";
            });
            }
        }

        const items = [];
        const anchors = Array.from(document.querySelectorAll("a[data-url]"));
        for (const a of anchors) {
            const cell = a.closest("td,th");
            const row  = cell?.parentElement || a.closest("tr, li, div, section");

            let timeText = "", dateText = "";
            if (row && cell && row.children && row.children.length) {
            const rowCells = Array.from(row.children);
            const colIndex = rowCells.indexOf(cell);
            const firstCell = rowCells[0];
            if (firstCell) {
                const raw = (firstCell.textContent || "").trim();
                const m = raw.match(/\b\d{1,2}:\d{2}\s?(AM|PM)\b/i);
                timeText = m ? m[0] : raw;
            }
            dateText = (headDates[colIndex] || "").trim();
            } else {
            const raw = (row?.textContent || "").trim();
            const tm = raw.match(/\b\d{1,2}:\d{2}\s?(AM|PM)\b/i);
            timeText = tm ? tm[0] : "";
            const dm = raw.match(/\b\d{2}\/\d{2}\/\d{4}\b/);
            dateText = dm ? dm[0] : "";
            }

            const title = (a.textContent || "").replace(/\s+/g, " ").trim();
            const hrefAttr = a.getAttribute("href") || a.getAttribute("data-url") || "";
            const href = toAbs(hrefAttr);

            // live: иконка рядом или "(Live)" в тексте
            let is_live = /\(Live\)/i.test(title);
            if (!is_live) {
            const scope = row || a.closest("li, tr, td, div") || a.parentElement || document;
            if (scope && scope.querySelector("i.fa-li-live, i.fa-circle.fa-li-live")) is_live = true;
            }

            items.push({ date: dateText, time: timeText, title, href, is_live });
        }
        return items;
        }
        """)

        # Постобработка на Python: если дата в колонке пустая — берём из href
        active, inactive = [], []
        for it in data:
            d = (it.get("date") or "").strip()
            if not d:
                d = self._extract_date_from_href(it.get("href") or "") or ""
            norm = {
                "date": d,
                "time": (it.get("time") or "").strip(),
                "title": (it.get("title") or "").strip(),
                "href": (it.get("href") or "").strip(),
                "is_live": bool(it.get("is_live")),
            }
            (active if norm["is_live"] else inactive).append(norm)
        return {"active": active, "inactive": inactive}


    async def _debug_calendar_counters(self):
        try:
            counts = await self.page.evaluate(r"""
            () => ({
            liveIcons: document.querySelectorAll('i.fa-circle.fa-li-live, i.fa-li-live').length,
            grayIcons: document.querySelectorAll('i.fa-circle.fa-li-gray, i.fa-li-gray').length,
            anchors:   document.querySelectorAll('a[data-url]').length
            })
            """)
            print("DBG calendar:", counts)
        except Exception as e:
            print("DBG calendar error:", e)


        # ------ helpers: клик без автоскролла ------
    async def _js_click_no_scroll(self, locator) -> bool:
        try:
            handle = await locator.element_handle()
            if not handle:
                return False
            await self.page.evaluate(
                """
                (el) => {
                  const sx = window.scrollX, sy = window.scrollY;
                  const orig = Element.prototype.scrollIntoView;
                  Element.prototype.scrollIntoView = function(){};
                  try {
                    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                  } finally {
                    setTimeout(() => {
                      window.scrollTo(sx, sy);
                      Element.prototype.scrollIntoView = orig;
                    }, 0);
                  }
                }
                """,
                handle,
            )
            return True
        except Exception:
            return False

    # ------ список модальных live-ссылок для дебага ------
    async def debug_list_live_titles(self) -> List[str]:
        await self.page.wait_for_selector("a[ng-click*='openModal']", timeout=15000)
        titles = await self.page.evaluate(
            r"""
            () => {
              const rows = Array.from(document.querySelectorAll("a[ng-click*='openModal']"));
              return rows.map(a => (a.textContent || "").replace(/\s+/g, " ").trim()).filter(Boolean);
            }
            """
        )
        print("LIVE modal titles (sample):", titles.slice(0, 20))
        return titles

    # ------ join по заголовку модальной ссылки (без скролла) ------
    async def join_live_from_calendar_by_title(self, title_like: str, *, wait_modal_timeout: int = 15000) -> bool:
        """
        Открывает https://www.copart.com/auctionCalendar, находит ссылку вида
        <a ng-click="openModal(auction)"> ... (Live) </a> с текстом, содержащим title_like,
        кликает БЕЗ скролла, ждёт модалку и жмёт Join. Возвращает True при успехе.
        """
        await self.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
        await self._maybe_accept_cookies()
        await self.page.wait_for_selector("a[ng-click*='openModal']", timeout=20000)

        # Ищем точным/укороченным совпадением
        link = self.page.locator("a[ng-click*='openModal']").filter(has_text=title_like)
        if not await link.count():
            base = title_like.split("(")[0].strip()
            if base:
                link = self.page.locator("a[ng-click*='openModal']").filter(has_text=base)

        if not await link.count():
            # Фоллбек: просто возьмём ПЕРВУЮ live-модалку (рядом должен быть .fa-li-live)
            live_rows = self.page.locator("i.fa-li-live").locator("xpath=ancestor::*[self::tr or self::li or self::div][1]")
            if await live_rows.count():
                link = live_rows.first.locator("a[ng-click*='openModal']")
                if not await link.count():
                    print("❌ Не нашёл <a ng-click*='openModal'> рядом с .fa-li-live.")
                    return False
            else:
                print("❌ На странице нет видимых .fa-li-live.")
                # полезно посмотреть что реально есть
                await self.debug_list_live_titles()
                return False

        # Клик по модальной ссылке — без автоскролла
        ok = await self._js_click_no_scroll(link.first)
        if not ok:
            try:
                await link.first.click()  # обычный клик как резерв
            except Exception as e:
                print(f"❌ Не удалось кликнуть модальную live-ссылку: {e}")
                return False

        # Ждём статус модалки
        try:
            await self.page.wait_for_selector("p[data-uname='modalStatustxt']", timeout=wait_modal_timeout)
        except Exception as e:
            print(f"⚠️ Не увидел статус в модалке (может, грузится дольше): {e}")

        # Жмём Join — тоже без автоскролла
        try:
            join_btn = self.page.locator("#liveJoinAuction[data-uname='joinLiveAuctionbtn']")
            await join_btn.wait_for(state="visible", timeout=12000)
            await self._js_click_no_scroll(join_btn)
        except Exception as e:
            print(f"❌ Не удалось нажать Join live auction: {e}")
            return False

        # Дождаться загрузки live-дашборда
        return True


    async def click_live_slot_and_join(self, link: str, *, wait_modal_timeout: int = 15000) -> bool:
        """
        Находится на /auctionCalendar. Кликает по live-ссылке БЕЗ скролла,
        ждёт модалку "Live auction in progress", жмёт "Join live auction".
        Возвращает True, если получилось.
        """
        # Нормализуем ссылку (на странице могут быть относительные href/data-url)
        abs_link = await self.page.evaluate("(u) => new URL(u, window.location.origin).href", link)

        # Ищем целевой <a> разными вариантами (href | data-url | endsWith)
        loc = self.page.locator(f"a[href='{abs_link}'], a[data-url='{abs_link}']")
        if not await loc.count():
            loc = self.page.locator(f"a[data-url$='{link}'], a[href$='{link}']")

        # Если не нашли — обновимся/подгрузим вью
        if not await loc.count():
            await self.page.wait_for_selector("a[data-url]", timeout=8000)
            if not await loc.count():
                print("❌ Не нашёл live-ссылку на странице календаря.")
                return False

        # JS-клик без прокрутки (сохранить/восстановить scroll, временно отключить scrollIntoView)
        try:
            handle = await loc.first.element_handle()
            await self.page.evaluate("""
            (el) => {
            const sx = window.scrollX, sy = window.scrollY;
            const orig = Element.prototype.scrollIntoView;
            Element.prototype.scrollIntoView = function(){}; // блокируем автопрокрутку
            try {
                // клик как пользовательский MouseEvent
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            } finally {
                // восстанавливаем позицию и поведение сразу после клика
                setTimeout(() => {
                window.scrollTo(sx, sy);
                Element.prototype.scrollIntoView = orig;
                }, 0);
            }
            }
            """, handle)
        except Exception as e:
            print(f"⚠️ JS-клик не удался, fallback: {e}")
            # как крайний случай — мягкий переход (но это может прокрутить)
            await self.page.goto(abs_link, wait_until="domcontentloaded")

        # Проверим, что мы всё ещё на календаре (по ТЗ — не уходим со страницы до Join)
        try:
            if "/auctionCalendar" not in self.page.url:
                # если вдруг SPA дернула навигацию — вернёмся
                await self.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
        except Exception:
            pass

        # Ждём модальный статус
        try:
            await self.page.wait_for_selector("p[data-uname='modalStatustxt']", timeout=wait_modal_timeout)
            # иногда текст всплывает с задержкой — дадим тикануть
            await self.page.wait_for_timeout(200)
        except Exception as e:
            print(f"⚠️ Модалка со статусом live не появилась: {e}")

        # Жмём Join
        try:
            join_btn = self.page.locator("#liveJoinAuction[data-uname='joinLiveAuctionbtn']")
            await join_btn.wait_for(state="visible", timeout=10000)
            # жмём тоже без автоскролла (на всякий случай)
            handle_join = await join_btn.element_handle()
            await self.page.evaluate("""
            (el) => {
            const sx = window.scrollX, sy = window.scrollY;
            const orig = Element.prototype.scrollIntoView;
            Element.prototype.scrollIntoView = function(){};
            try {
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            } finally {
                setTimeout(() => {
                window.scrollTo(sx, sy);
                Element.prototype.scrollIntoView = orig;
                }, 0);
            }
            }
            """, handle_join)
        except Exception as e:
            print(f"❌ Не удалось нажать Join live auction: {e}")
            return False

        # Дождёмся загрузки лайв-дашборда
        return await self.wait_for_live_dashboard()

    async def save_page_html(self, prefix: str = "copart_page") -> str:
        """
        Сохраняет текущий HTML и скриншот локально в ./debug_pages/
        Возвращает путь к HTML.
        """
        from datetime import datetime as _dt
        from pathlib import Path

        # создаём папку debug_pages рядом со скриптом
        out_dir = Path(__file__).parent / "debug_pages"
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = _dt.utcnow().strftime("%Y%m%d-%H%M%S")
        html_path = out_dir / f"{prefix}-{ts}.html"
        png_path  = out_dir / f"{prefix}-{ts}.png"

        # сохраняем HTML
        html = await self.page.content()
        html_path.write_text(html, encoding="utf-8")
        print(f"💾 HTML сохранён: {html_path}")

        # сохраняем скриншот (если получится)
        try:
            await self.page.screenshot(path=str(png_path), full_page=True)
            print(f"🖼  Скриншот сохранён: {png_path}")
        except Exception as e:
            print(f"⚠️ Скриншот не удалось сохранить: {e}")

        return str(html_path.resolve())


    async def wait_for_live_dashboard(self, *, timeout_ms: int = 30000) -> bool:
        try:
            # Быстро проверим «живые» маркёры в любом фрейме:
            # 1) сам bid-инпут
            await self.wait_for_selector_in_any_frame("input[data-uname='bidAmount']", timeout_ms=timeout_ms)
            return True
        except Exception as e:
            print(f"❌ Live dashboard (bidAmount) не найден: {e}")
            # Полезный дамп для ручной диагностики
            try:
                await self.save_page_html_deep(prefix="timeout_wait_bidAmount")
            except Exception:
                pass
            return False



    async def log_bid_amount_every_second(self, seconds: int = 30) -> None:
        """
        Каждую секунду читает value у input[data-uname='bidAmount'] и печатает в консоль.
        Формат: 2025-09-12T14:23:45.123Z | bidAmount="$3,550"
        """
        import asyncio
        from datetime import datetime, timezone

        inp = self.page.locator("input[data-uname='bidAmount']").first
        await inp.wait_for(state="visible", timeout=8000)

        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try:
                val = await inp.input_value()
            except Exception:
                val = ""
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            print(f"{ts} | bidAmount={val!s}")
            await asyncio.sleep(1.0)


    async def get_bidding_dialer(self, timeout_ms: int = 30000):
        """
        Возвращает Locator на bidding-dialer. Бросает, если нет.
        """
        dialer = self.page.locator("div.auctionrunningdiv-MACRO >> bidding-dialer-refactor")
        await dialer.first.wait_for(state="visible", timeout=timeout_ms)
        return dialer.first

    async def extract_current_lot_details_live(self) -> Dict[str, Any]:
        """
        Считывает правую панель деталей текущего лота на live-дашборде.
        Возвращает словарь по возможным меткам (Location, Doc Type, Odometer, Est. Retail Value,
        Primary Damage, Secondary Damage, Highlights, VIN, Body Style, Color, Engine Type, Cylinders,
        Drive, Fuel, Keys, Special Note, ...).
        """
        await self.page.wait_for_selector("section.lot-details-wrapper-MACRO", timeout=15000)

        # Универсальный сборщик: идём по всем "label -> value" парам
        details = await self.page.evaluate(r"""
        () => {
          const root = document.querySelector("section.lot-details-wrapper-MACRO");
          const out = {};
          if (!root) return out;

          const text = (el) => (el ? (el.textContent || "").replace(/\s+/g, " ").trim() : "");
          const rows = root.querySelectorAll("[data-uname='lot-details-label']");

          rows.forEach(lbl => {
            const name = text(lbl);
            // Значение обычно в [data-uname='lot-details-value'] в пределах той же "itemrow"
            const row = lbl.closest(".itemrow") || lbl.parentElement;
            let val = "";
            if (row) {
              const v1 = row.querySelector("[data-uname='lot-details-value']");
              if (v1) val = text(v1);
              else {
                // VIN может быть внутри компонента
                const vinA = row.querySelector("vin-number a");
                if (vinA) val = text(vinA);
              }
            }
            if (name) out[name] = val;
          });

          // Дополнительно — Highlights (если не попал общим правилом)
          if (!out["Highlights"]) {
            const hi = root.querySelector("#copart_COPART366A_lotDetailIconCodes_span, [id*='_lotDetailIconCodes_span']");
            if (hi) {
              const spans = Array.from(hi.querySelectorAll("span[title], span"));
              const vals = spans.map(s => text(s)).filter(Boolean);
              if (vals.length) out["Highlights"] = Array.from(new Set(vals)).join(", ");
            } else {
              // Иногда Highlights в явной паре label->value
              const hiRow = Array.from(root.querySelectorAll(".itemrow")).find(r => /Highlights/i.test(text(r)));
              if (hiRow) {
                const v = hiRow.querySelector("[data-uname='lot-details-value']");
                if (v) out["Highlights"] = text(v);
              }
            }
          }

          // Нормализация ключей (чтобы было удобно маппить)
          const norm = {};
          const map = {
            "Location": "location",
            "Doc Type": "doc_type",
            "Odometer": "odometer",
            "Est. Retail Value": "est_retail_value",
            "Sublot Location": "sublot_location",
            "Primary Damage": "primary_damage",
            "Secondary Damage": "secondary_damage",
            "Highlights": "highlights",
            "VIN": "vin",
            "Body Style": "body_style",
            "Color": "color",
            "Engine Type": "engine_type",
            "Cylinders": "cylinders",
            "Drive": "drive",
            "Fuel": "fuel",
            "Keys": "keys",
            "Special Note": "special_note"
          };

          for (const [k, v] of Object.entries(out)) {
            const key = map[k] || k.toLowerCase().replace(/\s+/g, "_");
            norm[key] = v;
          }

          return norm;
        }
        """)

        # Добавим текущий URL дашборда
        details["dashboard_url"] = self.page.url
        return details

    async def _auction_widget_id_from_url(self) -> str | None:
        try:
            p = urlparse(self.page.url)
            print(f"CURRENT URL: {p}")
            det = (parse_qs(p.query).get("auctionDetails") or [""])[0]  # "135-A"
            if not det:
                return None
            wid = det.replace("-", "")  # "135A"
            return f"#widget-COPART{wid}"
        except Exception:
            return None

    async def current_live_auction_name(self) -> str:
        """
        Возвращает название аукциона на live-дашборде (например 'CT - Hartford'),
        чтобы можно было сравнить с выбранным слотом.
        """
        try:
            # шапка с селектором площадки обычно в селекте/хедере
            await self.page.wait_for_selector("section.lot-details-wrapper-MACRO", timeout=12000)
            name = await self.page.evaluate(r"""
            () => {
              const t = (el) => (el ? (el.textContent||"").replace(/\s+/g," ").trim() : "");
              // возможные места, где светится название локации/аукциона
              const cand = [
                document.querySelector("select.select-option option:checked"),
                document.querySelector("div.live-header, header, h1, h2")
              ];
              for (const c of cand) {
                const s = t(c);
                if (s && /-/i.test(s)) return s; // что-то вроде "CT - Hartford"
              }
              // запасной: правый блок 'Location'
              const locLbl = Array.from(document.querySelectorAll("[data-uname='lot-details-label']"))
                    .find(el => /Location/i.test(t(el)));
              if (locLbl) {
                const row = locLbl.closest(".itemrow") || locLbl.parentElement;
                const val = row?.querySelector("[data-uname='lot-details-value']");
                const s = t(val);
                if (s) return s;
              }
              return "";
            }
            """)
            return (name or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _base_title(s: str) -> str:
        return (s or "").split("(")[0].strip().lower()

    async def _live_matches_choice(self, chosen: Dict[str,str]) -> bool:
        """
        Проверяет, что открытый live-дашборд действительно про тот слот, который мы выбирали.
        Сейчас сравниваем по 'base title' (без '(Live)') и по дате, если её можно достать из URL.
        """
        on_name = await self.current_live_auction_name()
        want_name = self._base_title(chosen.get("title",""))
        on_base  = self._base_title(on_name)
        ok_name  = (want_name and on_base and want_name in on_base) or (on_base in want_name)

        # дата из выбранного href
        want_date = self._extract_date_from_href(chosen.get("href","") or "") or (chosen.get("date") or "").strip()
        # дата из текущего URL (часто есть saleDate=)
        cur_date = self._extract_date_from_href(self.page.url) or ""

        ok_date = True
        if want_date and cur_date:
            ok_date = (want_date == cur_date)

        print(f"🔎 Валидация live: on='{on_name}' base='{on_base}' want='{want_name}'  date_on='{cur_date}' want='{want_date}'  → ok_name={ok_name} ok_date={ok_date}")
        return bool(ok_name and ok_date)

    # ---------- bidding ----------

    async def _find_live_controls(self, timeout_ms: int = 12000):
        """
        Возвращает (frame, bid_input_locator, bid_button_locator)
        из того фрейма, где живёт bidAmount.
        """
        fr, inp = await self.wait_for_selector_in_any_frame("input[data-uname='bidAmount']", timeout_ms=timeout_ms)
        btn = (
            fr.locator("button[data-uname='bidCurrentLot']").first
            .or_(fr.locator("button:has-text('Bid')").first)
            .or_(fr.locator("div.auctionrunningdiv-MACRO button:has-text('Bid')").first)
        )
        await btn.wait_for(state="visible", timeout=timeout_ms)
        return fr, inp, btn
    

    async def bid_current_lot(self, amount: int | str | None = None, *, times: int = 1, spacing_sec: float = 0.35) -> bool:
        """
        Если передан amount — вводит указанную сумму в bidAmount и нажимает Bid (1 клик).
        Если amount не передан — просто нажимает Bid 'times' раз.
        Возвращает True, если хотя бы один клик произошёл.
        """
        try:
            fr, inp, btn = await self._find_live_controls(timeout_ms=15000)

            # helper: disabled?
            async def _is_disabled(b):
                try:
                    if await b.is_disabled():
                        return True
                except Exception:
                    pass
                try:
                    aria = await b.get_attribute("aria-disabled")
                    if aria and aria.lower() in ("true", "1"):
                        return True
                except Exception:
                    pass
                try:
                    cls = (await b.get_attribute("class") or "").lower()
                    if "disabled" in cls or "is-disabled" in cls:
                        return True
                except Exception:
                    pass
                return False

            # Если задана сумма — подготовим поле и введём её
            if amount is not None:
                amt = self._normalize_amount(amount)
                if not amt:
                    print(f"⚠️ Некорректная сумма '{amount}', отменяю ввод и жму дефолтный Bid.")
                else:
                    try:
                        await inp.scroll_into_view_if_needed()
                        await inp.click(timeout=1000)
                    except Exception:
                        pass
                    # убрать readonly, если есть
                    try:
                        h = await inp.element_handle()
                        if h:
                            await fr.evaluate("(el)=>{ try{el.removeAttribute('readonly');}catch{}; el.readOnly=false; }", h)
                    except Exception:
                        pass
                    # очистить и ввести
                    try:
                        await inp.fill(amt)
                    except Exception:
                        # JS-запись + события (на случай масок)
                        try:
                            h = await inp.element_handle()
                            if h:
                                await fr.evaluate(
                                    "(el,val)=>{el.value=val; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}",
                                    h, amt
                                )
                        except Exception:
                            pass
                    # иногда форматируется на blur
                    try:
                        await inp.blur()
                    except Exception:
                        pass
                    # При ручном вводе кликаем один раз
                    times = 1

            # значение до клика (для логов)
            before = ""
            try:
                before = (await inp.input_value()).strip()
            except Exception:
                pass

            clicked_any = False
            for i in range(max(1, int(times))):
                if await _is_disabled(btn):
                    print("⚠️ Bid disabled — клик пропущен")
                    break
                try:
                    await btn.scroll_into_view_if_needed()
                except Exception:
                    pass

                # клик
                try:
                    await btn.click()
                    clicked_any = True
                except Exception:
                    # JS-fallback
                    try:
                        h = await btn.element_handle()
                        if h:
                            await fr.evaluate("(el)=>el.click()", h)
                            clicked_any = True
                        else:
                            raise
                    except Exception as e:
                        print(f"❌ Не удалось нажать Bid: {e}")
                        break

                # подтверждение (если всплыло)
                try:
                    confirm = (
                        fr.locator("[data-uname='confirmBid'], button:has-text('Confirm'), .modal-footer button.btn-primary").first
                        .or_(self.page.locator("button:has-text('Confirm'), .modal-footer .btn-primary").first)
                    )
                    if await confirm.count():
                        try:
                            await confirm.click(timeout=1500)
                        except Exception:
                            pass
                except Exception:
                    pass

                if spacing_sec > 0 and i < times - 1:
                    await asyncio.sleep(spacing_sec)

            # значение после
            after = ""
            try:
                after = (await inp.input_value()).strip()
            except Exception:
                pass

            print(f"🟠 Bid: before={before!s} → after={after!s} | clicked_any={clicked_any}")
            return clicked_any

        except Exception as e:
            print(f"❌ bid_current_lot failed: {e}")
            return False
    @staticmethod
    def _widget_id_from_details(details: str | None) -> str | None:
        """
        Превращает '23-A' → 'widget-COPART023A'
        """
        if not details:
            return None
        m = re.match(r"^\s*(\d+)\s*-\s*([A-Za-z])\s*$", details)
        if not m:
            return None
        num = int(m.group(1))
        letter = m.group(2).upper()
        return f"widget-COPART{num:03d}{letter}"

    def _auction_details_from_url(self) -> str | None:
        try:
            qs = parse_qs(urlparse(self.page.url).query)
            return (qs.get("auctionDetails") or [None])[0]
        except Exception:
            return None
    
    async def wait_and_get_live_widget(self, timeout_ms: int = 15000):
        """
        Возвращает Locator на живой виджет. Бросает исключение, если не найден.
        """
        sel = await self.resolve_live_widget_selector()
        if not sel:
            raise RuntimeError("Не удалось определить id live-виджета (widget-COPART###X).")
        loc = self.page.locator(sel)
        await loc.wait_for(state="visible", timeout=timeout_ms)
        return loc


    async def resolve_live_widget_selector(self) -> str | None:
        """
        Пытается вычислить селектор #widget-COPARTXXXZ (023A и т.п.):
        1) из auctionDetails в URL;
        2) сканирует DOM и забирает видимый id;
        3) если не нашли — None.
        """
        # 1) auctionDetails=NNN-L
        details = self._auction_details_from_url()
        wid = self._widget_id_from_details(details) if details else None
        if wid:
            sel = f"#{wid}"
            # проверим, что элемент существует (и по возможности видим)
            try:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    return sel
            except Exception:
                pass

        # 2) скан DOM
        wid2 = await self._scan_visible_live_widget_id()
        if wid2:
            return f"#{wid2}"

        # 3) не нашли
        return None

    async def wait_for_selector_in_any_frame(self, selector: str, timeout_ms: int = 30000):
        """Возвращает (frame, locator) для первого фрейма, где селектор стал видим."""
        deadline = self.page.context._loop.time() + (timeout_ms / 1000)
        while self.page.context._loop.time() < deadline:
            for fr in self.page.frames:
                loc = fr.locator(selector)
                try:
                    await loc.first.wait_for(state="visible", timeout=250)
                    return fr, loc.first
                except Exception:
                    continue
            await self.page.wait_for_timeout(150)
        raise TimeoutError(f"Selector '{selector}' not found in any frame within {timeout_ms}ms")


    async def stream_bid_amounts(self, seconds: int = 30):
        fr, inp = await self.wait_for_selector_in_any_frame("input[data-uname='bidAmount']", timeout_ms=20000)
        end = self.page.context._loop.time() + seconds
        print(f"⏱  bidAmount: логирую {seconds} сек… (frame url={fr.url})")
        while self.page.context._loop.time() < end:
            try:
                val = await inp.input_value()
            except Exception:
                val = ""
            from datetime import datetime, timezone
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
            print(f"{ts} | bidAmount={val!s}")
            await self.page.wait_for_timeout(1000)


    async def save_page_html_deep(self, prefix: str = "copart_page") -> None:
        from pathlib import Path
        from datetime import datetime as _dt

        ts = _dt.utcnow().strftime("%Y%m%d-%H%M%S")
        base = Path(f"{prefix}-{ts}")
        base.parent.mkdir(parents=True, exist_ok=True)

        # 1) основной документ
        html = await self.page.content()
        (base.with_suffix(".html")).write_text(html, encoding="utf-8")
        try:
            await self.page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
        except Exception:
            pass
        print(f"💾 Saved main: {base.with_suffix('.html')}")

        # 2) фреймы
        for i, fr in enumerate(self.page.frames):
            # у кросс-доменных фреймов .content() бросит, поэтому ловим исключение
            url = fr.url
            name = fr.name or ""
            safe = f"{i:02d}"
            try:
                fhtml = await fr.content()
                (base.parent / f"{base.name}.frame-{safe}.html").write_text(fhtml, encoding="utf-8")
                try:
                    # скрин конкретного фрейма, если есть видимый элемент <html>
                    root = fr.locator("html")
                    await root.screenshot(path=str(base.parent / f"{base.name}.frame-{safe}.png"))
                except Exception:
                    pass
                print(f"   └─ frame#{i} saved (same-origin) → {url} ({name})")
            except Exception:
                print(f"   └─ frame#{i} cross-origin → {url} ({name}) [HTML недоступен]")


    async def _scan_visible_live_widget_id(self) -> str | None:
        """
        Ищет на странице первый видимый div c id '^widget-COPART\\d{3}[A-Z]$'.
        Возвращает сам id либо None.
        """
        try:
            wid = await self.page.evaluate(r"""
            () => {
              const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };
              const nodes = document.querySelectorAll("div[id^='widget-COPART']");
              for (const el of nodes) {
                const id = el.id || "";
                if (/^widget-COPART\d{3}[A-Z]$/.test(id) && isVisible(el)) {
                  return id;
                }
              }
              // fallback: иногда целевой виджет не активен, но присутствует — вернём первый попавшийся
              for (const el of nodes) {
                const id = el.id || "";
                if (/^widget-COPART\d{3}[A-Z]$/.test(id)) return id;
              }
              return null;
            }
            """)
            return wid
        except Exception:
            return None


    def _normalize_amount(self, amount) -> str | None:
        """Принимает int/str вида '$2,250' → '2250'. Пустое/некорректное → None."""
        if amount is None:
            return None
        if isinstance(amount, (int, float)):
            try:
                return str(int(round(float(amount))))
            except Exception:
                return None
        if isinstance(amount, str):
            digits = "".join(ch for ch in amount if ch.isdigit())
            return digits or None
        return None

    async def read_bid_amount(self) -> Optional[str]:
        """
        Читает текущее значение из input[data-uname='bidAmount'].
        Возвращает строку (например '$4,300') или None, если не найдено.
        """
        try:
            inp = self.page.locator("input[data-uname='bidAmount']")
            await inp.wait_for(state="visible", timeout=8000)
            # Значение должно быть в value
            val = await inp.input_value()
            return val.strip() if val else ""
        except Exception:
            return None

    async def track_bid_amounts(self, seconds: int = 30, interval: float = 1.0) -> List[Dict[str, Any]]:
        """
        Каждую секунду читает bidAmount и возвращает список замеров:
        [{ts: '2025-09-08T15:04:05Z', amount: '$4,300'}, ...]
        """
        out: List[Dict[str, Any]] = []
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            amt = await self.read_bid_amount()
            out.append({"ts": datetime.utcnow().isoformat() + "Z", "amount": amt})
            await asyncio.sleep(interval)
        return out


# ======================
# Пример использования (рефакторинг: честные логи, без лишнего)
# ======================
async def main():
    import os

    # ENV:
    # COPART_USER, COPART_PASS, HEADLESS=1
    # COPART_LIVE_TITLE="CT - Hartford" (опционально: подсказка по площадке)
    # COPART_TRACK_SECS=15 (0 чтобы выключить)
    # COPART_DO_BID=1 (0 чтобы выключить)
    USERNAME = os.getenv("COPART_USER", "755554")
    PASSWORD = os.getenv("COPART_PASS", "newpass0408")
    HEADLESS       = os.getenv("HEADLESS", "1") == "0"
    LIVE_TITLE_HINT= (os.getenv("COPART_LIVE_TITLE") or "").strip()
    TRACK_SECONDS  = int(os.getenv("COPART_TRACK_SECS", "15") or "0")
    DO_BID         = os.getenv("COPART_DO_BID", "0") == "1"

    
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

        # 1) Календарь → собрать только live-модалки по иконке + "(Live)"
        await bot.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
        await bot._maybe_accept_cookies()
        await bot.page.wait_for_selector("a[ng-click*='openModal']", timeout=20000)

        live_titles = await bot.page.evaluate(r"""
        () => {
          const text = (el) => (el ? (el.textContent || "").replace(/\s+/g," ").trim() : "");
          const rows = Array.from(document.querySelectorAll("i.fa-li-live"))
              .map(icon => icon.closest("tr, li, div, section"))
              .filter(Boolean);
          const out = [];
          for (const row of rows) {
            const a = row.querySelector("a[ng-click*='openModal']");
            const t = text(a);
            if (a && /\(Live\)/i.test(t)) out.push(t);
          }
          return Array.from(new Set(out)); // уникальные
        }
        """)

        if not live_titles:
            print("⛔ Живых модалок (…(Live)) не найдено")
            return

        # 2) Приоритезируем по подсказке, если задана
        if LIVE_TITLE_HINT:
            live_titles.sort(key=lambda t: 0 if LIVE_TITLE_HINT in t.lower() else 1)

        # 3) Пытаемся join по каждой модалке до появления bidAmount (в любом фрейме)
        joined = False
        opened_label = ""
        for title in live_titles[:12]:
            print(f"→ Join по модалке: '{title}'")
            ok_click = await bot.join_live_from_calendar_by_title(title)
            if not ok_click:
                print("  ↪️ Не удалось нажать Join, следующая модалка…")
                await bot.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
                continue

            # Ждём реальный live UI по инпуту bidAmount (в любом фрейме).
            ok_ready = await bot.wait_for_live_dashboard(timeout_ms=45000)
            if not ok_ready:
                try:
                    await bot.save_page_html_deep(prefix="timeout_wait_bidAmount")
                except Exception:
                    pass
                print("  ↪️ bidAmount не появился, следующая модалка…")
                await bot.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
                continue

            # Считаем, что мы в live того же названия, по которому кликали.
            opened_label = title
            joined = True
            break

        if not joined:
            print("⛔ Не удалось присоединиться к живым модалкам")
            return

        print(f"✅ На live: {opened_label}")

        # 4) (опционально) показать id виджета, если на странице его реально видно
        try:
            widget = await bot.wait_and_get_live_widget(timeout_ms=15000)
            wid = await widget.evaluate("el => el.id")
            print(f"   Виджет: {wid}")
        except Exception:
            pass
        
        DO_BID = True
        # 5) (опционально) кликнуть Bid
        if DO_BID:
            # просто поставить текущую «шаговую» ставку
            await bot.bid_current_lot()

            # ввести вручную 5000 и потом нажать Bid
            await bot.bid_current_lot(amount=4000)

            # альтернативно строкой с валютой — нормализуется
            await bot.bid_current_lot(amount="$4,500")

            # сделать три быстрых клика (если amount не задан)
            await bot.bid_current_lot(times=3, spacing_sec=0.8)

        # 6) Логировать bidAmount каждую секунду N секунд из того фрейма, где он найден
        if TRACK_SECONDS > 0:
            try:
                await bot.stream_bid_amounts(seconds=TRACK_SECONDS)
            except Exception as e:
                print(f"⚠️ Не удалось логировать bidAmount: {e}")

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

# _hrs or _ful its diferrence between hd or not hd photo, _thb is thubnail photo