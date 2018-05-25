
def run(path: str, db: Session):
    configs = _load_configs(path)
    configured_modules = _parse_configs(configs)
    for module in configured_modules:
        if(_connect_pipes(module, db)):
            db.add(module)