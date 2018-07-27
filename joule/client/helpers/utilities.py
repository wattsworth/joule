import datetime


# parser for boolean args
def yesno(val):
    if val is None:
        raise ValueError("must be 'yes' or 'no'")
    # standardize the string
    val = val.lower().strip()
    if val == "yes":
        return True
    elif val == "no":
        return False
    else:
        raise ValueError("must be 'yes' or 'no'")


def time_now():
    return datetime.datetime.now().timestamp()*1e6