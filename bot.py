from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from structure import MENU_STRUCTURE
from content import CONTENT

from openpyxl import Workbook, load_workbook
from datetime import datetime
import os

import os
TOKEN = os.getenv("BOT_TOKEN")

EXCEL_FILE = "suggestions.xlsx"


# -------------------- СОХРАНЕНИЕ В EXCEL --------------------

def save_to_excel(user, text):
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.title = "Предложения"
        ws.append(["Дата", "Username", "User ID", "Текст"])
        wb.save(EXCEL_FILE)

    wb = load_workbook(EXCEL_FILE)
    ws = wb.active

    ws.append([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user.username,
        user.id,
        text
    ])

    wb.save(EXCEL_FILE)


# -------------------- ГЛАВНОЕ МЕНЮ --------------------

async def show_start(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    keyboard = [
        [InlineKeyboardButton("🎓 Студент", callback_data="user_student")],
        [InlineKeyboardButton("🏗 Практикующий инженер", callback_data="user_engineer")],
        [InlineKeyboardButton("📐 Инженер старой школы", callback_data="user_oldschool")],
        [InlineKeyboardButton("💬 Предложения", callback_data="suggestions")]
    ]

    text = (
        "Добро пожаловать в StructAI.\n"
        "Это учебный и справочный бот по Еврокодам (СП РК EN).\n\n"
        "Здесь вы можете быстро найти разделы нормативов, формулы, "
        "комбинации нагрузок и основные положения расчёта.\n\n"
        "В дальнейшем планируется внедрение интеллектуального помощника, "
        "который поможет ориентироваться в Еврокодах, находить нужные пункты, "
        "разъяснять требования и подсказывать по вопросам расчёта и проектирования.\n\n"
        "Цель бота — упростить изучение Еврокодов и сделать работу с ними "
        "более удобной и понятной.\n\n"
        "Пожалуйста, ответьте, кто Вы?"
    )

    if edit:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_start(update, context)


# -------------------- CALLBACK --------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ---------------- ПРЕДЛОЖЕНИЯ ----------------

    if data == "suggestions":
        context.user_data["suggest_mode"] = True
        keyboard = [
            [InlineKeyboardButton("⬅ Назад", callback_data="back_start")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(
            "Напишите ваше предложение по улучшению StructAI:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------------- РОЛЬ ----------------

    if data.startswith("user_"):
        keyboard = [
            [InlineKeyboardButton("📘 Изучать нормы поэтапно", callback_data="mode_study")],
            [InlineKeyboardButton("🤖 Задать вопрос по Еврокодам", callback_data="mode_question")],
            [InlineKeyboardButton("⬅ Назад", callback_data="back_start")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(
            "Что Вы хотите?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------- УЧЕБНЫЙ МОДУЛЬ ----------------

    elif data == "mode_study":
        keyboard = [
            [InlineKeyboardButton("🧩 Структура Еврокодов", callback_data="eu_structure")],
            [InlineKeyboardButton("📚 Выбрать Еврокод", callback_data="choose_eurocode")],
            [InlineKeyboardButton("⬅ Назад", callback_data="user_student")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(
            "Учебный модуль",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "eu_structure":
        text = CONTENT.get("EU_STRUCTURE", "Текст пока не добавлен.")
        keyboard = [
            [InlineKeyboardButton("⬅ Назад", callback_data="mode_study")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "mode_question":
        keyboard = [
            [InlineKeyboardButton("⬅ Назад", callback_data="user_student")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(
            "Здесь будет режим ИИ.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------- ВЫБОР ЕВРОКОДА ----------------

    elif data == "choose_eurocode":
        keyboard = [
            [InlineKeyboardButton("EN 1990 — Основы проектирования", callback_data="en1990_main")],
            [InlineKeyboardButton("⬅ Назад", callback_data="mode_study")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text("Выбери Еврокод", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------------- EN1990 ----------------

    elif data == "en1990_main":
        keyboard = [
            [InlineKeyboardButton("❓ Что такое EN 1990", callback_data="content_EN1990_about|en1990_main")],
            [InlineKeyboardButton("🎯 Зачем он нужен", callback_data="content_EN1990_purpose|en1990_main")],
            [InlineKeyboardButton("📑 Структура EN 1990", callback_data="content_EN1990_structure|en1990_main")],
            [InlineKeyboardButton("▶ Начать изучение", callback_data="en1990_sections")],
            [InlineKeyboardButton("⬅ Назад", callback_data="choose_eurocode")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(
            "EN 1990 — Основы проектирования",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------- РАЗДЕЛЫ ----------------

    elif data == "en1990_sections":
        sections = MENU_STRUCTURE["EN1990"]["sections"]
        keyboard = []

        for sec_id, sec in sections.items():
            keyboard.append([
                InlineKeyboardButton(sec["title"], callback_data=f"section_{sec_id}")
            ])

        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="en1990_main")])
        keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")])

        await query.edit_message_text(
            "Разделы EN 1990",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------- ПОДРАЗДЕЛЫ ----------------

    elif data.startswith("section_"):
        sec_id = data.replace("section_", "")
        section = MENU_STRUCTURE["EN1990"]["sections"].get(sec_id)

        keyboard = []

        for sub_key, sub_title in section["subsections"].items():
            keyboard.append([
                InlineKeyboardButton(
                    sub_title,
                    callback_data=f"content_{sub_key}|section_{sec_id}"
                )
            ])

        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="en1990_sections")])
        keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")])

        await query.edit_message_text(
            section["title"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------- КОНТЕНТ ----------------

    elif data.startswith("content_"):
        payload = data.replace("content_", "")
        key, back_callback = payload.split("|")

        text = CONTENT.get(key, "Текст пока не добавлен.")

        keyboard = [
            [InlineKeyboardButton("⬅ Назад", callback_data=back_callback)],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------------- ГЛАВНОЕ МЕНЮ ----------------

    elif data == "back_start":
        context.user_data.clear()
        await show_start(update, context, edit=True)


# -------------------- ОБРАБОТКА ТЕКСТА --------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("suggest_mode"):
        save_to_excel(update.message.from_user, update.message.text)
        context.user_data["suggest_mode"] = False
        await update.message.reply_text("Спасибо! Предложение будет учтено ✅")


# -------------------- MAIN --------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("StructAI запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
