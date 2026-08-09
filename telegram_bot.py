# -*- coding: utf-8 -*-

import json

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from telegram.request import HTTPXRequest


TOKEN = "8982395916:AAEDgHC_SJsdsDubscGdROPPJxsvMnQ2Rys"

PRODUCTS_FILE = "data/catalog_merged.json"

PAGE_SIZE = 5

ORDER_USERNAME = "@Oleg_Iron"


user_searches = {}
user_pages = {}


def load_products():
    with open(
        PRODUCTS_FILE,
        encoding="utf-8-sig",
    ) as f:
        products = json.load(f)

    return products


PRODUCTS = load_products()

print(f"Товаров загружено: {len(PRODUCTS)}")


def search_products(query):
    query = query.lower().strip()

    if not query:
        return []

    results = []

    words = [
        word
        for word in query.split()
        if len(word) >= 2
    ]

    for product in PRODUCTS:
        title = str(
            product.get("title", "")
        ).lower()

        author = str(
            product.get("author", "")
        ).lower()

        category = str(
            product.get("category", "")
        ).lower()

        score = 0

        if query == title:
            score += 100

        elif query in title:
            score += 50

        if query in author:
            score += 40

        if query in category:
            score += 20

        for word in words:
            if word in title:
                score += 10

            if word in author:
                score += 8

            if word in category:
                score += 5

        if score > 0:
            results.append(
                (
                    score,
                    product,
                )
            )

    results.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return [
        product
        for score, product in results
    ]


def format_price(price):
    if isinstance(price, list):
        if not price:
            return "не указана"

        return ", ".join(
            str(x)
            for x in price
        )

    return str(price)


def format_results(products, page):
    start = page * PAGE_SIZE

    items = products[
        start:start + PAGE_SIZE
    ]

    total_pages = max(
        1,
        (len(products) - 1) // PAGE_SIZE + 1,
    )

    text = (
        f"🔎 Найдено: {len(products)}\n"
        f"📄 Страница {page + 1}/{total_pages}\n\n"
    )

    for i, product in enumerate(
        items,
        start=start + 1,
    ):
        title = product.get(
            "title",
            "",
        )

        author = product.get(
            "author",
            "",
        )

        price = format_price(
            product.get(
                "price",
                [],
            )
        )

        text += (
            f"{i}. {title}\n"
            f"👤 {author}\n"
            f"💰 {price} грн\n\n"
        )

    return text


def format_product(product):
    title = product.get(
        "title",
        "",
    )

    author = product.get(
        "author",
        "",
    )

    price = format_price(
        product.get(
            "price",
            [],
        )
    )

    category = product.get(
        "category",
        "",
    )

    text = (
        f"📚 {title}\n\n"
        f"👤 {author}\n"
        f"💰 {price} грн\n"
    )

    if category:
        text += (
            f"📂 {category}\n"
        )

    text += (
        "\n"
        "🛒 Заказать:\n"
        f"{ORDER_USERNAME}"
    )

    return text


def page_keyboard(products, page):
    buttons = []

    start = page * PAGE_SIZE

    end = min(
        start + PAGE_SIZE,
        len(products),
    )

    for i in range(
        start,
        end,
    ):
        buttons.append(
            [
                InlineKeyboardButton(
                    f"Подробнее {i + 1}",
                    callback_data=f"product_{i}",
                )
            ]
        )

    nav = []

    max_page = (
        len(products) - 1
    ) // PAGE_SIZE

    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"page_{page - 1}",
            )
        )

    if page < max_page:
        nav.append(
            InlineKeyboardButton(
                "Вперед ➡️",
                callback_data=f"page_{page + 1}",
            )
        )

    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(buttons)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Привет!\n\n"
        "Введите название курса или автора."
    )


async def search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.message.text.strip()

    if not query:
        return

    results = search_products(query)

    if not results:
        await update.message.reply_text(
            "❌ Ничего не найдено.\n\n"
            "Попробуйте изменить запрос."
        )
        return

    user_id = (
        update.message
        .from_user
        .id
    )

    user_searches[user_id] = results

    user_pages[user_id] = 0

    await update.message.reply_text(
        format_results(
            results,
            0,
        ),
        reply_markup=page_keyboard(
            results,
            0,
        ),
    )


async def buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if user_id not in user_searches:
        await query.edit_message_text(
            "Поиск устарел.\n"
            "Введите запрос заново."
        )
        return

    data = query.data

    if data.startswith("page_"):
        page = int(
            data.split("_")[1]
        )

        user_pages[user_id] = page

        products = user_searches[user_id]

        await query.edit_message_text(
            format_results(
                products,
                page,
            ),
            reply_markup=page_keyboard(
                products,
                page,
            ),
        )

    elif data.startswith("product_"):
        index = int(
            data.split("_")[1]
        )

        product = user_searches[
            user_id
        ][index]

        page = user_pages.get(
            user_id,
            0,
        )

        await query.edit_message_text(
            format_product(product),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Назад к результатам",
                            callback_data=f"page_{page}",
                        )
                    ]
                ]
            ),
        )


def main():
    request = HTTPXRequest(
        connect_timeout=60,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=60,
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search,
        )
    )

    app.add_handler(
        CallbackQueryHandler(buttons)
    )

    print("🤖 TelegramBot2 запущен")

    app.run_polling()


if __name__ == "__main__":
    main()