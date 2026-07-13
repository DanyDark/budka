import json, logging, os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from database import *
from keyboards import get_poll_question_inline, get_confirm_restart_inline, get_admin_keyboard, get_party_leader_keyboard

def get_google_spreadsheet():
    creds = os.environ.get("GOOGLE_CREDS")
    sid = os.environ.get("GOOGLE_SHEET_ID")
    if not creds or not sid:
        logging.error("Google Sheets не настроен")
        return None
    info = json.loads(creds)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Исправленный способ авторизации
    creds_obj = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds_obj).open_by_key(sid)

def sanitize_sheet_name(name):
    return name.replace('/', '').replace('\\', '').replace('?', '').replace('*', '').replace('[', '').replace(']', '')[:100] or "Лист"

async def start_gvg_poll(update, context):
    context.user_data['gvg'] = {'step': 'datetime'}
    await update.message.reply_text("Введите дату и время ГВГ (ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Отмена")]], resize_keyboard=True))

async def handle_gvg_text(update, context):
    if 'gvg' not in context.user_data:
        return False
    data = context.user_data['gvg']
    text = update.message.text.strip()
    if text == "❌ Отмена":
        del context.user_data['gvg']
        await update.message.reply_text("Отменено.")
        return True
    if data['step'] == 'datetime':
        try:
            datetime.strptime(text, "%d.%m.%Y %H:%M")
        except:
            await update.message.reply_text("Неверный формат.")
            return True
        data['datetime'] = text
        data['step'] = 'opponents'
        await update.message.reply_text("Противники (или «-»):")
        return True
    elif data['step'] == 'opponents':
        data['opponents'] = text
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить ещё", callback_data="gvg_add")],
            [InlineKeyboardButton("✅ Создать опрос", callback_data="gvg_finish")]
        ])
        await update.message.reply_text(
            f"ГВГ: {data['datetime']} – {data['opponents']}\nДействие:", reply_markup=kb)
        data['step'] = 'wait'
        return True
    return False

async def gvg_callback(update, context):
    q = update.callback_query
    await q.answer()
    data = context.user_data.get('gvg')
    if not data:
        await q.edit_message_text("Сессия утеряна.")
        return
    if q.data == "gvg_add":
        if 'list' not in data:
            data['list'] = []
        data['list'].append({'datetime': data['datetime'], 'opponents': data['opponents']})
        data['step'] = 'datetime'
        await q.edit_message_text("Введите дату и время следующего ГВГ:")
    elif q.data == "gvg_finish":
        if 'list' not in data:
            data['list'] = []
        if data.get('datetime'):
            data['list'].append({'datetime': data['datetime'], 'opponents': data.get('opponents', '-')})
        meetings = [f"{g['datetime']} - {g['opponents']}" for g in data['list']]
        create_poll(f"ГВГ на {datetime.now().strftime('%d.%m.%Y')}", meetings)
        await q.edit_message_text(f"✅ Опрос создан ({len(meetings)} встреч)")
        del context.user_data['gvg']
        await q.message.reply_text("Админ-панель:", reply_markup=get_admin_keyboard())

