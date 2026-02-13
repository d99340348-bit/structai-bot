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
import sqlite3
from openai import OpenAI

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

EXCEL_FILE = "suggestions.xlsx"
DB_FILE = "structai_ai.db"

# ============================================================
# ========================== AI ===============================
# ============================================================

ai_client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def init_ai_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT
        )
    """)

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


# ============================================================
# ===================== ПОИСК ПО БАЗЕ ========================
# ============================================================

def search_similar_question(question):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT question, answer FROM history
        WHERE question LIKE ?
        ORDER BY id DESC
        LIMIT 1
    """, (f"%{question[:20]}%",))

    row = c.fetchone()
    conn.close()

    if row:
        return row[1]

    return None


# ============================================================
# ===================== РОЛИ ПОЛЬЗОВАТЕЛЯ ====================
# ============================================================

def save_user_role(user_id, role):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)", (user_id, role))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "engineer"

def build_system_prompt(role):

    base = """
Ты инженерный ассистент по Еврокодам EN 1990–1999,
СП РК EN и национальным приложениям.

Запрещено:
- темы вне проектирования
- выдуманные нормы

Если вопрос вне нормативов:
ответь: "Вопрос вне области нормативного проектирования."
"""

    if role == "student":
        return base + "\nОбъясняй просто и пошагово."
    elif role == "oldschool":
        return base + "\nОтвечай технически и указывай отличия от старых СП."
    return base + "\nОтвечай профессионально и технически."


# ============================================================
# ======================= ОСНОВНОЙ AI ========================
# ============================================================

async def ask_ai(user_id, question):

    # 1️⃣ Сначала ищем в базе
    cached_answer = search_similar_question(question)
    if cached_answer:
        return "📚 Найден ответ в базе:\n\n" + cached_answer

    # 2️⃣ Если нет — обращаемся к AI
    role = get_user_role(user_id)
    system_prompt = build_system_prompt(role)

    response = ai_client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.2,
        max_tokens=900
    )

    answer = response.choices[0].message.content

    # 3️⃣ Сохраняем в базу
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO history (user_id, question, answer, date) VALUES (?, ?, ?, ?)",
        (user_id, question, answer, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return answer


# ============================================================
# ===================== СОХРАНЕНИЕ В EXCEL ===================
# ============================================================

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


# ============================================================
# ======================== ГЛАВНОЕ МЕНЮ ======================
# ============================================================

async def show_start(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    keyboard = [
        [InlineKeyboardButton("🎓 Студент", callback_data="user_student")],
        [InlineKeyboardButton("🏗 Практикующий инженер", callback_data="user_engineer")],
        [InlineKeyboardButton("📐 Инженер старой школы", callback_data="user_oldschool")],
        [InlineKeyboardButton("💬 Предложения", callback_data="suggestions")]
    ]

    text = "Добро пожаловать в StructAI.\n\nПожалуйста, ответьте, кто Вы?"

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


# ============================================================
# =========================== CALLBACK =======================
# ============================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "user_student":
        save_user_role(query.from_user.id, "student")
    elif data == "user_engineer":
        save_user_role(query.from_user.id, "engineer")
    elif data == "user_oldschool":
        save_user_role(query.from_user.id, "oldschool")

    if data == "suggestions":
        context.user_data["suggest_mode"] = True
        await query.edit_message_text("Напишите ваше предложение:")
        return

    if data.startswith("user_"):
        keyboard = [
            [InlineKeyboardButton("🤖 Задать вопрос", callback_data="mode_question")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_start")]
        ]
        await query.edit_message_text(
            "Что Вы хотите?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "mode_question":
        context.user_data["ai_mode"] = True
        await query.edit_message_text("Напишите ваш вопрос по Еврокодам:")

    elif data == "back_start":
        await show_start(update, context, edit=True)


# ============================================================
# ======================= ОБРАБОТКА ТЕКСТА ===================
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("suggest_mode"):
        save_to_excel(update.message.from_user, update.message.text)
        context.user_data["suggest_mode"] = False
        await update.message.reply_text("Спасибо! Предложение сохранено ✅")
        return

    if context.user_data.get("ai_mode"):
        await update.message.reply_text("Анализ нормативной базы...")
        answer = await ask_ai(update.message.from_user.id, update.message.text)
        await update.message.reply_text(answer)
        return


# ============================================================
# ============================ MAIN ==========================
# ============================================================

def main():
    init_ai_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("StructAI запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
