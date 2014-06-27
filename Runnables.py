#-*- coding:UTF-8 -*-
'''
Created on 2014年6月13日

@author: hanchao
'''
from PyQt4 import QtCore, QtGui

import os, json
import sinastorage
from sinastorage.bucket import SCSBucket,ACL, SCSError, KeyNotFound, BadRequest, SCSResponse, SCSListing
from sinastorage.utils import rfc822_fmtdate, info_dict

from sinastorage.utils import (rfc822_parsedate)

class FileUploadRunnable(QtCore.QRunnable):
    ''' 文件上传 '''
    
    def __init__(self, bucketName, filePath, prefix, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.filePath = filePath
        self.bucketName = bucketName
        self.prefix = prefix
        self.mutex = QtCore.QMutex()
        self.total = 0
        self.received = 0
        
    def uploadCallBack(self, total, uploaded):
        self.total = total
        self.received = self.received + uploaded
        self.emitter.emit(QtCore.SIGNAL("fileUploadProgress(PyQt_PyObject, int, int)"), self, self.total, self.received)
    
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        scsResponse = s.putFile('%s%s'%(self.prefix,os.path.basename(self.filePath)),self.filePath,self.uploadCallBack)
        self.response =  scsResponse
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("fileUploadDidFinished(PyQt_PyObject)"), self)
        
class FileInfoRunnable(QtCore.QRunnable):
    ''' 文件信息 '''
    def __init__(self, bucketName, key, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.key = key
        self.bucketName = bucketName
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        scsResponse = s.send(s.request(method="HEAD", key=self.key))
        info = info_dict(dict(scsResponse.urllib2Response.info()))
        scsResponse.close()
        self.response =  scsResponse
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("fileInfoRunnable(PyQt_PyObject, PyQt_PyObject)"), self, info)
        
class UpdateFileACLRunnable(QtCore.QRunnable):
    ''' 文件信息 '''
    def __init__(self, bucketName, key, acl, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.key = key
        self.bucketName = bucketName
        self.acl = acl
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        scsResponse = s.update_acl(self.key, self.acl)
        self.response =  scsResponse
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("UpdateFileACLRunnable(PyQt_PyObject)"), self)
        
class ListBucketRunnable(QtCore.QRunnable):
    ''' 列bucket '''
    def __init__(self, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.mutex = QtCore.QMutex()
        
    def bucketIter(self):
        for item in self.buckets:
            entry = (item['Name'],rfc822_parsedate(item['CreationDate']))
            yield entry
        
    def run(self):
        try:
            self.mutex.lock()
            s = SCSBucket()
            self.response = s.send(s.request(key=''))
            bucketJsonObj = json.loads(self.response.read())
            self.response.close()
            self.buckets = bucketJsonObj['Buckets']
            self.mutex.unlock()
        except Exception, e:
            self.emitter.emit(QtCore.SIGNAL("ListBucketRunnableDidFailed(PyQt_PyObject)"), self)
#             print e
        else:
            self.emitter.emit(QtCore.SIGNAL("ListBucketRunnable(PyQt_PyObject)"), self)


class ListDirRunnable(QtCore.QRunnable):
    ''' 列目录 '''
    def __init__(self, bucketName, prefix=None, marker=None, limit=None, delimiter=None, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.prefix = prefix
        self.marker = marker
        self.limit = limit
        self.delimiter = delimiter
        self.parent = parent
        self.mutex = QtCore.QMutex()

    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        m = (("prefix", self.prefix),
             ("marker", self.marker),
             ("max-keys", self.limit),
             ("delimiter", self.delimiter),
             ("formatter","json"))
        args = dict((str(k), str(v)) for (k, v) in m if v is not None)
        self.response = s.send(s.request(key='', args=args))
        self.files_generator = SCSListing.parse(self.response)
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("ListDirRunnable(PyQt_PyObject)"), self)
        
        
class DeleteObjectRunnable(QtCore.QRunnable):
    ''' 删除object ''' 
    def __init__(self, bucketName, key, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.key = key
        self.parent = parent
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        try:
            self.response = s.send(s.request(method="DELETE", key=self.key))
        except KeyNotFound, e:
            e.fp.close()
            #TODO:处理异常
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("DeleteObjectRunnable()"))
        
        
class DownloadObjectRunnable(QtCore.QRunnable):
    ''' 下载Object '''
    def __init__(self, bucketName, key, destFilePath, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.key = key
        self.destFilePath = destFilePath
        self.parent = parent
        
        self.received = 0
        self.total = 0
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        self.response = s[self.key]
        
        responseHeaders = dict(self.response.urllib2Response.info())
        if "content-length" in responseHeaders:
            self.total = int(responseHeaders["content-length"])
        else:
            raise ValueError("Content-Length not returned!!")
        
        CHUNK = 16 * 1024
        with open(self.destFilePath, 'wb') as fp:
            while True:
                chunk = self.response.read(CHUNK)
                if not chunk: break
                fp.write(chunk)
                self.downloadCallBack(len(chunk))
        
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("DownloadObjectRunnable(PyQt_PyObject)"),self)
    
    
    def downloadCallBack(self, received):
        self.received = self.received + received
        self.emitter.emit(QtCore.SIGNAL("FileDownloadProgress(PyQt_PyObject, int, int)"), self, self.total, self.received)
    
    
    
class DeleteBucketRunnable(QtCore.QRunnable):
    ''' 删除bucket ''' 
    def __init__(self, bucketName, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.parent = parent
        self.mutex = QtCore.QMutex()
        
    def run(self):
        s = SCSBucket(self.bucketName)
        try:
            self.mutex.lock()
            self.response = s.send(s.request(method="DELETE", key=None))
            self.mutex.unlock()
        except KeyNotFound, e:
            e.fp.close()
            #TODO:处理异常
        except SCSError, e:
            self.emitter.emit(QtCore.SIGNAL("DeleteBucketRunnableDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
        else:
            self.emitter.emit(QtCore.SIGNAL("DeleteBucketRunnable(PyQt_PyObject)"), self)

class BucketInfoRunnable(QtCore.QRunnable):
    ''' bucket信息 '''
    def __init__(self, bucketName, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        self.response = s.send(s.request(method="GET", key=None, subresource='meta'))
        metaResult = json.loads(self.response.read())
        self.response.close()
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("BucketInfoRunnable(PyQt_PyObject, PyQt_PyObject)"), self, metaResult)


class CreateFolderRunnable(QtCore.QRunnable):
    ''' 创建文件夹 '''
    def __init__(self, bucketName, key, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.key = key
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        scsResponse = s.put(self.key,'')
        self.response =  scsResponse
        self.response.close()
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("CreateFolder(PyQt_PyObject)"), self)

class CreateBucketRunnable(QtCore.QRunnable):
    ''' 创建bucket '''
    def __init__(self, bucketName, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.mutex = QtCore.QMutex()
        
    def run(self):
        self.mutex.lock()
        s = SCSBucket(self.bucketName)
        self.response =  s.put_bucket()
        self.response.close()
        self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("CreateBucket(PyQt_PyObject)"), self)









        
        
