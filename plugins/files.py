import os

PLUGIN_INFO = {
    'name': 'Files',
    'version': '1.0',
    'description': 'Файловый менеджер'
}

async def ls(update, context):
    files = os.listdir('.')
    text = f"📁 *Текущая папка:*\n`{os.getcwd()}`\n\n"
    dirs = [f for f in files if os.path.isdir(f)]
    files_list = [f for f in files if os.path.isfile(f)]
    if dirs:
        text += "📂 *Папки:*\n"
        for d in dirs[:20]:
            text += f"  📁 {d}\n"
    if files_list:
        text += "\n📄 *Файлы:*\n"
        for f in files_list[:20]:
            text += f"  📄 {f}\n"
    return text

async def pwd(update, context):
    return f"📍 *Текущая папка:*\n`{os.getcwd()}`"

async def cd(update, context):
    if not context.args:
        return "❌ Используй: `/files_cd /путь`"
    path = " ".join(context.args)
    try:
        os.chdir(path)
        return f"✅ Переход в:\n`{os.getcwd()}`"
    except Exception as e:
        return f"❌ Ошибка: {e}"

async def home(update, context):
    os.chdir(os.path.expanduser('~'))
    return f"🏠 *Домашняя папка:*\n`{os.getcwd()}`"

async def sdcard(update, context):
    try:
        os.chdir('/sdcard')
        return f"💾 *SD карта:*\n`{os.getcwd()}`"
    except:
        return "❌ Нет доступа\n\nВыполни: `termux-setup-storage`"

COMMANDS = {
    'ls': ls,
    'pwd': pwd,
    'cd': cd,
    'home': home,
    'sdcard': sdcard
}