import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
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
        for k in ['awaiting_nick', 'awaiting_class', 'reject_mode', 'gvg', 'ext_step']:
            context.user_data.pop(k, None)
        await update.message.reply_text("Отменено.", reply_markup=get_main_keyboard(uid, is_admin(uid)))
        return

    # Регистрация (если не зарегистрирован)
    if not is_registered(uid) and not is_pending(uid):
        if 'awaiting_nick' in context.user_data or 'awaiting_class' in context.user_data:
            await handle_registration_text(update, context)
            return
        await update.message.reply_text("Нажмите /start для регистрации.")
        return

    if is_pending(uid):
        await update.message.reply_text("Заявка ожидает подтверждения.")
        return

    # Основное меню
    if text == "👤 Мой профиль":
        await update.message.reply_text(f"Ник: {get_user_nick(uid)}\nКласс: {get_user_class(uid)}")
    elif text == "📝 Мои ответы":
        await my_answers(update, context)
    elif text == "❓ Помощь":
        await update.message.reply_text("Обратитесь к администратору клана.")
    elif text == "📊 Админ-панель" and is_admin(uid):
        await update.message.reply_text("Админ-панель:", reply_markup=get_admin_keyboard())
    elif text == "📊 Управление опросами" and is_admin(uid):
        await update.message.reply_text("Опросы:", reply_markup=get_polls_management_keyboard())
    elif text == "📝 Создать опрос (ГВГ)" and is_admin(uid):
        await start_gvg_poll(update, context)
    elif text == "👥 Пройти за другого" and is_admin(uid):
        await admin_poll_for_other(update, context)
    elif text == "📤 Разослать опрос" and is_admin(uid):
        await send_poll_to_all(update, context)
    elif text == "📈 Результаты опроса" and is_admin(uid):
        await export_command(update, context)
    elif text == "❌ Не ответившие" and is_admin(uid):
        await non_responders_cmd(update, context)
    elif text == "📝 Регистрация" and is_admin(uid):
        await registration_menu(update, context)
    elif text == "🏰 Управление кланом" and is_admin(uid):
        await update.message.reply_text("Управление кланом:", reply_markup=get_clan_management_keyboard())
    elif text == "👥 Список пользователей" and is_admin(uid):
        await show_users_list(update, context)
    elif text == "📋 Список ожидания" and is_admin(uid):
        await list_pending(update, context)
    elif text == "✅ Подтвердить всех" and is_admin(uid):
        await confirm_all_pending_cmd(update, context)
    elif text == "❌ Отказать" and is_admin(uid):
        await reject_pending_menu(update, context)
    elif text == "🔙 Назад" and is_admin(uid):
        await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(uid, is_admin(uid)))
    elif context.user_data.get('reject_mode') and text.startswith("❌ "):
        await handle_reject_pending(update, context)
    elif 'gvg' in context.user_data and await handle_gvg_text(update, context):
        pass
    elif context.user_data.get('ext_step') and await handle_external_answer(update, context):
        pass
    else:
        await update.message.reply_text("Неизвестная команда.")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(CallbackQueryHandler(show_all_ids_callback, pattern="^show_all_ids$"))
    app.add_handler(CommandHandler("myanswers", my_answers))
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
