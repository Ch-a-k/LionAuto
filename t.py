import asyncio
import csv
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from io import BytesIO
from urllib.parse import urlparse
import mimetypes
from app.services.store.s3contabo import s3_service
from app.core.config.config import settings

load_dotenv()

# =======================
# Конфиг
# =======================

COPART_USER = os.getenv("COPART_USER", "")
COPART_PASS = os.getenv("COPART_PASS", "")
HEADLESS = os.getenv("HEADLESS", "1") == "0"

LOCAL_BATCH_URL = os.getenv("LOCAL_BATCH_URL", "http://37.60.253.236:89/lot/lots/batch")
LOCAL_AUTH = os.getenv("LOCAL_AUTH", "8fd3b8c4b91e47f5a6e2d7c9f1a4b3d2")  # secret_key из .env

MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "100"))

# URL страницы поиска с фильтрами
SEARCH_RESULTS_URL = (
    "https://www.copart.com/lotSearchResults?free=false&searchCriteria="
    "%7B%22query%22:%5B%22*%22%5D,%22filter%22:%7B%22ODM%22:%5B%22odometer_reading_received:%5B0%20TO%209999999%5D%22%5D,"
    "%22YEAR%22:%5B%22lot_year:%5B2015%20TO%202026%5D%22%5D,%22MISC%22:%5B%22%23VehicleTypeCode:VEHTYPE_V%22%5D%7D,"
    "%22searchName%22:%22%22,%22watchListOnly%22:false,%22freeFormSearch%22:false%7D%20"
    "&displayStr=AUTOMOBILE,%5B0%20TO%209999999%5D,%5B2015%20TO%202026%5D&from=%2FvehicleFinder"
    "&fromSource=widget&qId=af2f7b1c-fd0a-11e9-a583-48df3771ed50-1763666292713"
)
IMAGE_CONCURRENCY = int(os.getenv("IMAGE_CONCURRENCY", "5")) 

# =======================
# Утилиты
# =======================

def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# =======================
# SessionStore (SQLite)
# =======================

