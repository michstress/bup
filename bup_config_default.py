#!/usr/bin/python


def getDoNotCompress():
    return [".mp3",".7z",".zip",".gz","jpeg","jpg","gif","dng","png","avi","mpeg","mov","wmv","mp4"]

def getExcludeDirs():
    return [ 
        "/2wd",
        "/video", 
        "/public",
        "/@*",
        "/computer" ]

