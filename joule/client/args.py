
def dict2args(mydict):
    # convert mydict into a namespace object
    # by converting array types into JSON
    for key in mydict:
        if(mydict[key] 