class SessionStore:
    """
    Простейшее хранилище storage_state в SQLite.
    Ключом используем username.
    """
    def __init__(self, db_path: str = "sessions.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_sessions (
                    username TEXT PRIMARY KEY,
                    storage_state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def get_storage_state(self, username: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT storage_state_json FROM bot_sessions WHERE username = ?",
                (username,),
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
        now = now_iso_utc()
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


# =======================
# CopartBot
# =======================

class CopartBot:
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.headless = headless

        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, storage_state=None):
        self._pw = await async_playwright().start()

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
        self.context = await self.browser.new_context(
            storage_state=storage_state,
        )
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
        await self.page.wait_for_selector(
            "a[data-uname='homePageMemberSignIn']",
            timeout=8000,
        )
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
        try:
            await self.page.goto("https://www.copart.com/dashboard", wait_until="domcontentloaded")
            await self._maybe_accept_cookies()
            await self.page.wait_for_selector("text=Hi,", timeout=8000)
            return True
        except Exception:
            return False

    async def ensure_session(self, store: SessionStore) -> bool:
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

    # ---------- переход на страницу поиска ----------

    async def goto_search_results(self):
        print("🌐 Открываю страницу поиска с фильтрами...")
        await self.page.goto(SEARCH_RESULTS_URL, wait_until="domcontentloaded")
        await self._maybe_accept_cookies()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)

    # ---------- экспорт CSV ----------

    async def export_csv_once(self) -> Optional[str]:
        """
        Нажимает 'New list view', затем 'Экспорт', ждёт CSV.
        Возвращает путь к файлу.
        """
        print("📥 Подготовка к экспорту...")

        # 1. Перейти на страницу поиска
        await self.goto_search_results()

        # 2. Нажать 'New list view'
        try:
            print("🔄 Переключаюсь в New list view…")
            new_list_btn = self.page.locator("span:has-text('New list view')").first
            await new_list_btn.wait_for(state="visible", timeout=15000)
            await new_list_btn.click()
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            print(f"⚠️ Не удалось нажать 'New list view': {e}")

        # 3. Найти кнопку Экспорт
        print("📦 Жду кнопку 'Экспорт'...")
        export_btn = self.page.locator("button.export-csv-button").first
        await export_btn.wait_for(state="visible", timeout=25000)

        # 4. Скачать файл
        async with self.page.expect_download() as download_info:
            print("📥 Жму кнопку 'Экспорт' и жду CSV…")
            await export_btn.click()

        download = await download_info.value
        path = await download.path()
        filename = download.suggested_filename

        print(f"✅ CSV скачан: {filename} → {path}")
        return path

    # ---------- helpers for lot ----------

    def _lot_id_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"/lot/(\d+)", url)
        return m.group(1) if m else None

    async def _ensure_on_lot(self, expected_url: str, *, attempts: int = 3) -> bool:
        exp_lot = self._lot_id_from_url(expected_url)
        for i in range(1, attempts + 1):
            cur = self.page.url
            cur_lot = self._lot_id_from_url(cur)

            dom_lot = ""
            try:
                await self.page.wait_for_selector(
                    "h1.title, #LotNumber, .lot-detail-section",
                    timeout=6000,
                )
                try:
                    dom_lot = (await self.page.locator("#LotNumber").first.inner_text()).strip()
                except Exception:
                    dom_lot = ""
            except Exception:
                pass

            if cur_lot == exp_lot or (dom_lot and exp_lot and exp_lot in dom_lot):
                return True

            print(
                f"⚠️ Не та страница лота (got URL lot={cur_lot}, "
                f"DOM lot={dom_lot or '—'}, need={exp_lot}) — попытка {i}/{attempts}"
            )
            await self.page.goto(expected_url, wait_until="domcontentloaded")
            await self.page.wait_for_selector(
                "h1.title, #LotNumber, .lot-detail-section",
                timeout=15000,
            )
            await self._scroll_to_bottom(step=1200, max_iters=2)
        return False

    # ---------- get_lot_details ----------

    async def get_lot_details(self, lot_url: str) -> Dict[str, Any]:
        """
        Открывает страницу лота и вытягивает ключевые поля + ссылки на миниатюры,
        а также sale_state / sale_location / time_left из блока "Sale information".
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

        // ------ SALE INFO ------
        const saleLocation = txt("div#sale-information-block a[data-uname='lotdetailSaleinformationlocationvalue']");
        let saleState = "";
        if (saleLocation) {
            const parts = saleLocation.split("-");
            if (parts.length > 0) {
            saleState = parts[0].trim();  // "CT - HARTFORD..." -> "CT"
            }
        }

        // Time left: "0D 4H 41min"
        const timeLeft = txt("span[data-uname='lotdetailSaleinformationtimeleftvalue']");

        // ✅ Текущая ставка, например "$4,000.00"
        const currentBid = txt("span.bid-price");

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

            // НОВОЕ + старое:
            sale_state: saleState,
            sale_location: saleLocation,
            time_left: timeLeft,
            current_bid: currentBid,   // ✅ добавили
        };
        }
        """)
        details["lot_link"] = lot_url
        return details




# =======================
# Чтение CSV и ссылки
# =======================

