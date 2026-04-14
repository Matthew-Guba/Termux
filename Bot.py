import os
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from plugin_manager import PluginManager
import config
import logging

logging.basicConfig(
    format='%(asctime)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

plugin_manager = PluginManager(config.PLUGINS_DIR)

def is_authorized(user_id):
    return user_id in config.ALLOWED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
    plugins = plugin_manager.get_plugin_list()
    
    text = f"🤖 *Terminal Bot*\n\n"
    text += f"📦 Плагинов: {len(plugins)}\n"
    text += f"⚡ Команд: {len(plugin_manager.commands)}\n\n"
    text += "*Команды:*\n"
    text += "/start - Помощь\n"
    text += "/plugins - Список плагинов\n"
    text += "/reload - Перезагрузить\n\n"
    
    for p in plugins:
        text += f"*{p['name']}*\n"
        for cmd in p['commands']:
            text += f"  /{p['name']}_{cmd}\n"
    
    text += "\n💻 Или отправь команду shell"
    
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
    
    await update.message.reply_text("🔄 Перезагрузка...")
    
    plugin_manager.load_plugins()
    
    for cmd_name in plugin_manager.commands.keys():
        context.application.add_handler(
            CommandHandler(cmd_name, handle_plugin_command)
        )
    
    await update.message.reply_text(f"✅ Готово! Плагинов: {len(plugin_manager.plugins)}")

async def handle_plugin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    
    command = update.message.text[1:]
    
    try:
        result = plugin_manager.execute_command(command, update=update, context=context)
        
        if result:
            if len(str(result)) > 4000:
                result = str(result)[:4000] + "\n...(обрезано)"
            await update.message.reply_text(str(result), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def execute_shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    
    command = update.message.text
    
    if any(d in command for d in config.DANGEROUS_COMMANDS):
        await update.message.reply_text("⛔ Опасная команда!")
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
        await update.message.reply_text(f"❌ {e}")

def main():
    logger.info("🚀 Запуск бота...")
    
    plugin_manager.load_plugins()
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plugins", plugins_list))
    app.add_handler(CommandHandler("reload", reload_plugins))
    
    for cmd_name in plugin_manager.commands.keys():
        app.add_handler(CommandHandler(cmd_name, handle_plugin_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, execute_shell))
    
    logger.info("✅ Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
