import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import init_db, is_registered, is_pending, get_all_users, get_user_nick, get_user_class
from keyboards import (
    get_main_keyboard, get_admin_keyboard, get_polls_management_keyboard,
    get_registration_management_keyboard, get_clan_management_keyboard
)
from registration import (
    start, handle_registration_text, registration_menu, list_pending,
    confirm_all_pending_cmd, reject_pending_menu, handle_reject_pending
)
from polls import (
    start_gvg_poll, handle_gvg_text, gvg_callback,
    admin_poll_for_other, handle_external_answer,
    send_poll_to_all, poll_callback, confirm_callback, restart_callback,
    export_command, non_responders_cmd, my_answers
)
from database import (
    init_db, is_registered, is_pending, get_user_nick, get_user_class,
    get_all_users, is_party_leader, set_party_leader, remove_party_leader,
    get_party_members, add_party_member, remove_party_member,
    get_user_id_by_nick, set_substitute, is_substitute
)
from keyboards import (
    get_main_keyboard, get_admin_keyboard, get_polls_management_keyboard,
    get_registration_management_keyboard, get_clan_management_keyboard,
    get_party_leader_keyboard
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def main_menu(update, context):
    uid = update.effective_user.id
    if not is_registered(uid):
        await update.message.reply_text("Сначала /start")
        return
    await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(uid, is_admin(uid)))

from database import get_all_users

async def show_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("Нет зарегистрированных пользователей.")
        return
    text = "📋 *Список пользователей:*\n\n"
    for user_id, nick, user_class in users:
        safe_nick = nick.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
        safe_class = (user_class or "Не указан").replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
        text += f"• {safe_nick} — {safe_class}\n"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆘 Показать ID всех пользователей", callback_data="show_all_ids")]
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    
async def show_all_ids_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = get_all_users()
    if not users:
        await query.edit_message_text("Нет зарегистрированных пользователей.")
        return
    text = "🆔 *Список пользователей с ID:*\n\n"
    for user_id, nick, user_class in users:
        safe_nick = nick.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
        safe_class = (user_class or "Не указан").replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
        text += f"• {safe_nick} — {safe_class} — `{user_id}`\n"
    await query.edit_message_text(text, parse_mode="Markdown")