def extract_links_from_csv(csv_path: str) -> List[str]:
    """
    Считывает CSV и вытаскивает ссылки на лоты.
    НЕ зависит от имени колонки: ищет во всех значениях подстроку 'copart.com/lot/'.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV файл не найден: {csv_path}")

    print(f"📄 Читаю CSV: {csv_path}")
    links_set: set[str] = set()

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        print("🧾 Колонки CSV:", reader.fieldnames)

        for row in reader:
            if not row:
                continue
            for value in row.values():
                if not value:
                    continue
                v = str(value).strip()
                if "copart.com/lot/" in v:
                    v = v.strip().strip('"').strip()
                    links_set.add(v)

    unique_links = sorted(links_set)
    print(f"🔗 Найдено ссылок: {len(unique_links)}")
    if unique_links[:5]:
        print("Примеры ссылок:")
        for l in unique_links[:5]:
            print("  ", l)
    return unique_links


# =======================
# Маппер details -> VehicleModel (Factum style)
# =======================

def parse_odometer(odometer_str: str) -> tuple[int, Optional[str]]:
    """
    '101,779 mi (ACTUAL)' -> (101779, 'ACTUAL')
    """
    if not odometer_str:
        return 0, None
    digits = "".join(ch for ch in odometer_str if ch.isdigit())
    value = int(digits) if digits else 0

    brand = None
    m = re.search(r"\(([^()]+)\)", odometer_str)
    if m:
        brand = m.group(1).strip()
    return value, brand


def parse_year_from_title(title: str) -> Optional[int]:
    if not title:
        return None
    m = re.match(r"^\s*(\d{4})\b", title)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def split_title(title: str) -> tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
    """
    '2014 UTIL REEFER 53' - Refrigerated Van Trailer'
    -> year, make, model, body_type
    """
    if not title:
        return None, None, None, None
    parts = title.split(" - ", 1)
    left = parts[0].strip()
    body_type = parts[1].strip() if len(parts) > 1 else ""
    words = left.split()
    if not words:
        return None, None, None, body_type
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    if re.fullmatch(r"\d{4}", words[0]):
        try:
            year = int(words[0])
        except ValueError:
            year = None
        if len(words) >= 2:
            make = words[1]
            model = " ".join(words[2:]) or None
    else:
        make = words[0]
        model = " ".join(words[1:]) or None
    return year, make, model, body_type


def parse_cylinders(cyl_str: str) -> Optional[int]:
    """
    '6' -> 6, '3.0L  6' -> 6, '' -> None
    """
    if not cyl_str:
        return None
    m = re.search(r"\d+", cyl_str)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def build_image_sets(images: List[str]) -> tuple[List[str], List[str], Optional[str]]:
    """
    images (thumbnails) -> (link_img_small, link_img_hd, image_thumbnail)
    *_thb -> *_ful + *_hrs
    """
    thumbs: List[str] = []
    hd: List[str] = []
    for url in images or []:
        url = url.strip()
        if not url:
            continue
        thumbs.append(url)
        if "_thb" in url:
            base = url.replace("_thb", "")
            if base.endswith((".jpg", ".jpeg", ".png")):
                base_no_ext, ext = os.path.splitext(base)
            else:
                base_no_ext, ext = base, ""
            hd.append(f"{base_no_ext}_ful{ext}")
            hd.append(f"{base_no_ext}_hrs{ext}")
    image_thumbnail = thumbs[0] if thumbs else None
    return thumbs, hd, image_thumbnail


def title_case_name(value: Optional[str]) -> Optional[str]:
    """
    Делает 'bmw x5' -> 'Bmw X5', 'BMW' -> 'Bmw'.
    """
    if not value:
        return value
    return " ".join(w.capitalize() for w in value.split())


def normalize_make(make: Optional[str]) -> Optional[str]:
    """
    Маппер брендов:
      HYUN / HYUNDAI -> Hyundai
      NISS / NISSAN  -> Nissan
      и т.д. (добавишь по мере надобности)
    """
    if not make:
        return make
    up = make.upper().strip()
    mapping = {
        "HYUN": "Hyundai",
        "HYUNDAI": "Hyundai",
        "NISS": "Nissan",
        "NISSAN": "Nissan",
    }
    if up in mapping:
        return mapping[up]
    # дефолт — просто Title Case
    return title_case_name(make)


async def mirror_copart_images_to_s3(
    lot_id: str,
    thumbs: List[str],
    client: Optional[httpx.AsyncClient] = None,
) -> tuple[List[str], List[str]]:
    """
    Берём thumbnail-URLs Copart, считаем из них small + HD,
    качаем и грузим в S3 ПАРАЛЛЕЛЬНО с ограничением по количеству.

    Возвращает (s3_small_urls, s3_hd_urls).
    """
    small_urls, hd_urls, _ = build_image_sets(thumbs)

    sem = asyncio.Semaphore(IMAGE_CONCURRENCY)

    # если клиент не передали — создаём временный
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=30)

    assert client is not None

    async def _process_one(idx: int, url: str, kind: str) -> Optional[str]:
        url = (url or "").strip()
        if not url:
            return None

        async with sem:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception as e:
                print(f"⚠️ Не удалось скачать {kind}-картинку {url}: {e}")
                return None

            ct = (
                resp.headers.get("content-type")
                or mimetypes.guess_type(url)[0]
                or "image/jpeg"
            )
            ext = (
                mimetypes.guess_extension(ct)
                or os.path.splitext(urlparse(url).path)[1]
                or ".jpg"
            )

            key = f"copart/{lot_id}/{kind}/{idx:03d}{ext}"
            fileobj = BytesIO(resp.content)

            try:
                await s3_service.upload_fileobj(
                    fileobj=fileobj,
                    key=key,
                    content_type=ct,
                    public_read=True,
                )
            except Exception as e:
                print(f"⚠️ Не удалось загрузить {kind}-картинку в S3 ({key}): {e}")
                return None

            public_url = s3_service.build_public_url(key)
            public_url = public_url.replace(
                "https://usc1.contabostorage.com/fadder",
                settings.CONTABO_S3_PUBLIC_URL,
            )
            print(public_url)
            return public_url

    try:
        small_tasks = [
            _process_one(idx, url, "small") for idx, url in enumerate(small_urls)
        ]
        hd_tasks = [
            _process_one(idx, url, "hd") for idx, url in enumerate(hd_urls)
        ]

        s3_small = [u for u in await asyncio.gather(*small_tasks) if u]
        s3_hd = [u for u in await asyncio.gather(*hd_tasks) if u]

        return s3_small, s3_hd
    finally:
        if own_client:
            await client.aclose()



def map_factum_to_model_from_details(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Маппинг данных, полученных из get_lot_details(), в структуру VehicleModel/VehicleModelOther.

    Если лот заведомо невалиден (нет lot_number, не получается year,
    VIN не 17 символов и т.п.) — возвращает None (такой лот можно пропустить).
    """

    # ---------- Вспомогательные функции ----------

    def s(x: Any) -> str:
        """Гарантированно вернуть строку (для полей, где Pydantic хочет str, а не None)."""
        if x is None:
            return ""
        x = str(x).strip()
        return x

    def parse_year_from_title(title: str) -> Optional[int]:
        """Ищем год в заголовке, например '2014 UTIL REEFER 53' - ...'."""
        if not title:
            return None
        m = re.search(r"\b(19\d{2}|20\d{2})\b", title)
        if not m:
            return None
        try:
            return int(m.group(1))
        except ValueError:
            return None

    def parse_current_bid(bid_raw: str) -> int:
        """
        '$4,000.00' -> 4000
        '€ 1 500'   -> 1500
        """
        bid_raw = bid_raw or ""
        digits = re.sub(r"[^\d]", "", bid_raw)
        return int(digits) if digits else 0


    def parse_make_model_body_type(title: str) -> tuple[str, str, str]:
        """
        Заголовок вида:
          '2014 UTIL REEFER 53' - Refrigerated Van Trailer'
        Возвращает (make, model, body_type).
        """
        title = title or ""
        body_type = ""
        left = title
        if "-" in title:
            left, right = title.split("-", 1)
            body_type = right.strip()

        left = left.strip()
        parts = left.split()

        year_str = None
        if parts and re.fullmatch(r"(19\d{2}|20\d{2})", parts[0]):
            year_str = parts[0]
            parts = parts[1:]

        make = parts[0] if parts else ""
        model = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Приводим красиво: первая буква большая, остальные маленькие
        make = make.title()
        model = model.title()
        body_type = body_type.title()

        return make, model, body_type

    def parse_odometer(odo_raw: str) -> tuple[int, str]:
        """
        '101,779 mi (ACTUAL)' → (101779, 'ACTUAL')
        '0 mi (NOT ACTUAL)'  → (0, 'NOT ACTUAL')
        """
        odo_raw = odo_raw or ""
        # число
        m_num = re.search(r"([\d,]+)", odo_raw)
        if m_num:
            num = int(m_num.group(1).replace(",", ""))
        else:
            num = 0

        # бренд одометра (в скобках)
        m_brand = re.search(r"\(([^)]+)\)", odo_raw)
        brand = m_brand.group(1).strip() if m_brand else ""

        return num, brand

    def derive_hd_images(thumbnails: List[str]) -> List[str]:
        """
        Из thumbnail'ов вида ..._thb.jpg делаем список HD-ссылок:
        ..._ful.jpg и ..._hrs.jpg
        """
        hd: List[str] = []
        for url in thumbnails:
            url = url.strip()
            if not url:
                continue
            if "_thb" in url:
                base = url.replace("_thb.jpg", "")
                hd.append(base + "_ful.jpg")
                hd.append(base + "_hrs.jpg")
            else:
                # если вдруг уже HD — просто добавим как есть
                hd.append(url)
        # Уникализируем
        return list(dict.fromkeys(hd))

    def calc_auction_datetime(time_left_str: str) -> Optional[str]:
        """
        Превращает строку вида '0D 4H 41min' в ISO datetime (UTC), например:
        '2025-11-20T19:41:00+00:00'
        """
        time_left_str = (time_left_str or "").strip()
        if not time_left_str:
            return None

        m = re.search(r"(\d+)D\s+(\d+)H\s+(\d+)min", time_left_str)
        if not m:
            return None

        days = int(m.group(1))
        hours = int(m.group(2))
        minutes = int(m.group(3))

        now = datetime.now(timezone.utc)
        dt = now + timedelta(days=days, hours=hours, minutes=minutes)
        return dt.isoformat()

    # ---------- Разбор исходных данных ----------

    title = s(item.get("title"))
    lot_number_raw = item.get("lot_number") or item.get("lot_id") or ""

    lot_number_str = s(lot_number_raw)
    if not lot_number_str.isdigit():
        # без нормального lot_id в базу не шлём
        return None
    lot_id = int(lot_number_str)

    vin = s(item.get("vin")).upper()
    # жёсткое правило бэкенда: VIN должен быть ровно 17 символов
    if len(vin) != 17:
        return None

    year = parse_year_from_title(title)
    if year is None:
        # бэкенд ругался, если year был None, поэтому просто пропускаем такие лоты
        return None

    # odometer + odobrand
    odometer_raw = s(item.get("odometer"))
    odometer_val, odobrand = parse_odometer(odometer_raw)

    # Sale state/location
    sale_location = s(item.get("sale_location"))
    sale_state = s(item.get("sale_state"))
    if not sale_state and " - " in sale_location:
        # 'CT - HARTFORD SPRINGFIELD' → 'CT'
        sale_state = sale_location.split(" - ", 1)[0].strip()

    # Time left → auction_date (полный datetime)
    auction_date_iso = calc_auction_datetime(item.get("time_left"))


    current_bid_raw = s(item.get("current_bid"))
    current_bid_val = parse_current_bid(current_bid_raw)
    # make/model/body_type из title
    make, model, body_type = parse_make_model_body_type(title)

    # Цилиндры → int
    cylinders_raw = s(item.get("cylinders"))
    if cylinders_raw.isdigit():
        cylinders = int(cylinders_raw)
    else:
        cylinders = 0  # чтобы не вызывать int_parsing на '' или None

    # остальные поля как строки
    primary_damage = s(item.get("primary_damage"))
    color = s(item.get("color"))
    engine_type = s(item.get("engine_type"))
    transmission = s(item.get("transmission"))
    drive = s(item.get("drive"))
    vehicle_type = s(item.get("vehicle_type"))
    fuel = s(item.get("fuel"))
    keys = s(item.get("keys"))
    title_code = s(item.get("title_code"))

    # картинки
    thumbs: List[str] = item.get("images_small") or item.get("images") or []
    thumbs = [t for t in thumbs if t]

    hd_list: List[str] = item.get("images_hd") or []
    hd_list = [u for u in hd_list if u]

    link_img_small = thumbs
    link_img_hd = hd_list or thumbs  # если HD нет, дублируем small
    image_thumbnail = thumbs[0] if thumbs else (hd_list[0] if hd_list else None)

    now_iso = datetime.now(timezone.utc).isoformat()

    # ---------- Финальный словарь под VehicleModel / VehicleModelOther ----------

    return {
        "lot_id": lot_id,
        "base_site": "copart",          # фиксированно
        "odometer": odometer_val,
        "price": 0,
        "reserve_price": 0,
        "bid": 0,
        "current_bid": current_bid_val,
        "auction_date": auction_date_iso,  # ✅ полное datetime ISO из Time left
        "cost_repair": 0,
        "year": year,
        "cylinders": cylinders,
        "state": sale_state,               # строка, не None
        "location": sale_location,         # строка, не None

        "vehicle_type": vehicle_type,
        "make": make,
        "model": model,
        "damage_pr": primary_damage,
        "damage_sec": "",
        "keys": keys,
        "odobrand": odobrand,
        "fuel": fuel,
        "drive": drive,
        "transmission": transmission,
        "color": color,
        "status": "",
        "auction_status": "Not Sold",
        "body_type": body_type,
        "series": "",
        "title": title,

        "vin": vin,
        "engine": engine_type,
        "engine_size": None,
        "location_old": "",
        "country": "USA",

        "document": title_code,
        "document_old": "",
        "seller": "",

        "image_thubnail": image_thumbnail,
        "is_buynow": False,
        "link_img_hd": link_img_hd,
        "link_img_small": link_img_small,
        "link": s(item.get("lot_link")),
        "seller_type": "",

        "risk_index": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "is_historical": False,
    }

