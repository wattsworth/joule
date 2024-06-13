# Shared validator functions for the backend and API tools
from typing import Dict
import json
from joule.errors import ConfigurationError

def validate_event_fields(fields: Dict[str, str]) -> Dict[str, str]:
    """ 
    make sure values are either string, numeric, or category
    category has a JSON formatted list of categories after a ':' for example:
        category:["cat1","cat2","cat3"]
    """
    if not isinstance(fields, dict):
        raise ConfigurationError(f"event_fields must be a dictionary, not a {type(fields).__name__}")
    for dt_string in fields.values():
        data_type = dt_string.split(':')[0]
        if data_type not in ['string', 'numeric','category']:
            raise ConfigurationError("invalid value in event_fields, must be [numeric|string|category:cat1,cat2,...]")
        if data_type == 'category':
            try:
                # make sure there is a : and a JSON parseable list of strings after it
                if ':' not in dt_string:
                    raise ValueError()
                categories = json.loads(dt_string.split(':')[1])
                # make sure categories is a list of strings
                if not isinstance(categories, list):
                    raise ValueError()
                if len(categories) == 0:
                    raise ValueError()
                for category in categories:
                    if not isinstance(category, str):
                        raise ValueError()
            except (json.JSONDecodeError, ValueError):
                raise ConfigurationError("invalid value in event_fields, category type must a have JSON list of categories after a ':'")
    return fields