async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # Отмена
    if text == "❌ Отмена":
        for k in ['awaiting_nick', 'awaiting_class', 'reject_mode', 'gvg', 'ext_step',
                  'party_add_mode', 'in_party_menu', 'in_clan_menu', 'awaiting_leader_id']:
            context.user_data.pop(k, None)
        await update.message.reply_text("Отменено.", reply_markup=get_main_keyboard(uid))
        return

    # Регистрация
    if not is_registered(uid) and not is_pending(uid):
        if 'awaiting_nick' in context.user_data or 'awaiting_class' in context.user_data:
            await handle_registration_text(update, context)
            return
        await update.message.reply_text("Нажмите /start для регистрации.")
        return

    if is_pending(uid):
        await update.message.reply_text("Заявка ожидает подтверждения.")
        return

    # Ввод ID для назначения лидера пати (вызывается из меню управления кланом)
    if context.user_data.get('awaiting_leader_id'):
        try:
            new_id = int(text)
        except ValueError:
            await update.message.reply_text("ID должен быть числом.")
            return
        set_party_leader(new_id)
        context.user_data.pop('awaiting_leader_id', None)
        await update.message.reply_text(f"Лидер пати назначен: {new_id}")
        return

    # Меню лидера пати (для назначенного лидера)
    if text == "👑 Лидер пати" and is_party_leader(uid):
        context.user_data['in_party_menu'] = True
        await update.message.reply_text("Лидер пати:", reply_markup=get_party_leader_keyboard())
        return

    # Внутренние команды меню пати
    if context.user_data.get('in_party_menu'):
        if text == "➕ Добавить в состав":
            context.user_data['party_add_mode'] = True
            await update.message.reply_text(
                "Вводите по одному участнику в формате `НИК КЛАСС`.\n"
                "Пример: `Qudas СИН`\n"
                "Для завершения нажмите «Завершить».",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Завершить")]], resize_keyboard=True))
            return
        elif text == "➖ Удалить из состава":
            await show_party_delete_menu(uid, update)
            return
        elif text == "🗳 Проголосовать за пати":
            from polls import vote_for_party
            await vote_for_party(uid, update, context)
            return
        elif text == "Завершить" and context.user_data.get('party_add_mode'):
            context.user_data.pop('party_add_mode', None)
            await update.message.reply_text("Добавление завершено.", reply_markup=get_party_leader_keyboard())
            return
        elif text == "🔙 Назад":
            context.user_data.pop('in_party_menu', None)
            await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(uid))
            return

    # Добавление участника (режим party_add_mode)
    if context.user_data.get('party_add_mode') and text != "Завершить":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Формат: НИК КЛАСС (например Qudas СИН).")
            return
        nick, cls = parts
        add_party_member(uid, nick, cls.upper())
        await update.message.reply_text(f"✅ {nick} ({cls.upper()}) добавлен.")
        return

    # ---------- Меню управления кланом (для админов) ----------
    if text == "🏰 Управление кланом" and is_admin(uid):
        context.user_data['in_clan_menu'] = True
        await update.message.reply_text("Управление кланом:", reply_markup=get_clan_management_keyboard())
        return

    if context.user_data.get('in_clan_menu'):
        if text == "👥 Список пользователей":
            await show_users_list(update, context)
            return
        elif text == "📋 Список ожидания":
            await list_pending(update, context)
            return
        elif text == "✅ Подтвердить всех":
            await confirm_all_pending_cmd(update, context)
            return
        elif text == "❌ Отказать":
            await reject_pending_menu(update, context)
            return
        elif text == "👑 Назначить лидера пати":
            context.user_data['awaiting_leader_id'] = True
            await update.message.reply_text("Введите Telegram ID нового лидера пати:")
            return
        elif text == "❌ Снять лидера пати":
            remove_party_leader()
            await update.message.reply_text("Лидер пати снят.")
            return
        elif text == "🔙 Назад":
            context.user_data.pop('in_clan_menu', None)
            await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(uid))
            return
        else:
            # Внутри меню клана игнорируем неизвестные команды
            return

    # ---------- Основное меню (общие команды) ----------
    if text == "👤 Мой профиль":
        await update.message.reply_text(f"Ник: {get_user_nick(uid)}\nКласс: {get_user_class(uid)}")
        return
    elif text == "📝 Мои ответы":
        await my_answers(update, context)
        return
    elif text == "❓ Помощь":
        await update.message.reply_text("Обратитесь к администратору клана.")
        return
    elif text == "📊 Админ-панель" and is_admin(uid):
        await update.message.reply_text("Админ-панель:", reply_markup=get_admin_keyboard())
        return
    elif text == "📊 Управление опросами" and is_admin(uid):
        await update.message.reply_text("Опросы:", reply_markup=get_polls_management_keyboard())
        return
    elif text == "📝 Создать опрос (ГВГ)" and is_admin(uid):
        await start_gvg_poll(update, context)
        return
    elif text == "👥 Пройти за другого" and is_admin(uid):
        await admin_poll_for_other(update, context)
        return
    elif text == "📤 Разослать опрос" and is_admin(uid):
        await send_poll_to_all(update, context)
        return
    elif text == "📈 Результаты опроса" and is_admin(uid):
        await export_command(update, context)
        return
    elif text == "❌ Не ответившие" and is_admin(uid):
        await non_responders_cmd(update, context)
        return
    elif text == "📝 Регистрация" and is_admin(uid):
        await registration_menu(update, context)
        return
    elif text == "🔙 Назад" and is_admin(uid):
        await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(uid))
        return
    elif context.user_data.get('reject_mode') and text.startswith("❌ "):
        await handle_reject_pending(update, context)
        return
    elif 'gvg' in context.user_data and await handle_gvg_text(update, context):
        return
    elif context.user_data.get('ext_step') and await handle_external_answer(update, context):
        return
    else:
        await update.message.reply_text("Неизвестная команда.")
        return

async def show_party_delete_menu(leader_id, update: Update):
    members = get_party_members(leader_id)
    if not members:
        await update.message.reply_text("Состав пати пуст.", reply_markup=get_party_leader_keyboard())
        return
    keyboard = []
    for nick, cls in members:
        keyboard.append([InlineKeyboardButton(f"❌ {nick} ({cls})", callback_data=f"del_party_{nick}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="party_back")])
    await update.message.reply_text("Выберите участника для удаления:",
                                    reply_markup=InlineKeyboardMarkup(keyboard))

async def party_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "party_back":
        await query.edit_message_text("Лидер пати:", reply_markup=None)
        await query.message.reply_text("Лидер пати:", reply_markup=get_party_leader_keyboard())
        return
    if data.startswith("del_party_"):
        nick = data[len("del_party_"):]
        leader_id = query.from_user.id
        remove_party_member(leader_id, nick)
        await query.edit_message_text(f"Участник {nick} удалён.")
        await show_party_delete_menu(leader_id, query)
        return

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(CallbackQueryHandler(show_all_ids_callback, pattern="^show_all_ids$"))
    app.add_handler(CommandHandler("myanswers", my_answers))
    app.add_handler(CallbackQueryHandler(party_delete_callback, pattern="^(del_party_|party_back)"))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("send_poll", send_poll_to_all))
    app.add_handler(CallbackQueryHandler(poll_callback, pattern="^poll_"))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(restart_callback, pattern="^restart_"))
    app.add_handler(CallbackQueryHandler(gvg_callback, pattern="^(gvg_add|gvg_finish)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
