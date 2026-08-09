# -*- coding: utf-8 -*-

import json
import os
import re
import requests


NOTION_TOKEN = os.getenv("NOTION_TOKEN")

NOTION_PAGE_ID = "139632d020a38087abf3c31958472131"

OUTPUT_FILE = "data/notion_catalog.json"

NOTION_VERSION = "2022-06-28"


HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def get_children(block_id):
    """Получить все дочерние блоки Notion."""

    results = []
    cursor = None

    while True:

        params = {}

        if cursor:
            params["start_cursor"] = cursor

        response = requests.get(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            headers=HEADERS,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        results.extend(
            data.get("results", [])
        )

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")

    return results


def get_rich_text(block):
    """Получить обычный текст блока."""

    block_type = block.get("type")

    if not block_type:
        return ""

    data = block.get(
        block_type,
        {}
    )

    rich_text = data.get(
        "rich_text",
        []
    )

    return "".join(
        item.get("plain_text", "")
        for item in rich_text
    ).strip()


def extract_price(text):
    """
    Извлекает цены:
    100 грн
    150 грн.
    150 / 300 грн
    """

    matches = re.findall(
        r"(\d+(?:[.,]\d+)?)\s*(?:грн|гривн)",
        text,
        flags=re.IGNORECASE
    )

    prices = []

    for value in matches:

        value = value.replace(
            ",",
            "."
        )

        try:

            number = float(value)

            if number.is_integer():
                number = int(number)

            prices.append(number)

        except ValueError:
            pass

    return prices


def clean_title(text):
    """Очистка названия товара."""

    text = text.strip()

    text = re.sub(
        r"^[►•▪️🔹🔸]+\s*",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def remove_price_from_title(text):
    """Убирает цену из названия."""

    text = re.sub(
        r"\s*\d+(?:[.,]\d+)?\s*(?:грн|гривн)\.?",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


def is_valid_product(text):
    """Отсекает очевидный мусор."""

    if not text:
        return False

    text = text.strip()

    if len(text) < 2:
        return False

    bad = [
        "описание",
        "содержание",
        "ссылка",
        "замовити",
        "заказать",
        "купить",
        "telegram",
        "телеграм"
    ]

    lower = text.lower()

    if any(
        word in lower
        for word in bad
    ):
        return False

    return True


def make_product(author, text):
    """
    Создаёт товар из строки.
    """

    text = clean_title(text)

    if not is_valid_product(text):
        return None

    prices = extract_price(text)

    title = remove_price_from_title(
        text
    )

    if not title:
        return None

    return {
        "author": author,
        "title": title,
        "price": prices,
        "source": "notion"
    }


def scan_blocks(
    blocks,
    author,
    products,
    level=0
):
    """
    Рекурсивно обходит структуру Notion.

    ВАЖНО:

    toggle = товар

    Его children = описание,
    поэтому внутрь toggle
    НЕ заходим.

    paragraph = потенциальный товар

    bulleted_list_item = потенциальный товар

    numbered_list_item = потенциальный товар

    child_page = раздел,
    не товар автоматически.
    """

    for block in blocks:

        block_type = block.get(
            "type"
        )

        text = get_rich_text(
            block
        )

        # -------------------------
        # TOGGLE
        # -------------------------

        if block_type == "toggle":

            if text:

                product = make_product(
                    author,
                    text
                )

                if product:
                    products.append(
                        product
                    )

            # ВАЖНО:
            # содержимое toggle
            # является описанием.
            #
            # Не добавляем его
            # как отдельные товары.

            continue

        # -------------------------
        # PARAGRAPH
        # -------------------------

        if block_type == "paragraph":

            if text:

                product = make_product(
                    author,
                    text
                )

                if product:
                    products.append(
                        product
                    )

        # -------------------------
        # BULLETED LIST
        # -------------------------

        elif block_type == "bulleted_list_item":

            if text:

                product = make_product(
                    author,
                    text
                )

                if product:
                    products.append(
                        product
                    )

        # -------------------------
        # NUMBERED LIST
        # -------------------------

        elif block_type == "numbered_list_item":

            if text:

                product = make_product(
                    author,
                    text
                )

                if product:
                    products.append(
                        product
                    )

        # -------------------------
        # ДРУГИЕ БЛОКИ
        # -------------------------

        else:

            # Если блок не toggle,
            # но имеет детей,
            # рекурсивно идём внутрь.

            if block.get(
                "has_children",
                False
            ):

                children = get_children(
                    block["id"]
                )

                scan_blocks(
                    children,
                    author,
                    products,
                    level + 1
                )


def main():

    if not NOTION_TOKEN:

        print(
            "ОШИБКА: NOTION_TOKEN не найден."
        )

        return

    print()
    print("=" * 60)
    print("СИНХРОНИЗАЦИЯ NOTION")
    print("=" * 60)
    print()

    print(
        "Получаем страницы авторов..."
    )

    try:

        root_blocks = get_children(
            NOTION_PAGE_ID
        )

    except Exception as e:

        print(
            "Ошибка подключения к Notion:"
        )

        print(e)

        return

    author_pages = []

    for block in root_blocks:

        if block.get(
            "type"
        ) != "child_page":

            continue

        page_id = block.get(
            "id"
        )

        author = block.get(
            "child_page",
            {}
        ).get(
            "title",
            ""
        ).strip()

        if not page_id or not author:
            continue

        # "трекер выполнения"
        # не является автором

        if author.lower() == "трекер выполнения":
            continue

        author_pages.append(
            {
                "id": page_id,
                "author": author
            }
        )

    print(
        "Страниц авторов:",
        len(author_pages)
    )

    print()

    all_products = []

    for number, page in enumerate(
        author_pages,
        start=1
    ):

        author = page["author"]

        print(
            f"[{number}/{len(author_pages)}] {author}"
        )

        try:

            blocks = get_children(
                page["id"]
            )

            before = len(
                all_products
            )

            scan_blocks(
                blocks,
                author,
                all_products
            )

            found = (
                len(all_products)
                - before
            )

            print(
                "   найдено товаров:",
                found
            )

        except Exception as e:

            print(
                "   ОШИБКА:",
                e
            )

    # -------------------------
    # УДАЛЕНИЕ ДУБЛЕЙ
    # -------------------------

    unique = []
    seen = set()

    for product in all_products:

        key = (
            product["author"]
            .strip()
            .lower(),

            product["title"]
            .strip()
            .lower()
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            product
        )

    all_products = unique

    # -------------------------
    # СОХРАНЕНИЕ
    # -------------------------

    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            all_products,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)
    print("СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)

    print(
        "Всего товаров:",
        len(all_products)
    )

    print(
        "Файл:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()