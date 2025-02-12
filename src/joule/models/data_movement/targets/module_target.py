
# Perform import and export operations for a module
class ModuleTarget:
    def __init__(self, source_label: str,
                 module_name: str,
                 workspace_directory: str,
                 config_parameters: str):
        self.source_label = source_label
        self.module_name = module_name
        self.workspace_directory = workspace_directory
        self.config_parameters = config_parameters

    async def run_export(self,
                         target_directory: str) -> dict:
        return {}
    
    async def run_import(self,
                         source_directory: str) -> bool:
        return True
    
def module_target_from_config(config: dict) -> ModuleTarget:
    return ModuleTarget(source_label=config['source_label'],
                        module_name=config['module'],
                        workspace_directory=None, # must be supplied before running an export or import operation
                        config_parameters=config.get('parameters', ''))