# =======================
# Отправка батчей в API
# =======================

def send_batchs(models: List[Dict[str, Any]], chunk_size: int = MAX_BATCH_SIZE):
    if not models:
        print("ℹ️ Пустой список моделей, отправлять нечего.")
        return

    headers = {
        "Authorization": LOCAL_AUTH,
        "content-type": "application/json",
    }

    total = len(models)
    print(f"🚚 Отправляю {total} лотов в {LOCAL_BATCH_URL} батчами по {chunk_size} ...")

    # Один httpx.Client на все батчи → реюз соединения, быстрее и аккуратнее
    with httpx.Client(timeout=30) as client:
        for i in range(0, total, chunk_size):
            chunk = models[i: i + chunk_size]
            print(f"  → батч {i+1}-{i+len(chunk)} (из {total})")

            try:
                resp = client.post(LOCAL_BATCH_URL, json=chunk, headers=headers)
            except httpx.RequestError as e:
                print(f"    ❌ Ошибка при отправке батча: {e}")
                continue

            print("    STATUS:", resp.status_code)
            try:
                print("    RESPONSE JSON:", resp.json())
            except Exception:
                print("    RESPONSE TEXT:", resp.text[:1000])


def calc_auction_datetime(time_left_str: str) -> str | None:
    """
    Превращает строку вида:
       '0D 4H 41min'
       '4D 3H 5min'
    в UTC ISO дату:
       '2025-11-20T19:41:00Z'
    """

    if not time_left_str:
        return None

    # Ищем формата 4D 3H 5min
    m = re.search(r"(\d+)D\s+(\d+)H\s+(\d+)min", time_left_str)
    if not m:
        return None

    days = int(m.group(1))
    hours = int(m.group(2))
    minutes = int(m.group(3))

    # Текущее время в UTC
    now = datetime.now(timezone.utc)

    # Добавляем интервал
    dt = now + timedelta(days=days, hours=hours, minutes=minutes)

    return dt.isoformat()


