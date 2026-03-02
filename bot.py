import telebot
import os
import zipfile
from pypdf import PdfReader
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import img2pdf
import tempfile
import pdf2image  # pip install pdf2image

TOKEN = '8766074232:AAG3HpfydnGtxRxtH8iv1yOIW0V1nj9AGXQ'
bot = telebot.TeleBot(TOKEN)

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

user_choices = {}  # {user_id: 'a4_4', 'a4_9', 'thermal_75x120', 'thermal_100x150'}

@bot.message_handler(commands=['start'])
def start(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Объединить накладные 📄"))
    bot.send_message(message.chat.id, "Привет! Выбери формат и пришли ZIP/PDF", reply_markup=markup)

@bot.message_handler(func=lambda m: "объединить" in m.text.lower() or m.text == "Объединить накладные 📄")
def choose_format(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("A4 — 4 накладные", callback_data="a4_4"),
        InlineKeyboardButton("A4 — 9 накладных", callback_data="a4_9"),
    )
    markup.row(
        InlineKeyboardButton("Термопринтер 75×120 (1 шт)", callback_data="thermal_75x120"),
        InlineKeyboardButton("Термопринтер 100×150 (1 шт)", callback_data="thermal_100x150"),
    )
    bot.send_message(message.chat.id, "Выбери формат печати:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_format(call):
    user_choices[call.from_user.id] = call.data
    bot.answer_callback_query(call.id, f"Выбран формат: {call.data}")
    bot.send_message(call.message.chat.id, "Теперь пришли ZIP или PDF с накладными!")

@bot.message_handler(content_types=['document'])
def handle_doc(message):
    # Отладка: получен документ
    print(f"Получен документ от пользователя {message.from_user.id}: {message.document.file_name}")

    user_id = message.from_user.id
    format_choice = user_choices.get(user_id, 'thermal_75x120')  # По умолчанию 75x120

    doc = message.document
    file_info = bot.get_file(doc.file_id)
    file_name = doc.file_name or "file.pdf"
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
        os.remove(file_path)

        # Отладка: сколько PDF после распаковки
        print(f"Распаковано {len(pdf_paths)} PDF-файлов")

    elif file_name.lower().endswith('.pdf'):
        pdf_paths.append(file_path)

    if not pdf_paths:
        bot.reply_to(message, "PDF не найдены 😔")
        return

    # Конвертируем все PDF в изображения
    images = []
    for pdf in pdf_paths:
        # Если Poppler не в PATH — укажи путь здесь:
        # pages = pdf2image.convert_from_path(pdf, dpi=300, poppler_path=r'C:\poppler\Library\bin')
        pages = pdf2image.convert_from_path(
    pdf,
    dpi=300,
    poppler_path=r'C:\poppler\Library\bin'  # ← укажи точный путь к bin
)

        for page in pages:
            temp_img = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            page.save(temp_img.name, 'JPEG')
            images.append(temp_img.name)

    output_pdf = os.path.join(DOWNLOAD_DIR, f"ready_{message.message_id}.pdf")

    if 'thermal' in format_choice:
        if '75x120' in format_choice:
            width_mm, height_mm = 75, 120
        else:
            width_mm, height_mm = 100, 150

        size_pt = (img2pdf.mm_to_pt(width_mm), img2pdf.mm_to_pt(height_mm))
        layout_fun = img2pdf.get_layout_fun(size_pt)

        with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert(images, layout_fun=layout_fun))

    elif 'a4' in format_choice:
        a4_pt = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
        layout_fun = img2pdf.get_layout_fun(a4_pt)

        with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert(images, layout_fun=layout_fun))

    # Отладка: готов PDF
    print(f"Готов PDF с {len(images)} страницами, формат {format_choice}")

    # Отправляем
    with open(output_pdf, 'rb') as f:
        bot.send_document(
            message.chat.id,
            f,
            caption=f"Готово! Формат: {format_choice} | {len(images)} накладных"
        )

    # Уборка временных файлов
    for img in images:
        try:
            os.remove(img)
        except:
            pass
    for p in pdf_paths:
        try:
            os.remove(p)
        except:
            pass
    try:
        os.remove(output_pdf)
    except:
        pass

# Запуск бота
bot.infinity_polling(timeout=30)

# Отладка: бот ожидает
print("Бот в режиме ожидания сообщений...")