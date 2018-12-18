# parser for boolean args
def yesno(val: str):
    """
    Convert a "yes" or "no" argument into a boolean value. Returns ``true``
    if val is "yes" and ``false`` if val is "no". Raises ValueError otherwise.
    This is function can be used as the **type** parameter for to handle module arguments
    that are "yes|no" flags.
    """
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
