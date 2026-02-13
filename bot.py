import os
import sqlite3
from datetime import datetime
from openpyxl import Workbook, load_workbook
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from openai import OpenAI

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from structure import MENU_STRUCTURE
from content import CONTENT

# ================== НАСТРОЙКИ ==================

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

EXCEL_FILE = "suggestions.xlsx"
DB_FILE = "structai_ai.db"
PDF_FOLDER = "pdf_db"

# ================== AI CLIENT ==================

ai_client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ================== ИНИЦИАЛИЗАЦИЯ БД ==================

def init_ai_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()

# ================== PDF БАЗА ==================

def search_in_pdfs(question):

    if PyPDF2 is None:
        return None

    if not os.path.exists(PDF_FOLDER):
        return None

    question = question.lower()

    for file in os.listdir(PDF_FOLDER):
        if file.endswith(".pdf"):
            path = os.path.join(PDF_FOLDER, file)

            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)

                for page in reader.pages:
                    text = page.extract_text()
                    if text and question[:30] in text.lower():
                        return f"📚 Найдено в {file}:\n\n" + text[:1500]

    return None

# ================== AI ==================

async def ask_ai(user_id, question):

    pdf_answer = search_in_pdfs(question)
    if pdf_answer:
        return pdf_answer

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT answer FROM history WHERE question LIKE ? LIMIT 1",
        (f"%{question[:20]}%",)
    )
    row = c.fetchone()
    conn.close()

    if row:
        return "📚 Найдено в базе:\n\n" + row[0]

    response = ai_client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[
            {
                "role": "system",
                "content": """Ты инженерный ассистент по Еврокодам EN 1990–1999.
Используй нормативную базу.
Не выдумывай пункты норм.
Если вопрос вне проектирования — сообщи об этом."""
            },
            {"role": "user", "content": question}
        ],
        temperature=0.2,
        max_tokens=900
    )

    answer = response.choices[0].message.content

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO history (user_id, question, answer, date) VALUES (?, ?, ?, ?)",
        (user_id, question, answer, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return answer

# ================== EXCEL ==================

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

# ================== ГЛАВНОЕ МЕНЮ ==================

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

# ================== CALLBACK ==================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "suggestions":
        context.user_data["suggest_mode"] = True
        await query.edit_message_text("Напишите ваше предложение:")
        return

    if data.startswith("user_"):

        context.user_data["role"] = data

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
        return

    if data == "mode_study":

        keyboard = [
            [InlineKeyboardButton("EN 1990 – Основы", callback_data="study_1990")],
            [InlineKeyboardButton("EN 1991 – Нагрузки", callback_data="study_1991")],
            [InlineKeyboardButton("⬅ Назад", callback_data="back_role")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]

        await query.edit_message_text(
            "Выберите норматив для изучения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "mode_question":
        context.user_data["ai_mode"] = True
        await query.edit_message_text(
            "Напишите ваш вопрос по Еврокодам:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Назад", callback_data="back_role")],
                [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
            ])
        )
        return

    if data == "back_role":
        keyboard = [
            [InlineKeyboardButton("📘 Изучать нормы поэтапно", callback_data="mode_study")],
            [InlineKeyboardButton("🤖 Задать вопрос по Еврокодам", callback_data="mode_question")],
            [InlineKeyboardButton("⬅ Назад", callback_data="back_start")]
        ]

        await query.edit_message_text(
            "Что Вы хотите?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "back_start":
        context.user_data.clear()
        await show_start(update, context, edit=True)
        return

# ================== ОБРАБОТКА ТЕКСТА ==================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("suggest_mode"):
        save_to_excel(update.message.from_user, update.message.text)
        context.user_data["suggest_mode"] = False
        await update.message.reply_text("Спасибо! Предложение сохранено ✅")
        return

    if context.user_data.get("ai_mode"):

        msg = await update.message.reply_text("Анализ нормативной базы...")

        answer = await ask_ai(
            update.message.from_user.id,
            update.message.text
        )

        await msg.edit_text(answer)
        return

# ================== MAIN ==================

def main():
    init_ai_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("StructAI PRO запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
