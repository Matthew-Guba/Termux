import os
import subprocess
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from plugin_manager import PluginManager
import config
import logging

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
plugin_manager = PluginManager(config.PLUGINS_DIR)

def is_authorized(user_id):
    return user_id in config.ALLOWED_USERS

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = [
        ['📋 Рассылка', '📊 Система', '📁 Файлы'],
        ['💻 Shell режим', '⚙️ Настройки']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_scheduler_keyboard():
    """Клавиатура для Scheduler"""
    keyboard = [
        ['➕ Создать рассылку', '📋 Список'],
        ['🛑 Остановить все', '▶️ Запустить все'],
        ['◀️ Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_system_keyboard():
    """Клавиатура для системной информации"""
    keyboard = [
        ['💻 CPU', '🧠 Память', '🔋 Батарея'],
        ['💾 Диски', '📱 Система'],
        ['◀️ Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_files_keyboard():
    """Клавиатура для файлового менеджера"""
    keyboard = [
        ['📂 Список', '📍 Где я', '🏠 Домой'],
        ['💾 SD карта', '⬆️ Вверх'],
        ['◀️ Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_shell_keyboard():
    """Клавиатура для Shell режима"""
    keyboard = [
        ['ls -la', 'pwd', 'df -h'],
        ['free -h', 'ps aux', 'uname -a'],
        ['◀️ Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_keyboard():
    """Клавиатура настроек"""
    keyboard = [
        ['🔄 Перезагрузить плагины', '📦 Список плагинов'],
        ['ℹ️ О боте'],
        ['◀️ Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
    # Показать главное меню
    context.user_data['mode'] = 'main'
    
    text = (
        "🤖 *Terminal Bot*\n\n"
        "Выбери раздел:\n\n"
        "📋 *Рассылка* - автоматическая рассылка с фото\n"
        "📊 *Система* - информация о системе\n"
        "📁 *Файлы* - файловый менеджер\n"
        "💻 *Shell режим* - выполнение команд\n"
        "⚙️ *Настройки* - управление ботом"
    )
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений и кнопок"""
    if not is_authorized(update.effective_user.id):
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    # Проверить активную настройку scheduler
    if 'scheduler' in plugin_manager.plugins:
        scheduler_module = plugin_manager.plugins['scheduler']['module']
        if hasattr(scheduler_module, 'pending_setups'):
            if user_id in scheduler_module.pending_setups:
                result = await scheduler_module.handle_message(update, context)
                
                if isinstance(result, dict):
                    await update.message.reply_text(
                        result['text'],
                        parse_mode='Markdown',
                        reply_markup=result.get('reply_markup')
                    )
                return
    
    # === ГЛАВНОЕ МЕНЮ ===
    if text == '📋 Рассылка':
        context.user_data['mode'] = 'scheduler'
        await update.message.reply_text(
            "📋 *Меню рассылки*\n\nВыбери действие:",
            parse_mode='Markdown',
            reply_markup=get_scheduler_keyboard()
        )
    
    elif text == '📊 Система':
        context.user_data['mode'] = 'system'
        await update.message.reply_text(
            "📊 *Системная информация*\n\nВыбери раздел:",
            parse_mode='Markdown',
            reply_markup=get_system_keyboard()
        )
    
    elif text == '📁 Файлы':
        context.user_data['mode'] = 'files'
        await update.message.reply_text(
            "📁 *Файловый менеджер*\n\nВыбери действие:",
            parse_mode='Markdown',
            reply_markup=get_files_keyboard()
        )
    
    elif text == '💻 Shell режим':
        context.user_data['mode'] = 'shell'
        await update.message.reply_text(
            "💻 *Shell режим*\n\nВыбери команду или введи свою:",
            parse_mode='Markdown',
            reply_markup=get_shell_keyboard()
        )
    
    elif text == '⚙️ Настройки':
        context.user_data['mode'] = 'settings'
        await update.message.reply_text(
            "⚙️ *Настройки*\n\nВыбери действие:",
            parse_mode='Markdown',
            reply_markup=get_settings_keyboard()
        )
    
    elif text == '◀️ Главное меню':
        context.user_data['mode'] = 'main'
        await start(update, context)
    
    # === РАССЫЛКА ===
    elif text == '➕ Создать рассылку':
        result = await execute_plugin_command('scheduler_start', update, context)
        if isinstance(result, dict):
            await update.message.reply_text(
                result['text'],
                parse_mode='Markdown',
                reply_markup=result.get('reply_markup')
            )
    
    elif text == '📋 Список':
        result = await execute_plugin_command('scheduler_list', update, context)
        if isinstance(result, dict):
            await update.message.reply_text(
                result['text'],
                parse_mode='Markdown',
                reply_markup=result.get('reply_markup')
            )
    
    elif text == '🛑 Остановить все':
        result = await execute_plugin_command('scheduler_stop_all', update, context)
        if isinstance(result, dict):
            await update.message.reply_text(
                result['text'],
                parse_mode='Markdown',
                reply_markup=result.get('reply_markup')
            )
    
    elif text == '▶️ Запустить все':
        result = await execute_plugin_command('scheduler_resume_all', update, context)
        if isinstance(result, dict):
            await update.message.reply_text(
                result['text'],
                parse_mode='Markdown',
                reply_markup=result.get('reply_markup')
            )
    
    # === СИСТЕМА ===
    elif text == '💻 CPU':
        result = await execute_plugin_command('system_info_cpu', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '🧠 Память':
        result = await execute_plugin_command('system_info_memory', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '🔋 Батарея':
        result = await execute_plugin_command('system_info_battery', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '💾 Диски':
        result = await execute_plugin_command('system_info_disk', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '📱 Система':
        result = await execute_plugin_command('system_info_system', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    # === ФАЙЛЫ ===
    elif text == '📂 Список':
        result = await execute_plugin_command('files_ls', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '📍 Где я':
        result = await execute_plugin_command('files_pwd', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '🏠 Домой':
        result = await execute_plugin_command('files_home', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '💾 SD карта':
        result = await execute_plugin_command('files_sdcard', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    elif text == '⬆️ Вверх':
        await execute_shell_command('cd ..', update, context)
        result = await execute_plugin_command('files_pwd', update, context)
        await update.message.reply_text(str(result), parse_mode='Markdown')
    
    # === НАСТРОЙКИ ===
    elif text == '🔄 Перезагрузить плагины':
        await reload_plugins(update, context)
    
    elif text == '📦 Список плагинов':
        await plugins_list(update, context)
    
    elif text == 'ℹ️ О боте':
        await show_about(update, context)
    
    # === SHELL КОМАНДЫ ИЗ КНОПОК ===
    elif text in ['ls -la', 'pwd', 'df -h', 'free -h', 'ps aux', 'uname -a']:
        await execute_shell_command(text, update, context)
    
    # === СВОБОДНЫЙ ВВОД ===
    else:
        # Определить режим
        mode = context.user_data.get('mode', 'main')
        
        if mode == 'shell' or text.startswith('/') is False:
            # Shell команда
            await execute_shell_command(text, update, context)
        else:
            await update.message.reply_text(
                "❓ Неизвестная команда. Используй кнопки меню или `/start`"
            )

async def execute_plugin_command(command_name, update, context):
    """Выполнить команду плагина"""
    try:
        result = await plugin_manager.execute_command(command_name, update=update, context=context)
        return result
    except Exception as e:
        logger.error(f"Ошибка команды {command_name}: {e}")
        return f"❌ Ошибка: {e}"

async def execute_shell_command(command, update, context):
    """Выполнить shell команду"""
    if any(d in command for d in config.DANGEROUS_COMMANDS):
        await update.message.reply_text("⛔ Опасная команда заблокирована!")
        return
    
    await update.message.reply_text(f"⚙️ `{command}`", parse_mode='Markdown')
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=config.COMMAND_TIMEOUT,
            cwd=os.getcwd()
        )
        
        output = result.stdout if result.stdout else result.stderr
        if not output:
            output = "✅ Выполнено"
        
        if len(output) > config.MAX_OUTPUT_LENGTH:
            output = output[:config.MAX_OUTPUT_LENGTH] + "\n...(обрезано)"
        
        await update.message.reply_text(f"```\n{output}\n```", parse_mode='Markdown')
        await update.message.reply_text(f"📁 `{os.getcwd()}`", parse_mode='Markdown')
    
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Таймаут!")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото (для scheduler)"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Проверить активную настройку scheduler
    if 'scheduler' in plugin_manager.plugins:
        scheduler_module = plugin_manager.plugins['scheduler']['module']
        if hasattr(scheduler_module, 'pending_setups'):
            if user_id in scheduler_module.pending_setups:
                result = await scheduler_module.handle_message(update, context)
                
                if isinstance(result, dict):
                    await update.message.reply_text(
                        result['text'],
                        parse_mode='Markdown',
                        reply_markup=result.get('reply_markup')
                    )
                return
    
    await update.message.reply_text("❓ Фото получено, но нет активной настройки рассылки")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline кнопок"""
    if not is_authorized(update.effective_user.id):
        query = update.callback_query
        await query.answer("❌ Access Denied!")
        return
    
    if 'scheduler' in plugin_manager.plugins:
        scheduler_module = plugin_manager.plugins['scheduler']['module']
        if hasattr(scheduler_module, 'handle_callback'):
            try:
                await scheduler_module.handle_callback(update, context)
            except Exception as e:
                logger.error(f"Ошибка callback: {e}")
                query = update.callback_query
                await query.answer(f"❌ Ошибка: {e}")

async def plugins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список плагинов"""
    if not is_authorized(update.effective_user.id):
        return
    
    plugins = plugin_manager.get_plugin_list()
    
    text = f"📦 *Плагины ({len(plugins)})*\n\n"
    
    for p in plugins:
        text += f"▫️ *{p['name']}* v{p['info'].get('version', '1.0')}\n"
        text += f"   {p['info'].get('description', '')}\n"
        text += f"   Команд: {len(p['commands'])}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def reload_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезагрузка плагинов"""
    if not is_authorized(update.effective_user.id):
        return
    
    await update.message.reply_text("🔄 Перезагрузка плагинов...")
    
    # Очистить старые обработчики
    handlers_to_remove = []
    for handler in context.application.handlers[0]:
        if isinstance(handler, CommandHandler):
            for cmd in handler.commands:
                if '_' in cmd:
                    handlers_to_remove.append(handler)
                    break
    
    for handler in handlers_to_remove:
        context.application.handlers[0].remove(handler)
    
    # Перезагрузить
    plugin_manager.load_plugins()
    
    # Зарегистрировать команды
    for cmd_name in plugin_manager.commands.keys():
        context.application.add_handler(CommandHandler(cmd_name, handle_plugin_command))
    
    await update.message.reply_text(
        f"✅ Готово!\n📦 Плагинов: {len(plugin_manager.plugins)}\n⚡ Команд: {len(plugin_manager.commands)}"
    )

async def handle_plugin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команд плагинов через /"""
    if not is_authorized(update.effective_user.id):
        return
    
    command = update.message.text[1:]
    
    try:
        result = await plugin_manager.execute_command(command, update=update, context=context)
        
        if result:
            if isinstance(result, dict):
                text = result.get('text', str(result))
                reply_markup = result.get('reply_markup', None)
                
                if len(text) > 4000:
                    text = text[:4000] + "\n...(обрезано)"
                
                await update.message.reply_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                text = str(result)
                if len(text) > 4000:
                    text = text[:4000] + "\n...(обрезано)"
                
                await update.message.reply_text(text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Ошибка команды {command}: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о боте"""
    text = (
        "ℹ️ *Terminal Bot*\n\n"
        f"📦 Плагинов: {len(plugin_manager.plugins)}\n"
        f"⚡ Команд: {len(plugin_manager.commands)}\n\n"
        "*Возможности:*\n"
        "• 📋 Автоматическая рассылка с фото\n"
        "• 📊 Системная информация\n"
        "• 📁 Файловый менеджер\n"
        "• 💻 Выполнение shell команд\n"
        "• 🎮 Удобное управление кнопками\n\n"
        "*Версия:* 4.0\n"
        "*Создатель:* @username"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск Terminal Bot...")
    
    # Загрузить плагины
    plugin_manager.load_plugins()
    
    # Создать приложение
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Команда /start
    app.add_handler(CommandHandler("start", start))
    
    # Команды плагинов (через /)
    for cmd_name in plugin_manager.commands.keys():
        app.add_handler(CommandHandler(cmd_name, handle_plugin_command))
        logger.info(f"  /{cmd_name}")
    
    # Inline кнопки
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Фото
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Текстовые сообщения (кнопки и команды)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Статистика
    logger.info("✅ Бот запущен!")
    logger.info(f"📦 Плагинов: {len(plugin_manager.plugins)}")
    logger.info(f"⚡ Команд: {len(plugin_manager.commands)}")
    
    for plugin_name, plugin_data in plugin_manager.plugins.items():
        logger.info(f"  • {plugin_name} v{plugin_data['info'].get('version', '1.0')}")
    
    # Запуск
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()