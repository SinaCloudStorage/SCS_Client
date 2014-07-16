#-*- coding:UTF-8 -*-
'''
Created on 2014年6月30日

@author: hanchao
'''
import math, os

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
    
def getFileAmount(path):
    count = 0
    for i in os.listdir(path): 
        if os.path.isdir(os.path.join(path, i)): 
            count += getFileAmount(os.path.join(path, i))

        count += 1

    return count

def renameFileByPath(localPath, fileName, suffix=0):
    ''' 判断localPath路径下是否有重名文件，若存在，则重命名当前文件 '''
    renamedFileName = fileName if suffix==0 else u'%s(%d)%s'%(os.path.splitext(fileName)[0], suffix,
                                                    os.path.splitext(fileName)[1] if len(os.path.splitext(fileName))>1 else '')
    
    if os.path.exists(os.path.join(localPath, renamedFileName)) :
        suffix += 1
        return renameFileByPath(localPath, fileName, suffix)
    
    return renamedFileName
    


def getValueFromWindowsRegistryByKey(key):
    ''' 从注册表中根据key取值 '''
    if cmp(os.name,'nt') == 0:
        import _winreg
        
        regPrefixPath = _winreg.HKEY_CURRENT_USER
        regSubPath = u'Software\\SCS_client'
        
        reg = None
        try:
            reg = _winreg.OpenKey(regPrefixPath, regSubPath)
            return _winreg.QueryValue(reg, key)
        except EnvironmentError:
            pass
        finally:
            try:
                if reg: _winreg.CloseKey(reg)
            except Exception:
                pass
    else:
        print u'current platform is not windows!'
    
    return None
    

def addKeyValueToWindowsRegistry(key, value):
    ''' 保存键值对到windows注册表中 '''
    if cmp(os.name,'nt') == 0:
        import _winreg
        
        regPrefixPath = _winreg.HKEY_CURRENT_USER
        regSubPath = u'Software\\SCS_client'
        
        try:
            reg = _winreg.OpenKey(regPrefixPath, regSubPath)
        except EnvironmentError:
            try:
                reg = _winreg.CreateKey(regPrefixPath, regSubPath)
            except:
                print "*** Unable to register!"
                return False
        try:
            if (_winreg.QueryValue(reg, key) != value):
                _winreg.DeleteKey(reg, key)
                _winreg.SetValue(reg, key, _winreg.REG_SZ, value)
        except Exception ,e:
            _winreg.SetValue(reg, key, _winreg.REG_SZ, value)
        
        try:
            if reg: _winreg.CloseKey(reg)
        except Exception:
            pass
        
        return True
    else:
        print u'current platform is not windows!'
    
    return False


def removeKeyFromWindowsRegistry(key):
    ''' 从windows注册表中删除键值对 '''
    if cmp(os.name,'nt') == 0:
        import _winreg
        
        regPrefixPath = _winreg.HKEY_CURRENT_USER
        regSubPath = u'Software\\SCS_client'
        
        try:
            reg = _winreg.OpenKey(regPrefixPath, regSubPath)
            _winreg.DeleteKey(reg, key)
            _winreg.CloseKey(reg)
        except EnvironmentError:
            pass
        
        return True
    else:
        print u'current platform is not windows!'
    
    return False

    
    
    
    