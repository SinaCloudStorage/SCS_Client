#-*- coding:UTF-8 -*-
'''
Created on 2014年6月13日

@author: hanchao
'''
from PyQt4 import QtCore, QtGui
import os, json
import sinastorage
from sinastorage.bucket import (SCSBucket,ACL, SCSError, ManualCancel, 
                                KeyNotFound, BadRequest, SCSResponse, SCSListing, _upload_part_by_fileWithCallback)
from sinastorage.utils import rfc822_fmtdate, info_dict, FileWithCallback

from sinastorage.utils import (rfc822_parsedate)
from encoding import smart_str, smart_unicode

import time

class RunnableState(object):
    WAITING = 1
    RUNNING = 2
    DID_FINISHED = 3
    DID_FAILED = 4
    FORBIDDEN = 5       #禁止操作
    DID_CANCELED = 6    #取消操作

class BaseRunnable(QtCore.QRunnable):
    def __init__(self):
        QtCore.QRunnable.__init__(self)
        self.state = RunnableState.WAITING

class FileMultipartUploadRunnable(BaseRunnable):
    ''' 文件分片上传 '''
    def __init__(self, bucketName, filePath, prefix, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.parent = parent
        self.filePath = filePath
        self.bucketName = bucketName
        self.prefix = prefix
        self.mutex = QtCore.QMutex()
        self.total = 0
        self.received = 0
        
        self.multipart = None                   #分片上传结果
        self.source_size = os.stat(self.filePath).st_size
        
        '''操作列表，用于显示操作详情
            {u'response':scsResponse,
             u'operation_name':u'合并分片',
             u'result':u'完成'}
        '''
        self.operationList = []
        
    def multipartUploadCallBack(self, upload_id, part_num, total, received):
        self.received += received
        
        ''' 顺序上传, 进度=当前分片数/总分片数*当前分片百分比 '''
        self.emitter.emit(QtCore.SIGNAL("fileUploadProgress(PyQt_PyObject, int, int)"), 
                          self, 
                          self.source_size, 
                          self.received)
        
    def multipartUpload(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            
            self.useMultipartUpload = True
            
            import math
            from sinastorage.multipart import FileChunkWithCallback
            min_bytes_per_chunk = 5 * 1024 * 1024                     #每片分片最大文件大小
            s = SCSBucket(self.bucketName)

            keyName = '%s%s'%(self.prefix,os.path.basename(self.filePath))
            self.multipart = s.initiate_multipart_upload(keyName, acl=None, metadata={}, 
                                                    mimetype=None, headers={})
            
            self.operationList.append({u'response':self.multipart.init_multipart_response,
                                       u'operation_name':u'初始化分片上传',
                                       u'result':u'完成'})
            
            bytes_per_chunk = max(int(math.sqrt(min_bytes_per_chunk) * math.sqrt(self.source_size)),
                                  min_bytes_per_chunk)
            chunk_amount = int(math.ceil(self.source_size / float(bytes_per_chunk)))
            self.multipart.bytes_per_part = bytes_per_chunk
            self.multipart.parts_amount = chunk_amount
            
            i = 0
            for part in self.multipart.get_next_part():
                if self.state == RunnableState.DID_CANCELED:
                    raise sinastorage.bucket.ManualCancel('operation abort')
                offset = i * bytes_per_chunk
                remaining_bytes = self.source_size - offset
                chunk_bytes = min([bytes_per_chunk, remaining_bytes])
                
                self._current_fileChunkWithCallback = FileChunkWithCallback(self.filePath, 'rb', offset=offset,
                                                                            bytes=chunk_bytes, cb=self.multipartUploadCallBack, 
                                                                            upload_id=self.multipart.upload_id, part_num=part.part_num)
    
                try:
                    part_result = _upload_part_by_fileWithCallback(self.bucketName, keyName, 
                                                                   self.multipart, part, 
                                                                   self._current_fileChunkWithCallback, None)
                    self.multipart.parts.append(part_result)
                    
                    self.operationList.append({u'response':part_result.response,
                                       u'operation_name':u'分片上传%d'%part_result.part_num,
                                       u'result':u'完成'})
                    
                finally:
                    self._current_fileChunkWithCallback.close()
                
                i = i + 1
                
            if len(self.multipart.parts) == chunk_amount:
                scsResponse = s.complete_multipart_upload(self.multipart)
                self.multipart.complete_multipart_response = scsResponse
                self.operationList.append({u'response':scsResponse,
                                       u'operation_name':u'合并分片',
                                       u'result':u'完成'})
    #             key = s.get_key(keyName)
    #             key.set_acl(acl)
            else:
                print  len(self.multipart.parts) , chunk_amount
                raise RuntimeError("multipart upload is failed!!")
        except SCSError, e:
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            if isinstance(e, ManualCancel):     #手动取消
                self.state = RunnableState.DID_CANCELED
                self.response._responseBody = u'手动取消'
                self.emitter.emit(QtCore.SIGNAL("fileUploadDidCanceled(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            else:
                self.state = RunnableState.DID_FAILED
                self.response._responseBody = e.data
                self.emitter.emit(QtCore.SIGNAL("fileUploadDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
            
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("fileUploadDidFinished(PyQt_PyObject)"), self)
    
    def run(self):
        self.multipartUpload()
        
    def cancel(self):
        self.state = RunnableState.DID_CANCELED
        self._current_fileChunkWithCallback.cancelRead = True
        print '========cancel============='
        

class FileUploadRunnable(BaseRunnable):
    ''' 文件上传 '''
    def __init__(self, bucketName, filePath, prefix, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.parent = parent
        self.filePath = filePath
        self.bucketName = bucketName
        self.prefix = prefix
        self.mutex = QtCore.QMutex()
        self.total = 0
        self.received = 0
        
        self.useMultipartUpload = False         #是否使用分片上传
        self.multipart = None                   #分片上传结果
        
        self.source_size = os.stat(self.filePath).st_size
        
        
    def uploadCallBack(self, total, uploaded):
        self.total = total
        self.received = self.received + uploaded
        self.emitter.emit(QtCore.SIGNAL("fileUploadProgress(PyQt_PyObject, int, int)"), self, self.total, self.received)
    
    def upload(self):
        ''' 普通上传 '''
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            
            s = SCSBucket(self.bucketName)
            self.fileWithCallback = FileWithCallback(self.filePath, 'rb', self.uploadCallBack)
            scsResponse = s.putFileByHeaders('%s%s'%(self.prefix,os.path.basename(self.filePath)), self.fileWithCallback)
            self.response =  scsResponse
        except SCSError, e:
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            if isinstance(e, ManualCancel):     #手动取消
                self.state = RunnableState.DID_CANCELED
                self.response._responseBody = u'手动取消'
                self.emitter.emit(QtCore.SIGNAL("fileUploadDidCanceled(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            else:
                self.state = RunnableState.DID_FAILED
                self.response._responseBody = e.data
                self.emitter.emit(QtCore.SIGNAL("fileUploadDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.fileWithCallback.close()
            self.mutex.unlock()
            
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("fileUploadDidFinished(PyQt_PyObject)"), self)
        
    
    def run(self):
        self.upload()
        
    def cancel(self):
        self.state = RunnableState.DID_CANCELED
        if self.useMultipartUpload:
            pass
        else:
            self.fileWithCallback.cancelRead = True
        
class FileInfoRunnable(BaseRunnable):
    ''' 文件信息 '''
    def __init__(self, bucketName, key, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.key = key
        self.bucketName = bucketName
        self.mutex = QtCore.QMutex()
        
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            scsResponse = s.send(s.request(method="HEAD", key=self.key))
            info = info_dict(dict(scsResponse.urllib2Response.info()))
            scsResponse.close()
            self.response =  scsResponse
        except SCSError, e:
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.state = RunnableState.DID_FAILED
            self.emitter.emit(QtCore.SIGNAL("fileInfoDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("fileInfoRunnable(PyQt_PyObject, PyQt_PyObject)"), self, info)
        
class UpdateFileACLRunnable(BaseRunnable):
    ''' 文件信息 '''
    def __init__(self, bucketName, key, acl, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.key = key
        self.bucketName = bucketName
        self.acl = acl
        self.mutex = QtCore.QMutex()
        
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            scsResponse = s.update_acl(self.key, self.acl)
            self.response =  scsResponse
        except SCSError, e:
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.state = RunnableState.DID_FAILED
            self.emitter.emit(QtCore.SIGNAL("UpdateFileACLDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("UpdateFileACLRunnable(PyQt_PyObject)"), self)
        
class ListBucketRunnable(BaseRunnable):
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
            self.state = RunnableState.RUNNING
            s = SCSBucket()
            self.response = s.send(s.request(key=''))
            bucketJsonObj = json.loads(self.response.read())
            self.response.close()
            self.buckets = bucketJsonObj['Buckets']
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("ListBucketRunnableDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("ListBucketRunnable(PyQt_PyObject)"), self)


class ListDirRunnable(BaseRunnable):
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
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            m = (("prefix", smart_str(self.prefix)),
                 ("marker", self.marker),
                 ("max-keys", self.limit),
                 ("delimiter", self.delimiter),
                 ("formatter","json"))
            args = dict((str(k), str(v)) for (k, v) in m if v is not None)
            self.response = s.send(s.request(key='', args=args))
            self.files_generator = SCSListing.parse(self.response)
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("ListDirDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("ListDirRunnable(PyQt_PyObject)"), self)
        
        
class DeleteObjectRunnable(BaseRunnable):
    ''' 删除object ''' 
    def __init__(self, bucketName, key, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.key = key
        self.parent = parent
        self.mutex = QtCore.QMutex()
        
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            if self.key.rfind('/') == len(self.key)-1 :
                m = (("prefix", smart_str(self.key)),
                     ("delimiter", '/'),
                     ("max-keys", 5),
                     ("formatter","json"))
                args = dict((str(k), str(v)) for (k, v) in m if v is not None)
                response = s.send(s.request(key='', args=args))
                files_generator = SCSListing.parse(response)
                
                if files_generator.contents_quantity > 0 or files_generator.common_prefixes_quantity > 0 :
                    for item in files_generator:
                        if cmp(item[0],self.key) != 0:
                            self.emitter.emit(QtCore.SIGNAL("DeleteObjectForbidden(PyQt_PyObject,PyQt_PyObject)"), self, u'不能删除非空目录(前缀) ')
                            return
            
#             s = SCSBucket(self.bucketName)
            self.response = s.send(s.request(method="DELETE", key=self.key))
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("DeleteObjectDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("DeleteObjectRunnable(PyQt_PyObject)"), self)
        
        
class DownloadObjectRunnable(BaseRunnable):
    ''' 下载Object '''
    def __init__(self, bucketName, key, fileMD5, destFilePath, tmpFilePath, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.key = key
        self.fileMD5 = fileMD5
        self.destFilePath = destFilePath    #下载完成后重命名至该文件路径
        self.tmpFilePath = tmpFilePath      #用于断点续传的临时文件路径
        self.parent = parent
        
        self.received = 0                   #已下载byte数量
        self.total = 0                      #文件总大小
        
        self.isAbort = False
        self.mutex = QtCore.QMutex()
        
    def cancel(self):
        self.isAbort = True
        self.state = RunnableState.DID_CANCELED    
    
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
#             self.response = s[self.key]

            headers = {}
            ''' 若文件存在，则received等于已下载的文件大小 '''
            if os.path.exists(self.tmpFilePath):
                self.received = os.stat(self.tmpFilePath).st_size
                headers['If-Range'] = u'"%s"'%self.fileMD5
                headers['Range'] = u'bytes=%d-'%self.received
            
            self.response = s.send(s.request(key=self.key,headers=headers))
            
            statusCode = getattr(self.response.urllib2Response, "code", None)
            responseHeaders = dict(self.response.urllib2Response.info())
            if statusCode == 200:
                if "content-length" in responseHeaders:
                    self.total = int(responseHeaders["content-length"])
                else:
                    raise ValueError("Content-Length not returned!!")
            elif statusCode == 206:
                ''' 用于断点续传时获取文件总大小 '''
                if "content-range" in responseHeaders:
                    content_range = responseHeaders["content-range"]
                    self.total = int(content_range[content_range.rfind('/')+1:])
                else:
                    raise ValueError("Content-Length not returned!!")
            
            lastTimestamp = time.time()
            CHUNK = 16 * 1024
            _received_tmp = 0              #内部临时变量
            with open(self.tmpFilePath, 'ab') as fp:
                while True:
                    if self.isAbort:
                        self.state = RunnableState.DID_CANCELED
                        self.response._responseBody = u'手动取消'
                        self.emitter.emit(QtCore.SIGNAL("DownloadObjectDidCanceled(PyQt_PyObject)"), self)
                        return
                    
                    chunk = self.response.read(CHUNK)
                    if not chunk: break
                    fp.write(chunk)
                    
                    _received_tmp += len(chunk)
                    if time.time() - lastTimestamp >= 1.0:
                        self.downloadCallBack(_received_tmp)
                        lastTimestamp = time.time()
                        _received_tmp = 0
            
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("DownloadObjectDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.response.close()
            self.mutex.unlock()
        
        #将tmpFilePath重命名为 destFilePath
        if os.path.exists(self.destFilePath): os.remove(self.destFilePath)
        os.rename(self.tmpFilePath, self.destFilePath)
        
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("DownloadObjectRunnable(PyQt_PyObject)"),self)
    
    
    def downloadCallBack(self, received):
        self.received = self.received + received
        self.emitter.emit(QtCore.SIGNAL("FileDownloadProgress(PyQt_PyObject, int, int)"), self, self.total, self.received)
    
class DeleteBucketRunnable(BaseRunnable):
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
            self.state = RunnableState.RUNNING
            self.response = s.send(s.request(method="DELETE", key=None))
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("DeleteBucketRunnableDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("DeleteBucketRunnable(PyQt_PyObject)"), self)

class BucketInfoRunnable(BaseRunnable):
    ''' bucket信息 '''
    def __init__(self, bucketName, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.mutex = QtCore.QMutex()
        
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            self.response = s.send(s.request(method="GET", key=None, subresource='meta'))
            metaResult = json.loads(self.response.read())
            self.response.close()
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("BucketInfoDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("BucketInfoRunnable(PyQt_PyObject, PyQt_PyObject)"), self, metaResult)


class CreateFolderRunnable(BaseRunnable):
    ''' 创建文件夹 '''
    def __init__(self, bucketName, key, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.key = key
        self.filePath = None
        self.mutex = QtCore.QMutex()
        
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            scsResponse = s.put(self.key,'')
            self.response =  scsResponse
            self.response.close()
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            self.emitter.emit(QtCore.SIGNAL("CreateFolderDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("CreateFolder(PyQt_PyObject)"), self)

class CreateBucketRunnable(BaseRunnable):
    ''' 创建bucket '''
    def __init__(self, bucketName, parent=None):
        self.emitter = QtCore.QObject()
        QtCore.QRunnable.__init__(self)
        self.bucketName = bucketName
        self.mutex = QtCore.QMutex()
        
    def run(self):
        try:
            self.mutex.lock()
            self.state = RunnableState.RUNNING
            s = SCSBucket(self.bucketName)
            self.response =  s.put_bucket()
            self.response.close()
        except SCSError, e:
            self.state = RunnableState.DID_FAILED
            self.emitter.emit(QtCore.SIGNAL("CreateBucketDidFailed(PyQt_PyObject,PyQt_PyObject)"), self, e.msg)
            self.response = SCSResponse(e.urllib2Request, e.urllib2Response)
            self.response._responseBody = e.data
            return
        finally:
            self.mutex.unlock()
        self.state = RunnableState.DID_FINISHED
        self.emitter.emit(QtCore.SIGNAL("CreateBucket(PyQt_PyObject)"), self)



class CheckNewVersionRunnable(QtCore.QRunnable):
    ''' 检查新版本 '''
    def __init__(self):
        QtCore.QRunnable.__init__(self)
        self.emitter = QtCore.QObject()
        self.mutex = QtCore.QMutex()
        self.versionDict = {}

    def run(self):
        try:
            self.mutex.lock()
            import urllib2
            response = urllib2.urlopen('http://sinastorage.com/sdk/SCS-Client-Win7/check_version.json', timeout=10)
            '''
                {
                    "version_name": "v1.0",
                    "version_code": "1",
                    "download_url": "http://open.sinastorage.com"
                }
            '''
            self.versionDict = json.loads(response.read())
        finally:
            self.mutex.unlock()
        self.emitter.emit(QtCore.SIGNAL("CheckNewVersion(PyQt_PyObject)"), self.versionDict)


        
        
