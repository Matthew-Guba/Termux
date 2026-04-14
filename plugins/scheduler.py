from telethon import TelegramClient
from telethon.errors import FloodWaitError
import asyncio
import os
import config
from datetime import datetime

PLUGIN_INFO = {
    'name': 'Scheduler',
    'version': '1.0',
    'description': 'Автоматическая рассылка с фото'
}

# Глобальные переменные
userbot_client = None
scheduled_broadcasts = {}
broadcast_counter = 0

# Хранилище ожидающих настройки
pending_setups = {}

async def get_userbot():
    """Получить userbot клиент"""
    global userbot_client
    if userbot_client is None or not userbot_client.is_connected():
        session_file = os.path.join(os.path.expanduser('~'), 'termux_bot', config.SESSION_NAME)
        userbot_client = TelegramClient(session_file, config.API_ID, config.API_HASH)
        await userbot_client.start(phone=config.PHONE_NUMBER)
    return userbot_client

async def login(update, context):
    """Авторизация userbot"""
    try:
        client = await get_userbot()
        me = await client.get_me()
        return f"✅ Авторизован\n\n👤 {me.first_name}\n🆔 {me.id}\n📱 {me.phone}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

async def start_broadcast(update, context):
    """Начать настройку рассылки"""
    user_id = update.effective_user.id
    
    pending_setups[user_id] = {
        'step': 'text',
        'text': None,
        'photo': None,
        'chats': None,
        'interval': None
    }
    
    return """
📝 *Настройка рассылки - Шаг 1/4*

Отправь текст сообщения для рассылки.

Или отправь `/scheduler_cancel` для отмены.
    """

async def cancel(update, context):
    """Отменить настройку"""
    user_id = update.effective_user.id
    if user_id in pending_setups:
        del pending_setups[user_id]
        return "❌ Настройка отменена"
    return "Нет активной настройки"

async def handle_message(update, context):
    """Обработчик сообщений для настройки"""
    user_id = update.effective_user.id
    
    if user_id not in pending_setups:
        return None
    
    setup = pending_setups[user_id]
    
    # Шаг 1: Получить текст
    if setup['step'] == 'text':
        setup['text'] = update.message.text
        setup['step'] = 'photo'
        await update.message.reply_text("""
📸 *Шаг 2/4*

Отправь фото для рассылки.

Или отправь `/scheduler_skip` чтобы пропустить фото.
        """, parse_mode='Markdown')
        return "processing"
    
    # Шаг 2: Получить фото
    if setup['step'] == 'photo':
        if update.message.photo:
            # Скачать фото
            photo_file = await update.message.photo[-1].get_file()
            photo_path = os.path.join(os.path.expanduser('~'), 'termux_bot', f'photo_{user_id}.jpg')
            await photo_file.download_to_drive(photo_path)
            setup['photo'] = photo_path
        
        setup['step'] = 'chats'
        await update.message.reply_text("""
💬 *Шаг 3/4*

Отправь ID чатов через запятую.

Например: `-1001234567890,-1009876543210`

Чтобы узнать ID чатов, используй `/scheduler_dialogs`
        """, parse_mode='Markdown')
        return "processing"
    
    # Шаг 3: Получить чаты
    if setup['step'] == 'chats':
        chat_ids = [cid.strip() for cid in update.message.text.split(',')]
        processed_ids = []
        for cid in chat_ids:
            try:
                processed_ids.append(int(cid))
            except:
                processed_ids.append(cid)
        
        setup['chats'] = processed_ids
        setup['step'] = 'interval'
        await update.message.reply_text("""
⏰ *Шаг 4/4*

Укажи интервал рассылки в минутах.

Например: `60` (каждый час)
Или: `1440` (каждый день)
        """, parse_mode='Markdown')
        return "processing"
    
    # Шаг 4: Получить интервал
    if setup['step'] == 'interval':
        try:
            interval = int(update.message.text)
            setup['interval'] = interval
            
            # Создать задачу рассылки
            global broadcast_counter
            broadcast_counter += 1
            broadcast_id = broadcast_counter
            
            scheduled_broadcasts[broadcast_id] = {
                'text': setup['text'],
                'photo': setup['photo'],
                'chats': setup['chats'],
                'interval': interval,
                'active': True,
                'last_run': None
            }
            
            # Запустить рассылку
            asyncio.create_task(run_broadcast(broadcast_id, update))
            
            del pending_setups[user_id]
            
            return f"""
✅ *Рассылка создана!*

🆔 ID: {broadcast_id}
📝 Текст: {setup['text'][:50]}...
📸 Фото: {'Да' if setup['photo'] else 'Нет'}
💬 Чатов: {len(setup['chats'])}
⏰ Интервал: {interval} мин

Рассылка запущена!

Управление:
/scheduler_list - Список рассылок
/scheduler_stop {broadcast_id} - Остановить
            """
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введи число (минуты)")
            return "processing"
    
    return None

