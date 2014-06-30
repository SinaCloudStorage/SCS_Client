#-*- coding:UTF-8 -*-
'''
Created on 2014年6月30日

@author: hanchao
'''
import math

def filesizeformat(bytes, precision=2):
    """Returns a humanized string for a given amount of bytes"""
    bytes = int(bytes)
    if bytes is 0:
        return '0 Bytes'
    
    log = math.floor(math.log(bytes, 1024))
    return "%.*f %s" % (
                       precision,
                       bytes / math.pow(1024, log),
                       ['Bytes', 'KB', 'MB', 'GB', 'TB','PB', 'EB', 'ZB', 'YB']
                       [int(log)]
                       )