# =======================
# Основная логика
# =======================

async def fetch_details_for_links(bot: CopartBot, links: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    total = len(links)

    async with httpx.AsyncClient(timeout=30) as client:
        for idx, url in enumerate(links, start=1):
            lot_id_from_url = url.split("/lot/")[-1].split("/")[0]
            print(f"[{idx}/{total}] Тяну детали лота {lot_id_from_url}…")
            try:
                details = await bot.get_lot_details(url)

                # определяем lot_id для ключей в S3
                lot_number = details.get("lot_number") or lot_id_from_url
                lot_id_str = str(lot_number)

                # исходные thumbnail'ы с Copart
                thumbs: List[str] = details.get("images") or []

                # заливаем в S3 → получаем S3 small / hd (уже async + параллельно)
                s3_small, s3_hd = await mirror_copart_images_to_s3(
                    lot_id_str,
                    thumbs,
                    client=client,
                )

                # сохраняем S3-ссылки в деталях
                details["images_small"] = s3_small
                details["images_hd"] = s3_hd
                details["images"] = s3_small  # для совместимости

                results.append(details)
            except Exception as e:
                print(f"❌ Ошибка при разборе лота {lot_id_from_url}: {e}")

    return results


async def main():
    if not COPART_USER or not COPART_PASS:
        print("⛔ Укажи COPART_USER и COPART_PASS в .env")
        return

    store = SessionStore("sessions.db")
    await store.init()

    bot = CopartBot(username=COPART_USER, password=COPART_PASS, headless=HEADLESS)
    await bot.start(storage_state=await store.get_storage_state(COPART_USER))

    try:
        if not await bot.ensure_session(store):
            print("⛔ Авторизация не удалась")
            return
        print("✅ Сессия валидна")

        # 1) СКАЧИВАНИЕ CSV ЧЕРЕЗ EXPORT
        csv_path = await bot.export_csv_once()
        if not csv_path:
            print("⛔ Не удалось получить путь к CSV")
            return

        # 2) ВЫТАСКИВАЕМ ССЫЛКИ ИЗ CSV
        links = extract_links_from_csv(csv_path)
        if not links:
            print("⛔ В CSV не найдено ни одной ссылки на лоты")
            return

        total_links = len(links)
        print(f"\n🔢 Всего ссылок на лоты: {total_links}")

        BATCH_SIZE = 20
        total_sent = 0
        total_skipped = 0
        first_example_printed = False

        # 3) ИДЁМ ПО ССЫЛКАМ БАТЧАМИ ПО 20
        for start in range(0, total_links, BATCH_SIZE):
            batch_links = links[start:start + BATCH_SIZE]
            print(
                f"\n🚀 Обработка батча ссылок {start + 1}–{start + len(batch_links)} "
                f"из {total_links}"
            )

            # 3.1) ТЯНЕМ ДЕТАЛИ ПО БАТЧУ ССЫЛОК
            details_list = await fetch_details_for_links(bot, batch_links)
            print(f"  ✅ В этом батче разобрано лотов: {len(details_list)}")

            # 3.2) МАППИМ В ФОРМАТ FACTUM / VehicleModel
            mapped_batch: List[Dict[str, Any]] = []
            skipped_batch = 0
            for d in details_list:
                m = map_factum_to_model_from_details(d)
                if m is None:
                    skipped_batch += 1
                    continue
                mapped_batch.append(m)

            total_sent += len(mapped_batch)
            total_skipped += skipped_batch

            print(
                f"  📦 В этом батче готово моделей к отправке: {len(mapped_batch)}, "
                f"пропущено (невалидные): {skipped_batch}"
            )

            # 3.3) Для первого валидного батча покажем пример
            if mapped_batch and not first_example_printed:
                print("\nПример mapped[0]:")
                for k, v in mapped_batch[0].items():
                    print(f"  {k}: {v}")
                first_example_printed = True

            # 3.4) ОТПРАВКА ЭТОГО БАТЧА В API
            if mapped_batch:
                # отправляем именно этот батч; внутренняя разбивка в send_batchs
                # тоже может делиться, но мы явно задаём chunk_size=BATCH_SIZE,
                # чтобы улетало по 20.
                send_batchs(mapped_batch, chunk_size=BATCH_SIZE)
            else:
                print("  ⚠️ В этом батче нет валидных моделей для отправки.")

        print(
            f"\n✅ Готово. Всего отправлено моделей: {total_sent}, "
            f"пропущено (невалидные): {total_skipped}"
        )

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