async def skip_photo(update, context):
    """Пропустить фото"""
    user_id = update.effective_user.id
    if user_id in pending_setups and pending_setups[user_id]['step'] == 'photo':
        pending_setups[user_id]['step'] = 'chats'
        return """
💬 *Шаг 3/4*

Отправь ID чатов через запятую.

Пример: `-1001234567890,-1009876543210`
        """
    return "Нет активной настройки"

async def run_broadcast(broadcast_id, update):
    """Запустить рассылку в фоне"""
    broadcast = scheduled_broadcasts[broadcast_id]
    
    while broadcast['active']:
        try:
            client = await get_userbot()
            
            success = 0
            failed = 0
            
            for chat_id in broadcast['chats']:
                try:
                    if broadcast['photo']:
                        await client.send_file(
                            chat_id,
                            broadcast['photo'],
                            caption=broadcast['text']
                        )
                    else:
                        await client.send_message(chat_id, broadcast['text'])
                    
                    success += 1
                    await asyncio.sleep(2)  # Задержка между сообщениями
                    
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    failed += 1
                    print(f"Ошибка отправки в {chat_id}: {e}")
            
            broadcast['last_run'] = datetime.now()
            
            # Ждать до следующей рассылки
            await asyncio.sleep(broadcast['interval'] * 60)
            
        except Exception as e:
            print(f"Ошибка рассылки {broadcast_id}: {e}")
            await asyncio.sleep(60)

async def list_broadcasts(update, context):
    """Список активных рассылок"""
    if not scheduled_broadcasts:
        return "📭 Нет активных рассылок"
    
    text = "📋 *Активные рассылки:*\n\n"
    
    for bid, broadcast in scheduled_broadcasts.items():
        status = "✅ Активна" if broadcast['active'] else "⏸ Остановлена"
        text += f"🆔 *{bid}*\n"
        text += f"   {status}\n"
        text += f"   📝 {broadcast['text'][:30]}...\n"
        text += f"   💬 Чатов: {len(broadcast['chats'])}\n"
        text += f"   ⏰ Каждые {broadcast['interval']} мин\n"
        if broadcast['last_run']:
            text += f"   🕐 Последняя: {broadcast['last_run'].strftime('%H:%M')}\n"
        text += "\n"
    
    return text

async def stop_broadcast(update, context):
    """Остановить рассылку"""
    if not context.args:
        return "❌ Используй: `/scheduler_stop <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            scheduled_broadcasts[broadcast_id]['active'] = False
            return f"⏸ Рассылка {broadcast_id} остановлена"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def resume_broadcast(update, context):
    """Возобновить рассылку"""
    if not context.args:
        return "❌ Используй: `/scheduler_resume <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            if not scheduled_broadcasts[broadcast_id]['active']:
                scheduled_broadcasts[broadcast_id]['active'] = True
                asyncio.create_task(run_broadcast(broadcast_id, update))
                return f"▶️ Рассылка {broadcast_id} возобновлена"
            else:
                return f"⚠️ Рассылка {broadcast_id} уже активна"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def delete_broadcast(update, context):
    """Удалить рассылку"""
    if not context.args:
        return "❌ Используй: `/scheduler_delete <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            # Остановить и удалить
            scheduled_broadcasts[broadcast_id]['active'] = False
            
            # Удалить фото если есть
            if scheduled_broadcasts[broadcast_id]['photo']:
                try:
                    os.remove(scheduled_broadcasts[broadcast_id]['photo'])
                except:
                    pass
            
            del scheduled_broadcasts[broadcast_id]
            return f"🗑 Рассылка {broadcast_id} удалена"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def get_dialogs(update, context):
    """Список чатов для рассылки"""
    try:
        client = await get_userbot()
        dialogs = await client.get_dialogs(limit=30)
        
        text = "💬 *Твои чаты:*\n\n"
        
        for i, dialog in enumerate(dialogs, 1):
            text += f"{i}. `{dialog.id}` - {dialog.name}\n"
        
        text += "\n💡 Скопируй ID для рассылки"
        
        return text
    except Exception as e:
        return f"❌ Ошибка: {e}"

# Регистрация команд
COMMANDS = {
    'login': login,
    'start': start_broadcast,
    'cancel': cancel,
    'skip': skip_photo,
    'list': list_broadcasts,
    'stop': stop_broadcast,
    'resume': resume_broadcast,
    'delete': delete_broadcast,
    'dialogs': get_dialogs
}

# Специальный обработчик для текста/фото
async def handle_user_input(update, context):
    """Обработка текста и фото при настройке"""
    return await handle_message(update, context)