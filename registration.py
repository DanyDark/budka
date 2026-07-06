import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from database import (
    is_registered, is_pending, is_nick_taken, get_user_nick, get_user_class,
    add_pending_user, get_pending_users, confirm_all_pending,
    remove_pending_user_by_nick, register_user
)
from keyboards import *

ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_adm = user_id in ADMIN_IDS
    if is_registered(user_id):
        await update.message.reply_text(
            f"С возвращением, {get_user_nick(user_id)} (класс: {get_user_class(user_id)})!",
            reply_markup=get_main_keyboard(user_id, is_adm))
    elif is_pending(user_id):
        await update.message.reply_text("Ваша заявка уже отправлена администратору. Ожидайте.")
    else:
        await update.message.reply_text(
            "⚠️ *Внимание!*\nБот использует ваш игровой ник и Telegram ID.\n\nВведите свой ник:",
            parse_mode="Markdown")
        context.user_data['awaiting_nick'] = True

async def handle_registration_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get('awaiting_nick'):
        if is_nick_taken(text):
            await update.message.reply_text("❌ Ник уже занят. Введите другой.")
            return
        context.user_data['temp_nick'] = text
        context.user_data['awaiting_nick'] = False
        context.user_data['awaiting_class'] = True
        await update.message.reply_text("Отлично! Выберите класс:", reply_markup=get_class_keyboard())
        return

    if context.user_data.get('awaiting_class'):
        valid = ["ВАР", "МАГ", "ТАНК", "ДРУ", "ПРИСТ", "ЛУК", "СИН", "ШАМ", "СИК", "МИСТИК"]
        if text not in valid:
            await update.message.reply_text("Выберите класс из кнопок.")
            return
        nick = context.user_data.pop('temp_nick')
        user_class = text
        context.user_data.pop('awaiting_class')

        if user_id in ADMIN_IDS:
            # Администратор регистрируется сразу
            register_user(user_id, nick, user_class)
            await update.message.reply_text(
                f"✅ Регистрация завершена!\nНик: {nick}\nКласс: {user_class}",
                reply_markup=get_main_keyboard(user_id, is_admin=True))
            return

        # Обычный пользователь — заявка
        add_pending_user(user_id, nick, user_class)
        await update.message.reply_text(
            f"✅ Заявка отправлена!\nНик: {nick}\nКласс: {user_class}\nОжидайте подтверждения.",
            reply_markup=get_main_keyboard(user_id, is_admin=False))
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(aid, f"📝 Заявка: {nick} ({user_class}) ID:{user_id}")
            except:
                pass
        return

# ---------- Админские ----------
async def registration_menu(update, context):
    await update.message.reply_text("Управление регистрацией:", reply_markup=get_registration_management_keyboard())

async def list_pending(update, context):
    pending = get_pending_users()
    if not pending:
        await update.message.reply_text("Нет ожидающих.")
        return
    msg = "📝 Ожидают:\n\n"
    for uid, nick, cls, dt in pending:
        msg += f"• {nick} ({cls}) – ID:{uid}\n"
    await update.message.reply_text(msg)

async def confirm_all_pending_cmd(update, context):
    confirmed = confirm_all_pending()
    await update.message.reply_text(f"✅ Подтверждено {len(confirmed)} пользователей.")

async def reject_pending_menu(update, context):
    pending = get_pending_users()
    kb = get_reject_keyboard(pending)
    if not kb:
        await update.message.reply_text("Нет ожидающих.")
        return
    await update.message.reply_text("Выберите для отмены:", reply_markup=kb)
    context.user_data['reject_mode'] = True

async def handle_reject_pending(update, context):
    if not context.user_data.get('reject_mode'):
        return False
    text = update.message.text
    if text == "🔙 Назад":
        context.user_data.pop('reject_mode', None)
        await registration_menu(update, context)
        return True
    if text.startswith("❌ "):
        nick = text[2:]
        remove_pending_user_by_nick(nick)
        await update.message.reply_text(f"Заявка {nick} отклонена.")
        await reject_pending_menu(update, context)
        return True
    return False
