# manheim.py
# -*- coding: utf-8 -*-
import asyncio
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Импорт: сначала patchright, потом Playwright (fallback)
try:
    from patchright.async_api import async_playwright, Browser, Page
    USING_PATCHRIGHT = True
except Exception:
    from playwright.async_api import async_playwright, Browser, Page  # type: ignore
    USING_PATCHRIGHT = False


class ManheimScraper:
    """
    Скрейпер Manheim (site.manheim.com) через patchright/Playwright.

    Поток:
      1) Главная -> клик по "Buy" (устойчиво, с несколькими fallback)
      2) Переход на /en/locations
      3) Раскрыть "By state name" (несколько селекторов + программное раскрытие)
      4) Собрать все ссылки штатов из '#states-results a.dropdown-item' БЕЗ требования видимости
      5) Для каждой ссылки штата: забрать карточки '.single-location__container' (≤ таймаута) и распарсить поля

    Headless выключен по умолчанию.
    """

    HOME_URL = "https://site.manheim.com/"
    LOCATIONS_URL = "https://site.manheim.com/en/locations"

    BUY_LABEL_SELECTOR = 'label#uhf---panelbutton--buy'
    BUY_WRAP_SELECTOR = 'div.uhf-accordion__trigger[data-test-id="uhf-panel-trigger-buy"]'
    STATES_BOX_SELECTOR = "#states-results"
    STATES_ANCHORS_SELECTOR = "#states-results a.dropdown-item"
    LOCATION_CARD_SELECTOR = "div.single-location__container"

    def __init__(
        self,
        headless: bool = False,            # окно браузера видно
        slowmo_ms: int = 40,
        navigation_timeout_ms: int = 45000,
        state_wait_timeout_ms: int = 6000,
        proxy: Optional[Dict[str, str]] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.headless = headless
        self.slowmo_ms = slowmo_ms
        self.navigation_timeout_ms = navigation_timeout_ms
        self.state_wait_timeout_ms = state_wait_timeout_ms
        self.proxy = proxy
        self.user_agent = user_agent or (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._playwright = None

    # ---------------- Lifecycle ----------------
    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        launch_args = {"headless": self.headless, "slow_mo": self.slowmo_ms}
        if self.proxy:
            launch_args["proxy"] = self.proxy

        self._browser = await self._playwright.chromium.launch(**launch_args)
        context = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1366, "height": 900},
            java_script_enabled=True,
        )
        page = await context.new_page()
        page.set_default_timeout(self.navigation_timeout_ms)
        self._page = page

    async def close(self) -> None:
        try:
            if self._page:
                await self._page.context.close()
        finally:
            try:
                if self._browser:
                    await self._browser.close()
            finally:
                if self._playwright:
                    await self._playwright.stop()

    # ---------------- Utils ----------------
    async def _maybe_accept_cookies(self, page: Page) -> None:
        for sel in [
            'button:has-text("Accept")',
            'button:has-text("I Agree")',
            'button[aria-label="Accept cookies"]',
            'button:has-text("OK")',
        ]:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(0.2)
                    break
            except Exception:
                continue

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        if not text:
            return ""
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\s*\n\s*", "\n", text)
        return text.strip()

    async def _text_or_empty(self, root, selector: str) -> str:
        el = await root.query_selector(selector)
        if not el:
            return ""
        try:
            return self._clean_text(await el.inner_text())
        except Exception:
            return ""

    async def _all_texts(self, root, selector: str) -> List[str]:
        els = await root.query_selector_all(selector)
        out: List[str] = []
        for el in els:
            try:
                txt = await el.inner_text()
                txt = self._clean_text(txt)
                if txt:
                    out.append(txt)
            except Exception:
                continue
        return out

    async def _attr_or_empty(self, root, selector: str, attr: str) -> str:
        el = await root.query_selector(selector)
        if not el:
            return ""
        val = await el.get_attribute(attr)
        return val or ""

    # ---------------- Robust actions ----------------
    async def _robust_click_buy(self, page: Page) -> None:
        """
        Очень настойчиво кликает по Buy:
        - пытается по label
        - по wrapper div
        - scrollIntoView + force=True
        - прямой JS click
        Если всё равно не вышло — продолжаем (это не критично для дальнейшего потока).
        """
        try:
            # 1) label
            lab = page.locator(self.BUY_LABEL_SELECTOR)
            if await lab.count():
                try:
                    await lab.scroll_into_view_if_needed()
                except Exception:
                    pass
                try:
                    await lab.click(timeout=2000, force=True)
                    return
                except Exception:
                    # JS click как fallback
                    try:
                        handle = await page.query_selector(self.BUY_LABEL_SELECTOR)
                        if handle:
                            await page.evaluate("(el)=>el.click()", handle)
                            return
                    except Exception:
                        pass

            # 2) wrapper div
            wrap = page.locator(self.BUY_WRAP_SELECTOR)
            if await wrap.count():
                try:
                    await wrap.scroll_into_view_if_needed()
                except Exception:
                    pass
                try:
                    await wrap.click(timeout=2000, force=True)
                    return
                except Exception:
                    # кликнуть дочерний label через wrapper
                    try:
                        handle = await page.query_selector(f"{self.BUY_WRAP_SELECTOR} {self.BUY_LABEL_SELECTOR}")
                        if handle:
                            await page.evaluate("(el)=>el.click()", handle)
                            return
                    except Exception:
                        pass
        except Exception:
            pass
        # не критично — просто идём дальше

    # ---------------- Flow ----------------
    async def _go_home_and_open_cars(self, page: Page) -> None:
        """Главная (куки + Buy), затем /en/locations."""
        await page.goto(self.HOME_URL, wait_until="domcontentloaded")
        await self._maybe_accept_cookies(page)
        # попытаться кликнуть Buy (по просьбе из ТЗ)
        await self._robust_click_buy(page)
        # для сбора штатов всё равно идём на Locations
        await page.goto(self.LOCATIONS_URL, wait_until="domcontentloaded")
        await self._maybe_accept_cookies(page)

    async def _collect_state_links(self, page: Page) -> List[Tuple[str, str]]:
        """
        На странице /en/locations раскрываем "By state name" и собираем
        '#states-results a.dropdown-item' без требования видимости.
        """
        # раскрыть выпадашку "By state name"
        toggle_selectors = [
            'button[aria-controls="states-results"]',
            'button:has-text("By state name")',
            '#states-results-toggle',
            '[data-target="#states-results"]',
        ]
        for sel in toggle_selectors:
            try:
                el = await page.wait_for_selector(sel, state="attached", timeout=2000)
                if el:
                    try:
                        await el.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    try:
                        await el.click(timeout=1500)
                    except Exception:
                        # JS-клик как fallback
                        try:
                            await page.evaluate("(s)=>{const e=document.querySelector(s); if(e) e.click();}", sel)
                        except Exception:
                            pass
                    break
            except Exception:
                continue

        # если не раскрылось — принудительно добавить класс 'visible'
        try:
            await page.wait_for_selector(self.STATES_BOX_SELECTOR, timeout=5000)
            await page.evaluate("""
                (sel) => {
                  const box = document.querySelector(sel);
                  if (box && !box.classList.contains('visible')) {
                    box.classList.add('visible');
                  }
                }
            """, self.STATES_BOX_SELECTOR)
        except Exception:
            pass

        # Ждём пока DOM наполнится якорями (без видимости!)
        await page.wait_for_function(
            """() => !!document.querySelectorAll('#states-results a.dropdown-item').length""",
            timeout=10000,
        )

        # Забираем все href+text через evaluate (не зависит от видимости)
        anchors: List[Tuple[str, str]] = await page.evaluate(
            """() => {
                const out = [];
                const list = document.querySelectorAll('#states-results a.dropdown-item');
                for (const a of list) {
                    const href = a.getAttribute('href') || '';
                    const txt = (a.textContent || '').trim();
                    if (href && txt) out.push([txt, href]);
                }
                return out;
            }"""
        )

        # Уникализируем
        seen = set()
        uniq: List[Tuple[str, str]] = []
        for text, href in anchors:
            if href in seen:
                continue
            seen.add(href)
            uniq.append((text, href))
        return uniq

    async def _parse_location_card(self, page: Page, card) -> Dict[str, Any]:
        title = await self._text_or_empty(card, "h3.location-title a")
        loc_url = await self._attr_or_empty(card, "h3.location-title a", "href")
        address = await self._text_or_empty(card, ".address-detail .detail-description")

        phones_text = await self._text_or_empty(card, ".phone-detail .detail-description")
        phones = [p.strip() for p in re.split(r"[\n,]+", phones_text) if p.strip()]

        sale_days = await self._all_texts(card, ".sale-detail .detail-description li")
        office_hours = await self._text_or_empty(card, ".office-detail .detail-description")
        transport_hours = await self._text_or_empty(card, ".transport-detail .detail-description")

        cta_links: List[Dict[str, str]] = []
        try:
            cta_anchors = await card.query_selector_all(".location-cta-buttons a")
            for a in cta_anchors:
                href = await a.get_attribute("href") or ""
                label_el = await a.query_selector(".location-cta-button-label")
                label = self._clean_text(await label_el.inner_text()) if label_el else ""
                if href:
                    cta_links.append({"label": label, "href": href})
        except Exception:
            pass

        logo = await self._attr_or_empty(card, ".facility-image img, .mobile-location-logo", "src")

        return {
            "title": title,
            "location_url": loc_url,
            "logo": logo,
            "address": address,
            "phones": phones,
            "primary_sale_days": sale_days,
            "office_hours": office_hours,
            "transport_hours": transport_hours,
            "cta_links": cta_links,
        }

    async def _scrape_state(self, page: Page, state_name: str, state_url: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            await page.goto(state_url, wait_until="domcontentloaded")
        except Exception:
            return out

        try:
            await page.wait_for_selector(self.LOCATION_CARD_SELECTOR, timeout=self.state_wait_timeout_ms)
        except Exception:
            # Для отладки сохраним скрин и HTML, чтобы понять верстку конкретного штата
            try:
                await page.screenshot(path=f"debug_{state_name.lower().replace(' ', '_')}.png", full_page=True)
                html = await page.content()
                Path(f"debug_{state_name}.html").write_text(html, encoding="utf-8")
            except Exception:
                pass
            return out

        cards = await page.query_selector_all(self.LOCATION_CARD_SELECTOR)
        for card in cards:
            data = await self._parse_location_card(page, card)
            data["state"] = state_name
            out.append(data)

        await asyncio.sleep(random.uniform(0.3, 0.9))
        return out

    # ---------------- Public API ----------------
    async def run(self, save_json: Optional[Path] = None) -> List[Dict[str, Any]]:
        await self.start()
        try:
            page = self._page
            assert page is not None

            await self._go_home_and_open_cars(page)
            state_links = await self._collect_state_links(page)

            results: List[Dict[str, Any]] = []
            for state_name, state_url in state_links:
                chunk = await self._scrape_state(page, state_name, state_url)
                results.extend(chunk)

            if save_json:
                save_json.parent.mkdir(parents=True, exist_ok=True)
                with save_json.open("w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)

            return results
        finally:
            await self.close()


# ---------------- Example run ----------------
if __name__ == "__main__":
    async def _main():
        scraper = ManheimScraper(
            headless=False,                  # headless снят
            slowmo_ms=30,
            navigation_timeout_ms=45000,
            state_wait_timeout_ms=6000,
            proxy=None,
        )
        data = await scraper.run(save_json=Path("manheim_locations.json"))
        print(f"Collected locations: {len(data)}")
        for item in data[:3]:
            print(json.dumps(item, ensure_ascii=False, indent=2))

    asyncio.run(_main())
