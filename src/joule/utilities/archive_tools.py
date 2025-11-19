import zipfile
import json
from dataclasses import dataclass, asdict

def read_metadata(path) -> dict:
    """
    returns the metadata, raises ValueError if path is not a valid Joule archive
    """
    try:
        with(zipfile.ZipFile(path, 'r') as zip,
                zip.open("metadata.json") as f):
            metadata = json.load(f)
            if 'magic' not in metadata or metadata['magic']!='joule-data-archive-bundle':
                raise ValueError()
            return metadata
    except:
        raise ValueError() # propogate any exceptions as a ValueError to simplify downstream handlers
    
class ImportLogger:
    def __init__(self):
        self._source_label = None
        # for data and event streams, destination = path
        # for modules, destination = module name
        self._destination = None
        self._target_type = None # data_stream, event_stream, or module
        self._info = []
        self._warnings = []
        self._errors = []
    
    def set_metadata(self,source_label,destination,target_type):
        self._source_label = source_label
        self._destination = destination
        self._target_type = target_type
    
    def info(self,msg):
        self._info.append(LogMessage(self._source_label,self._destination,msg,self._target_type))
    
    def warning(self, msg):
        self._warnings.append(LogMessage(self._source_label,self._destination,msg,self._target_type))
    
    def error(self, msg):
        self._errors.append(LogMessage(self._source_label,self._destination,msg,self._target_type))

    def to_json(self):
        return {
            'info': [asdict(x) for x in self._info],
            'warnings': [asdict(x) for x in  self._warnings],
            'errors': [asdict(x) for x in self._errors]
        }
    
    def from_json(self, json_data):
        self._info     = [LogMessage(item['source_label'],item['destination'],item['message'],item['target_type']) for item in json_data['info']]
        self._warnings = [LogMessage(item['source_label'],item['destination'],item['message'],item['target_type']) for item in json_data['warnings']]
        self._errors   = [LogMessage(item['source_label'],item['destination'],item['message'],item['target_type']) for item in json_data['errors']]

    @property
    def success(self):
        if len(self._warnings)>0 or len(self._errors)>0:
            return False
        else:
            return True
    @property
    def warning_messages(self):
        return self._warnings
    
    @property
    def info_messages(self):
        return self._info
    
    @property
    def error_messages(self):
        return self._errors
    
@dataclass
class LogMessage:
    source_label: str
    destination: str
    message: str
    target_type: str