# copart_service.py
import asyncio
import json
import re
from datetime import datetime, date, timezone
from typing import Optional, Any, Dict, List
from urllib.parse import urlparse, parse_qs, unquote

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
        Достаём дату из href: /YYYY-MM-DD или saleDate=epoch_ms → MM/DD/YYYY
        """
        if not href:
            return None

        m = re.search(r"/(\d{4}-\d{2}-\d{2})(?:[/?#]|$)", href)
        if m:
            iso = m.group(1)
            try:
                dt = datetime.strptime(iso, "%Y-%m-%d")
                return dt.strftime("%m/%d/%Y")
            except ValueError:
                pass

        try:
            qs = parse_qs(urlparse(href).query)
            if "saleDate" in qs and qs["saleDate"]:
                ms = int(qs["saleDate"][0])
                dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
                return dt.strftime("%m/%d/%Y")
        except Exception:
            pass

        return None

    async def get_regions_for_date(self, target: Optional[date] = None) -> List[Dict[str, str]]:
        """
        Возвращает регионы (таймслот, название, ссылка) на указанную дату (по умолчанию — сегодня).
        """
        target = target or date.today()
        target_str = target.strftime("%m/%d/%Y")

        items = await self.get_auction_links()
        regions = []
        for it in items:
            raw_date = (it.get("date") or "").strip() or self._extract_date_from_href(it.get("href") or "")
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
        На /auctionCalendar собирает ссылки и статус:
        live=True — если рядом с пунктом календаря есть <i class="fa ... fa-li-live">,
        иначе — inactive. Гораздо более устойчиво к структуре DOM.
        """
        await self.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
        await self._maybe_accept_cookies()
        # даём SPA дорисоваться и подгрузиться
        await self.page.wait_for_selector("a[data-url]", timeout=20000)
        await self._scroll_to_bottom(step=1200, max_iters=6)
        await self.page.wait_for_timeout(400)

        data = await self.page.evaluate(r"""
        () => {
        const toAbs = (u) => new URL(u, window.location.origin).href;
        const results = { active: [], inactive: [] };

        // 1) Помечаем контейнеры, в которых встречаются иконки
        const markContainer = (node, kind) => {
            if (!node) return;
            if (!node.__copartStatus__) node.__copartStatus__ = { live:false, gray:false };
            if (kind === "live") node.__copartStatus__.live = true;
            if (kind === "gray") node.__copartStatus__.gray = true;
        };

        const icons = Array.from(document.querySelectorAll("i.fa-circle"));
        for (const i of icons) {
            const isLive = i.classList.contains("fa-li-live");
            const isGray = i.classList.contains("fa-li-gray");
            const cont = i.closest("tr, li, div, td, section") || i.parentElement;
            if (isLive) markContainer(cont, "live");
            else if (isGray) markContainer(cont, "gray");
        }

        // 2) Подготовим карту дат в заголовках таблицы (если она вообще таблица)
        const table = document.querySelector("a[data-url]")?.closest("table") || document.querySelector("table");
        const headDates = [];
        if (table) {
            const headRow = table.querySelector("thead tr");
            if (headRow) {
            Array.from(headRow.children).forEach((cell, idx) => {
                let txt = (cell.textContent || "").trim().replace(/\s*\n\s*/g, " ");
                const m = txt.match(/\b\d{2}\/\d{2}\/\d{4}\b/);
                if (m) txt = m[0];
                headDates[idx] = txt;
            });
            }
        }

        // 3) Собираем все ссылки
        const anchors = Array.from(document.querySelectorAll("a[data-url]"));
        for (const a of anchors) {
            const cell = a.closest("td,th");
            const row  = cell?.parentElement || a.closest("tr, li, div, section");

            // Время/дата если структура табличная
            let timeText = "";
            let dateText = "";
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
            // фоллбек — парсим из текста строки
            const raw = (row?.textContent || "").trim();
            const m = raw.match(/\b\d{1,2}:\d{2}\s?(AM|PM)\b/i);
            timeText = m ? m[0] : "";
            const d = raw.match(/\b\d{2}\/\d{2}\/\d{4}\b/);
            dateText = d ? d[0] : "";
            }

            const title = (a.textContent || "").trim();
            const hrefAttr = a.getAttribute("href") || a.getAttribute("data-url") || "";
            const href = toAbs(hrefAttr);

            // 4) Определяем live-статус
            let is_live = false;
            if (row && row.__copartStatus__ && row.__copartStatus__.live) is_live = true;
            // если явно помечено как gray — перезапишем
            if (row && row.__copartStatus__ && row.__copartStatus__.gray) is_live = false;

            // Доп. поиск иконки рядом (на случай странной разметки)
            if (!is_live) {
            const scope = row || a.closest("li, tr, td, div") || a.parentElement || document;
            if (scope.querySelector("i.fa-li-live, i.fa-circle.fa-li-live")) {
                is_live = true;
            }
            }

            const item = { date: dateText, time: timeText, title, href, is_live };
            (is_live ? results.active : results.inactive).push(item);
        }

        return results;
        }
        """)
        return data

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
        return await self.wait_for_live_dashboard()


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


    async def wait_for_live_dashboard(self, timeout_ms: int = 30000) -> bool:
        """
        Признаки лайв-дашборда:
        - селект фильтра (Show All / Watching / Outbid / ...)
        - панель деталей лота (section.lot-details-wrapper-MACRO)
        """
        try:
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_selector("select.select-option", timeout=timeout_ms)
            await self.page.wait_for_selector("section.lot-details-wrapper-MACRO", timeout=timeout_ms)
            return True
        except Exception as e:
            print(f"❌ Live dashboard не загрузился: {e}")
            return False

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

    
    # ---------- bidding ----------
    async def bid_current_lot(self) -> bool:
        """
        Нажимает кнопку 'Bid' на текущем лоте.
        Возвращает True если клик произошёл (кнопка была доступна).
        """
        try:
            btn = self.page.locator("button[data-uname='bidCurrentLot']")
            await btn.wait_for(state="visible", timeout=8000)
            disabled = await btn.is_disabled()
            if disabled:
                print("⚠️ Кнопка Bid недоступна (disabled).")
                return False
            await btn.click()
            return True
        except Exception as e:
            print(f"❌ Не удалось нажать Bid: {e}")
            return False

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
# Пример использования (исправленный)
# ======================
async def main():
    import os

    # ENV:
    # COPART_USER, COPART_PASS, COPART_DO_BID=1, COPART_TRACK_SECS=15, HEADLESS=1, COPART_LIVE_TITLE="CT - Hartford"
    USERNAME = os.getenv("COPART_USER", "755554")
    PASSWORD = os.getenv("COPART_PASS", "newpass0408")
    DO_BID = os.getenv("COPART_DO_BID", "0") == "1"
    TRACK_SECONDS = int(os.getenv("COPART_TRACK_SECS", "15"))
    HEADLESS = os.getenv("HEADLESS", "0") == "1"
    LIVE_TITLE_HINT = os.getenv("COPART_LIVE_TITLE", "").strip()  # например: "CT - Hartford"
    print(f"LIVE TITLE HINT: {LIVE_TITLE_HINT}")
    store = SessionStore("sessions.db")
    await store.init()

    # 1) восстановить сессию и старт
    storage = await store.get_storage_state(USERNAME)
    bot = CopartBot(username=USERNAME, password=PASSWORD, headless=HEADLESS)
    await bot.start(storage_state=storage)

    try:
        # 2) сессия
        ok = await bot.ensure_session(store)
        if not ok:
            print("⛔ Не удалось авторизоваться.")
            return

        # A) health
        is_ok = await bot.health_check()
        print(f"health_check: {is_ok}")

        # B) календарь и join лайва: сначала пробуем по модальной ссылке (ng-click)
        await bot.page.goto("https://www.copart.com/auctionCalendar", wait_until="domcontentloaded")
        await bot._maybe_accept_cookies()
        cal = await bot.get_calendar_live_status()
        print(f"На календаре: активных слотов = {len(cal['active'])}, неактивных = {len(cal['inactive'])}")
        # for it in cal["active"]:
        #     print(f"  LIVE: {it['time']} | {it['title']} | {it['href']}")

        joined = False
        if LIVE_TITLE_HINT:
            print(f"▶1 Присоединяюсь к live по модальной ссылке: {LIVE_TITLE_HINT}")
            joined = await bot.join_live_from_calendar_by_title(LIVE_TITLE_HINT)
            print(f'JOINED OR NOT: JOINED? {joined}')

        if not joined and cal["active"]:
            first = cal["active"][0]
            print(f'FUCKING FIRST CAL: {cal["active"][0]}')
            title_hint = (first.get("title") or "").split("(")[0].strip()
            if title_hint:
                print(f"▶2 Присоединяюсь к live по модальной ссылке: {title_hint}")
                joined = await bot.join_live_from_calendar_by_title(title_hint)

            if not joined and first.get("href"):
                print(f"▶ Фоллбек: присоединяюсь по href: {first['time']} | {first['href']}")
                joined = await bot.click_live_slot_and_join(first["href"])

        if not joined:
            print("⛔ Не удалось присоединиться к live-аукциону.")
            try:
                await bot.debug_list_live_titles()
            except Exception:
                pass
            return

        # C) мы на live-дашборде; вычислим widgetId по URL (auctionDetails=135-A → #widget-COPART135A)
        widget_id = await bot._auction_widget_id_from_url()
        print(f"WIDGET ID: {widget_id}")
        if not widget_id:
            # на всякий случай дождаться любого виджета
            await bot.wait_for_live_dashboard(timeout_ms=45000)
            widget_id = await bot._auction_widget_id_from_url()

        print(f"Widget container: {widget_id or '(не определён)'}")

        # D) дождёмся загрузки целевого виджета и ключевых элементов
        ok = await bot.wait_for_live_dashboard(widget_id=widget_id, timeout_ms=45000)
        if not ok:
            print("⛔ Live dashboard не прогрузил нужный виджет.")
            return

        # E) снимем детали текущего лота
        lot_live = await bot.extract_current_lot_details_live()
        print("Live lot details:", json.dumps(lot_live, ensure_ascii=False, indent=2))

        # F) слежение за ставками: инпут + SVG-текст
        print(f"⏱  Слежу за ставкой {TRACK_SECONDS} сек…")
        samples = await bot.track_bid_amounts(widget_id=widget_id, seconds=TRACK_SECONDS, interval=1.0)
        # лог красиво: ts | input=… | price=…
        for s in samples:
            print(f"{s['ts']} | input={s.get('input_value')!s} | price={s.get('display_price')!s}")

        # G) (опционально) кликнуть Bid
        if DO_BID:
            bid_ok = await bot.bid_current_lot(widget_id=widget_id)
            print(f"Bid clicked: {bid_ok}")

            # прочитаем ещё раз значения после клика
            after_input = await bot.read_bid_amount(widget_id=widget_id)
            after_price = await bot.read_display_price(widget_id=widget_id)
            print(f"After bid → input={after_input!s} | price={after_price!s}")

        # (Необязательно) прежние примеры
        regions_today = await bot.get_regions_for_date()
        print(f"Сегодня найдено регионов: {len(regions_today)}")
        for r in regions_today:
            print(f"  {r['time']} | {r['title']} | {r['link']}")

        example_lot_url = "https://www.copart.com/lot/48501315/salvage-2022-nissan-frontier-s-fl-ft-pierce?resultIndex=0&totalRecords=94&backTo=%2FsaleListResult%2F86%2F2025-09-03%2FA%3Flocation%3DFL%20-%20Ft.%20Pierce&saleDate=1756908000000&liveAuction=false&from=&yardNum=86&displayStr=Sale%20list%20for%20FL%20-%20Ft.%20Pierce&viewedLot=48501315&fromSearch=true"
        try:
            lot = await bot.get_lot_details(example_lot_url)
            print("Lot (card page):", json.dumps(lot, ensure_ascii=False, indent=2))
        except Exception as e:
            print("Ошибка при получении лота:", e)

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

# _hrs or _ful its diferrence between hd or not hd photo, _thb is thubnail photo