import subprocess
import platform

PLUGIN_INFO = {
    'name': 'System Info',
    'version': '1.0',
    'description': 'Системная информация'
}

def cmd(c):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except:
        return "N/A"

async def system(update, context):
    android = cmd("getprop ro.build.version.release")
    device = cmd("getprop ro.product.model")
    brand = cmd("getprop ro.product.brand")
    text = f"Система\n\n{brand} {device}\nAndroid {android}\n{platform.system()}\nPython {platform.python_version()}"
    return text

async def cpu(update, context):
    cores = cmd("nproc")
    uptime = cmd("uptime")
    text = f"CPU\n\nЯдер: {cores}\n\n{uptime}"
    return text

async def memory(update, context):
    mem = cmd("free -h")
    return f"Память\n\n{mem}"

async def disk(update, context):
    disk = cmd("df -h")
    return f"Диски\n\n{disk}"

async def battery(update, context):
    level = cmd("cat /sys/class/power_supply/battery/capacity 2>/dev/null")
    status = cmd("cat /sys/class/power_supply/battery/status 2>/dev/null")
    if level != "N/A":
        return f"Батарея\n\nЗаряд: {level}%\nСтатус: {status}"
    return "Данные недоступны"

COMMANDS = {
    'system': system,
    'cpu': cpu,
    'memory': memory,
    'disk': disk,
    'battery': battery
}