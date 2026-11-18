"""End-to-end tests in a real browser (Playwright) against a running service.

    BASE_URL=http://localhost:8010 ADMIN_PASSWORD=... python -m pytest e2e -q

Run separately from unit tests: they need the service, a browser and a seeded catalog.
"""
import os
import re

import pytest
from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8010").rstrip("/")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "pelargonium2026")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(locale="ru-RU", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    yield page
    context.close()


def test_buyer_orders_with_courier_and_sees_order_number(page):
    page.goto(f"{BASE_URL}/demo")
    cards = page.locator(".psw-card")
    expect(cards).to_have_count(15)

    # filter: only rosebud varieties
    page.locator("select[data-r=type]").select_option("rosebud")
    expect(cards).to_have_count(2)
    page.locator("select[data-r=type]").select_option("")

    # add a variety from its card and open the cart
    card = cards.filter(has_text="Rocky Mountain White")
    card.locator("[data-act=add]").click()
    expect(page.locator("[data-r=count]")).to_have_text("1")
    page.locator("[data-r=cartBtn]").click()
    page.locator("[data-act=checkout]").click()

    form = page.locator(".psw-drawer form")
    form.locator("button.psw-btn").click()  # empty form must be rejected
    expect(form.locator("[data-f=name] .psw-err")).not_to_be_empty()

    form.locator("input[name=name]").fill("E2E Покупатель")
    phone = form.locator("input[name=phone]")
    phone.click()
    phone.press_sequentially("87011234567")
    expect(phone).to_have_value("+7 701 123 45 67")  # phone mask while typing

    form.locator("input[value=courier]").check()
    page.locator(".psw-drawer input[name=address]").fill("ул. Тестовая 1")
    page.locator(".psw-drawer form button.psw-btn").click()
    expect(page.locator(".psw-num")).to_have_text(re.compile(r"^PS-\d+$"))


def test_language_switch_to_kazakh(page):
    page.goto(f"{BASE_URL}/demo")
    page.locator(".psw-langs [data-l=kk]").click()
    expect(page.locator("[data-r=cartLbl]")).to_have_text("Себет")


def test_owner_sees_order_and_changes_status(page):
    page.goto(f"{BASE_URL}/admin")
    page.locator("#pw").fill("wrong-password")
    page.locator("#login button").click()
    expect(page.locator("#pwErr")).not_to_be_empty()

    page.locator("#pw").fill(ADMIN_PASSWORD)
    page.locator("#login button").click()
    row = page.locator("#ordersBody tr", has_text="E2E Покупатель").first
    expect(row).to_be_visible()
    row.locator("select").select_option("cancelled")  # also returns the plant to stock
    expect(row.locator(".st")).to_have_class(re.compile("st-cancelled"))
