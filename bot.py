import os
import subprocess
from telegram import Update, CallbackQuery
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from plugin_manager import PluginManager
import config
import logging

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
plugin_manager = PluginManager(config.PLUGINS_DIR)

def is_authorized(user_id):
    return user_id in config.ALLOWED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
    plugins = plugin_manager.get_plugin_list()
    
    text = "🤖 *Terminal Bot*\n\n"
    text += f"📦 Плагинов: {len(plugins)}\n"
    text += f"⚡ Команд: {len(plugin_manager.commands)}\n\n"
    text += "*Основные команды:*\n"
    text += "`/start` - Это меню\n"
    text += "`/plugins` - Список плагинов\n"
    text += "`/reload` - Перезагрузить\n\n"
    text += "*Доступные плагины:*\n\n"
    
    for p in plugins:
        text += f"📦 *{p['name']}*\n"
        text += f"   _{p['info'].get('description', '')}_\n"
        
        # Показать только первые 5 команд каждого плагина
        commands_to_show = p['commands'][:5]
        for cmd in commands_to_show:
            text += f"   • `/{p['name']}_{cmd}`\n"
        
        if len(p['commands']) > 5:
            text += f"   _...и ещё {len(p['commands']) - 5} команд_\n"
        
        text += "\n"
    
    text += "💻 Или отправь команду shell (без /)"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def plugins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    
    plugins = plugin_manager.get_plugin_list()
    
    text = f"📦 *Плагины ({len(plugins)})*\n\n"
    
    for p in plugins:
        text += f"▫️ *{p['name']}*\n"
        text += f"   {p['info'].get('description', '')}\n"
        text += f"   Команд: {len(p['commands'])}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def reload_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    
    await update.message.reply_text("🔄 Перезагрузка плагинов...")
    
    # Очистить старые обработчики команд плагинов
    handlers_to_remove = []
    for handler in context.application.handlers[0]:
        if isinstance(handler, CommandHandler):
            for cmd in handler.commands:
                if '_' in cmd:  # Команды плагинов содержат подчёркивание
                    handlers_to_remove.append(handler)
                    break
    
    for handler in handlers_to_remove:
        context.application.handlers[0].remove(handler)
    
    # Перезагрузить плагины
    plugin_manager.load_plugins()
    
    # Зарегистрировать новые команды
    for cmd_name in plugin_manager.commands.keys():
        context.application.add_handler(CommandHandler(cmd_name, handle_plugin_command))
    
    await update.message.reply_text(
        f"✅ Готово!\n"
        f"📦 Плагинов: {len(plugin_manager.plugins)}\n"
        f"⚡ Команд: {len(plugin_manager.commands)}"
    )

async def handle_plugin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команд плагинов"""
    if not is_authorized(update.effective_user.id):
        return
    
    command = update.message.text[1:]  # Убрать /
    
    try:
        result = await plugin_manager.execute_command(command, update=update, context=context)
        
        if result:
            # Проверить это dict с кнопками или обычный текст
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
                # Обычный текст
                text = str(result)
                if len(text) > 4000:
                    text = text[:4000] + "\n...(обрезано)"
                
                await update.message.reply_text(text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Ошибка команды {command}: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на inline кнопки"""
    if not is_authorized(update.effective_user.id):
        query = update.callback_query
        await query.answer("❌ Access Denied!")
        return
    
    # Передать обработку в плагин scheduler если он есть
    if 'scheduler' in plugin_manager.plugins:
        scheduler_module = plugin_manager.plugins['scheduler']['module']
        if hasattr(scheduler_module, 'handle_callback'):
            try:
                await scheduler_module.handle_callback(update, context)
            except Exception as e:
                logger.error(f"Ошибка обработки callback: {e}")
                query = update.callback_query
                await query.answer(f"❌ Ошибка: {e}")

async def handle_text_and_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста и фото - сначала проверяем плагины, потом shell"""
    if not is_authorized(update.effective_user.id):
        return
    
    # Проверить плагин scheduler на наличие активной настройки
    if 'scheduler' in plugin_manager.plugins:
        scheduler_module = plugin_manager.plugins['scheduler']['module']
        if hasattr(scheduler_module, 'pending_setups'):
            user_id = update.effective_user.id
            if user_id in scheduler_module.pending_setups:
                # Пользователь в процессе настройки рассылки
                result = await scheduler_module.handle_message(update, context)
                
                # Если результат dict с кнопками - отправить их
                if isinstance(result, dict):
                    await update.message.reply_text(
                        result['text'],
                        parse_mode='Markdown',
                        reply_markup=result.get('reply_markup')
                    )
                
                return
    
    # Если это не настройка рассылки - выполнить как shell команду (только для текста)
    if update.message.text:
        await execute_shell(update, context)

async def execute_shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнение shell команд"""
    if not is_authorized(update.effective_user.id):
        return
    
    command = update.message.text
    
    # Проверка опасных команд
    if any(d in command for d in config.DANGEROUS_COMMANDS):
        await update.message.reply_text("⛔ Опасная команда заблокирована!")
        return
    
    await update.message.reply_text(f"⚙️ Выполняю: `{command}`", parse_mode='Markdown')
    
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
            output = "✅ Команда выполнена"
        
        # Ограничение длины вывода
        if len(output) > config.MAX_OUTPUT_LENGTH:
            output = output[:config.MAX_OUTPUT_LENGTH] + "\n...(обрезано)"
        
        await update.message.reply_text(f"```\n{output}\n```", parse_mode='Markdown')
        
        # Показать текущую директорию
        current_dir = os.getcwd()
        await update.message.reply_text(f"📁 `{current_dir}`", parse_mode='Markdown')
    
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Таймаут! Команда выполнялась слишком долго")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка:\n```\n{str(e)}\n```", parse_mode='Markdown')

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск Terminal Bot...")
    
    # Загрузить все плагины
    plugin_manager.load_plugins()
    
    # Создать приложение
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Основные команды бота
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plugins", plugins_list))
    app.add_handler(CommandHandler("reload", reload_plugins))
    
    # Команды плагинов
    for cmd_name in plugin_manager.commands.keys():
        app.add_handler(CommandHandler(cmd_name, handle_plugin_command))
        logger.info(f"  Зарегистрирована команда: /{cmd_name}")
    
    # Обработчик inline кнопок (для scheduler и других плагинов с кнопками)
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Обработчик фото (для scheduler при загрузке фото)
    app.add_handler(MessageHandler(filters.PHOTO, handle_text_and_photo))
    
    # Обработчик текстовых сообщений (shell команды + настройка плагинов)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_and_photo))
    
    # Вывод статистики
    logger.info("✅ Бот запущен и готов к работе!")
    logger.info(f"📦 Загружено плагинов: {len(plugin_manager.plugins)}")
    logger.info(f"⚡ Зарегистрировано команд: {len(plugin_manager.commands)}")
    
    # Список плагинов
    for plugin_name, plugin_data in plugin_manager.plugins.items():
        logger.info(f"  • {plugin_name} v{plugin_data['info'].get('version', '1.0')}")
    
    # Запустить polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()