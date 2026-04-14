from telethon import TelegramClient
from telethon.errors import FloodWaitError
import asyncio
import os
import config
from datetime import datetime

PLUGIN_INFO = {
    'name': 'Scheduler',
    'version': '2.0',
    'description': 'Автоматическая рассылка с фото'
}

userbot_client = None
scheduled_broadcasts = {}
broadcast_counter = 0
pending_setups = {}

async def get_userbot():
    global userbot_client
    if userbot_client is None or not userbot_client.is_connected():
        session_file = os.path.join(os.path.expanduser('~'), 'termux_bot', config.SESSION_NAME)
        userbot_client = TelegramClient(session_file, config.API_ID, config.API_HASH)
        await userbot_client.start(phone=config.PHONE_NUMBER)
    return userbot_client

async def login(update, context):
    try:
        client = await get_userbot()
        me = await client.get_me()
        return f"✅ *Авторизован*\n\n👤 {me.first_name}\n🆔 {me.id}\n📱 {me.phone}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

async def start_broadcast(update, context):
    user_id = update.effective_user.id
    pending_setups[user_id] = {
        'step': 'text',
        'text': None,
        'photo': None,
        'chats': None,
        'interval': None
    }
    return (
        "📝 *Настройка рассылки - Шаг 1/4*\n\n"
        "Отправь текст сообщения для рассылки.\n\n"
        "Или `/scheduler_cancel` для отмены."
    )

async def cancel(update, context):
    user_id = update.effective_user.id
    if user_id in pending_setups:
        del pending_setups[user_id]
        return "❌ Настройка отменена"
    return "Нет активной настройки"

