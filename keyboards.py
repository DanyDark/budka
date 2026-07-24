import os
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import is_party_leader

ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_main_keyboard(user_id):
    kb = [
        [KeyboardButton("👤 Мой профиль")],
        [KeyboardButton("📝 Мои ответы"), KeyboardButton("❓ Помощь")]
    ]
    if is_admin(user_id):
        kb.append([KeyboardButton("📊 Админ-панель")])
    if is_party_leader(user_id):
        kb.append([KeyboardButton("👑 Лидер пати")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
def get_party_leader_keyboard():
    kb = [
        [KeyboardButton("➕ Добавить в состав")],
        [KeyboardButton("➖ Удалить из состава")],
        [KeyboardButton("🗳 Проголосовать за пати")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
def get_clan_management_keyboard():
    kb = [
        [KeyboardButton("👥 Список пользователей")],
        [KeyboardButton("🔹 Добавить в подсады"), KeyboardButton("🔸 Убрать из подсадов")],
        [KeyboardButton("🗑 Удалить пользователя")],
        [KeyboardButton("👑 Назначить лидера пати"), KeyboardButton("❌ Снять лидера пати")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
def get_admin_keyboard():
    kb = [
        [KeyboardButton("📊 Управление опросами")],
        [KeyboardButton("📝 Регистрация")],
        [KeyboardButton("🏰 Управление кланом")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_polls_management_keyboard():
    kb = [[KeyboardButton("📝 Создать опрос (ГВГ)"), KeyboardButton("👥 Пройти за другого")],
          [KeyboardButton("📤 Разослать опрос"), KeyboardButton("📈 Результаты опроса")],
          [KeyboardButton("❌ Не ответившие"), KeyboardButton("🔙 Назад")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_registration_management_keyboard():
    kb = [[KeyboardButton("📋 Список ожидания")],
          [KeyboardButton("✅ Подтвердить всех")],
          [KeyboardButton("❌ Отказать")],
          [KeyboardButton("🔙 Назад")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_class_keyboard():
    classes = ["ВАР", "МАГ", "ТАНК", "ДРУ", "ПРИСТ", "ЛУК", "СИН", "ШАМ", "СИК", "МИСТИК"]
    kb = [[KeyboardButton(cls) for cls in classes[i:i+3]] for i in range(0, len(classes), 3)]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)

def get_reject_keyboard(pending_users):
    if not pending_users:
        return None
    kb = []
    row = []
    for _, nick, *_ in pending_users:
        row.append(KeyboardButton(f"❌ {nick}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_poll_question_inline(poll_id, meeting, index):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Да", callback_data=f"poll_{poll_id}_{meeting}_да_{index}"),
        InlineKeyboardButton("❌ Нет", callback_data=f"poll_{poll_id}_{meeting}_нет_{index}"),
        InlineKeyboardButton("❓ Не знаю", callback_data=f"poll_{poll_id}_{meeting}_не знаю_{index}")
    ]])

def get_confirm_restart_inline(poll_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, всё верно", callback_data=f"confirm_{poll_id}")],
        [InlineKeyboardButton("❌ Нет, пройти заново", callback_data=f"restart_{poll_id}")]
    ])
