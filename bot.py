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

# ============================================================
# ====================== НАСТРОЙКИ ===========================
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

EXCEL_FILE = "suggestions.xlsx"
DB_FILE = "structai_ai.db"

ai_client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ============================================================
# =================== СОХРАНЕНИЕ В EXCEL =====================
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
# ======================= AI БАЗА ============================
# ============================================================

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT
        )
    """)

    conn.commit()
    conn.close()

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

def search_documents(query):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT content FROM documents WHERE content LIKE ?", (f"%{query}%",))
    results = c.fetchall()
    conn.close()
    return "\n\n".join([r[0][:2000] for r in results[:3]])

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

async def ask_ai(user_id, question):
    role = get_user_role(user_id)
    system_prompt = build_system_prompt(role)
    docs_context = search_documents(question)

    response = ai_client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Контекст:\n{docs_context}\n\nВопрос:\n{question}"}
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

# ============================================================
# ====================== ИНТЕРФЕЙС ===========================
# ============================================================

async def show_start(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    keyboard = [
        [InlineKeyboardButton("🎓 Студент", callback_data="user_student")],
        [InlineKeyboardButton("🏗 Практикующий инженер", callback_data="user_engineer")],
        [InlineKeyboardButton("📐 Инженер старой школы", callback_data="user_oldschool")],
        [InlineKeyboardButton("💬 Предложения", callback_data="suggestions")]
    ]

    text = "Добро пожаловать в StructAI.\nКто Вы?"

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
# ======================= CALLBACK ============================
# ============================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Роль
    if data == "user_student":
        save_user_role(query.from_user.id, "student")
    elif data == "user_engineer":
        save_user_role(query.from_user.id, "engineer")
    elif data == "user_oldschool":
        save_user_role(query.from_user.id, "oldschool")

    # Предложения
    if data == "suggestions":
        context.user_data["suggest_mode"] = True
        await query.edit_message_text("Напишите ваше предложение:")
        return

    # AI режим
    elif data == "mode_question":
        context.user_data["ai_mode"] = True
        await query.edit_message_text("Напишите ваш вопрос по Еврокодам:")
        return

    # Назад в меню
    elif data == "back_start":
        context.user_data.clear()
        await show_start(update, context, edit=True)
        return

# ============================================================
# ===================== ОБРАБОТКА ТЕКСТА =====================
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("suggest_mode"):
        save_to_excel(update.message.from_user, update.message.text)
        context.user_data["suggest_mode"] = False
        await update.message.reply_text("Спасибо! ✅")
        return

    if context.user_data.get("ai_mode"):
        await update.message.reply_text("Анализ нормативной базы...")
        answer = await ask_ai(update.message.from_user.id, update.message.text)
        await update.message.reply_text(answer)
        return

# ============================================================
# ========================== MAIN ============================
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