async def handle_message(update, context):
    user_id = update.effective_user.id
    if user_id not in pending_setups:
        return None
    setup = pending_setups[user_id]
    
    if setup['step'] == 'text':
        setup['text'] = update.message.text
        setup['step'] = 'photo'
        await update.message.reply_text(
            "📸 *Шаг 2/4*\n\n"
            "Отправь фото для рассылки.\n\n"
            "Или `/scheduler_skip` чтобы пропустить.",
            parse_mode='Markdown'
        )
        return "processing"
    
    if setup['step'] == 'photo':
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            photo_path = os.path.join(os.path.expanduser('~'), 'termux_bot', f'photo_{user_id}.jpg')
            await photo_file.download_to_drive(photo_path)
            setup['photo'] = photo_path
        
        setup['step'] = 'chats'
        await update.message.reply_text(
            "💬 *Шаг 3/4*\n\n"
            "Отправь чаты через запятую.\n\n"
            "*Можно использовать:*\n"
            "• ID: `-1001234567890`\n"
            "• Username: `@mychannel`\n"
            "• Без @: `mychannel`\n\n"
            "*Примеры:*\n"
            "`-1001234567890,@mychannel,mygroup`\n"
            "`username1,username2,@username3`\n\n"
            "Узнать ID/Username: `/scheduler_dialogs`",
            parse_mode='Markdown'
        )
        return "processing"
    
    if setup['step'] == 'chats':
        chat_inputs = [cid.strip() for cid in update.message.text.split(',')]
        processed_ids = []
        
        for cid in chat_inputs:
            # Убрать пробелы
            cid = cid.strip()
            
            # Если начинается с @ - оставить как есть
            if cid.startswith('@'):
                processed_ids.append(cid)
            else:
                # Попробовать преобразовать в число
                try:
                    processed_ids.append(int(cid))
                except:
                    # Если не число и не начинается с @ или - 
                    # добавить @ автоматически
                    if not cid.startswith('-'):
                        processed_ids.append(f"@{cid}")
                    else:
                        processed_ids.append(cid)
        
        setup['chats'] = processed_ids
        setup['step'] = 'interval'
        
        await update.message.reply_text(
            "⏰ *Шаг 4/4*\n\n"
            "Укажи интервал рассылки в минутах.\n\n"
            "*Примеры:*\n"
            "`30` - каждые 30 минут\n"
            "`60` - каждый час\n"
            "`1440` - каждый день",
            parse_mode='Markdown'
        )
        return "processing"
    
    if setup['step'] == 'interval':
        try:
            interval = int(update.message.text)
            
            if interval < 1:
                await update.message.reply_text("❌ Минимум 1 минута")
                return "processing"
            
            setup['interval'] = interval
            
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
            
            asyncio.create_task(run_broadcast(broadcast_id, update))
            
            del pending_setups[user_id]
            
            # Форматировать список чатов для отображения
            chats_display = ', '.join([f"`{c}`" for c in setup['chats'][:3]])
            if len(setup['chats']) > 3:
                chats_display += f" и ещё {len(setup['chats']) - 3}"
            
            return (
                f"✅ *Рассылка создана!*\n\n"
                f"🆔 ID: `{broadcast_id}`\n"
                f"📝 Текст: _{setup['text'][:50]}{'...' if len(setup['text']) > 50 else ''}_\n"
                f"📸 Фото: {'✅ Да' if setup['photo'] else '❌ Нет'}\n"
                f"💬 Чаты: {chats_display}\n"
                f"⏰ Интервал: {interval} мин\n\n"
                f"🚀 Рассылка запущена!\n\n"
                f"*Управление:*\n"
                f"`/scheduler_list` - список\n"
                f"`/scheduler_stop {broadcast_id}` - остановить\n"
                f"`/scheduler_delete {broadcast_id}` - удалить"
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введи число (минуты)")
            return "processing"
    
    return None

async def skip_photo(update, context):
    user_id = update.effective_user.id
    if user_id in pending_setups and pending_setups[user_id]['step'] == 'photo':
        pending_setups[user_id]['step'] = 'chats'
        return (
            "💬 *Шаг 3/4*\n\n"
            "Отправь чаты через запятую.\n\n"
            "*Можно:* ID, @username или username\n\n"
            "Пример: `mychannel,@mygroup,-1001234567890`"
        )
    return "Нет активной настройки"

async def run_broadcast(broadcast_id, update):
    broadcast = scheduled_broadcasts[broadcast_id]
    
    while broadcast['active']:
        try:
            client = await get_userbot()
            
            success = 0
            failed = 0
            errors = []
            
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
                    await asyncio.sleep(2)
                    
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    # Повторная попытка
                    try:
                        if broadcast['photo']:
                            await client.send_file(chat_id, broadcast['photo'], caption=broadcast['text'])
                        else:
                            await client.send_message(chat_id, broadcast['text'])
                        success += 1
                    except:
                        failed += 1
                        errors.append(f"{chat_id}: FloodWait")
                        
                except Exception as e:
                    failed += 1
                    errors.append(f"{chat_id}: {str(e)[:30]}")
            
            broadcast['last_run'] = datetime.now()
            
            # Ждать до следующей рассылки
            await asyncio.sleep(broadcast['interval'] * 60)
            
        except Exception as e:
            print(f"Ошибка рассылки {broadcast_id}: {e}")
            await asyncio.sleep(60)

async def list_broadcasts(update, context):
    if not scheduled_broadcasts:
        return "📭 Нет активных рассылок\n\nСоздать: `/scheduler_start`"
    
    text = f"📋 *Активные рассылки ({len(scheduled_broadcasts)}):*\n\n"
    
    for bid, broadcast in scheduled_broadcasts.items():
        status = "✅ Активна" if broadcast['active'] else "⏸ Остановлена"
        
        text += f"*ID {bid}* - {status}\n"
        text += f"📝 _{broadcast['text'][:40]}{'...' if len(broadcast['text']) > 40 else ''}_\n"
        text += f"💬 Чатов: {len(broadcast['chats'])}\n"
        text += f"⏰ Каждые {broadcast['interval']} мин\n"
        
        if broadcast['last_run']:
            text += f"🕐 Последняя: {broadcast['last_run'].strftime('%H:%M')}\n"
        
        text += f"`/scheduler_stop {bid}` `/scheduler_delete {bid}`\n\n"
    
    return text

async def stop_broadcast(update, context):
    if not context.args:
        return "❌ Используй: `/scheduler_stop <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            scheduled_broadcasts[broadcast_id]['active'] = False
            return f"⏸ Рассылка *{broadcast_id}* остановлена\n\nВозобновить: `/scheduler_resume {broadcast_id}`"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def resume_broadcast(update, context):
    if not context.args:
        return "❌ Используй: `/scheduler_resume <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            if not scheduled_broadcasts[broadcast_id]['active']:
                scheduled_broadcasts[broadcast_id]['active'] = True
                asyncio.create_task(run_broadcast(broadcast_id, update))
                return f"▶️ Рассылка *{broadcast_id}* возобновлена"
            else:
                return f"⚠️ Рассылка {broadcast_id} уже активна"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def delete_broadcast(update, context):
    if not context.args:
        return "❌ Используй: `/scheduler_delete <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            scheduled_broadcasts[broadcast_id]['active'] = False
            
            if scheduled_broadcasts[broadcast_id]['photo']:
                try:
                    os.remove(scheduled_broadcasts[broadcast_id]['photo'])
                except:
                    pass
            
            del scheduled_broadcasts[broadcast_id]
            return f"🗑 Рассылка *{broadcast_id}* удалена"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def get_dialogs(update, context):
    try:
        client = await get_userbot()
        dialogs = await client.get_dialogs(limit=50)
        
        text = "💬 *Твои чаты:*\n\n"
        
        for i, dialog in enumerate(dialogs, 1):
            entity = dialog.entity
            
            # ID
            chat_id = f"`{dialog.id}`"
            
            # Username (если есть)
            username = ""
            if hasattr(entity, 'username') and entity.username:
                username = f" `@{entity.username}`"
            
            # Название
            name = dialog.name or "Без имени"
            
            text += f"{i}. {chat_id}{username}\n   {name}\n\n"
        
        text += "💡 *Можно использовать:*\n"
        text += "• Числовой ID\n"
        text += "• Username с @ или без"
        
        return text
    except Exception as e:
        return f"❌ Ошибка: {e}\n\nСначала: `/scheduler_login`"

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

async def handle_user_input(update, context):
    return await handle_message(update, context)