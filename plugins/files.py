import os

PLUGIN_INFO = {
    'name': 'Files',
    'version': '1.0',
    'description': 'Файловый менеджер'
}

async def ls(update, context):
    files = os.listdir('.')
    text = f"Папка: {os.getcwd()}\n\n"
    for f in files[:20]:
        text += f"  {f}\n"
    return text

async def pwd(update, context):
    return f"Текущая папка: {os.getcwd()}"

async def cd(update, context):
    if not context.args:
        return "Используй: /files_cd /путь"
    path = " ".join(context.args)
    try:
        os.chdir(path)
        return f"OK: {os.getcwd()}"
    except Exception as e:
        return f"Ошибка: {e}"

async def home(update, context):
    os.chdir(os.path.expanduser('~'))
    return f"Домой: {os.getcwd()}"

async def sdcard(update, context):
    try:
        os.chdir('/sdcard')
        return f"SD: {os.getcwd()}"
    except:
        return "Нет доступа"

COMMANDS = {
    'ls': ls,
    'pwd': pwd,
    'cd': cd,
    'home': home,
    'sdcard': sdcard
}