async def admin_poll_for_other(update, context):
    poll = get_active_poll()
    if not poll:
        await update.message.reply_text("Нет активного опроса.")
        return
    context.user_data['ext_poll'] = poll
    context.user_data['ext_step'] = True
    await update.message.reply_text(
        f"Введите: НИК \\ КЛАСС \\ ОТВЕТЫ\nПример: Qudas \\ СИН \\ Буду \\ Не буду\nВстречи: {', '.join(poll['meetings'])}",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Отмена")]], resize_keyboard=True))

async def handle_external_answer(update, context):
    if not context.user_data.get('ext_step'):
        return False
    text = update.message.text.strip()
    if text == "❌ Отмена":
        context.user_data.pop('ext_step', None)
        context.user_data.pop('ext_poll', None)
        await update.message.reply_text("Отменено.", reply_markup=get_admin_keyboard())
        return True
    parts = [p.strip() for p in text.split('\\')]
    poll = context.user_data['ext_poll']
    if len(parts) < 2 + len(poll['meetings']):
        await update.message.reply_text("Неверное количество ответов.")
        return True
    nick = parts[0]
    cls = parts[1]
    answers = parts[2:]
    for i, meeting in enumerate(poll['meetings']):
        save_external_response(poll['id'], nick, cls, meeting, answers[i], update.effective_user.id)
    await update.message.reply_text(f"✅ Ответы для {nick} сохранены. Введите следующего или «❌ Отмена».")
    return True

async def send_poll_to_all(update, context):
    poll = get_active_poll()
    if not poll:
        await update.message.reply_text("Нет активного опроса.")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("Нет пользователей.")
        return
    await update.message.reply_text(f"Рассылка {len(users)} пользователям...")
    count = 0
    for uid, _, _ in users:
        try:
            await send_first_question(uid, poll, context)
            count += 1
        except Exception as e:
            logging.error(f"Ошибка отправки {uid}: {e}")
    await update.message.reply_text(f"Отправлено {count} сообщений.")

async def send_first_question(chat_id, poll, context):
    m = poll['meetings'][0]
    kb = get_poll_question_inline(poll['id'], m, 1)
    await context.bot.send_message(chat_id, f"📢 Опрос\n\n{poll['text']}\n\nВопрос 1/{len(poll['meetings'])}:\n{m}", parse_mode="Markdown", reply_markup=kb)

async def poll_callback(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_registered(user_id):
        await q.edit_message_text("❌ Вы не зарегистрированы.")
        return
    parts = q.data.split('_')
    poll_id = int(parts[1])
    answer = next(p for p in parts if p in ('да', 'нет', 'не знаю'))
    meeting = '_'.join(parts[2:parts.index(answer)])
    next_idx = int(parts[-1])
    poll = get_active_poll()
    if not poll or poll['id'] != poll_id:
        await q.edit_message_text("Опрос неактивен.")
        return
    if 'answers' not in context.user_data:
        context.user_data['answers'] = {}
    context.user_data['answers'][meeting] = answer
    if next_idx >= len(poll['meetings']):
        summary = "✅ Ответы:\n\n" + "\n".join(f"• {m}: {context.user_data['answers'].get(m, '—')}" for m in poll['meetings'])
        await q.edit_message_text(summary + "\n\nВсё верно?", reply_markup=get_confirm_restart_inline(poll_id))
    else:
        next_m = poll['meetings'][next_idx]
        await q.edit_message_text(
            f"📢 Опрос\n\n{poll['text']}\n\nВопрос {next_idx+1}/{len(poll['meetings'])}:\n{next_m}",
            reply_markup=get_poll_question_inline(poll_id, next_m, next_idx+1))

async def confirm_callback(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_registered(user_id):
        await q.edit_message_text("❌ Не зарегистрированы.")
        return
    poll_id = int(q.data.split('_')[1])
    answers = context.user_data.pop('answers', {})
    if answers:
        save_responses_batch(user_id, poll_id, answers)
    await q.edit_message_text("✅ Ответы сохранены.")
    
def get_responses_grouped_by_meeting(poll_id):
    grouped = {}
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""SELECT u.user_id, u.nick, u.class, pr.meeting, pr.answer
                   FROM poll_responses pr JOIN users u ON pr.user_id=u.user_id
                   WHERE pr.poll_id=?""", (poll_id,))
    for uid, nick, cls, meeting, answer in cur.fetchall():
        prefix = "🔹 " if is_substitute(uid) else ""
        grouped.setdefault(meeting, []).append((f"{prefix}{nick}", cls or "Не указан", answer))
    cur.execute("SELECT external_nick, external_class, meeting, answer FROM external_responses WHERE poll_id=?", (poll_id,))
    for nick, cls, meeting, answer in cur.fetchall():
        grouped.setdefault(meeting, []).append((nick, cls or "Внешний", answer))
    conn.close()
    return grouped

async def restart_callback(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_registered(user_id):
        await q.edit_message_text("❌ Не зарегистрированы.")
        return
    poll_id = int(q.data.split('_')[1])
    context.user_data['answers'] = {}
    poll = get_active_poll()
    if not poll or poll['id'] != poll_id:
        await q.edit_message_text("Опрос неактивен.")
        return
    await q.edit_message_text("Начинаем заново...")
    await send_first_question(user_id, poll, context)

async def export_command(update, context):
    sh = get_google_spreadsheet()
    if not sh:
        await update.message.reply_text("❌ Google Sheets недоступен.")
        return
    poll = get_active_poll()
    if not poll:
        await update.message.reply_text("Нет опроса.")
        return
    grouped = get_responses_grouped_by_meeting(poll['id'])
    if not grouped:
        await update.message.reply_text("Нет ответов.")
        return
    for meeting, resp in grouped.items():
        try:
            ws = sh.worksheet(sanitize_sheet_name(meeting))
            ws.clear()
        except:
            ws = sh.add_worksheet(sanitize_sheet_name(meeting), rows="1000", cols="20")
        data = [["Ник", "Класс", "Ответ"]] + [[r[0], r[1], r[2]] for r in sorted(resp, key=lambda x: x[1])]
        ws.update(data, 'A1')
    await update.message.reply_text("✅ Выгружено.")

async def non_responders_cmd(update, context):
    poll = get_active_poll()
    if not poll:
        await update.message.reply_text("Нет опроса.")
        return
    nr = get_non_responders(poll['id'])
    if not nr:
        await update.message.reply_text("Все ответили!")
        return
    await update.message.reply_text("❌ Не ответили:\n" + "\n".join(f"• {nick}" for _, nick in nr))

async def my_answers(update, context):
    answers = get_user_current_poll_answers(update.effective_user.id)
    if not answers:
        await update.message.reply_text("Вы ещё не отвечали.")
        return
    msg = "📝 Ваши ответы:\n" + "\n".join(f"• {m}: {a}" for m, a in answers.items())
    await update.message.reply_text(msg)
    
# ---------- ГОЛОСОВАНИЕ ЗА ПАТИ ----------
async def vote_for_party(leader_id, update, context):
    from database import get_active_poll, get_party_members
    poll = get_active_poll()
    if not poll:
        await update.message.reply_text("Нет активного опроса.")
        return
    members = get_party_members(leader_id)  # список (nick, class)
    if not members:
        await update.message.reply_text("Состав пати пуст. Добавьте участников.")
        return
    context.user_data['party_vote'] = {
        'members': members,
        'poll': poll,
        'current_member_idx': 0,
        'current_meeting_idx': 0,
        'answers': {}
    }
    await ask_party_vote_question(leader_id, update, context)

async def ask_party_vote_question(chat_id, update_or_query, context):
    data = context.user_data['party_vote']
    members = data['members']
    poll = data['poll']
    member_idx = data['current_member_idx']
    meeting_idx = data['current_meeting_idx']

    if member_idx >= len(members):
        await save_all_party_votes(chat_id, update_or_query, context)
        return

    nick, cls = members[member_idx]
    meetings = poll['meetings']
    if meeting_idx >= len(meetings):
        data['current_member_idx'] += 1
        data['current_meeting_idx'] = 0
        await ask_party_vote_question(chat_id, update_or_query, context)
        return

    meeting = meetings[meeting_idx]
    keyboard = get_poll_question_inline(poll['id'], meeting, meeting_idx+1)
    text = f"🗳 Голосование за **{nick}** ({cls})\n\nВстреча: {meeting}"
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def save_all_party_votes(chat_id, update_or_query, context):
    data = context.user_data.pop('party_vote', None)
    if not data:
        return
    poll = data['poll']
    answers = data['answers']
    for nick, meeting_answers in answers.items():
        member = next((m for m in data['members'] if m[0] == nick), None)
        cls = member[1] if member else "Не указан"
        for meeting, answer in meeting_answers.items():
            save_external_response(poll['id'], nick, cls, meeting, answer, chat_id)
    text = "✅ Голоса за пати сохранены!"
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, reply_markup=get_party_leader_keyboard())
    else:
        await update_or_query.edit_message_text(text)
        await update_or_query.message.reply_text("Лидер пати:", reply_markup=get_party_leader_keyboard())

# Обновляем poll_callback, чтобы он обрабатывал голосование за пати
async def poll_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Если идёт голосование за пати – обрабатываем внутри него
    if 'party_vote' in context.user_data:
        return await party_poll_callback_logic(update, context)

    # Обычная обработка
    if not is_registered(user_id):
        await query.edit_message_text("❌ Вы не зарегистрированы.")
        return
    parts = query.data.split('_')
    poll_id = int(parts[1])
    answer = next(p for p in parts if p in ('да', 'нет', 'не знаю'))
    meeting = '_'.join(parts[2:parts.index(answer)])
    next_idx = int(parts[-1])
    poll = get_active_poll()
    if not poll or poll['id'] != poll_id:
        await query.edit_message_text("Опрос неактивен.")
        return
    if 'answers' not in context.user_data:
        context.user_data['answers'] = {}
    context.user_data['answers'][meeting] = answer
    if next_idx >= len(poll['meetings']):
        summary = "✅ Ответы:\n\n" + "\n".join(f"• {m}: {context.user_data['answers'].get(m, '—')}" for m in poll['meetings'])
        await query.edit_message_text(summary + "\n\nВсё верно?", reply_markup=get_confirm_restart_inline(poll_id))
    else:
        next_m = poll['meetings'][next_idx]
        await query.edit_message_text(
            f"📢 Опрос\n\n{poll['text']}\n\nВопрос {next_idx+1}/{len(poll['meetings'])}:\n{next_m}",
            reply_markup=get_poll_question_inline(poll_id, next_m, next_idx+1))

async def party_poll_callback_logic(update, context):
    query = update.callback_query
    await query.answer()
    data = context.user_data['party_vote']
    parts = query.data.split('_')
    poll_id = int(parts[1])
    answer = next(p for p in parts if p in ('да', 'нет', 'не знаю'))
    meeting = '_'.join(parts[2:parts.index(answer)])
    next_idx = int(parts[-1])
    poll = get_active_poll()
    if not poll or poll['id'] != poll_id:
        await query.edit_message_text("Опрос неактивен.")
        return
    member_idx = data['current_member_idx']
    members = data['members']
    if member_idx >= len(members):
        return
    nick, cls = members[member_idx]
    if nick not in data['answers']:
        data['answers'][nick] = {}
    data['answers'][nick][meeting] = answer
    if next_idx >= len(poll['meetings']):
        data['current_member_idx'] += 1
        data['current_meeting_idx'] = 0
    else:
        data['current_meeting_idx'] = next_idx
    await ask_party_vote_question(query.from_user.id, query, context)
