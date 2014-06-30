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
    

def bytesFromFilesizeFormat(filesize):
    if filesize is None or len(filesize)==0:
        return 0
    
    try:
        formatArray = ['Bytes', 'KB', 'MB', 'GB', 'TB','PB', 'EB', 'ZB', 'YB']
        
        if filesize.find('Bytes') == -1:
            format = filesize[len(filesize)-2:]
            idx = formatArray.index(format)
            size = float(filesize[0:len(filesize)-3])
            for i in xrange(idx):
                size = size * 1024
                
            return size
        else:
            return float(filesize[0:len(filesize)-6])
    except Exception , e:
        return 0