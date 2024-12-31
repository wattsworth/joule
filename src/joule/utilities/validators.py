# Shared validator functions for the backend and API tools
from typing import Dict
import json
from joule.errors import ConfigurationError
import re
from typing import Optional, List
from joule.constants import ApiErrorMessages

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
            except ValueError:
                raise ConfigurationError("invalid value in event_fields, category type must a have JSON list of categories after a ':'")
    return fields

def validate_event_filter(filter_string: str) -> List:
    """
    make sure the filter string syntax is valid
    boolean expression syntax: [[A,op,B]] where op is an operation in [is,not,like,unlike,gt,lt,gte,lte,eq,neq]
    AND clause is a list of boolean expressions
    OR clause is a list of AND clauses
    """
    try:
        filter_list = json.loads(filter_string)
    except json.JSONDecodeError:
        raise ConfigurationError(ApiErrorMessages.invalid_filter_json_syntax)
    if not isinstance(filter_list, list):
        raise ConfigurationError()
    for and_clause in filter_list:
        if not isinstance(and_clause, list):
            raise ConfigurationError(ApiErrorMessages.invalid_filter_parameter)
        for expr in and_clause:
            if not isinstance(expr, list):
                raise ConfigurationError(ApiErrorMessages.invalid_filter_parameter)
            if len(expr) != 3:
                raise ConfigurationError("invalid filter string, boolean expression must have 3 elements")
            if expr[1] not in ['is','not','like','unlike','gt','lt','gte','lte','eq','neq']:
                raise ConfigurationError("invalid filter string, boolean expression must have a valid operation")
            # if operation is like or unlike, make sure the value is a string
            if expr[1] in ['like','unlike','is','not']:
                if not isinstance(expr[2], str):
                    raise ConfigurationError("invalid filter string, is/not/like/unlike operation must have a string value")
            # first field must be a string label
            if not isinstance(expr[0], str):
                raise ConfigurationError("invalid filter string, first element of boolean expression must be a string label")
    return filter_list
    

def validate_monotonic_timestamps(data, last_ts: Optional[int], name: str):
    import numpy as np
    if len(data) == 0:
        return True
    # if there are multiple rows, check that all timestamps are increasing
    if len(data) > 1 and np.min(np.diff(data['timestamp'])) <= 0:
        min_idx = np.argmin(np.diff(data['timestamp']))
        msg = ("Non-monotonic timestamp in new data to stream [%s] (%d<=%d)" %
               (name, data['timestamp'][min_idx + 1], data['timestamp'][min_idx]))
        print(msg)
        return False
    # check to make sure the first timestamp is larger than the previous block
    if last_ts is not None and (last_ts >= data['timestamp'][0]):
            msg = ("Non-monotonic timestamp between writes to stream [%s] (%d<=%d)" %
                   (name, data['timestamp'][0], last_ts))
            print(msg)
            return False
    return True

def validate_no_nan_values(data):
    import numpy as np
    if np.isnan(data['timestamp']).any():
        return False
    if np.isnan(data['data']).any():
        return False
    return True

def validate_stream_path(path:str) -> str:
    if path != '/' and re.fullmatch(r'^(/[\w -]+)+$', path) is None:
        raise ValueError(
            "invalid path, use format: /dir/subdir/../file "
            "valid characters: [0-9,A-Z,a-z,_,-, ]")
    return path