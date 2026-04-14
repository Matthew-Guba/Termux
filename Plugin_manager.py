import os
import importlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins_dir="plugins"):
        self.plugins_dir = plugins_dir
        self.plugins = {}
        self.commands = {}
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            open(os.path.join(plugins_dir, "__init__.py"), 'w').close()
    
    def load_plugins(self):
        self.plugins.clear()
        self.commands.clear()
        if not os.path.exists(self.plugins_dir):
            return
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                self._load_plugin(filename[:-3])
        logger.info(f"Загружено: {len(self.plugins)}")
    
    def _load_plugin(self, plugin_name):
        try:
            module_path = f"{self.plugins_dir}.{plugin_name}"
            if module_path in importlib.sys.modules:
                importlib.reload(importlib.sys.modules[module_path])
                module = importlib.sys.modules[module_path]
            else:
                module = importlib.import_module(module_path)
            if not hasattr(module, 'PLUGIN_INFO'):
                return
            self.plugins[plugin_name] = {
                'module': module,
                'info': module.PLUGIN_INFO,
                'commands': {}
            }
            if hasattr(module, 'COMMANDS'):
                for cmd_name, cmd_func in module.COMMANDS.items():
                    full_cmd_name = f"{plugin_name}_{cmd_name}"
                    self.commands[full_cmd_name] = cmd_func
                    self.plugins[plugin_name]['commands'][cmd_name] = cmd_func
            logger.info(f"OK: {plugin_name}")
        except Exception as e:
            logger.error(f"ERR: {plugin_name}: {e}")
    
    def get_plugin_list(self):
        return [
            {
                'name': n,
                'info': d['info'],
                'commands': list(d['commands'].keys())
            }
            for n, d in self.plugins.items()
        ]
    
    def get_command(self, command_name):
        return self.commands.get(command_name)
    
    def execute_command(self, command_name, *args, **kwargs):
        cmd_func = self.get_command(command_name)
        if cmd_func:
            return cmd_func(*args, **kwargs)
        return None
