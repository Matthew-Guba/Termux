from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import os
import config
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

PLUGIN_INFO = {
    'name': 'Scheduler',
    'version': '4.0',
    'description': 'Автоматическая рассылка с кнопками'
}

userbot_client = None
scheduled_broadcasts = {}
broadcast_tasks = {}
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
        
        keyboard = [
            [InlineKeyboardButton("📋 Список чатов", callback_data="dialogs")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="login")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return {
            'text': f"✅ *Авторизован*\n\n👤 {me.first_name}\n🆔 {me.id}\n📱 {me.phone}",
            'reply_markup': reply_markup
        }
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
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_setup")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return {
        'text': (
            "📝 *Настройка рассылки - Шаг 1/4*\n\n"
            "Отправь текст сообщения для рассылки.\n"
            "✨ Поддерживаются Telegram Premium эмодзи!"
        ),
        'reply_markup': reply_markup
    }

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
    
    if setup['step'] == 'edit_photo':
        if update.message.photo:
            broadcast_id = setup['broadcast_id']
            
            if broadcast_id in scheduled_broadcasts:
                if scheduled_broadcasts[broadcast_id]['photo']:
                    try:
                        os.remove(scheduled_broadcasts[broadcast_id]['photo'])
                    except:
                        pass
                
                photo_file = await update.message.photo[-1].get_file()
                photo_path = os.path.join(os.path.expanduser('~'), 'termux_bot', f'photo_broadcast_{broadcast_id}.jpg')
                await photo_file.download_to_drive(photo_path)
                
                scheduled_broadcasts[broadcast_id]['photo'] = photo_path
                
                del pending_setups[user_id]
                
                keyboard = [[InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ Фото рассылки *{broadcast_id}* обновлено!",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return "processing"
        else:
            await update.message.reply_text("❌ Отправь фото")
            return "processing"
    
    if setup['step'] == 'text':
        setup['text'] = update.message.text
        setup['step'] = 'photo'
        
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить фото", callback_data="skip_photo")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📸 *Шаг 2/4*\n\nОтправь фото для рассылки.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return "processing"
    
    if setup['step'] == 'photo':
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            photo_path = os.path.join(os.path.expanduser('~'), 'termux_bot', f'photo_{user_id}_{int(datetime.now().timestamp())}.jpg')
            await photo_file.download_to_drive(photo_path)
            setup['photo'] = photo_path
        
        setup['step'] = 'chats'
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои чаты", callback_data="dialogs")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💬 *Шаг 3/4*\n\n"
            "Отправь чаты через запятую.\n\n"
            "*Можно:* ID, @username или username\n\n"
            "*Пример:* `mychannel,mygroup,-1001234567890`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return "processing"
    
    if setup['step'] == 'chats':
        chat_inputs = [cid.strip() for cid in update.message.text.split(',')]
        processed_ids = []
        
        for cid in chat_inputs:
            cid = cid.strip()
            if cid.startswith('@'):
                processed_ids.append(cid)
            else:
                try:
                    processed_ids.append(int(cid))
                except:
                    if not cid.startswith('-'):
                        processed_ids.append(f"@{cid}")
                    else:
                        processed_ids.append(cid)
        
        setup['chats'] = processed_ids
        setup['step'] = 'interval'
        
        keyboard = [
            [InlineKeyboardButton("1 мин", callback_data="interval_1")],
            [InlineKeyboardButton("5 мин", callback_data="interval_5")],
            [InlineKeyboardButton("30 мин", callback_data="interval_30")],
            [InlineKeyboardButton("1 час", callback_data="interval_60")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⏰ *Шаг 4/4*\n\n"
            "Укажи интервал рассылки.\n"
            "Выбери кнопку или отправь число (минуты):",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return "processing"
    
    if setup['step'] == 'interval':
        try:
            interval = int(update.message.text)
            
            if interval < 1:
                await update.message.reply_text("❌ Минимум 1 минута")
                return "processing"
            
            return await finalize_broadcast(update, context, setup, interval)
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введи число (минуты)")
            return "processing"
    
    return None

async def finalize_broadcast(update, context, setup, interval):
    """Завершить создание рассылки"""
    global broadcast_counter
    broadcast_counter += 1
    broadcast_id = broadcast_counter
    
    scheduled_broadcasts[broadcast_id] = {
        'text': setup['text'],
        'photo': setup['photo'],
        'chats': setup['chats'],
        'interval': interval,
        'active': True,
        'last_run': None,
        'total_sent': 0,
        'total_failed': 0
    }
    
    task = asyncio.create_task(run_broadcast_loop(broadcast_id))
    broadcast_tasks[broadcast_id] = task
    
    user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.message.from_user.id
    if user_id in pending_setups:
        del pending_setups[user_id]
    
    chats_display = ', '.join([f"`{c}`" for c in setup['chats'][:3]])
    if len(setup['chats']) > 3:
        chats_display += f" и ещё {len(setup['chats']) - 3}"
    
    keyboard = [
        [InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")],
        [InlineKeyboardButton("⏸ Остановить", callback_data=f"stop_{broadcast_id}")],
        [InlineKeyboardButton("📋 Все рассылки", callback_data="list_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"✅ *Рассылка создана!*\n\n"
        f"🆔 ID: `{broadcast_id}`\n"
        f"📝 {setup['text'][:50]}{'...' if len(setup['text']) > 50 else ''}\n"
        f"📸 Фото: {'✅' if setup['photo'] else '❌'}\n"
        f"💬 Чаты: {chats_display}\n"
        f"⏰ Интервал: *{interval} мин*\n\n"
        f"🚀 Рассылка запущена!"
    )
    
    return {'text': text, 'reply_markup': reply_markup}

async def skip_photo(update, context):
    user_id = update.effective_user.id
    if user_id in pending_setups and pending_setups[user_id]['step'] == 'photo':
        pending_setups[user_id]['step'] = 'chats'
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои чаты", callback_data="dialogs")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return {
            'text': "💬 *Шаг 3/4*\n\nОтправь чаты через запятую.",
            'reply_markup': reply_markup
        }
    return "Нет активной настройки"

async def run_broadcast_loop(broadcast_id):
    logger.info(f"🚀 Запущена рассылка {broadcast_id}")
    
    while True:
        if broadcast_id not in scheduled_broadcasts:
            logger.info(f"⏹ Рассылка {broadcast_id} удалена")
            break
        
        broadcast = scheduled_broadcasts[broadcast_id]
        
        if not broadcast['active']:
            logger.info(f"⏸ Рассылка {broadcast_id} остановлена")
            break
        
        try:
            logger.info(f"📤 Начало рассылки {broadcast_id}")
            
            client = await get_userbot()
            
            success = 0
            failed = 0
            
            for chat_id in broadcast['chats']:
                if broadcast_id not in scheduled_broadcasts or not scheduled_broadcasts[broadcast_id]['active']:
                    logger.info(f"⏹ Рассылка {broadcast_id} остановлена во время выполнения")
                    return
                
                try:
                    if broadcast['photo']:
                        await client.send_file(
                            chat_id,
                            broadcast['photo'],
                            caption=broadcast['text'],
                            parse_mode='html'
                        )
                    else:
                        await client.send_message(
                            chat_id, 
                            broadcast['text'],
                            parse_mode='html'
                        )
                    
                    success += 1
                    logger.info(f"✅ Отправлено в {chat_id}")
                    await asyncio.sleep(2)
                    
                except FloodWaitError as e:
                    logger.warning(f"⏱ FloodWait {e.seconds} сек")
                    await asyncio.sleep(e.seconds)
                    try:
                        if broadcast['photo']:
                            await client.send_file(chat_id, broadcast['photo'], caption=broadcast['text'])
                        else:
                            await client.send_message(chat_id, broadcast['text'])
                        success += 1
                    except:
                        failed += 1
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"❌ Ошибка: {e}")
            
            if broadcast_id in scheduled_broadcasts:
                scheduled_broadcasts[broadcast_id]['last_run'] = datetime.now()
                scheduled_broadcasts[broadcast_id]['total_sent'] += success
                scheduled_broadcasts[broadcast_id]['total_failed'] += failed
            
            logger.info(f"✅ Рассылка {broadcast_id}: {success} успешно, {failed} ошибок")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка {broadcast_id}: {e}")
        
        if broadcast_id not in scheduled_broadcasts or not scheduled_broadcasts[broadcast_id]['active']:
            break
        
        interval_seconds = broadcast['interval'] * 60
        logger.info(f"⏰ Рассылка {broadcast_id} ждёт {broadcast['interval']} мин")
        
        for _ in range(int(interval_seconds / 10)):
            await asyncio.sleep(10)
            if broadcast_id not in scheduled_broadcasts or not scheduled_broadcasts[broadcast_id]['active']:
                return
        
        remaining = interval_seconds % 10
        if remaining > 0:
            await asyncio.sleep(remaining)
    
    logger.info(f"🏁 Цикл рассылки {broadcast_id} завершён")

async def list_broadcasts(update, context):
    if not scheduled_broadcasts:
        keyboard = [[InlineKeyboardButton("➕ Создать рассылку", callback_data="create_new")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return {
            'text': "📭 Нет активных рассылок",
            'reply_markup': reply_markup
        }
    
    text = f"📋 *Рассылки ({len(scheduled_broadcasts)}):*\n\n"
    keyboard = []
    
    for bid, broadcast in scheduled_broadcasts.items():
        status_icon = "✅" if broadcast['active'] else "⏸"
        
        text += f"{status_icon} *ID {bid}* - {broadcast['interval']} мин\n"
        text += f"📝 _{broadcast['text'][:30]}..._\n"
        text += f"💬 {len(broadcast['chats'])} чатов | 📊 {broadcast['total_sent']} отправлено\n\n"
        
        keyboard.append([
            InlineKeyboardButton(f"📋 ID {bid}", callback_data=f"show_{bid}"),
            InlineKeyboardButton("⏸" if broadcast['active'] else "▶️", callback_data=f"toggle_{bid}"),
            InlineKeyboardButton("🗑", callback_data=f"delete_{bid}")
        ])
    
    keyboard.append([InlineKeyboardButton("🛑 Остановить ВСЕ", callback_data="stop_all")])
    keyboard.append([InlineKeyboardButton("➕ Создать новую", callback_data="create_new")])
    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="list_all")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return {'text': text, 'reply_markup': reply_markup}

async def stop_all_broadcasts(update, context):
    """Остановить ВСЕ рассылки"""
    if not scheduled_broadcasts:
        return "📭 Нет активных рассылок"
    
    stopped_count = 0
    
    for broadcast_id in list(scheduled_broadcasts.keys()):
        if scheduled_broadcasts[broadcast_id]['active']:
            scheduled_broadcasts[broadcast_id]['active'] = False
            
            if broadcast_id in broadcast_tasks:
                task = broadcast_tasks[broadcast_id]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del broadcast_tasks[broadcast_id]
            
            stopped_count += 1
            logger.info(f"⏹ Рассылка {broadcast_id} остановлена (stop_all)")
    
    keyboard = [
        [InlineKeyboardButton("📋 Список", callback_data="list_all")],
        [InlineKeyboardButton("▶️ Возобновить все", callback_data="resume_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return {
        'text': f"🛑 Остановлено рассылок: *{stopped_count}*",
        'reply_markup': reply_markup
    }

async def resume_all_broadcasts(update, context):
    """Возобновить ВСЕ рассылки"""
    if not scheduled_broadcasts:
        return "📭 Нет рассылок"
    
    resumed_count = 0
    
    for broadcast_id in list(scheduled_broadcasts.keys()):
        if not scheduled_broadcasts[broadcast_id]['active']:
            scheduled_broadcasts[broadcast_id]['active'] = True
            
            task = asyncio.create_task(run_broadcast_loop(broadcast_id))
            broadcast_tasks[broadcast_id] = task
            
            resumed_count += 1
            logger.info(f"▶️ Рассылка {broadcast_id} возобновлена (resume_all)")
    
    keyboard = [[InlineKeyboardButton("📋 Список", callback_data="list_all")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return {
        'text': f"▶️ Возобновлено рассылок: *{resumed_count}*",
        'reply_markup': reply_markup
    }

async def stop_broadcast(update, context):
    if not context.args:
        return "❌ Используй: `/scheduler_stop <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            scheduled_broadcasts[broadcast_id]['active'] = False
            
            if broadcast_id in broadcast_tasks:
                task = broadcast_tasks[broadcast_id]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del broadcast_tasks[broadcast_id]
            
            logger.info(f"⏸ Рассылка {broadcast_id} остановлена")
            
            keyboard = [
                [InlineKeyboardButton("▶️ Возобновить", callback_data=f"resume_{broadcast_id}")],
                [InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")],
                [InlineKeyboardButton("📋 Все", callback_data="list_all")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {
                'text': f"⏸ Рассылка *{broadcast_id}* остановлена",
                'reply_markup': reply_markup
            }
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
                
                task = asyncio.create_task(run_broadcast_loop(broadcast_id))
                broadcast_tasks[broadcast_id] = task
                
                logger.info(f"▶️ Рассылка {broadcast_id} возобновлена")
                
                keyboard = [
                    [InlineKeyboardButton("⏸ Остановить", callback_data=f"stop_{broadcast_id}")],
                    [InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                return {
                    'text': f"▶️ Рассылка *{broadcast_id}* возобновлена",
                    'reply_markup': reply_markup
                }
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
            if broadcast_id in broadcast_tasks:
                task = broadcast_tasks[broadcast_id]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del broadcast_tasks[broadcast_id]
            
            if scheduled_broadcasts[broadcast_id]['photo']:
                try:
                    os.remove(scheduled_broadcasts[broadcast_id]['photo'])
                except:
                    pass
            
            del scheduled_broadcasts[broadcast_id]
            
            logger.info(f"🗑 Рассылка {broadcast_id} удалена")
            
            keyboard = [[InlineKeyboardButton("📋 Список", callback_data="list_all")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {
                'text': f"🗑 Рассылка *{broadcast_id}* удалена",
                'reply_markup': reply_markup
            }
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def show_broadcast(update, context):
    if not context.args:
        return "❌ Используй: `/scheduler_show <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            broadcast = scheduled_broadcasts[broadcast_id]
            
            status = "✅ Активна" if broadcast['active'] else "⏸ Остановлена"
            
            chats_display = ""
            for i, chat in enumerate(broadcast['chats'][:5], 1):
                chats_display += f"{i}. `{chat}`\n"
            if len(broadcast['chats']) > 5:
                chats_display += f"...и ещё {len(broadcast['chats']) - 5}"
            
            text = (
                f"📋 *Рассылка {broadcast_id}*\n\n"
                f"🔘 Статус: {status}\n\n"
                f"📝 *Текст:*\n_{broadcast['text']}_\n\n"
                f"📸 Фото: {'✅ Да' if broadcast['photo'] else '❌ Нет'}\n\n"
                f"💬 *Чаты ({len(broadcast['chats'])}):*\n{chats_display}\n\n"
                f"⏰ Интервал: *{broadcast['interval']} мин*\n"
            )
            
            if broadcast['last_run']:
                text += f"🕐 Последняя: {broadcast['last_run'].strftime('%d.%m %H:%M:%S')}\n"
            
            text += f"📊 Отправлено: {broadcast['total_sent']} | Ошибок: {broadcast['total_failed']}"
            
            keyboard = []
            
            if broadcast['active']:
                keyboard.append([InlineKeyboardButton("⏸ Остановить", callback_data=f"stop_{broadcast_id}")])
            else:
                keyboard.append([InlineKeyboardButton("▶️ Возобновить", callback_data=f"resume_{broadcast_id}")])
            
            keyboard.append([
                InlineKeyboardButton("✏️ Текст", callback_data=f"edit_text_{broadcast_id}"),
                InlineKeyboardButton("📸 Фото", callback_data=f"edit_photo_{broadcast_id}")
            ])
            keyboard.append([
                InlineKeyboardButton("💬 Чаты", callback_data=f"edit_chats_{broadcast_id}"),
                InlineKeyboardButton("⏰ Интервал", callback_data=f"edit_interval_{broadcast_id}")
            ])
            keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{broadcast_id}")])
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="list_all")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {'text': text, 'reply_markup': reply_markup}
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def edit_text(update, context):
    if not context.args or len(context.args) < 2:
        return "❌ `/scheduler_edit_text <id> <новый текст>`"
    
    try:
        broadcast_id = int(context.args[0])
        new_text = " ".join(context.args[1:])
        
        if broadcast_id in scheduled_broadcasts:
            scheduled_broadcasts[broadcast_id]['text'] = new_text
            
            keyboard = [[InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {
                'text': f"✅ Текст рассылки *{broadcast_id}* изменён",
                'reply_markup': reply_markup
            }
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def edit_photo(update, context):
    if not context.args:
        return "❌ `/scheduler_edit_photo <id>` затем отправь фото"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            user_id = update.effective_user.id
            
            pending_setups[user_id] = {
                'step': 'edit_photo',
                'broadcast_id': broadcast_id,
                'text': None,
                'photo': None,
                'chats': None,
                'interval': None
            }
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_setup")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {
                'text': f"📸 Отправь новое фото для рассылки *{broadcast_id}*",
                'reply_markup': reply_markup
            }
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def remove_photo(update, context):
    if not context.args:
        return "❌ `/scheduler_remove_photo <id>`"
    
    try:
        broadcast_id = int(context.args[0])
        
        if broadcast_id in scheduled_broadcasts:
            if scheduled_broadcasts[broadcast_id]['photo']:
                try:
                    os.remove(scheduled_broadcasts[broadcast_id]['photo'])
                except:
                    pass
                
                scheduled_broadcasts[broadcast_id]['photo'] = None
                
                keyboard = [[InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                return {
                    'text': f"🗑 Фото удалено из рассылки *{broadcast_id}*",
                    'reply_markup': reply_markup
                }
            else:
                return f"⚠️ В рассылке {broadcast_id} нет фото"
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def edit_chats(update, context):
    if not context.args or len(context.args) < 2:
        return "❌ `/scheduler_edit_chats <id> <чаты>`"
    
    try:
        broadcast_id = int(context.args[0])
        chat_inputs = " ".join(context.args[1:]).split(',')
        
        if broadcast_id in scheduled_broadcasts:
            processed_ids = []
            
            for cid in chat_inputs:
                cid = cid.strip()
                if cid.startswith('@'):
                    processed_ids.append(cid)
                else:
                    try:
                        processed_ids.append(int(cid))
                    except:
                        if not cid.startswith('-'):
                            processed_ids.append(f"@{cid}")
                        else:
                            processed_ids.append(cid)
            
            scheduled_broadcasts[broadcast_id]['chats'] = processed_ids
            
            keyboard = [[InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {
                'text': f"✅ Чаты рассылки *{broadcast_id}* изменены\n\nЧатов: {len(processed_ids)}",
                'reply_markup': reply_markup
            }
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный ID"

async def edit_interval(update, context):
    if not context.args or len(context.args) < 2:
        return "❌ `/scheduler_edit_interval <id> <минуты>`"
    
    try:
        broadcast_id = int(context.args[0])
        new_interval = int(context.args[1])
        
        if new_interval < 1:
            return "❌ Минимум 1 минута"
        
        if broadcast_id in scheduled_broadcasts:
            scheduled_broadcasts[broadcast_id]['interval'] = new_interval
            
            keyboard = [[InlineKeyboardButton("📋 Детали", callback_data=f"show_{broadcast_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return {
                'text': f"✅ Интервал рассылки *{broadcast_id}* изменён на {new_interval} мин",
                'reply_markup': reply_markup
            }
        else:
            return f"❌ Рассылка {broadcast_id} не найдена"
    except ValueError:
        return "❌ Неверный формат"

async def get_dialogs(update, context):
    try:
        client = await get_userbot()
        dialogs = await client.get_dialogs(limit=50)
        
        text = "💬 *Твои чаты:*\n\n"
        
        for i, dialog in enumerate(dialogs, 1):
            entity = dialog.entity
            
            chat_id = f"`{dialog.id}`"
            
            username = ""
            if hasattr(entity, 'username') and entity.username:
                username = f" `@{entity.username}`"
            
            name = dialog.name or "Без имени"
            
            text += f"{i}. {chat_id}{username}\n   {name}\n\n"
            
            if i >= 20:  # Ограничение для читаемости
                text += f"...и ещё {len(dialogs) - 20}"
                break
        
        keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data="dialogs")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return {'text': text, 'reply_markup': reply_markup}
    except Exception as e:
        return f"❌ Ошибка: {e}\n\nСначала: `/scheduler_login`"

# Обработчик callback кнопок
async def handle_callback(update, context):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Логика обработки
    if data == "list_all":
        result = await list_broadcasts(update, context)
    elif data == "create_new":
        result = await start_broadcast(update, context)
    elif data == "dialogs":
        result = await get_dialogs(update, context)
    elif data == "login":
        result = await login(update, context)
    elif data == "cancel_setup":
        result = await cancel(update, context)
    elif data == "skip_photo":
        result = await skip_photo(update, context)
    elif data == "stop_all":
        result = await stop_all_broadcasts(update, context)
    elif data == "resume_all":
        result = await resume_all_broadcasts(update, context)
    elif data.startswith("show_"):
        broadcast_id = int(data.split("_")[1])
        context.args = [str(broadcast_id)]
        result = await show_broadcast(update, context)
    elif data.startswith("stop_"):
        broadcast_id = int(data.split("_")[1])
        context.args = [str(broadcast_id)]
        result = await stop_broadcast(update, context)
    elif data.startswith("resume_"):
        broadcast_id = int(data.split("_")[1])
        context.args = [str(broadcast_id)]
        result = await resume_broadcast(update, context)
    elif data.startswith("delete_"):
        broadcast_id = int(data.split("_")[1])
        context.args = [str(broadcast_id)]
        result = await delete_broadcast(update, context)
    elif data.startswith("toggle_"):
        broadcast_id = int(data.split("_")[1])
        if scheduled_broadcasts[broadcast_id]['active']:
            context.args = [str(broadcast_id)]
            result = await stop_broadcast(update, context)
        else:
            context.args = [str(broadcast_id)]
            result = await resume_broadcast(update, context)
    elif data.startswith("interval_"):
        # Быстрый выбор интервала
        interval = int(data.split("_")[1])
        user_id = query.from_user.id
        if user_id in pending_setups:
            setup = pending_setups[user_id]
            result = await finalize_broadcast(query, context, setup, interval)
        else:
            result = "Ошибка настройки"
    else:
        result = "Неизвестная команда"
    
    # Отправка результата
    if isinstance(result, dict):
        await query.edit_message_text(
            text=result['text'],
            parse_mode='Markdown',
            reply_markup=result.get('reply_markup')
        )
    else:
        await query.edit_message_text(text=str(result), parse_mode='Markdown')

COMMANDS = {
    'login': login,
    'start': start_broadcast,
    'cancel': cancel,
    'skip': skip_photo,
    'list': list_broadcasts,
    'stop': stop_broadcast,
    'resume': resume_broadcast,
    'delete': delete_broadcast,
    'dialogs': get_dialogs,
    'show': show_broadcast,
    'edit_text': edit_text,
    'edit_photo': edit_photo,
    'edit_chats': edit_chats,
    'edit_interval': edit_interval,
    'remove_photo': remove_photo,
    'stop_all': stop_all_broadcasts,
    'resume_all': resume_all_broadcasts
}

async def handle_user_input(update, context):
    return await handle_message(update, context)