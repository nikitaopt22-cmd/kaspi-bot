import telebot
import os
import zipfile
from pypdf import PdfMerger
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Токен из переменной окружения (на Render добавь BOT_TOKEN в Environment Variables)
TOKEN = os.getenv('BOT_TOKEN') or '8766074232:AAG3HpfydnGtxRxtH8iv1yOIW0V1nj9AGXQ'
bot = telebot.TeleBot(TOKEN)

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

user_choices = {}  # {user_id: формат}

@bot.message_handler(commands=['start'])
def start(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Объединить накладные 📄"))
    bot.send_message(message.chat.id, "Привет! Я бот для объединения накладных Kaspi.\nВыбери формат и пришли ZIP или PDF.", reply_markup=markup)

@bot.message_handler(func=lambda m: "объединить" in m.text.lower() or m.text == "Объединить накладные 📄")
def choose_format(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("A4 (целиком)", callback_data="a4"),
        InlineKeyboardButton("Термопринтер 75×120", callback_data="thermal_75x120"),
        InlineKeyboardButton("Термопринтер 100×150", callback_data="thermal_100x150"),
    )
    bot.send_message(message.chat.id, "Выбери формат печати:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_format(call):
    user_choices[call.from_user.id] = call.data
    bot.answer_callback_query(call.id, f"Выбран: {call.data}")
    bot.send_message(call.message.chat.id, "Теперь пришли ZIP или PDF с накладными!")

@bot.message_handler(content_types=['document'])
def handle_doc(message):
    print(f"[{message.date}] Получен файл от {message.from_user.id}: {message.document.file_name}")

    user_id = message.from_user.id
    format_choice = user_choices.get(user_id, 'thermal_75x120')

    doc = message.document
    file_info = bot.get_file(doc.file_id)
    file_name = doc.file_name or "nakladnye.pdf"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    downloaded = bot.download_file(file_info.file_path)
    with open(file_path, 'wb') as f:
        f.write(downloaded)

    bot.reply_to(message, f"Получил {file_name}. Обрабатываю...")

    pdf_paths = []

    if file_name.lower().endswith('.zip'):
        extract_dir = os.path.join(DOWNLOAD_DIR, "extract")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(file_path, 'r') as z:
            z.extractall(extract_dir)
        for root, _, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith('.pdf'):
                    pdf_paths.append(os.path.join(root, f))
        try:
            os.remove(file_path)
        except:
            pass
        print(f"Распаковано {len(pdf_paths)} PDF")

    elif file_name.lower().endswith('.pdf'):
        pdf_paths.append(file_path)

    if not pdf_paths:
        bot.reply_to(message, "PDF-файлы не найдены 😔")
        return

    output_pdf = os.path.join(DOWNLOAD_DIR, f"ready_{message.message_id}.pdf")

    try:
        merger = PdfMerger()
        for pdf in pdf_paths:
            merger.append(pdf)
        merger.write(output_pdf)
        merger.close()

        print(f"Готов PDF: {len(pdf_paths)} страниц, формат {format_choice}")

        with open(output_pdf, 'rb') as f:
            bot.send_document(
                message.chat.id,
                f,
                caption=f"Готово! {format_choice} | {len(pdf_paths)} накладных\nМожешь печатать 🔥"
            )

    except Exception as e:
        print(f"Ошибка создания PDF: {e}")
        bot.reply_to(message, f"Ошибка: {str(e)}")

    finally:
        # Уборка временных файлов
        for p in pdf_paths:
            try:
                os.remove(p)
            except:
                pass
        try:
            os.remove(output_pdf)
        except:
            pass

print("Бот запущен...")
print("Ожидание сообщений...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
