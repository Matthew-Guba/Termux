import os
import importlib
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins_dir="plugins"):
        self.plugins_dir = plugins_dir
        self.plugins = {}
        self.commands = {}
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            with open(os.path.join(plugins_dir, "__init__.py"), 'w') as f:
                pass
    
    def load_plugins(self):
        self.plugins.clear()
        self.commands.clear()
        if not os.path.exists(self.plugins_dir):
            logger.warning(f"Папка {self.plugins_dir} не найдена")
            return
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                plugin_name = filename[:-3]
                self._load_plugin(plugin_name)
        logger.info(f"Загружено плагинов: {len(self.plugins)}")
        logger.info(f"Команд: {len(self.commands)}")
    
    def _load_plugin(self, plugin_name):
        try:
            module_path = f"{self.plugins_dir}.{plugin_name}"
            if module_path in importlib.sys.modules:
                importlib.reload(importlib.sys.modules[module_path])
                module = importlib.sys.modules[module_path]
            else:
                module = importlib.import_module(module_path)
            
            if not hasattr(module, 'PLUGIN_INFO'):
                logger.warning(f"Плагин {plugin_name} без PLUGIN_INFO")
                return
            
            plugin_info = module.PLUGIN_INFO
            
            self.plugins[plugin_name] = {
                'module': module,
                'info': plugin_info,
                'commands': {}
            }
            
            if hasattr(module, 'COMMANDS'):
                for cmd_name, cmd_func in module.COMMANDS.items():
                    full_cmd_name = f"{plugin_name}_{cmd_name}"
                    self.commands[full_cmd_name] = cmd_func
                    self.plugins[plugin_name]['commands'][cmd_name] = cmd_func
                    logger.info(f"  Команда: /{full_cmd_name}")
            
            logger.info(f"✓ {plugin_name}")
            
        except Exception as e:
            logger.error(f"✗ {plugin_name}: {e}")
            import traceback
            traceback.print_exc()
    
    def get_plugin_list(self):
        return [
            {
                'name': name,
                'info': data['info'],
                'commands': list(data['commands'].keys())
            }
            for name, data in self.plugins.items()
        ]
    
    def get_command(self, command_name):
        return self.commands.get(command_name)
    
    async def execute_command(self, command_name, *args, **kwargs):
        """Выполнить команду плагина"""
        cmd_func = self.get_command(command_name)
        if cmd_func:
            # Проверить это async функция или нет
            if asyncio.iscoroutinefunction(cmd_func):
                return await cmd_func(*args, **kwargs)
            else:
                return cmd_func(*args, **kwargs)
        return None