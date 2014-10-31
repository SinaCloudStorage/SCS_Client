#-*- coding:UTF-8 -*-
#!/usr/bin/env python
'''
Created on 2014年5月29日

@author: hanchao
'''

import sip
from compiler.ast import Lambda
sip.setapi('QVariant', 2)

import os
from PyQt4 import QtCore, QtGui

import sinastorage
from sinastorage.bucket import SCSBucket,ACL, SCSError, KeyNotFound, BadRequest, SCSResponse
from sinastorage.utils import rfc822_fmtdate, rfc822_parsedate

from Utils import (filesizeformat, bytesFromFilesizeFormat, getFileAmount, 
                   getValueFromWindowsRegistryByKey, addKeyValueToWindowsRegistry,
                   removeKeyFromWindowsRegistry, renameFileByPath)

from Runnables import (BaseRunnable, RunnableState, FileUploadRunnable, FileInfoRunnable, UpdateFileACLRunnable, 
                       ListDirRunnable, ListBucketRunnable, DeleteObjectRunnable,
                       DownloadObjectRunnable, DeleteBucketRunnable, BucketInfoRunnable,
                       CreateFolderRunnable, CreateBucketRunnable, FileMultipartUploadRunnable)

global USE_HTTPS_CONNECTION

class OperationLogDetailForMultipartUpload(QtGui.QDialog):
    ''' 用于显示分片上传操作的详细页面 '''
    def __init__(self, multipartRunnable, parent=None):
        super(OperationLogDetailForMultipartUpload, self).__init__(parent)
        self.multipartRunnable = multipartRunnable
        self.openner = parent
        
        self.mainLayout = QtGui.QGridLayout()
        
        self.initSubUploadTableLayout()
        self.showRequestLayout(None)
        self.showRsponseLayout(None)
        
        self.mainLayout.addWidget(self.subUploadTable, 0, 0, 2, 1)
        self.mainLayout.addWidget(self.requestGroupBox, 0, 1)
        self.mainLayout.addWidget(self.responseGroupBox, 1, 1)
        
        self.setLayout(self.mainLayout)
        self.setMinimumHeight(700)
        self.subUploadTable.selectRow(0)
        self.connect(self, QtCore.SIGNAL("finished(int)"), lambda code:self.deleteLater())
    
    def showDetail(self):
        row = self.subUploadTable.selectedIndexes()[0].row()
        respDict = self.multipartRunnable.operationList[row]
        
        if hasattr(self, 'requestGroupBox'):
            self.mainLayout.removeWidget(self.requestGroupBox)
            self.requestGroupBox.hide()
            sip.delete(self.requestGroupBox)
            del self.requestGroupBox
        self.showRequestLayout(respDict['response'].urllib2Request)
        self.mainLayout.addWidget(self.requestGroupBox, 0, 1)
        
        if hasattr(self, 'responseGroupBox'):
            self.mainLayout.removeWidget(self.responseGroupBox)
            self.responseGroupBox.hide()
            sip.delete(self.responseGroupBox)
            del self.responseGroupBox
        self.showRsponseLayout(respDict['response'].urllib2Response)
        self.mainLayout.addWidget(self.responseGroupBox, 1, 1)
        
        
    def initSubUploadTableLayout(self):
        ''' 左侧分片上传任务列表 '''
        self.subUploadTable = QtGui.QTableWidget(0, 2, self)
        self.subUploadTable.setHorizontalHeaderLabels((u"分片", u"状态"))
        self.subUploadTable.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.subUploadTable.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
#         self.subUploadTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
#         self.subUploadTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.subUploadTable.verticalHeader().hide()
        self.subUploadTable.setShowGrid(False)
        self.subUploadTable.setMaximumWidth(220)
        self.subUploadTable.setMinimumWidth(200)
        self.subUploadTable.itemSelectionChanged.connect(self.showDetail)
        
        self.subUploadTable.clearContents()
        self.subUploadTable.setRowCount(0)
        
        
#         '''操作列表，用于显示操作详情
#             {u'response':scsResponse,
#              u'operation_name':u'合并分片',
#              u'result':u'完成'}
#         '''
#         self.operationList = []
        
        for operDict in self.multipartRunnable.operationList :
            
            operation = QtGui.QTableWidgetItem(operDict['operation_name'])  #name
            operation.setFlags(operation.flags() & ~QtCore.Qt.ItemIsEditable)
            
            result = QtGui.QTableWidgetItem(operDict['result'])
            result.setFlags(result.flags() & ~QtCore.Qt.ItemIsEditable)
            
            row = self.subUploadTable.rowCount()
            self.subUploadTable.insertRow(row)
            self.subUploadTable.setItem(row, 0, operation)
            self.subUploadTable.setItem(row, 1, result)
            
        
    def showRequestLayout(self, urllib2Request): 
        ''' 初始化请求layout '''
        self.requestGroupBox = QtGui.QGroupBox(u"请求")
            
        urlNameLabel = QtGui.QLabel(u"请求地址:")
        urlLabel = QtGui.QLabel(urllib2Request.get_full_url() if urllib2Request else '')
        urlLabel.setWordWrap(True)
        methodNameLabel = QtGui.QLabel(u"请求方式:")
        methodLabel = QtGui.QLabel(urllib2Request.get_method() if urllib2Request else '')
        
        requestHeaderNameLabel = QtGui.QLabel(u"<b>请求header:</b>")
        
        requestBodyNameLabel = QtGui.QLabel(u"<b>请求body:</b>")
        self.requestBodyTextEdit = QtGui.QTextEdit()
        self.requestBodyTextEdit.setReadOnly(True)
        self.requestBodyTextEdit.setMaximumHeight(50)
        self.requestBodyTextEdit.setMinimumHeight(50)
        self.requestBodyTextEdit.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        
        if urllib2Request and hasattr(urllib2Request.data,'fileno'): #file like
            self.requestBodyTextEdit.setText('<file data. %s>'%urllib2Request.data.name)
        else:
            self.requestBodyTextEdit.setText(urllib2Request.data if urllib2Request and urllib2Request.data else '<request is empty!>')
        
        rowIdx = 0
        layout = QtGui.QGridLayout()
        
        layout.addWidget(urlNameLabel, rowIdx, 0)
        layout.addWidget(urlLabel, rowIdx, 1)
        rowIdx+=1
        layout.addWidget(methodNameLabel, rowIdx, 0)
        layout.addWidget(methodLabel, rowIdx, 1)
        rowIdx+=1
        layout.addWidget(requestHeaderNameLabel, rowIdx, 0)
        rowIdx+=1
        if urllib2Request:
            for k, v in urllib2Request.header_items() :
                layout.addWidget(QtGui.QLabel(k), rowIdx, 0)
                layout.addWidget(QtGui.QLabel(v), rowIdx, 1)
                rowIdx += 1
            
        layout.addWidget(requestBodyNameLabel, rowIdx, 0,)
        rowIdx += 1
        layout.addWidget(self.requestBodyTextEdit, rowIdx, 0, 1, 5)
        
        self.requestGroupBox.setLayout(layout)
    
    def showRsponseLayout(self, urllib2Response, responseBody=None):
        ''' 初始化响应layout '''
        self.responseGroupBox = QtGui.QGroupBox(u"响应")
            
        responseCodeNameLabel = QtGui.QLabel(u"<b>响应码:</b>")
        responseCodeLabel = QtGui.QLabel()
        if urllib2Response and hasattr(urllib2Response, 'code') :
            if urllib2Response.code >= 200 and urllib2Response.code <= 300:
                responseCode = '%d'%urllib2Response.code
            else:
                responseCode = '<font color=red>%d</font>'%urllib2Response.code
            responseCodeLabel.setText(responseCode)
        responseHeaderNameLabel = QtGui.QLabel(u"<b>响应header:</b>")
        responseBodyNameLabel = QtGui.QLabel(u"<b>响应body:</b>")
        self.responseBodyTextEdit = QtGui.QTextEdit()
        self.responseBodyTextEdit.setReadOnly(True)
        self.responseBodyTextEdit.setMaximumHeight(50)
        self.responseBodyTextEdit.setMinimumHeight(50)
        self.responseBodyTextEdit.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        
        if responseBody is not None:
            body = responseBody
        else:
            body = '<respondy body is empty!>'
        self.responseBodyTextEdit.setText( body )
        
        layout = QtGui.QGridLayout()
        layout.addWidget(responseCodeNameLabel, 0, 0)
        layout.addWidget(responseCodeLabel, 0, 1)
        layout.addWidget(responseHeaderNameLabel, 1, 0)
        rowIdx = 2
        headers = dict(urllib2Response.info()) if hasattr(urllib2Response, 'info') else {}
        for k, v in headers.iteritems() :
            layout.addWidget(QtGui.QLabel(k), rowIdx, 0)
            layout.addWidget(QtGui.QLabel(v), rowIdx, 1)
            rowIdx += 1
            
        layout.addWidget(responseBodyNameLabel, rowIdx, 0,)
        rowIdx += 1
        layout.addWidget(self.responseBodyTextEdit, rowIdx, 0, 1, 5)
        
        self.responseGroupBox.setLayout(layout)
        
        
class OperationLogDetail(QtGui.QDialog):
    ''' 操作详细页面 '''
    def __init__(self, scsResponse, parent=None):
        super(OperationLogDetail, self).__init__(parent)
        self.openner = parent
        self.scsResponse = scsResponse
        
        self.initRequestLayout()
        self.initRsponseLayout()
        
        mainLayout = QtGui.QVBoxLayout()
        mainLayout.addWidget(self.requestGroupBox)
        mainLayout.addWidget(self.responseGroupBox)
        self.setLayout(mainLayout)
        self.connect(self, QtCore.SIGNAL("finished(int)"), lambda code:self.deleteLater())

        
    def initRequestLayout(self):    
        ''' 初始化请求layout '''
        self.requestGroupBox = QtGui.QGroupBox(u"请求")
        urlNameLabel = QtGui.QLabel(u"请求地址:")
        urlLabel = QtGui.QLabel(self.scsResponse.urllib2Request.get_full_url())
        urlLabel.setWordWrap(True)
        methodNameLabel = QtGui.QLabel(u"请求方式:")
        methodLabel = QtGui.QLabel(self.scsResponse.urllib2Request.get_method())
        
        requestHeaderNameLabel = QtGui.QLabel(u"<b>请求header:</b>")
        
        requestBodyNameLabel = QtGui.QLabel(u"<b>请求body:</b>")
        self.requestBodyTextEdit = QtGui.QTextEdit()
        self.requestBodyTextEdit.setReadOnly(True)
        self.requestBodyTextEdit.setMaximumHeight(50)
        self.requestBodyTextEdit.setMinimumHeight(50)
        self.requestBodyTextEdit.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        
        if hasattr(self.scsResponse.urllib2Request.data,'fileno'): #file like
            self.requestBodyTextEdit.setText('<file data. %s>'%self.scsResponse.urllib2Request.data.name)
        else:
            self.requestBodyTextEdit.setText(self.scsResponse.urllib2Request.data if self.scsResponse.urllib2Request.data is not None else '<request is empty!>')
        
        rowIdx = 0
        layout = QtGui.QGridLayout()
        
        layout.addWidget(urlNameLabel, rowIdx, 0)
        layout.addWidget(urlLabel, rowIdx, 1)
        rowIdx+=1
        layout.addWidget(methodNameLabel, rowIdx, 0)
        layout.addWidget(methodLabel, rowIdx, 1)
        rowIdx+=1
        layout.addWidget(requestHeaderNameLabel, rowIdx, 0)
        rowIdx+=1
        for k, v in self.scsResponse.urllib2Request.header_items() :
            layout.addWidget(QtGui.QLabel(k), rowIdx, 0)
            layout.addWidget(QtGui.QLabel(v), rowIdx, 1)
            rowIdx += 1
            
        layout.addWidget(requestBodyNameLabel, rowIdx, 0,)
        rowIdx += 1
        layout.addWidget(self.requestBodyTextEdit, rowIdx, 0, 1, 5)
        
        self.requestGroupBox.setLayout(layout)
        
    def initRsponseLayout(self):    
        ''' 初始化响应layout '''
        self.responseGroupBox = QtGui.QGroupBox(u"响应")
        responseCodeNameLabel = QtGui.QLabel(u"<b>响应码:</b>")
        responseCodeLabel = QtGui.QLabel()
        if hasattr(self.scsResponse.urllib2Response, 'code') :
            if self.scsResponse.urllib2Response.code >= 200 and self.scsResponse.urllib2Response.code <= 300:
                responseCode = '%d'%self.scsResponse.urllib2Response.code
            else:
                responseCode = '<font color=red>%d</font>'%self.scsResponse.urllib2Response.code
            responseCodeLabel.setText(responseCode)
        responseHeaderNameLabel = QtGui.QLabel(u"<b>响应header:</b>")
        responseBodyNameLabel = QtGui.QLabel(u"<b>响应body:</b>")
        self.responseBodyTextEdit = QtGui.QTextEdit()
        self.responseBodyTextEdit.setReadOnly(True)
        self.responseBodyTextEdit.setMaximumHeight(50)
        self.responseBodyTextEdit.setMinimumHeight(50)
        self.responseBodyTextEdit.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        
        if self.scsResponse.responseBody is not None:
            body = self.scsResponse.responseBody
        else:
            body = '<respondy body is empty!>'
        self.responseBodyTextEdit.setText( body )
        
        layout = QtGui.QGridLayout()
        layout.addWidget(responseCodeNameLabel, 0, 0)
        layout.addWidget(responseCodeLabel, 0, 1)
        layout.addWidget(responseHeaderNameLabel, 1, 0)
        rowIdx = 2
        headers = dict(self.scsResponse.urllib2Response.info()) if hasattr(self.scsResponse.urllib2Response, 'info') else {}
        for k, v in headers.iteritems() :
            layout.addWidget(QtGui.QLabel(k), rowIdx, 0)
            layout.addWidget(QtGui.QLabel(v), rowIdx, 1)
            rowIdx += 1
            
        layout.addWidget(responseBodyNameLabel, rowIdx, 0,)
        rowIdx += 1
        layout.addWidget(self.responseBodyTextEdit, rowIdx, 0, 1, 5)
        
        self.responseGroupBox.setLayout(layout)

class OperationLogTable(QtGui.QTableWidget):
    '''
        操作日志列表窗口
        {'operation':'upload file', 
         'result':'success',
         'request':request, 
         'response':response}
    '''
    logArray = []
    
    def __init__(self, openner=None):
        super(OperationLogTable, self).__init__(0, 2)
        self.openner = openner
        
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setHorizontalHeaderLabels((u"操作", u"结果"))
#         self.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
#         self.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.cellActivated.connect(self.showDetailDialog)    #双击
        
        self.setMinimumHeight(400)
        self.setMinimumWidth(200)
        
    def contextMenuEvent(self, event):
        ''' 详细、取消、重试、清空 '''
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        menu = QtGui.QMenu(self)
        if len(rowSet) == 1:#单选
            operDict = OperationLogTable.logArray[self.selectedIndexes()[0].row()]
            operRunnable = operDict['thread'];
            
            ''' 详细信息 '''
            detailAct = QtGui.QAction(u"详细信息", self,
                shortcut="Ctrl+D", statusTip=u"查看详细信息",
                triggered=self.detailAction)
            menu.addAction(detailAct)
            if operRunnable.state == RunnableState.WAITING or operRunnable.state == RunnableState.RUNNING :
                detailAct.setEnabled(False)
            else:
                detailAct.setEnabled(True)
            
            ''' 取消 '''
            cancelAct = QtGui.QAction(u"取消操作", self,
                shortcut="Ctrl+Q", statusTip=u"取消当前操作",
                triggered=self.cancelAction)
            menu.addAction(cancelAct)
            if operRunnable.state == RunnableState.RUNNING:
                cancelAct.setEnabled(True)
            else:
                cancelAct.setEnabled(False)
            
            ''' 重试 '''
            retryAct = QtGui.QAction(u"重试", self,
                shortcut="Ctrl+R", statusTip=u"重试当前失败的操作",
                triggered=self.retryAction)
            menu.addAction(retryAct)
            if operRunnable.state == RunnableState.DID_FAILED or operRunnable.state == RunnableState.DID_CANCELED:
                retryAct.setEnabled(True)
            else:
                retryAct.setEnabled(False)
            
            menu.addSeparator()
            
            ''' 清空 '''
            emptyAct = QtGui.QAction(u"清空列表", self,
                shortcut="Ctrl+E", statusTip=u"清空历史操作列表",
                triggered=self.emptyAction)
            menu.addAction(emptyAct)
            
            menu.exec_(event.globalPos())
        else:#多选
            print '--------'
            
    #  右键事件    
    def detailAction(self, event):
        if len(self.selectedIndexes()) > 0:
            self.showDetailDialog(self.selectedIndexes()[0].row(), 0)
    
    def cancelAction(self, event):
        if len(self.selectedIndexes()) > 0:
            operDict = OperationLogTable.logArray[self.selectedIndexes()[0].row()]
            operRunnable = operDict['thread'];
            if isinstance(operRunnable, FileUploadRunnable) or isinstance(operRunnable, DownloadObjectRunnable) or isinstance(operRunnable, FileMultipartUploadRunnable):
                operRunnable.cancel()
        
    def retryAction(self, event):
        if len(self.selectedIndexes()) > 0:
            operDict = OperationLogTable.logArray[self.selectedIndexes()[0].row()]
            operRunnable = operDict['thread'];
            if operRunnable.state == RunnableState.DID_CANCELED or operRunnable.state == RunnableState.DID_FAILED:
                if isinstance(operRunnable, FileUploadRunnable):
                    fileUploadRunnable = FileUploadRunnable(operRunnable.bucketName, operRunnable.filePath, operRunnable.prefix, operRunnable.parent)
                    QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadProgress(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),operRunnable.parent.uploadFileUpdateProgress)
                    QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFinished(PyQt_PyObject)'),operRunnable.parent.uploadMultiFileDidFinished)
                    QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFailed(PyQt_PyObject,PyQt_PyObject)'),operRunnable.parent.uploadMultiFileDidFailed)
                    QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidCanceled(PyQt_PyObject,PyQt_PyObject)'),operRunnable.parent.uploadMultiFileDidCanceled)
                    operRunnable.parent.openner.startOperationRunnable(fileUploadRunnable)
                    self.openner.operationLogTable.updateLogDict({'operation':'upload file' if isinstance(operRunnable, FileUploadRunnable) else 'download file', 
                                                                     'result':u'处理中',
                                                                     'thread':fileUploadRunnable})
                elif isinstance(operRunnable, FileMultipartUploadRunnable):
                    ''' 分片上传 '''
                    fileMultipartUploadRunnable = FileMultipartUploadRunnable(operRunnable.bucketName, operRunnable.filePath, operRunnable.prefix, operRunnable.parent)
                    QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadProgress(PyQt_PyObject, int, int)'),operRunnable.parent.uploadFileUpdateProgress)
                    QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFinished(PyQt_PyObject)'),operRunnable.parent.uploadMultiFileDidFinished)
                    QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFailed(PyQt_PyObject,PyQt_PyObject)'),operRunnable.parent.uploadMultiFileDidFailed)
                    QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidCanceled(PyQt_PyObject,PyQt_PyObject)'),operRunnable.parent.uploadMultiFileDidCanceled)
                    operRunnable.parent.openner.startOperationRunnable(fileMultipartUploadRunnable)
                    self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                                 'result':u'处理中',
                                                                 'thread':fileMultipartUploadRunnable})
                else:
                    downloadObjectRunnable = DownloadObjectRunnable(operRunnable.bucketName, operRunnable.key, operRunnable.fileMD5, operRunnable.destFilePath, operRunnable.tmpFilePath, operRunnable.parent)
                    QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('DownloadObjectRunnable(PyQt_PyObject)'),operRunnable.parent.downloadFileDidFinished)
                    QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('FileDownloadProgress(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),operRunnable.parent.downloadFileUpdateProgress)
                    QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('DownloadObjectDidFailed(PyQt_PyObject,PyQt_PyObject)'),operRunnable.parent.downloadFileDidFailed)
                    QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('DownloadObjectDidCanceled(PyQt_PyObject)'),operRunnable.parent.downloadFileDidCanceled)
                    result = self.openner.startOperationRunnable(downloadObjectRunnable)
                    
                    if result:
                        self.openner.operationLogTable.updateLogDict({'operation':'download file', 
                                                                     'result':u'处理中',
                                                                     'thread':downloadObjectRunnable})
                
                        self.openner.operationLogTable.removeOperation(operDict)
        
        
    def emptyAction(self, event):
        del OperationLogTable.logArray
        OperationLogTable.logArray = []
        self.refreshOperationList()
        
    def refreshOperationList(self):
        self.clearContents()
        self.setRowCount(0)
        
        for logDict in OperationLogTable.logArray :
            ''' 添加返回上级row '''
            operation = QtGui.QTableWidgetItem(logDict['operation'])  #name
            operation.setFlags(operation.flags() & ~QtCore.Qt.ItemIsEditable)
#             thread = logDict['thread']
            result = QtGui.QTableWidgetItem(u'%s'%(logDict['result']))
            result.setFlags(result.flags() & ~QtCore.Qt.ItemIsEditable)
    
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, operation)
            self.setItem(row, 1, result)
        
    def showDetailDialog(self, row, column):
        operDict = OperationLogTable.logArray[row]
        operRunnable = operDict['thread'];
        
        if isinstance(operRunnable, FileMultipartUploadRunnable):
            self.operationLogDetail = OperationLogDetailForMultipartUpload(operRunnable, self)
            self.operationLogDetail.show()
        else:
            if hasattr(operRunnable,'response') :
                self.operationLogDetail = OperationLogDetail(operRunnable.response, self)
                self.operationLogDetail.show()
            else:
                #TODO:提示稍后
                pass
    
    def removeOperation(self, logDict):
        for idx,dict in enumerate(OperationLogTable.logArray):
            if logDict['thread'] == dict['thread'] :
                del OperationLogTable.logArray[idx]
                break
#         self.refreshOperationList()
        self.removeRow(idx)
    
    def updateLogDict(self, logDict):
        ''' 更新操作日志 
            {'operation':'upload file', 
               'result':'uploading...',
               'thread':thread}
        '''
        founded = False
        for idx,dict in enumerate(OperationLogTable.logArray):
            if logDict['thread'] == dict['thread'] :
                dict['result'] = logDict['result']
                founded = True
                break
        
        if founded is False:
            OperationLogTable.logArray.append(logDict)
            idx = len(OperationLogTable.logArray)
            self.refreshOperationList()
            self.scrollToBottom()
        else:
            self.updateCell(idx, logDict)
#             self.refreshOperationList()
            
    def updateCell(self, rowIdx, logDict):
        ''' 更新指定行内容 '''
        result = self.item(rowIdx, 1)
        result.setText(logDict['result'])
        
        
class LoginWindow(QtGui.QWidget):
    ''' 登录页面 '''
    def __init__(self,openner=None):
        super(LoginWindow, self).__init__()
        
        self.openner = openner
        self.setupViews()
        
        
    def setupViews(self):
        self.loginGroup = QtGui.QGroupBox(u"登录")
        layout = QtGui.QGridLayout()

        self.accessKeylabel = QtGui.QLabel("Access Key:")
        self.accessKeyEdit = QtGui.QLineEdit()
        self.accessKeyEdit.setText('')
        layout.addWidget(self.accessKeylabel, 0, 0)
        layout.addWidget(self.accessKeyEdit, 0, 1, 1, 2)
        
        accessKey = getValueFromWindowsRegistryByKey(u'accessKey')
        if accessKey : self.accessKeyEdit.setText(accessKey)
        
        self.accessSecretlabel = QtGui.QLabel("Access Secret:")
        self.accessSecretEdit = QtGui.QLineEdit()
        self.accessSecretEdit.setText('')
        layout.addWidget(self.accessSecretlabel, 1, 0)
        layout.addWidget(self.accessSecretEdit, 1, 1)
        
        isSaveSecret = getValueFromWindowsRegistryByKey(u'isSaveSecret')
        accessSecret = getValueFromWindowsRegistryByKey(u'accessSecret')
        
        self.saveSecretCheckBox = QtGui.QCheckBox(u"记住secret")
        self.saveSecretCheckBox.setChecked(False)
        layout.addWidget(self.saveSecretCheckBox, 1, 2)
        
        if cmp('1',isSaveSecret)==0 and accessSecret is not None: 
            self.saveSecretCheckBox.setChecked(True)
            self.accessSecretEdit.setText(accessSecret)
            
        self.isSecureConnectionCheckBox = QtGui.QCheckBox(u"使用https加密连接")
        self.isSecureConnectionCheckBox.setChecked(True)
        layout.addWidget(self.isSecureConnectionCheckBox, 2, 1)

        self.startButton = QtGui.QPushButton(u"登录")
        self.startButton.clicked.connect(self.loginAction)
        layout.addWidget(self.startButton, 3, 0)
        
        self.loginGroup.setLayout(layout)
        self.loginGroup.setFixedSize(400, 200)
        
        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins((self.openner.width()-400)/2, (self.openner.height()-200)/2,
                                   (self.openner.width()-400)/2, (self.openner.height()-200)/2)
    
        layout.addWidget(self.loginGroup)
        
        self.setLayout(layout)
        
    def keyPressEvent(self, event):
        ''' 回车键登录 '''
        if event.key() == QtCore.Qt.Key_Return: 
            self.loginAction()
            
    def loginAction(self):
        self.openner.loginBtnAction()


class BucketInfoDialog(QtGui.QDialog):
    isRunning = False
    ''' bucket信息对话框 '''
    def __init__(self, bucketName, parent=None):
        super(BucketInfoDialog, self).__init__(parent)
        
        self.openner = parent
        self.bucketName = bucketName
        self.isRunning = True
        
        bucketNameLabel = QtGui.QLabel(u"<b>%s</b>"%self.bucketName)
        deleteQuantityNameLabel = QtGui.QLabel("deleteQuantity:")
        self.deleteQuantityLabel = QtGui.QLabel("")
        projectIdNameLabel = QtGui.QLabel("project id:")
        self.projectIdLabel = QtGui.QLabel("")
        downloadQuantityNameLabel = QtGui.QLabel("downloadQuantity:")
        self.downloadQuantityLabel = QtGui.QLabel("")
        downloadCapacityNameLabel = QtGui.QLabel("downloadCapacity:")
        self.downloadCapacityLabel = QtGui.QLabel("")
        capacityCNameLabel = QtGui.QLabel("CapacityC:")
        self.capacityCLabel = QtGui.QLabel("")
        quantityCNameLabel = QtGui.QLabel("QuantityC:")
        self.quantityCLabel = QtGui.QLabel("")
        uploadCapacityNameLabel = QtGui.QLabel("UploadCapacity:")
        self.uploadCapacityLabel = QtGui.QLabel("")
        uploadQuantityNameLabel = QtGui.QLabel("UploadQuantity:")
        self.uploadQuantityLabel = QtGui.QLabel("")
        last_modifiedNameLabel = QtGui.QLabel("Last-Modified:")
        self.last_modifiedLabel = QtGui.QLabel('')
        sizeCNameLabel = QtGui.QLabel("SizeC:")
        self.sizeCLabel = QtGui.QLabel('')
        deleteCapacityNameLabel = QtGui.QLabel("DeleteCapacity:")
        self.deleteCapacityLabel = QtGui.QLabel('')
        quantityNameLabel = QtGui.QLabel(u"文件总数量:")
        self.quantityLabel = QtGui.QLabel('')
        capacityNameLabel = QtGui.QLabel(u"文件总大小:")
        self.capacityLabel = QtGui.QLabel('')
        ownerNameLabel = QtGui.QLabel("Owner:")
        self.ownerLabel = QtGui.QLabel('')
        
        mainLayout = QtGui.QGridLayout()
        mainLayout.addWidget(bucketNameLabel, 0, 0, 1, 2)
        mainLayout.addWidget(deleteQuantityNameLabel, 1, 0)
        mainLayout.addWidget(self.deleteQuantityLabel, 1, 1)
        mainLayout.addWidget(projectIdNameLabel, 2, 0)
        mainLayout.addWidget(self.projectIdLabel, 2, 1)
        mainLayout.addWidget(downloadQuantityNameLabel, 3, 0)
        mainLayout.addWidget(self.downloadQuantityLabel, 3, 1)
        mainLayout.addWidget(downloadCapacityNameLabel, 4, 0)
        mainLayout.addWidget(self.downloadCapacityLabel, 4, 1)
        mainLayout.addWidget(capacityCNameLabel, 5, 0)
        mainLayout.addWidget(self.capacityCLabel, 5, 1)
        mainLayout.addWidget(quantityCNameLabel, 6, 0)
        mainLayout.addWidget(self.quantityCLabel, 6, 1)
        mainLayout.addWidget(uploadCapacityNameLabel, 7, 0)
        mainLayout.addWidget(self.uploadCapacityLabel, 7, 1)
        mainLayout.addWidget(uploadQuantityNameLabel, 8, 0)
        mainLayout.addWidget(self.uploadQuantityLabel, 8, 1)
        mainLayout.addWidget(last_modifiedNameLabel, 9, 0)
        mainLayout.addWidget(self.last_modifiedLabel, 9, 1)
        mainLayout.addWidget(sizeCNameLabel, 10, 0)
        mainLayout.addWidget(self.sizeCLabel, 10, 1)
        mainLayout.addWidget(deleteCapacityNameLabel, 11, 0)
        mainLayout.addWidget(self.deleteCapacityLabel, 11, 1)
        mainLayout.addWidget(quantityNameLabel, 12, 0)
        mainLayout.addWidget(self.quantityLabel, 12, 1)
        mainLayout.addWidget(capacityNameLabel, 13, 0)
        mainLayout.addWidget(self.capacityLabel, 13, 1)
        mainLayout.addWidget(ownerNameLabel, 14, 0)
        mainLayout.addWidget(self.ownerLabel, 14, 1)
        
        ''' acl '''
        self.aclTable = QtGui.QTableWidget(2, 5, self)
        self.aclTable.setHorizontalHeaderLabels((u"组", u"读权限", u"写权限", u"读ACL", u"写ACL"))
        self.aclTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.aclTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.verticalHeader().hide()
        self.aclTable.setShowGrid(False)
        
        columns = 5
        rows = 2
        for column in range(columns):
            if column == 0:
                continue
            for row in range(rows):
                item = QtGui.QTableWidgetItem('')
                item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                              QtCore.Qt.ItemIsEnabled)
#                 item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.aclTable.setItem(row, column, item)
        
        
        item = QtGui.QTableWidgetItem(u'匿名用户组')
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclTable.setItem(0, 0, item)
        
        item = QtGui.QTableWidgetItem(u'认证用户组')
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclTable.setItem(1, 0, item)
        mainLayout.addWidget(self.aclTable,15,0,1,2)
        
        ''' acl user '''        
        self.aclUserTable = QtGui.QTableWidget(0, 5, self)
        self.aclUserTable.setHorizontalHeaderLabels((u"UserId", u"读权限", u"写权限", u"读ACL", u"写ACL"))
        self.aclUserTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.aclUserTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.verticalHeader().hide()
        self.aclUserTable.setShowGrid(False)
        
        self.aclUserTable.contextMenuEvent = self.aclUserTableContextMenuEvent
        
        mainLayout.addWidget(self.aclUserTable,16,0,1,2)
        
        ''' button '''
        self.buttonBox = QtGui.QDialogButtonBox()
        self.acceptBtn = QtGui.QPushButton(u"确认")
        self.acceptBtn.setEnabled(False)
        self.buttonBox.addButton(self.acceptBtn, QtGui.QDialogButtonBox.AcceptRole)
        
        self.cancelBtn = QtGui.QPushButton(u"取消")
        self.cancelBtn.setEnabled(True)
        self.buttonBox.addButton(self.cancelBtn, QtGui.QDialogButtonBox.RejectRole)
        
        self.buttonBox.accepted.connect(self.updateAcl)
        self.buttonBox.rejected.connect(self.reject)
        
        mainLayout.addWidget(self.buttonBox, 17, 0, 1, 2)
        
        self.setLayout(mainLayout)
        self.setWindowTitle(u'%s的Meta信息'%self.bucketName)
        self.resize(400, 600)
        self.connect(self, QtCore.SIGNAL("finished(int)"), self.finished)
        self.refreshViews()
    
    def finished(self, code):
        self.isRunning = False
        self.deleteLater()    
    
    
    def aclUserTableCellChanged (self, row, col):
        ''' cell 修改监听事件 '''
        if col == 0:
            userId = u'%s'%self.aclUserTable.item(row, col).text()
            if len(userId) != 20 and len(userId) != 0:
                QtGui.QMessageBox.information(self,
                                              u"UserId长度不合法", 
                                              u'<p>UserId长度必须是20位</p>')
                item = self.aclUserTable.item(row, col)
                self.aclUserTable.scrollToItem(item)
                self.aclUserTable.setItemSelected(item,True)
        
    def aclUserTableContextMenuEvent(self, event):
        ''' userTable 右键 '''
        rows=[]
        for idx in self.aclUserTable.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        menu = QtGui.QMenu(self.aclUserTable)
        
        ''' 添加 '''
        addAct = QtGui.QAction(u"添加用户", self.aclUserTable,
            shortcut="Ctrl+A", statusTip=u"添加一条用户授权信息",
            triggered=self.addUserAction)
        menu.addAction(addAct)
            
        menu.addSeparator()
        ''' 删除 '''
        delAct = QtGui.QAction(u"删除", self.aclUserTable,
            shortcut="Ctrl+D", statusTip=u"删除选中的用户授权记录",
            triggered=self.delUserAction)
        menu.addAction(delAct)
        
        if len(rowSet) == 0:
            delAct.setEnabled(False)
        else:
            delAct.setEnabled(True)
            
        menu.exec_(event.globalPos())

    ''' aclUserTable 右键 begin'''
    def addUserAction(self, event):
        row = self.aclUserTable.rowCount()
        self.aclUserTable.insertRow(row)
        
        useritem = QtGui.QTableWidgetItem('')
        useritem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
        useritem.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclUserTable.setItem(row, 0, useritem)
        
        for idx in xrange(4):
            item = QtGui.QTableWidgetItem('')
            item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.aclUserTable.setItem(row, idx+1, item)
    
        self.aclUserTable.scrollToBottom()
        self.aclUserTable.editItem(useritem)
    
    def delUserAction(self, event):
        rows=[]
        for idx in self.aclUserTable.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        if len(rowSet)>0:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                   u"删除用户授权", 
                   u'<p>您确定删除当前选中的userid么？</p>',
                   QtGui.QMessageBox.NoButton, self)
            msgBox.addButton(u"继续", QtGui.QMessageBox.AcceptRole)
            msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
            if msgBox.exec_() == QtGui.QMessageBox.AcceptRole:
                for row in rowSet:
                    self.aclUserTable.removeRow(row)
        
    ''' aclUserTable 右键 end'''
        
>>>>>>> FETCH_HEAD
    def refreshViews(self):
        if self.isRunning:
            bucketInfoRunnable = BucketInfoRunnable(self.bucketName, self)
            QtCore.QObject.connect(bucketInfoRunnable.emitter,QtCore.SIGNAL('BucketInfoRunnable(PyQt_PyObject, PyQt_PyObject)'),self.setupView)
            QtCore.QObject.connect(bucketInfoRunnable.emitter,QtCore.SIGNAL('BucketInfoDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.bucketInfoDidFailed)
            self.openner.openner.startOperationRunnable(bucketInfoRunnable)
            
            self.openner.openner.operationLogTable.updateLogDict({'operation':'get bucket info', 
                                                       'result':u'处理中',
                                                       'thread':bucketInfoRunnable})
        
    def bucketInfoDidFailed(self, runnable, errorMsg):
        if self.isRunning :
            self.openner.openner.operationLogTable.updateLogDict({'operation':'get bucket info', 
                                                       'result':u'失败',
                                                       'thread':runnable})
            reply = QtGui.QMessageBox.information(self,
                    u"获取bucket信息失败", 
                    u'<p>失败原因：%s</p>'%errorMsg)
        
    def setupView(self, runnable, metaResult):
        ''' 接口返回数据后，更新界面 '''
        if self.isRunning is None:
            return
        
        self.openner.openner.operationLogTable.updateLogDict({'operation':'get bucket info', 
                                                   'result':u'完成',
                                                   'thread':runnable})
        
        '''
        {u'DeleteQuantity': 17, u'DeleteCapacity': 58876525, 
        u'Capacity': 209726592,
u'PoolName': u'plSAE', 
        u'ProjectID': 4544, u'SizeC': 0, 
        u'DownloadCapacity': 971260828, u'UploadQuantity': 24, 
        u'CapacityC': 0,
   u'ACL': {u'SINA0000001001NHT3M7': [u'read', u'write', u'read_acp', u'write_acp']}, 
u'Project': u'create-a-bucket22', 
        u'UploadCapacity': 268603117, 
u'RelaxUpload': True, 
        u'DownloadQuantity': 1587, 
        u'Last-Modified': u'Mon, 19 May 2014 09:29:50 UTC', 
        u'QuantityC': 0, u'Owner': u'SINA0000001001NHT3M7', 
        u'Quantity': 7}
        '''
        self.deleteQuantityLabel.setText('%d'%metaResult['DeleteQuantity'])
        self.deleteCapacityLabel.setText('%d'%metaResult['DeleteCapacity'])
        self.capacityLabel.setText(filesizeformat('%d'%metaResult['Capacity']))
        self.projectIdLabel.setText('%d'%metaResult['ProjectID'])
        self.sizeCLabel.setText('%d'%metaResult['SizeC'])
        self.downloadCapacityLabel.setText('%d'%metaResult['DownloadCapacity'])
        self.uploadQuantityLabel.setText('%d'%metaResult['UploadQuantity'])
        self.capacityCLabel.setText('%d'%metaResult['CapacityC'])
        self.uploadCapacityLabel.setText('%d'%metaResult['UploadCapacity'])
        self.downloadQuantityLabel.setText('%d'%metaResult['DownloadQuantity'])
        self.last_modifiedLabel.setText(rfc822_parsedate(metaResult['Last-Modified']).strftime('%Y-%m-%d %H:%M:%S'))
        self.quantityCLabel.setText('%d'%metaResult['QuantityC'])
        self.quantityLabel.setText('%d'%metaResult['Quantity'])
        
        self.ownerLabel.setText(metaResult['Owner'])
        ''' acl '''
        aclDict = metaResult['ACL']
        for key, value in aclDict.iteritems():
            if cmp(key,'GRPS000000ANONYMOUSE') == 0 :#匿名用户组
                #[u'read', u'write', u'read_acp', u'write_acp']
                if 'read' in value:
                    self.aclTable.item(0, 1).setCheckState(QtCore.Qt.Checked)
                
                if 'write' in value:
                    self.aclTable.item(0, 2).setCheckState(QtCore.Qt.Checked)
                    
                if 'read_acp' in value:
                    self.aclTable.item(0, 3).setCheckState(QtCore.Qt.Checked)
                    
                if 'write_acp' in value:
                    self.aclTable.item(0, 4).setCheckState(QtCore.Qt.Checked)
                
            elif cmp(key,'GRPS0000000CANONICAL') == 0 :#认证用户组
                if 'read' in value:
                    self.aclTable.item(1, 1).setCheckState(QtCore.Qt.Checked)
                
                if 'write' in value:
                    self.aclTable.item(1, 2).setCheckState(QtCore.Qt.Checked)
                    
                if 'read_acp' in value:
                    self.aclTable.item(1, 3).setCheckState(QtCore.Qt.Checked)
                    
                if 'write_acp' in value:
                    self.aclTable.item(1, 4).setCheckState(QtCore.Qt.Checked)
            else:#其他用户
                row = self.aclUserTable.rowCount()
                self.aclUserTable.insertRow(row)
                
                item = QtGui.QTableWidgetItem(key)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable |QtCore.Qt.ItemIsSelectable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.aclUserTable.setItem(row, 0, item)
                
                for idx in xrange(4):
                    item = QtGui.QTableWidgetItem('')
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                                  QtCore.Qt.ItemIsEnabled)
                    item.setCheckState(QtCore.Qt.Unchecked)
                    self.aclUserTable.setItem(row, idx+1, item)
                    
                if 'read' in value:
                    self.aclUserTable.item(row, 1).setCheckState(QtCore.Qt.Checked)
                
                if 'write' in value:
                    self.aclUserTable.item(row, 2).setCheckState(QtCore.Qt.Checked)
                    
                if 'read_acp' in value:
                    self.aclUserTable.item(row, 3).setCheckState(QtCore.Qt.Checked)
                    
                if 'write_acp' in value:
                    self.aclUserTable.item(row, 4).setCheckState(QtCore.Qt.Checked)
            
        self.acceptBtn.setEnabled(True)
        
        self.aclUserTable.cellChanged.connect(self.aclUserTableCellChanged)
        
        
    def updateAcl(self):
        acl = {}
        
        '''处理 ACL_GROUP_ANONYMOUSE'''
        anonymouseAclArray = []
        if self.aclTable.item(0, 1).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_READ)
        if self.aclTable.item(0, 2).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_WRITE)
        if self.aclTable.item(0, 3).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_READ_ACP)
        if self.aclTable.item(0, 4).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_WRITE_ACP)
        
        '''处理 ACL_GROUP_CANONICAL'''
        canonicalAclArray = []
        if self.aclTable.item(1, 1).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_READ)
        if self.aclTable.item(1, 2).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_WRITE)
        if self.aclTable.item(1, 3).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_READ_ACP)
        if self.aclTable.item(1, 4).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_WRITE_ACP)
        
        if len(anonymouseAclArray) > 0:
            acl[ACL.ACL_GROUP_ANONYMOUSE] = anonymouseAclArray
        if len(canonicalAclArray) > 0:
            acl[ACL.ACL_GROUP_CANONICAL] = canonicalAclArray
            
        ''' 处理用户acl '''  
        userAclDict = {}  
        aclArray = []
        aclUserTableRowCount = self.aclUserTable.rowCount()
        for row in xrange(aclUserTableRowCount):
            aclArray = []
            userId = u'%s'%self.aclUserTable.item(row, 0).text()
            acl_read = (self.aclUserTable.item(row, 1).checkState() == QtCore.Qt.Checked)
            acl_write = (self.aclUserTable.item(row, 2).checkState() == QtCore.Qt.Checked)
            acl_read_acp = (self.aclUserTable.item(row, 3).checkState() == QtCore.Qt.Checked)
            acl_write_acp = (self.aclUserTable.item(row, 4).checkState() == QtCore.Qt.Checked)
        
            if acl_read or acl_write or acl_read_acp or acl_write_acp :
                if acl_read:
                    aclArray.append(ACL.ACL_READ)
                if acl_write:
                    aclArray.append(ACL.ACL_WRITE)
                if acl_read_acp:
                    aclArray.append(ACL.ACL_READ_ACP)
                if acl_write_acp:
                    aclArray.append(ACL.ACL_WRITE_ACP)
                
                userAclDict[userId] = aclArray
                
        if len(aclArray) > 0:
            for k,v in userAclDict.iteritems():
                acl[k] = v
        
        updateFileACLRunnable = UpdateFileACLRunnable(self.bucketName, None, acl)
        QtCore.QObject.connect(updateFileACLRunnable.emitter,QtCore.SIGNAL('UpdateFileACLRunnable(PyQt_PyObject)'),self.openner.updateFileACLDidFinished)
        QtCore.QObject.connect(updateFileACLRunnable.emitter,QtCore.SIGNAL('UpdateFileACLDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.openner.updateFileAclDidFailed)
        self.openner.openner.startOperationRunnable(updateFileACLRunnable)
        ''' add oper log'''
        self.openner.openner.operationLogTable.updateLogDict({'operation':'update bucket acl', 
                                                    'result':u'处理中',
                                                    'thread':updateFileACLRunnable})
        
        self.accept()

class MultiFileInfoDialog(QtGui.QDialog):
    isRunning = False
    ''' 多文件信息对话框 '''
    def __init__(self, parent=None, bucketName=None, keys=None, prefix=None):
        super(MultiFileInfoDialog, self).__init__(parent)
        
        self.openner = parent
        
        self.bucketName = bucketName
        self.keys = keys
        self.prefix = prefix
        self.isRunning = True
        #目录数量
        folderAmount = 0
        for key in keys:
            if key.find('/') == len(key)-1 :
                folderAmount += 1
        self.fileNameLabel = QtGui.QLabel(u"<b>%d个文件</b>"%len(keys))
        
        self.kindLabel = QtGui.QLabel(u"类型:")
        self.kindValueLabel = QtGui.QLabel("多种类型")
        
        self.bucketLabel = QtGui.QLabel(u"所属bucket:")
        self.bucketValueLabel = QtGui.QLabel(bucketName)
        
        ''' button '''
        self.buttonBox = QtGui.QDialogButtonBox()
        self.acceptBtn = QtGui.QPushButton(u"确认")
        self.acceptBtn.setEnabled(True)
        self.buttonBox.addButton(self.acceptBtn, QtGui.QDialogButtonBox.AcceptRole)
        
        self.cancelBtn = QtGui.QPushButton(u"取消")
        self.cancelBtn.setEnabled(True)
        self.buttonBox.addButton(self.cancelBtn, QtGui.QDialogButtonBox.RejectRole)
        
        self.buttonBox.accepted.connect(self.updateAcl)
        self.buttonBox.rejected.connect(self.reject)
        
        mainLayout = QtGui.QGridLayout()
        mainLayout.addWidget(self.fileNameLabel, 0, 0, 1, 2)
        mainLayout.addWidget(self.kindLabel, 1, 0)
        mainLayout.addWidget(self.kindValueLabel, 1, 1)
        
        mainLayout.addWidget(self.bucketLabel, 2, 0)
        mainLayout.addWidget(self.bucketValueLabel, 2, 1)
        
        ''' acl '''
        self.aclTable = QtGui.QTableWidget(2, 5, self)
        self.aclTable.setHorizontalHeaderLabels((u"组", u"读权限", u"写权限", u"读ACL", u"写ACL"))
        self.aclTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.aclTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.verticalHeader().hide()
        self.aclTable.setShowGrid(False)
        
        columns = 5
        rows = 2
        for column in range(columns):
            if column == 0:
                continue
            for row in range(rows):
                item = QtGui.QTableWidgetItem('')
                item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                              QtCore.Qt.ItemIsEnabled)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.aclTable.setItem(row, column, item)
        
        item = QtGui.QTableWidgetItem(u'匿名用户组')
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclTable.setItem(0, 0, item)
        
        item = QtGui.QTableWidgetItem(u'认证用户组')
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclTable.setItem(1, 0, item)
        mainLayout.addWidget(self.aclTable,3,0,1,2)
        
        ''' acl user '''        
        self.aclUserTable = QtGui.QTableWidget(0, 5, self)
        self.aclUserTable.setHorizontalHeaderLabels((u"UserId", u"读权限", u"写权限", u"读ACL", u"写ACL"))
        self.aclUserTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.aclUserTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.verticalHeader().hide()
        self.aclUserTable.setShowGrid(False)
        self.aclUserTable.cellChanged.connect(self.aclUserTableCellChanged)
        
        self.aclUserTable.contextMenuEvent = self.aclUserTableContextMenuEvent
        
        mainLayout.addWidget(self.aclUserTable,4,0,1,2)
        
        mainLayout.addWidget(self.buttonBox, 5, 0, 1, 2)
        
        self.setLayout(mainLayout)
        self.setWindowTitle(key)
        self.resize(400, 400)
        self.connect(self, QtCore.SIGNAL("finished(int)"), self.finished)
        
    def finished(self, code):
        self.isRunning = False
        self.deleteLater()
        
    def aclUserTableCellChanged (self, row, col):
        ''' cell 修改监听事件 '''
        if col == 0:
            userId = u'%s'%self.aclUserTable.item(row, col).text()
            if len(userId) != 20 and len(userId) != 0:
                QtGui.QMessageBox.information(self,
                                              u"UserId长度不合法", 
                                              u'<p>UserId长度必须是20位</p>')
                item = self.aclUserTable.item(row, col)
                self.aclUserTable.scrollToItem(item)
                self.aclUserTable.setItemSelected(item,True)
        
    def aclUserTableContextMenuEvent(self, event):
        ''' userTable 右键 '''
        rows=[]
        for idx in self.aclUserTable.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        menu = QtGui.QMenu(self.aclUserTable)
        
        
        ''' 添加 '''
        addAct = QtGui.QAction(u"添加用户", self.aclUserTable,
            shortcut="Ctrl+A", statusTip=u"添加一条用户授权信息",
            triggered=self.addUserAction)
        menu.addAction(addAct)
            
        menu.addSeparator()
        ''' 删除 '''
        delAct = QtGui.QAction(u"删除", self.aclUserTable,
            shortcut="Ctrl+D", statusTip=u"删除选中的用户授权记录",
            triggered=self.delUserAction)
        menu.addAction(delAct)
        
        if len(rowSet) == 0:
            delAct.setEnabled(False)
        else:
            delAct.setEnabled(True)
            
        menu.exec_(event.globalPos())

    ''' aclUserTable 右键 begin'''
    def addUserAction(self, event):
        row = self.aclUserTable.rowCount()
        self.aclUserTable.insertRow(row)
        
        useritem = QtGui.QTableWidgetItem('')
        useritem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
        useritem.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclUserTable.setItem(row, 0, useritem)
        
        for idx in xrange(4):
            item = QtGui.QTableWidgetItem('')
            item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.aclUserTable.setItem(row, idx+1, item)
    
        self.aclUserTable.scrollToBottom()
        self.aclUserTable.editItem(useritem)
    
    def delUserAction(self, event):
        rows=[]
        for idx in self.aclUserTable.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        if len(rowSet)>0:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                   u"删除用户授权", 
                   u'<p>您确定删除当前选中的userid么？</p>',
                   QtGui.QMessageBox.NoButton, self)
            msgBox.addButton(u"继续", QtGui.QMessageBox.AcceptRole)
            msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
            if msgBox.exec_() == QtGui.QMessageBox.AcceptRole:
                for row in rowSet:
                    self.aclUserTable.removeRow(row)
        
    ''' aclUserTable 右键 end'''

    def updateAcl(self):
        acl = {}
        
        '''处理 ACL_GROUP_ANONYMOUSE'''
        anonymouseAclArray = []
        if self.aclTable.item(0, 1).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_READ)
        if self.aclTable.item(0, 2).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_WRITE)
        if self.aclTable.item(0, 3).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_READ_ACP)
        if self.aclTable.item(0, 4).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_WRITE_ACP)
        
        '''处理 ACL_GROUP_CANONICAL'''
        canonicalAclArray = []
        if self.aclTable.item(1, 1).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_READ)
        if self.aclTable.item(1, 2).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_WRITE)
        if self.aclTable.item(1, 3).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_READ_ACP)
        if self.aclTable.item(1, 4).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_WRITE_ACP)
        
        if len(anonymouseAclArray) > 0:
            acl[ACL.ACL_GROUP_ANONYMOUSE] = anonymouseAclArray
        if len(canonicalAclArray) > 0:
            acl[ACL.ACL_GROUP_CANONICAL] = canonicalAclArray
            
        ''' 处理用户acl '''  
        userAclDict = {}  
        aclArray = []
        aclUserTableRowCount = self.aclUserTable.rowCount()
        for row in xrange(aclUserTableRowCount):
            aclArray = []
            userId = u'%s'%self.aclUserTable.item(row, 0).text()
            acl_read = (self.aclUserTable.item(row, 1).checkState() == QtCore.Qt.Checked)
            acl_write = (self.aclUserTable.item(row, 2).checkState() == QtCore.Qt.Checked)
            acl_read_acp = (self.aclUserTable.item(row, 3).checkState() == QtCore.Qt.Checked)
            acl_write_acp = (self.aclUserTable.item(row, 4).checkState() == QtCore.Qt.Checked)
        
            if acl_read or acl_write or acl_read_acp or acl_write_acp :
                if acl_read:
                    aclArray.append(ACL.ACL_READ)
                if acl_write:
                    aclArray.append(ACL.ACL_WRITE)
                if acl_read_acp:
                    aclArray.append(ACL.ACL_READ_ACP)
                if acl_write_acp:
                    aclArray.append(ACL.ACL_WRITE_ACP)
                
                userAclDict[userId] = aclArray
                
        if len(aclArray) > 0:
            for k,v in userAclDict.iteritems():
                acl[k] = v
        
        '''============='''
        for key in self.keys:
            updateFileACLRunnable = UpdateFileACLRunnable(self.bucketName, '%s%s'%(self.prefix, key), acl)
            QtCore.QObject.connect(updateFileACLRunnable.emitter,QtCore.SIGNAL('UpdateFileACLRunnable(PyQt_PyObject)'),self.openner.updateFileAclDidFinished)
            QtCore.QObject.connect(updateFileACLRunnable.emitter,QtCore.SIGNAL('UpdateFileACLDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.openner.updateFileAclDidFailed)
            self.openner.openner.startOperationRunnable(updateFileACLRunnable)
            ''' add oper log'''
            self.openner.openner.operationLogTable.updateLogDict({'operation':'update file acl', 
                                                        'result':u'处理中',
                                                        'thread':updateFileACLRunnable})
        
        self.accept()


class GenUrlDialog(QtGui.QDialog):
    
    def generateURL(self):
        iso8601_fmt = '%Y-%m-%d %H:%M:%S'
        import datetime
        d = datetime.datetime.strptime(u'%s'%self.datetimeEdit.text(), iso8601_fmt)
        expire = d - datetime.datetime.now()
        
        ip = u'%s'%self.ipEdit.text()
        if len(ip) < 7:
            ip = None
        
        scs = None
        bucketAsDomain = False
        if self.bucketAsDomainCheckbox.checkState() and len(self.bucketAsDomainEdit.text()) > 0:
            scs = SCSBucket(u'%s'%self.bucketAsDomainEdit.text())
            bucketAsDomain = True
        else:
            scs = SCSBucket(self.bucketName)
        url = scs.make_url_authed(key=u'%s%s'%(self.prefix,self.key), expire=expire, ip=ip, bucketAsDomain=bucketAsDomain);
        self.resultEdit.setText(url)
    
    def bucketAsDomainCheckboxChanged(self, event):
        if self.bucketAsDomainCheckbox.checkState():
            self.bucketAsDomainEdit.setEnabled(True)
        else:
            self.bucketAsDomainEdit.setText('')
            self.bucketAsDomainEdit.setEnabled(False)
    
    ''' 文件信息对话框 '''
    def __init__(self, parent=None, bucketName=None, key=None, prefix=None):
        super(GenUrlDialog, self).__init__(parent)
        
        self.openner = parent
        
        self.bucketName = bucketName
        self.key = key
        self.prefix = prefix
        self.fileNameLabel = QtGui.QLabel(u"<b>%s</b>"%key)
        
        self.datetimeEdit = QtGui.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.datetimeEdit.setDisplayFormat('yyyy-MM-dd hh:mm:ss')
        self.datetimeEdit.setDateRange(QtCore.QDate(2000, 1, 1), QtCore.QDate(2050, 12, 30))
        self.datetimeLabel = QtGui.QLabel(u"过期时间(%s - %s)："%(self.datetimeEdit.minimumDate().toString(QtCore.Qt.ISODate),
                                                             self.datetimeEdit.maximumDate().toString(QtCore.Qt.ISODate)))
        
        self.ipLabel = QtGui.QLabel(u"IP地址限制：")
        self.ipEdit = QtGui.QLineEdit()

        self.bucketAsDomainCheckbox = QtGui.QCheckBox(u"自定义域名")
        self.bucketAsDomainCheckbox.stateChanged.connect(self.bucketAsDomainCheckboxChanged)
        self.bucketAsDomainCheckbox.setChecked(False)
        self.bucketAsDomainEdit = QtGui.QLineEdit()
        self.bucketAsDomainEdit.setEnabled(False)
        
        ''' url结果editor '''
        self.resultEdit = QtGui.QTextEdit()
        
        ''' button '''
        self.buttonBox = QtGui.QDialogButtonBox()
        self.acceptBtn = QtGui.QPushButton(u"生成")
        self.acceptBtn.setEnabled(True)
        self.buttonBox.addButton(self.acceptBtn, QtGui.QDialogButtonBox.AcceptRole)
        
        self.cancelBtn = QtGui.QPushButton(u"关闭")
        self.cancelBtn.setEnabled(True)
        self.buttonBox.addButton(self.cancelBtn, QtGui.QDialogButtonBox.RejectRole)
        
        self.buttonBox.accepted.connect(self.generateURL)
        self.buttonBox.rejected.connect(self.reject)

        
        mainLayout = QtGui.QGridLayout()
        mainLayout.addWidget(self.fileNameLabel, 0, 0, 1, 2)
        mainLayout.addWidget(self.datetimeLabel, 1, 0)
        mainLayout.addWidget(self.datetimeEdit, 1, 1)
        
        mainLayout.addWidget(self.ipLabel, 2, 0)
        mainLayout.addWidget(self.ipEdit, 2, 1)
        
        mainLayout.addWidget(self.bucketAsDomainCheckbox, 3, 0)
        mainLayout.addWidget(self.bucketAsDomainEdit, 3, 1)
        
        mainLayout.addWidget(self.resultEdit, 4, 0, 1, 2)
        
        mainLayout.addWidget(self.buttonBox, 5, 0, 1, 2)
        
        self.setLayout(mainLayout)
        self.setWindowTitle(key)
        self.resize(400, 400)
        self.connect(self, QtCore.SIGNAL("finished(int)"), lambda code:self.deleteLater())
        

class FileInfoDialog(QtGui.QDialog):
    ''' 文件信息对话框 '''
    isRunning = False
    
    def __init__(self, parent=None, bucketName=None, key=None, prefix=None):
        super(FileInfoDialog, self).__init__(parent)
        
        self.openner = parent
        
        self.bucketName = bucketName
        self.key = key
        self.prefix = prefix
        self.fileNameLabel = QtGui.QLabel(u"<b>%s</b>"%key)
        
        self.kindLabel = QtGui.QLabel(u"类型:")
        self.kindValueLabel = QtGui.QLabel("")
        
        self.sizeLabel = QtGui.QLabel(u"文件大小:")
        self.sizeValueLabel = QtGui.QLabel("")
        
        self.bucketLabel = QtGui.QLabel(u"所属bucket:")
        self.bucketValueLabel = QtGui.QLabel(bucketName)
        
        self.createDateLabel = QtGui.QLabel(u"修改日期:")
        self.createDateValueLabel = QtGui.QLabel('')
        
        ''' button '''
        self.buttonBox = QtGui.QDialogButtonBox()
        self.acceptBtn = QtGui.QPushButton(u"确认")
        self.acceptBtn.setEnabled(False)
        self.buttonBox.addButton(self.acceptBtn, QtGui.QDialogButtonBox.AcceptRole)
        
        self.cancelBtn = QtGui.QPushButton(u"取消")
        self.cancelBtn.setEnabled(True)
        self.buttonBox.addButton(self.cancelBtn, QtGui.QDialogButtonBox.RejectRole)
        
        self.buttonBox.accepted.connect(self.updateAcl)
        self.buttonBox.rejected.connect(self.reject)
        
        mainLayout = QtGui.QGridLayout()
        mainLayout.addWidget(self.fileNameLabel, 0, 0, 1, 2)
        mainLayout.addWidget(self.kindLabel, 1, 0)
        mainLayout.addWidget(self.kindValueLabel, 1, 1)
        mainLayout.addWidget(self.sizeLabel, 2, 0)
        mainLayout.addWidget(self.sizeValueLabel, 2, 1)
        
        mainLayout.addWidget(self.bucketLabel, 3, 0)
        mainLayout.addWidget(self.bucketValueLabel, 3, 1)
        
        mainLayout.addWidget(self.createDateLabel, 4, 0)
        mainLayout.addWidget(self.createDateValueLabel, 4, 1)
        
        ''' acl '''
        self.aclTable = QtGui.QTableWidget(2, 5, self)
        self.aclTable.setHorizontalHeaderLabels((u"组", u"读权限", u"写权限", u"读ACL", u"写ACL"))
        self.aclTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.aclTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.horizontalHeader().setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        self.aclTable.verticalHeader().hide()
        self.aclTable.setShowGrid(False)
        
        columns = 5
        rows = 2
        for column in range(columns):
            if column == 0:
                continue
            for row in range(rows):
                item = QtGui.QTableWidgetItem('')
                item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                              QtCore.Qt.ItemIsEnabled)
#                 item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.aclTable.setItem(row, column, item)
        
        
        item = QtGui.QTableWidgetItem(u'匿名用户组')
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclTable.setItem(0, 0, item)
        
        item = QtGui.QTableWidgetItem(u'认证用户组')
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclTable.setItem(1, 0, item)
        mainLayout.addWidget(self.aclTable,5,0,1,2)

        
        ''' acl user '''        
        self.aclUserTable = QtGui.QTableWidget(0, 5, self)
        self.aclUserTable.setHorizontalHeaderLabels((u"UserId", u"读权限", u"写权限", u"读ACL", u"写ACL"))
        self.aclUserTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.aclUserTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.horizontalHeader().setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        self.aclUserTable.verticalHeader().hide()
        self.aclUserTable.setShowGrid(False)
        
        self.aclUserTable.contextMenuEvent = self.aclUserTableContextMenuEvent
        
        mainLayout.addWidget(self.aclUserTable,6,0,1,2)
        
        mainLayout.addWidget(self.buttonBox, 7, 0, 1, 2)
        
        self.setLayout(mainLayout)
        self.setWindowTitle(key)
        self.resize(400, 400)
        self.isRunning = True
        self.connect(self, QtCore.SIGNAL("finished(int)"), self.finished)
        
        self.getFileInfo()
        
        
    def finished(self,code):    
        self.isRunning = False
        self.deleteLater()
    
        
    def aclUserTableCellChanged (self, row, col):
        ''' cell 修改监听事件 '''
        if col == 0:
            userId = u'%s'%self.aclUserTable.item(row, col).text()
            if len(userId) != 20 and len(userId) != 0:
                QtGui.QMessageBox.information(self,
                                              u"UserId长度不合法", 
                                              u'<p>UserId长度必须是20位</p>')
                item = self.aclUserTable.item(row, col)
                self.aclUserTable.scrollToItem(item)
                self.aclUserTable.setItemSelected(item,True)
        
    def aclUserTableContextMenuEvent(self, event):
        ''' userTable 右键 '''
        rows=[]
        for idx in self.aclUserTable.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        menu = QtGui.QMenu(self.aclUserTable)
        
        
        ''' 添加 '''
        addAct = QtGui.QAction(u"添加用户", self.aclUserTable,
            shortcut="Ctrl+A", statusTip=u"添加一条用户授权信息",
            triggered=self.addUserAction)
        menu.addAction(addAct)
            
        menu.addSeparator()
        ''' 删除 '''
        delAct = QtGui.QAction(u"删除", self.aclUserTable,
            shortcut="Ctrl+D", statusTip=u"删除选中的用户授权记录",
            triggered=self.delUserAction)
        menu.addAction(delAct)
        
        if len(rowSet) == 0:
#             addAct.setEnabled(True)
            delAct.setEnabled(False)
        else:
#             addAct.setEnabled(False)
            delAct.setEnabled(True)
            
        menu.exec_(event.globalPos())

    ''' aclUserTable 右键 begin'''
    def addUserAction(self, event):
        row = self.aclUserTable.rowCount()
        self.aclUserTable.insertRow(row)
        
        useritem = QtGui.QTableWidgetItem('')
        useritem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
        useritem.setTextAlignment(QtCore.Qt.AlignCenter)
        self.aclUserTable.setItem(row, 0, useritem)
        
        for idx in xrange(4):
            item = QtGui.QTableWidgetItem('')
            item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.aclUserTable.setItem(row, idx+1, item)
    
        self.aclUserTable.scrollToBottom()
        self.aclUserTable.editItem(useritem)
    
    def delUserAction(self, event):
        rows=[]
        for idx in self.aclUserTable.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        if len(rowSet)>0:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                   u"删除用户授权", 
                   u'<p>您确定删除当前选中的userid么？</p>',
                   QtGui.QMessageBox.NoButton, self)
            msgBox.addButton(u"继续", QtGui.QMessageBox.AcceptRole)
            msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
            if msgBox.exec_() == QtGui.QMessageBox.AcceptRole:
                for row in rowSet:
                    self.aclUserTable.removeRow(row)
        
    ''' aclUserTable 右键 end'''
    
    
    def setupFileInfoView(self, runnable, info):
        if self.isRunning:
            self.openner.openner.operationLogTable.updateLogDict({'operation':'get file info', 
                                                       'result':u'完成',
                                                       'thread':runnable})
            self.kindValueLabel.setText(info['mimetype'])
            self.sizeValueLabel.setText(filesizeformat(info['size']))#"%d KB" % (int((info['size'] + 1023) / 1024)))
            self.createDateValueLabel.setText(info['modify'].strftime('%Y-%m-%d %H:%M:%S'))
            
            self.getFileAcl()
    
    def fileInfoDidFailed(self, runnable, errorMsg):
        self.openner.openner.operationLogTable.updateLogDict({'operation':'get file info', 
                                                   'result':u'失败',
                                                   'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"获取object信息失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
    
    def getFileInfo(self):
        fileInfoRunnable = FileInfoRunnable(self.bucketName, u'%s%s'%(self.prefix,self.key))
        QtCore.QObject.connect(fileInfoRunnable.emitter,QtCore.SIGNAL('fileInfoRunnable(PyQt_PyObject, PyQt_PyObject)'),self.setupFileInfoView)
        QtCore.QObject.connect(fileInfoRunnable.emitter,QtCore.SIGNAL('fileInfoDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.fileInfoDidFailed)
        self.openner.openner.startOperationRunnable(fileInfoRunnable)
        
        self.openner.openner.operationLogTable.updateLogDict({'operation':'get file info', 
                                                   'result':u'处理中',
                                                   'thread':fileInfoRunnable})
    
    def getFileAcl(self):
        s = SCSBucket(self.bucketName)
        resultDict = s.acl_info(u'%s%s'%(self.prefix,self.key))
        
        aclDict = resultDict['ACL']
        
        for key, value in aclDict.iteritems():
            if cmp(key,'GRPS000000ANONYMOUSE') == 0 :#匿名用户组
                #[u'read', u'write', u'read_acp', u'write_acp']
                if 'read' in value:
                    self.aclTable.item(0, 1).setCheckState(QtCore.Qt.Checked)
                
                if 'write' in value:
                    self.aclTable.item(0, 2).setCheckState(QtCore.Qt.Checked)
                    
                if 'read_acp' in value:
                    self.aclTable.item(0, 3).setCheckState(QtCore.Qt.Checked)
                    
                if 'write_acp' in value:
                    self.aclTable.item(0, 4).setCheckState(QtCore.Qt.Checked)
                
            elif cmp(key,'GRPS0000000CANONICAL') == 0 :#认证用户组
                if 'read' in value:
                    self.aclTable.item(1, 1).setCheckState(QtCore.Qt.Checked)
                
                if 'write' in value:
                    self.aclTable.item(1, 2).setCheckState(QtCore.Qt.Checked)
                    
                if 'read_acp' in value:
                    self.aclTable.item(1, 3).setCheckState(QtCore.Qt.Checked)
                    
                if 'write_acp' in value:
                    self.aclTable.item(1, 4).setCheckState(QtCore.Qt.Checked)
            else:#其他用户
                row = self.aclUserTable.rowCount()
                self.aclUserTable.insertRow(row)
                
                item = QtGui.QTableWidgetItem(key)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable |QtCore.Qt.ItemIsSelectable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.aclUserTable.setItem(row, 0, item)
                
                for idx in xrange(4):
                    item = QtGui.QTableWidgetItem('')
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                                  QtCore.Qt.ItemIsEnabled)
                    item.setCheckState(QtCore.Qt.Unchecked)
                    self.aclUserTable.setItem(row, idx+1, item)
                    
                if 'read' in value:
                    self.aclUserTable.item(row, 1).setCheckState(QtCore.Qt.Checked)
                
                if 'write' in value:
                    self.aclUserTable.item(row, 2).setCheckState(QtCore.Qt.Checked)
                    
                if 'read_acp' in value:
                    self.aclUserTable.item(row, 3).setCheckState(QtCore.Qt.Checked)
                    
                if 'write_acp' in value:
                    self.aclUserTable.item(row, 4).setCheckState(QtCore.Qt.Checked)
                    
        self.acceptBtn.setEnabled(True)
        
        self.aclUserTable.cellChanged.connect(self.aclUserTableCellChanged)
            
            
    def updateAcl(self):
        acl = {}
        
        '''处理 ACL_GROUP_ANONYMOUSE'''
        anonymouseAclArray = []
        if self.aclTable.item(0, 1).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_READ)
        if self.aclTable.item(0, 2).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_WRITE)
        if self.aclTable.item(0, 3).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_READ_ACP)
        if self.aclTable.item(0, 4).checkState() == QtCore.Qt.Checked :
            anonymouseAclArray.append(ACL.ACL_WRITE_ACP)
        
        '''处理 ACL_GROUP_CANONICAL'''
        canonicalAclArray = []
        if self.aclTable.item(1, 1).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_READ)
        if self.aclTable.item(1, 2).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_WRITE)
        if self.aclTable.item(1, 3).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_READ_ACP)
        if self.aclTable.item(1, 4).checkState() == QtCore.Qt.Checked :
            canonicalAclArray.append(ACL.ACL_WRITE_ACP)
        
        if len(anonymouseAclArray) > 0:
            acl[ACL.ACL_GROUP_ANONYMOUSE] = anonymouseAclArray
        if len(canonicalAclArray) > 0:
            acl[ACL.ACL_GROUP_CANONICAL] = canonicalAclArray
            
        ''' 处理用户acl '''  
        userAclDict = {}  
        aclArray = []
        aclUserTableRowCount = self.aclUserTable.rowCount()
        for row in xrange(aclUserTableRowCount):
            aclArray = []
            userId = u'%s'%self.aclUserTable.item(row, 0).text()#unicode(self.aclUserTable.item(row, 0).text(),'utf-8','ignore')
            acl_read = (self.aclUserTable.item(row, 1).checkState() == QtCore.Qt.Checked)
            acl_write = (self.aclUserTable.item(row, 2).checkState() == QtCore.Qt.Checked)
            acl_read_acp = (self.aclUserTable.item(row, 3).checkState() == QtCore.Qt.Checked)
            acl_write_acp = (self.aclUserTable.item(row, 4).checkState() == QtCore.Qt.Checked)
        
            if acl_read or acl_write or acl_read_acp or acl_write_acp :
                if acl_read:
                    aclArray.append(ACL.ACL_READ)
                if acl_write:
                    aclArray.append(ACL.ACL_WRITE)
                if acl_read_acp:
                    aclArray.append(ACL.ACL_READ_ACP)
                if acl_write_acp:
                    aclArray.append(ACL.ACL_WRITE_ACP)
                
                userAclDict[userId] = aclArray
                
        if len(aclArray) > 0:
            for k,v in userAclDict.iteritems():
                acl[k] = v
        
        updateFileACLRunnable = UpdateFileACLRunnable(self.bucketName, '%s%s'%(self.prefix,self.key), acl)
        QtCore.QObject.connect(updateFileACLRunnable.emitter,QtCore.SIGNAL('UpdateFileACLRunnable(PyQt_PyObject)'),self.openner.updateFileAclDidFinished)
        QtCore.QObject.connect(updateFileACLRunnable.emitter,QtCore.SIGNAL('UpdateFileACLDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.openner.updateFileAclDidFailed)
        self.openner.openner.startOperationRunnable(updateFileACLRunnable)
        ''' add oper log'''
        self.openner.openner.operationLogTable.updateLogDict({'operation':'update file acl', 
                                                    'result':u'处理中',
                                                    'thread':updateFileACLRunnable})
        
        self.accept()
            

class BucketTable(QtGui.QTableWidget):
    ''' bucket列表table '''
    def __init__(self, openner=None):
        super(BucketTable, self).__init__(0, 2)

        self.openner = openner
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setHorizontalHeaderLabels((u"Bucket名称", u"创建时间"))
        self.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)#0, QtGui.QHeaderView.Stretch)
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.cellActivated.connect(self.cellActivatedAct)    #双击

    def cellActivatedAct(self, row, column):
        item = self.item(row, 0)
        currentBucketName = u'%s'%item.text()#unicode(item.text(),'utf-8','ignore')
        
        self.openner.openBucketOfTableItem(currentBucketName)

    def setBuckets(self, buckets_generator):
        ''' 设置bucket结果集
            buckets_generator:迭代器
        '''
        self.clearContents()
        self.setRowCount(0)
        
        for bucketName,cretatDate in buckets_generator:
            bucketNameItem = QtGui.QTableWidgetItem(bucketName)
            bucketNameItem.setFlags(bucketNameItem.flags() ^ QtCore.Qt.ItemIsEditable)
            ''' time zone!!! '''
            cretatDateItem = QtGui.QTableWidgetItem(cretatDate.strftime('%Y-%m-%d %H:%M:%S'))
#             cretatDateItem.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            cretatDateItem.setFlags(cretatDateItem.flags() ^ QtCore.Qt.ItemIsEditable)

            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, bucketNameItem)
            self.setItem(row, 1, cretatDateItem)
            
    def createBucket(self, bucketName):
        createBucketRunnable = CreateBucketRunnable(bucketName, self)
        QtCore.QObject.connect(createBucketRunnable.emitter,QtCore.SIGNAL('CreateBucket(PyQt_PyObject)'),self.createBucketDidFinished)
        QtCore.QObject.connect(createBucketRunnable.emitter,QtCore.SIGNAL('CreateBucketDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.createBucketDidFailed)
        self.openner.startOperationRunnable(createBucketRunnable)
        
        self.openner.operationLogTable.updateLogDict({'operation':'create bucket', 
                                                             'result':u'处理中',
                                                             'thread':createBucketRunnable})
        
    def createBucketDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'create bucket', 
                                                             'result':u'失败',
                                                             'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"创建bucket失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
    
    def createBucketDidFinished(self, runnable):
        self.openner.operationLogTable.updateLogDict({'operation':'create bucket', 
                                                             'result':u'完成',
                                                             'thread':runnable})
        self.refreshTableList()
    
    def contextMenuEvent(self, event):
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        menu = QtGui.QMenu(self)
        
        if len(rowSet) == 1:#单选
#             ''' 下载 '''
#             downloadFileAct = QtGui.QAction("&下载文件", self,
#                 shortcut="Ctrl+D",
#                 statusTip="下载文件到本地磁盘.",
#                 triggered=self.downloadFileAction)
#             menu.addAction(downloadFileAct)
            ''' bucket信息 '''
            fileInfoAct = QtGui.QAction(u"Meta信息", self,
                shortcut="Ctrl+I", statusTip=u"显示bucket的Meta信息",
                triggered=self.bucketInfoAction)
            menu.addAction(fileInfoAct)
            
            menu.addSeparator()
            ''' 删除 '''
            delAct = QtGui.QAction(u"删除", self,
                shortcut="Ctrl+R", statusTip=u"删除bucket",
                triggered=self.delAction)
            menu.addAction(delAct)
            
            menu.exec_(event.globalPos())
        else:#多选
            print '--------'
            
    def bucketInfoAction(self,event):
        ''' bucket列表右键contextMenu-Meta信息 action '''
        bucketName = u'%s'%self.item(self.selectedIndexes()[0].row(), 0).text()#unicode(self.item(self.selectedIndexes()[0].row(), 0).text(),'utf-8','ignore')
        bucketInfoDialog = BucketInfoDialog(bucketName, self)
        bucketInfoDialog.exec_()
        
    def delAction(self, event):
        ''' bucket列表右键contextMenu-Meta信息 action '''
        msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                u"删除bucket", 
                u'<p>您确定删除当前bucket么？</p><p>若bucket内有文件存在，请删除所有文件后再执行本操作！</p>',
                QtGui.QMessageBox.NoButton, self)
        msgBox.addButton(u"继续", QtGui.QMessageBox.AcceptRole)
        msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
        if msgBox.exec_() == QtGui.QMessageBox.AcceptRole:
            bucketName = u'%s'%self.item(self.selectedIndexes()[0].row(), 0).text()#unicode(self.item(self.selectedIndexes()[0].row(), 0).text(),'utf-8','ignore')
            
            deleteBucketRunnable = DeleteBucketRunnable(bucketName, self)
            QtCore.QObject.connect(deleteBucketRunnable.emitter,QtCore.SIGNAL('DeleteBucketRunnable(PyQt_PyObject)'),self.refreshTableList)
            QtCore.QObject.connect(deleteBucketRunnable.emitter,QtCore.SIGNAL('DeleteBucketRunnableDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.deleteDidFailedAct)
            self.openner.startOperationRunnable(deleteBucketRunnable)
            
            self.openner.operationLogTable.updateLogDict({'operation':'delete bucket', 
                                                               'result':u'处理中',
                                                               'thread':deleteBucketRunnable})
    
    def deleteDidFailedAct(self,runnable,errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'delete bucket', 
                                                       'result':u'失败',
                                                       'thread':runnable})
        
        reply = QtGui.QMessageBox.information(self,
                u"删除失败", 
                u'<p>bucket 删除失败</p><p>失败原因：%s</p>'%errorMsg)
    
    def refreshTableList(self,runnable=None):
        if runnable is not None:
            self.openner.operationLogTable.updateLogDict({'operation':'delete bucket', 
                                                           'result':u'完成',
                                                           'thread':runnable})
        ''' 刷新当前列表 '''
        listBucketRunnable = ListBucketRunnable(self)
        QtCore.QObject.connect(listBucketRunnable.emitter,QtCore.SIGNAL('ListBucketRunnable(PyQt_PyObject)'),self.loginDidFinished)
        QtCore.QObject.connect(listBucketRunnable.emitter,QtCore.SIGNAL('ListBucketRunnableDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.listBucketDidFailed)
        self.openner.startOperationRunnable(listBucketRunnable)
        
        self.openner.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'处理中',
                                                   'thread':listBucketRunnable})
        
    def loginDidFinished(self,runnable):
        self.openner.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'完成',
                                                   'thread':runnable})
        
        self.setBuckets(runnable.bucketIter())
        
    def listBucketDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'失败',
                                                   'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"获取bucket列表失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
        
    ''' bucket 详细窗口 确认按钮 begin '''
    def updateFileACLDidFinished(self, runnable):
        ''' add oper log'''
        self.openner.operationLogTable.updateLogDict({'operation':'update bucket acl', 
                                                    'result':u'完成',
                                                    'thread':runnable})
        
    def updateFileAclDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'update bucket acl', 
                                                    'result':u'失败',
                                                    'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"更新bucket ACL失败", 
                u'<p>失败原因：%s</p>'%errorMsg)


class UploadFilesConfirmDialog(QtGui.QDialog):
    ''' 用于拖拽文件时的确认对话框 '''
    def __init__(self, filesPath, openner):
        super(UploadFilesConfirmDialog, self).__init__(openner)
        self.openner = openner
        self.filesPath = filesPath
        self.checkAllState = False  #用于全选的状态标识
        self.initViews()
        
    def initViews(self):
        mainLayout = QtGui.QGridLayout()
        
        ''' button '''
        self.buttonBox = QtGui.QDialogButtonBox()
        self.checkAllBtn = QtGui.QPushButton(u"全选")
        self.checkAllBtn.setEnabled(True)
        self.checkAllBtn.clicked.connect(self.checkAllAction)
        self.buttonBox.addButton(self.checkAllBtn, QtGui.QDialogButtonBox.ActionRole)
        self.acceptBtn = QtGui.QPushButton(u"上传")
        self.acceptBtn.setEnabled(False)
        self.buttonBox.addButton(self.acceptBtn, QtGui.QDialogButtonBox.AcceptRole)
        self.cancelBtn = QtGui.QPushButton(u"取消")
        self.cancelBtn.setEnabled(True)
        self.buttonBox.addButton(self.cancelBtn, QtGui.QDialogButtonBox.RejectRole)
        self.buttonBox.accepted.connect(self.uploadSelectedFile)
        self.buttonBox.rejected.connect(self.reject)
        
        mainLayout.addWidget(self.buttonBox, 1, 0, 1, 2)
        
        self.uploadTable = QtGui.QTableWidget(0, 2, self)
        self.uploadTable.setHorizontalHeaderLabels((u"文件路径", u"文件大小"))
        self.uploadTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.uploadTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        self.uploadTable.verticalHeader().hide()
        self.uploadTable.setShowGrid(False)
        self.uploadTable.itemChanged.connect(self.itemChangedAct)
        
#         print '----self.filesPath---------',self.filesPath
        from urllib2 import unquote
        path = unquote('%s'%self.filesPath[0]).decode('utf8','ignore')
        if os.name == 'nt':
            self.basePath = os.path.dirname(path)
        else:
            if os.path.isdir(path):
                self.basePath = os.path.dirname(os.path.dirname(path))
            else:
                self.basePath = os.path.dirname(path)
        
        for str in self.filesPath:
            filePath = unquote('%s'%str).decode('utf8','ignore')
            if os.name == 'nt':
                filePath = filePath[1:]
            
            if filePath is None or len(filePath) == 0 :#or os.path.isdir(filePath):
                continue
            
            row = self.uploadTable.rowCount()
            self.uploadTable.insertRow(row)
            
            if os.path.isdir(filePath):
                filesAmount = getFileAmount(filePath)

                if os.name == 'nt':
                    folderName = os.path.basename(filePath)
                else:
                    folderName = os.path.basename(os.path.dirname(filePath))
                
                item = FileTableCellItem(u'%s(共%d项)'%(folderName,filesAmount), self.uploadTable)
                item.setIcon(QtGui.QIcon(':/folder_icon.png'))
                if filesAmount > 500 :
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable )
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
                else:
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            else:
                item = FileTableCellItem(os.path.basename(filePath), self.uploadTable)
                item.setIcon(QtGui.QIcon(':/file_icon.png'))
                item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                
            item.userInfo['filePath'] = filePath
            item.setCheckState(QtCore.Qt.Unchecked)
            
            
            self.uploadTable.setItem(row, 0, item)
            
            if os.path.isdir(filePath):
                item = FileSizeCellItem('--', self.uploadTable)
            else:
                item = FileSizeCellItem(filesizeformat(os.stat(filePath).st_size), self.uploadTable)
                
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.uploadTable.setItem(row, 1, item)
        
        self.uploadTable.setSortingEnabled(True)
        mainLayout.addWidget(self.uploadTable,0,0,1,2)
        
        noteLabel = QtGui.QLabel(u"<font color=red>注：若文件夹内文件数量大于500，则不支持批量上传</font>")
        mainLayout.addWidget(noteLabel,2,0,1,2)
            
        self.setLayout(mainLayout)
        self.setWindowTitle(u'确认待上传文件')
        self.resize(400, 400)
        
        self.connect(self, QtCore.SIGNAL("finished(int)"), lambda code:self.deleteLater())
    
    def itemChangedAct(self, item):
        for i in xrange(self.uploadTable.rowCount()):
            cell = self.uploadTable.item(i, 0)
            if cell.checkState() == QtCore.Qt.Checked:
                self.acceptBtn.setEnabled(True)
                return
            
        self.acceptBtn.setEnabled(False)

    
    def uploadSelectedFile(self):
        ''' 上传文件 '''
        uploadFilePathArray = []
        for i in xrange(self.uploadTable.rowCount()):
            cell = self.uploadTable.item(i, 0)
            if cell.checkState() == QtCore.Qt.Checked:
                filePath = u'%s'%cell.userInfo['filePath']
                if os.path.isdir(filePath):
                    for (path, dirs, files) in os.walk(filePath):
                        for dirName in dirs:
                            uploadFilePathArray.append(os.path.join(path,dirName))
                        for fileName in files:
                            uploadFilePathArray.append(os.path.join(path,fileName))
                else:
                    uploadFilePathArray.append(u'%s'%cell.userInfo['filePath'])
            
        self.openner.uploadMultiObjectAction(uploadFilePathArray,self.basePath+'/')
        self.hide()
        
    def checkAllAction(self):
        ''' 全选按钮事件 '''
        for i in xrange(self.uploadTable.rowCount()):
            cell = self.uploadTable.item(i, 0)
            if not self.checkAllState:
                if cell.flags() & QtCore.Qt.ItemIsEnabled:
                    cell.setCheckState(QtCore.Qt.Checked)
            else:
                cell.setCheckState(QtCore.Qt.Unchecked)
        
        self.checkAllState = not self.checkAllState

class FilesTable(QtGui.QTableWidget):
    ''' 用于文件列表的table '''
    def __init__(self, bucketName, openner=None):
        super(FilesTable, self).__init__(0, 5)
        
        self.currentBucketName = ''
        self.currentPrefix = ''
        
        self.setSortingEnabled(False)
        
        self.openner = openner
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setHorizontalHeaderLabels((u"文件名称", u"SHA1", u"修改日期", u"MD5", u"文件大小"))
        self.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.cellActivated.connect(self.filesTableCellActivatedAction)    #双击
        self.itemSelectionChanged.connect(self.enableToolBarButton)    #选中
        
        self.currentBucketName = bucketName;
        self.refreshTableList()
        
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event):
#         self.setText("<drop content>")
#         self.setBackgroundRole(QtGui.QPalette.Highlight)
        event.acceptProposedAction()
#         self.changed.emit(event.mimeData())

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mimeData = event.mimeData()
#         for str in mimeData.formats():
#             print '==========',str
        
        if mimeData.hasUrls():
            urlArray = []
            for url in mimeData.urls():
                urlArray.append(url.encodedPath())
        
            uploadFilesConfirmDialog = UploadFilesConfirmDialog(urlArray, self)
            uploadFilesConfirmDialog.show()
        
#         if mimeData.hasImage():
# #             self.setPixmap(QtGui.QPixmap(mimeData.imageData()))
#             print '=========dropEvent================hasImage'
#         elif mimeData.hasHtml():
#             print '=========dropEvent================hasHtml'
# #             self.setText(mimeData.html())
# #             self.setTextFormat(QtCore.Qt.RichText)
#         elif mimeData.hasText():
#             print '=========dropEvent================hasText'
#             print '0----------------------text--[%s]'%mimeData.text()
# #             self.setText(mimeData.text())
# #             self.setTextFormat(QtCore.Qt.PlainText)
#         elif mimeData.hasUrls():
#             print '=========dropEvent================hasUrls'
# #             self.setText("\n".join([url.path() for url in mimeData.urls()]))
#         else:
# #             self.setText("Cannot display data")
#             print '=========dropEvent================Cannot display data'

#         self.setBackgroundRole(QtGui.QPalette.Dark)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        event.accept()
        
        
        
    ''' 用于文件详情窗口的更新操作 begin '''    
    def updateFileAclDidFinished(self, runnable):
        ''' add oper log'''
        self.openner.operationLogTable.updateLogDict({'operation':'update file acl', 
                                                    'result':u'完成',
                                                    'thread':runnable})
    def updateFileAclDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'update file acl', 
                                                    'result':u'失败',
                                                    'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"更新文件ACL失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
    
    ''' 用于文件详情窗口的更新操作 end '''  
    
    
    
    def uploadFileDidFinished(self, thread):
        self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                             'result':u'完成',
                                                             'thread':thread})
        self.refreshTableList()
        
    def uploadFileDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                             'result':u'失败',
                                                             'thread':runnable})
        
        reply = QtGui.QMessageBox.information(self,
                u"上传失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
        
    def uploadFileUpdateProgress(self, thread, total, received):
        ''' 更新上传进度 '''
        try:
            if received*100 / total != 100:
                result = u'上传中(%d%%)'%(received*100 / total)
            else:
                result = u'完成'
                
            self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                       'result':result,
                                                       'thread':thread})
        except Exception,e:
            pass
    
    def createFolder(self, folderName):
        ''' 创建目录 '''
#         if len(self.currentPrefix) == 0 or cmp(self.currentPrefix,'/') == 0:
#             filePath = '%s/'%folderName
#         else:
#             filePath = '%s/%s/'%(os.path.basename(self.currentPrefix),folderName)
            
        filePath = '%s%s/'%(self.currentPrefix,folderName)
        
        createFolderRunnable = CreateFolderRunnable(self.currentBucketName, filePath, self)
        QtCore.QObject.connect(createFolderRunnable.emitter,QtCore.SIGNAL('CreateFolder(PyQt_PyObject)'),self.createFolderDidFinished)
        QtCore.QObject.connect(createFolderRunnable.emitter,QtCore.SIGNAL('CreateFolderDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.createFolderDidFailed)
        self.openner.startOperationRunnable(createFolderRunnable)
        self.openner.operationLogTable.updateLogDict({'operation':'create folder', 
                                                             'result':u'处理中',
                                                             'thread':createFolderRunnable})
    
    def createFolderDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'create folder', 
                                                             'result':u'失败',
                                                             'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"创建目录失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
    
    def createFolderDidFinished(self, runnable):
        self.openner.operationLogTable.updateLogDict({'operation':'create folder', 
                                                             'result':u'完成',
                                                             'thread':runnable})
        self.refreshTableList()
    
    def downloadFileAction(self, event):
        ''' 文件列表右键contextMenu-downloadfile action '''
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        for rowNum in rowSet:
            fileName = u'%s'%self.item(rowNum, 0).text()
            fileMD5 = u'%s'%self.item(rowNum, 3).text()
            localFileName = fileName        #待保存到本地的文件名
            
            options = QtGui.QFileDialog.DontResolveSymlinks | QtGui.QFileDialog.ShowDirsOnly
            directory = QtGui.QFileDialog.getExistingDirectory(self,
                    u"请选择保存路径",
                    '', options)
            
            if len(directory) > 0:
                ''' 检查当前目录是否存在同名文件 '''
                if os.path.exists(os.path.join(u'%s'%directory,fileName)):
                    msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                                               u"文件已存在", 
                                               u'<p>当前目录存在相同文件名！</p>',
                                               QtGui.QMessageBox.NoButton, self)
                    
                    msgBox.addButton(u"覆盖", QtGui.QMessageBox.HelpRole)
                    msgBox.addButton(u"并存", QtGui.QMessageBox.ActionRole)
                    msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
                    
                    btnIdx = msgBox.exec_()
                    if btnIdx == 0:
                        pass            #覆盖
                    elif btnIdx == 1:   #并存
                        ''' 找可用的文件名 '''
                        localFileName = renameFileByPath(u'%s'%directory, localFileName)
                    else:               #取消
                        return
                
                tmpFilePath = os.path.join(u'%s'%directory,u'%s_%s.tmp'%(fileName, fileMD5))
                
                downloadObjectRunnable = DownloadObjectRunnable(self.currentBucketName, 
                                                                '%s%s'%(self.currentPrefix,fileName),
                                                                fileMD5,
                                                                os.path.join(u'%s'%directory,localFileName), 
                                                                tmpFilePath,
                                                                self)
                QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('DownloadObjectRunnable(PyQt_PyObject)'),self.downloadFileDidFinished)
                QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('FileDownloadProgress(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),self.downloadFileUpdateProgress)
                QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('DownloadObjectDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.downloadFileDidFailed)
                QtCore.QObject.connect(downloadObjectRunnable.emitter,QtCore.SIGNAL('DownloadObjectDidCanceled(PyQt_PyObject)'),self.downloadFileDidCanceled)
                result = self.openner.startOperationRunnable(downloadObjectRunnable)
                
                if result:
                    self.openner.operationLogTable.updateLogDict({'operation':'download file', 
                                                                 'result':u'处理中',
                                                                 'thread':downloadObjectRunnable})
                
    def downloadFileUpdateProgress(self, thread, total, received):
        ''' 更新下载进度 '''
        if thread.received*100 / thread.total != 100:
            result = u'下载中(%d%%)'%(thread.received*100 / thread.total)
        else:
            result = u'完成'
            
        self.openner.operationLogTable.updateLogDict({'operation':'download file', 
                                                   'result':result,
                                                   'thread':thread})
    def downloadFileDidFinished(self, thread):
        ''' 下载完成 '''
        self.openner.operationLogTable.updateLogDict({'operation':'download file', 
                                                             'result':u'完成',
                                                             'thread':thread})
        

    def fileInfoAction(self,event):
        ''' 文件列表右键contextMenu-file info action '''
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        if len(rowSet) == 1:        #单选
            fileName = u'%s'%self.item(self.selectedIndexes()[0].row(), 0).text()#unicode(self.item(self.selectedIndexes()[0].row(), 0).text(),'utf-8','ignore')
                
            self.fileInfoDialog = FileInfoDialog(self, self.currentBucketName, fileName, self.currentPrefix)
            self.fileInfoDialog.exec_()
        elif len(rowSet) > 1:       #多选
            fileNames = []
            for row in rowSet:
                fileNames.append(u'%s'%self.item(row, 0).text())
            if len(fileNames) > 0:
                self.multiFileInfoDialog = MultiFileInfoDialog(self, self.currentBucketName, fileNames, self.currentPrefix)
                self.multiFileInfoDialog.exec_()
        

    def uploadMultiObjectAction(self, filePathArray, basePath):
        ''' 批量上传文件 '''
        self.toBeUploadObjectsArray = []
        if filePathArray and len(filePathArray) > 0:
            for qfilepath in filePathArray:
                self.toBeUploadObjectsArray.append(u'%s'%qfilepath)
        
        if os.name == 'nt':
            basePath = os.path.dirname(basePath)+'/'
#         else:
#             basePath = os.path.dirname(os.path.dirname(basePath))+'/'
        for filePath in self.toBeUploadObjectsArray :
            if os.path.isdir(filePath):
                dirName = filePath[filePath.find(basePath)+len(basePath):]
                if os.name == 'nt':
                    dirName = dirName.replace('\\','/')
#                 print '=1===isdir(filePath)======',dirName
                createFolderRunnable = CreateFolderRunnable(self.currentBucketName, u'%s%s/'%(self.currentPrefix,dirName), self)
                createFolderRunnable.filePath = filePath
                QtCore.QObject.connect(createFolderRunnable.emitter,QtCore.SIGNAL('CreateFolder(PyQt_PyObject)'),self.createMultiFolderDidFinished)
                QtCore.QObject.connect(createFolderRunnable.emitter,QtCore.SIGNAL('CreateFolderDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.createMultiFolderDidFailed)
                self.openner.startOperationRunnable(createFolderRunnable)
                self.openner.operationLogTable.updateLogDict({'operation':'create folder', 
                                                                     'result':u'处理中',
                                                                     'thread':createFolderRunnable})
            else:
                fName = filePath[filePath.find(basePath)+len(basePath):]
                if os.name == 'nt':
                    fName = fName.replace('\\','/')
                prefix = u'%s%s'%(self.currentPrefix,os.path.dirname(fName)+'/' if len(os.path.dirname(fName))>0 else '')
                if cmp(prefix, '/') == 0:
                    prefix = ''
#                 print '=2===not isdir(filePath)======',fName,prefix
                
#                 #TODO:分片上传未完成
#                 if os.stat(filePath).st_size > 50 * 1024 * 1024 :     #文件大于50M采用分片上传
#                     ''' 分片上传 '''
#                     fileMultipartUploadRunnable = FileMultipartUploadRunnable(self.currentBucketName, filePath, prefix, self)
#                     QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadProgress(PyQt_PyObject, int, int)'),self.uploadFileUpdateProgress)
#                     QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFinished(PyQt_PyObject)'),self.uploadMultiFileDidFinished)
#                     QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.uploadMultiFileDidFailed)
#                     QtCore.QObject.connect(fileMultipartUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidCanceled(PyQt_PyObject,PyQt_PyObject)'),self.uploadMultiFileDidCanceled)
#                     self.openner.startOperationRunnable(fileMultipartUploadRunnable)
#                     self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
#                                                                  'result':u'处理中',
#                                                                  'thread':fileMultipartUploadRunnable})
#                 else:
                fileUploadRunnable = FileUploadRunnable(self.currentBucketName, filePath, prefix, self)
                QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadProgress(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),self.uploadFileUpdateProgress)
                QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFinished(PyQt_PyObject)'),self.uploadMultiFileDidFinished)
                QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.uploadMultiFileDidFailed)
                QtCore.QObject.connect(fileUploadRunnable.emitter,QtCore.SIGNAL('fileUploadDidCanceled(PyQt_PyObject,PyQt_PyObject)'),self.uploadMultiFileDidCanceled)
                self.openner.startOperationRunnable(fileUploadRunnable)
                self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                                 'result':u'处理中',
                                                                 'thread':fileUploadRunnable})

    def createMultiFolderDidFinished(self, runnable):
        ''' 批量上传目录--完成 '''
        if runnable.filePath in self.toBeUploadObjectsArray:
            self.toBeUploadObjectsArray.remove(runnable.filePath)
            
        self.openner.operationLogTable.updateLogDict({'operation':'create folder', 
                                                         'result':u'完成',
                                                         'thread':runnable})
        ''' 刷新列表 '''
        if len(self.toBeUploadObjectsArray) == 0:
            self.refreshTableList()
            
    def createMultiFolderDidFailed(self, runnable, errorMsg):
        ''' 批量上传目录--失败 '''
        if runnable.filePath in self.toBeUploadObjectsArray:
            self.toBeUploadObjectsArray.remove(runnable.filePath)
            
        self.openner.operationLogTable.updateLogDict({'operation':'create folder', 
                                                         'result':u'失败',
                                                         'thread':runnable})
        ''' 刷新列表 '''
        if len(self.toBeUploadObjectsArray) == 0:
            self.refreshTableList()

    def uploadMultiFileDidFinished(self, runnable):
        ''' 批量上传文件--完成 '''
        if runnable.filePath in self.toBeUploadObjectsArray:
            self.toBeUploadObjectsArray.remove(runnable.filePath)
            
        self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                             'result':u'完成',
                                                             'thread':runnable})
        ''' 刷新列表 '''
        if len(self.toBeUploadObjectsArray) == 0:
            self.refreshTableList()
    
    def uploadMultiFileDidFailed(self, runnable, errorMsg):
        ''' 批量上传文件--失败 '''
        if runnable.filePath in self.toBeUploadObjectsArray:
            self.toBeUploadObjectsArray.remove(runnable.filePath)
            
        self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                             'result':u'失败',
                                                             'thread':runnable})
        ''' 刷新列表 '''
        if len(self.toBeUploadObjectsArray) == 0:
            self.refreshTableList()
    
    def uploadMultiFileDidCanceled(self, runnable, errorMsg):
        ''' 批量上传文件--手动取消 '''
        if runnable.filePath in self.toBeUploadObjectsArray:
            self.toBeUploadObjectsArray.remove(runnable.filePath)
            
        self.openner.operationLogTable.updateLogDict({'operation':'upload file', 
                                                             'result':u'取消',
                                                             'thread':runnable})
        ''' 刷新列表 '''
        if len(self.toBeUploadObjectsArray) == 0:
            self.refreshTableList()

    def delMultiObjectAction(self, event):
        ''' 批量删除文件 '''
        msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                u"删除Object", 
                u'<p>您确定删除当前选中的Object么？</p>',
                QtGui.QMessageBox.NoButton, self)
        msgBox.addButton(u"继续", QtGui.QMessageBox.AcceptRole)
        msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
        if msgBox.exec_() == QtGui.QMessageBox.AcceptRole:
            rows=[]
            for idx in self.selectedIndexes():
                rows.append(idx.row()) 
            rowSet = set(rows)
            self.toBeDeleteObjectsArray  = []
            for rowNum in rowSet:
                fileName = u'%s'%self.item(rowNum, 0).text()
                self.toBeDeleteObjectsArray.append('%s%s'%(self.currentPrefix,fileName))
                
            for path in self.toBeDeleteObjectsArray :
                deleteObjectRunnable = DeleteObjectRunnable(self.currentBucketName,path)
                QtCore.QObject.connect(deleteObjectRunnable.emitter,QtCore.SIGNAL('DeleteObjectRunnable(PyQt_PyObject)'),self.deleteMultiObjectDidFinished)
                QtCore.QObject.connect(deleteObjectRunnable.emitter,QtCore.SIGNAL('DeleteObjectDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.deleteMultiObjectDidFailed)
                QtCore.QObject.connect(deleteObjectRunnable.emitter,QtCore.SIGNAL('DeleteObjectForbidden(PyQt_PyObject,PyQt_PyObject)'),self.deleteMultiObjectForbidden)
                self.openner.startOperationRunnable(deleteObjectRunnable)
        
    def deleteMultiObjectDidFinished(self, runnable):
        if runnable.key in self.toBeDeleteObjectsArray:
            self.toBeDeleteObjectsArray.remove(runnable.key)
        self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                           'result':u'完成',
                                                           'thread':runnable})
            
        ''' 刷新列表 '''
        if len(self.toBeDeleteObjectsArray) == 0:
            self.refreshTableList()
    
    def deleteMultiObjectForbidden(self, runnable, errorMsg):
        ''' 批量删除某个文件-禁止（针对有文件的文件夹） '''
        if runnable.key in self.toBeDeleteObjectsArray:
            self.toBeDeleteObjectsArray.remove(runnable.key)
        self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                           'result':u'禁止操作',
                                                           'thread':runnable})
        runnable.state = RunnableState.FORBIDDEN
        
        ''' 刷新列表 '''
        if len(self.toBeDeleteObjectsArray) == 0:
            self.refreshTableList()
    
    def deleteMultiObjectDidFailed(self, runnable, errorMsg):
        ''' 批量删除某个文件-失败 '''
        if runnable.key in self.toBeDeleteObjectsArray:
            self.toBeDeleteObjectsArray.remove(runnable.key)
        self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                           'result':u'失败',
                                                           'thread':runnable})
        
        ''' 刷新列表 '''
        if len(self.toBeDeleteObjectsArray) == 0:
            self.refreshTableList()
    

    def delAction(self, event):
        ''' 文件列表右键contextMenu-删除文件 action '''
        msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                u"删除Object", 
                u'<p>您确定删除当前Object么？</p>',
                QtGui.QMessageBox.NoButton, self)
        msgBox.addButton(u"继续", QtGui.QMessageBox.AcceptRole)
        msgBox.addButton(u"取消", QtGui.QMessageBox.RejectRole)
        if msgBox.exec_() == QtGui.QMessageBox.AcceptRole:
            rows=[]
            for idx in self.selectedIndexes():
                rows.append(idx.row()) 
            rowSet = set(rows)
            
            for rowNum in rowSet:
                fileName = u'%s'%self.item(rowNum, 0).text()
                deleteObjectRunnable = DeleteObjectRunnable(self.currentBucketName,'%s%s'%(self.currentPrefix,fileName))
                QtCore.QObject.connect(deleteObjectRunnable.emitter,QtCore.SIGNAL('DeleteObjectRunnable(PyQt_PyObject)'),self.deleteObjectDidFinished)
                QtCore.QObject.connect(deleteObjectRunnable.emitter,QtCore.SIGNAL('DeleteObjectDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.deleteObjectDidFailed)
                QtCore.QObject.connect(deleteObjectRunnable.emitter,QtCore.SIGNAL('DeleteObjectForbidden(PyQt_PyObject,PyQt_PyObject)'),self.deleteObjectForbidden)
                self.openner.startOperationRunnable(deleteObjectRunnable)
                
                self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                               'result':u'处理中',
                                                               'thread':deleteObjectRunnable})
    
    def deleteObjectForbidden(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                           'result':u'禁止操作',
                                                           'thread':runnable})
        runnable.state = RunnableState.FORBIDDEN
        
        reply = QtGui.QMessageBox.information(self,
                u"删除object失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
    
    def deleteObjectDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                           'result':u'失败',
                                                           'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"删除object失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
        
    def deleteObjectDidFinished(self, runnable):
        self.openner.operationLogTable.updateLogDict({'operation':'delete object', 
                                                           'result':u'完成',
                                                           'thread':runnable})
        
        self.refreshTableList()
        
        
    def generateUrlAction(self, event):
        ''' 生成签名url '''
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        if len(rowSet) == 1:        #单选
            fileName = u'%s'%self.item(self.selectedIndexes()[0].row(), 0).text()
            
            genUrlDialog = GenUrlDialog(self, self.currentBucketName, fileName, self.currentPrefix)
            genUrlDialog.exec_()
        else:
            QtGui.QMessageBox.information(self,
                u"生成url失败", 
                u'<p>暂时不支持多文件</p>')
        
    def contextMenuEvent(self, event):
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        menu = QtGui.QMenu(self)
        menu.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        
        if len(rowSet) <= 0:
            return
        
        fileName = u'%s'%self.item(self.selectedIndexes()[0].row(), 0).text()
        ''' 下载 '''
        downloadFileAct = QtGui.QAction(u"&下载文件", self,
            shortcut="Ctrl+D",
            statusTip=u"下载文件到本地磁盘.",
            triggered=self.downloadFileAction)
        menu.addAction(downloadFileAct)
        ''' 文件信息 '''
        fileInfoAct = QtGui.QAction(u"文件信息", self,
            shortcut="Ctrl+I", statusTip=u"打开文件详细信息页",
            triggered=self.fileInfoAction)
        menu.addAction(fileInfoAct)
        
        ''' 生成url '''
        genUrlAct = QtGui.QAction(u"下载地址", self,
            shortcut="Ctrl+U", statusTip=u"生成文件下载地址",
            triggered=self.generateUrlAction)
        menu.addAction(genUrlAct)
        
        genUrlAct.setEnabled(False)
        
        if len(rowSet) == 1:#单选
            if fileName.find('/') == len(fileName)-1 :
                fileInfoAct.setEnabled(False) 
                downloadFileAct.setEnabled(False)
            else:
                fileInfoAct.setEnabled(True) 
                downloadFileAct.setEnabled(True)
                genUrlAct.setEnabled(True)
            
            menu.addSeparator()
            ''' 删除 '''
            delAct = QtGui.QAction(u"删除文件", self,
                shortcut="Ctrl+R", statusTip=u"删除远端文件",
                triggered=self.delAction)
            menu.addAction(delAct)
        else:#多选
            downloadFileAct.setEnabled(False)
            
            hasFolder = False
            for row in rowSet:
                fileName = u'%s'%self.item(row, 0).text()
                if fileName.find('/') == len(fileName)-1 :
                    hasFolder = True
                    break
                
            if hasFolder:
                fileInfoAct.setEnabled(False)
            else:
                fileInfoAct.setEnabled(True)
            
            menu.addSeparator()
            ''' 删除 '''
            delAct = QtGui.QAction(u"删除文件", self,
                shortcut="Ctrl+R", statusTip=u"删除远端文件",
                triggered=self.delMultiObjectAction)
            menu.addAction(delAct)
            
        menu.exec_(event.globalPos())
            

    def enableToolBarButton(self):
        '''
        self.itemSelectionChanged.connect(self.enableToolBarButton)
        FilesTable选中事件。
            1.没有选中时，文件信息按钮无效
            2.当选中第一行时，文件信息按钮无效
            3.如果被选中的行存在文件夹，文件信息按钮无效
            4.其他情况，文件信息按钮有效
        '''
        rows=[]
        for idx in self.selectedIndexes():
            rows.append(idx.row()) 
        rowSet = set(rows)
        
        if len(rowSet) > 0:
            if 0 not in rowSet:
                for row in rowSet:
                    fileName = u'%s'%self.item(row, 0).text()
                    if fileName.find('/') == len(fileName)-1 :
                        self.openner.objectInfoAct.setEnabled(False)
                        return
                self.openner.objectInfoAct.setEnabled(True)
            else:
                self.openner.objectInfoAct.setEnabled(False)
        else:
            self.openner.objectInfoAct.setEnabled(False)
        

    def filesTableCellActivatedAction(self, row, column):
        ''' 文件列表row双击事件 '''
        if row == 0:
            ''' 返回上一级 '''
            if self.currentPrefix is None or len(self.currentPrefix) == 0 :#or cmp(self.currentPrefix,'/') == 0
                self.currentPrefix = ''
                ''' 显示bucket table '''
                self.openner.central_widget.removeWidget(self)
                self.openner.filesTable = None
                self.openner.uploadAct.setEnabled(False)
                self.openner.objectInfoAct.setEnabled(False)
                self.openner.setWindowTitle('')
                self.deleteLater()
                
                return
            else:
                import os
                self.currentPrefix = os.path.dirname(os.path.dirname(self.currentPrefix))+'/'
                if cmp(self.currentPrefix,'/') == 0:
                    self.currentPrefix = ''
        else:
            selectedFileName = u'%s'%self.item(row, 0).text()#unicode(self.item(row, 0).text(),'utf-8','ignore')
            if selectedFileName.endswith('/') is not True:#文件
                self.downloadFileAction(None)
                return
            else:
                self.currentPrefix += selectedFileName
        
        self.refreshTableList()
    
    def downloadFileDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'download file', 
                                                   'result':u'失败',
                                                   'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"下载object失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
        
    def downloadFileDidCanceled(self, runnable):
        self.openner.operationLogTable.updateLogDict({'operation':'download file', 
                                                   'result':u'取消',
                                                   'thread':runnable})
    
    def refreshTableList(self):
        ''' 刷新当前列表 '''
        self.clearContents()
        self.setRowCount(0)
        
        listDirRunnable = ListDirRunnable(bucketName=self.currentBucketName, prefix=self.currentPrefix, delimiter='/')
        QtCore.QObject.connect(listDirRunnable.emitter,QtCore.SIGNAL('ListDirRunnable(PyQt_PyObject)'),self.showFilesOfBucket)
        QtCore.QObject.connect(listDirRunnable.emitter,QtCore.SIGNAL('ListDirDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.listDirDidFailed)
        self.openner.startOperationRunnable(listDirRunnable)
        
        self.openner.operationLogTable.updateLogDict({'operation':'list dir', 
                                                   'result':u'处理中',
                                                   'thread':listDirRunnable})
        
    def listDirDidFailed(self, runnable, errorMsg):
        self.openner.operationLogTable.updateLogDict({'operation':'list dir', 
                                                   'result':u'失败',
                                                   'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"获取object列表失败", 
                u'<p>失败原因：%s</p>'%errorMsg)
    
    def showFilesOfBucket(self, runnable):#bucketName, prefix=None, marker=None, limit=None, delimiter='/'):
        self.openner.operationLogTable.updateLogDict({'operation':'list dir', 
                                                   'result':u'完成',
                                                   'thread':runnable})
        
        self.setSortingEnabled(False)
        files_generator = runnable.files_generator
        
        self.currentBucketName = runnable.bucketName
        self.currentPrefix = files_generator.prefix
        self.clearContents()
        self.setRowCount(0)
        
        ''' 添加返回上级row '''
        fileNameItem = FileTableCellItem('..', self)  #name
        fileNameItem.setIcon(QtGui.QIcon(':/folder_icon.png'))
        sha1Item = FileTableCellItem('--', self)  #sha1
        modifyItem = FileTableCellItem('--', self)  #modify
        md5Item = FileTableCellItem('--', self)  #md5
        sizeItem = FileTableCellItem('--', self)  #size
        fileNameItem.setFlags(fileNameItem.flags() & ~QtCore.Qt.ItemIsEditable & ~QtCore.Qt.ItemIsSelectable)
        sha1Item.setFlags(sha1Item.flags() & ~QtCore.Qt.ItemIsEditable & ~QtCore.Qt.ItemIsSelectable)
        modifyItem.setFlags(modifyItem.flags() & ~QtCore.Qt.ItemIsEditable & ~QtCore.Qt.ItemIsSelectable)
        md5Item.setFlags(md5Item.flags() & ~QtCore.Qt.ItemIsEditable & ~QtCore.Qt.ItemIsSelectable)
        sizeItem.setFlags(sizeItem.flags() & ~QtCore.Qt.ItemIsEditable & ~QtCore.Qt.ItemIsSelectable)

        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, fileNameItem)
        self.setItem(row, 1, sha1Item)
        self.setItem(row, 2, modifyItem)
        self.setItem(row, 3, md5Item)
        self.setItem(row, 4, sizeItem)
        
        ''' 根据bucketName获取bucket下得所有文件 '''
        #name, isPrefix, sha1, expiration_time, modify, owner, md5, content_type, size
        for item in files_generator:
            ''' 过滤掉与prefix相同的空文件,名称为‘/’的 '''
            if cmp(item[0],self.currentPrefix) == 0 or cmp(item[0][0],'/') == 0:
                continue
            
            fileNameStr = item[0]
            if fileNameStr.find(self.currentPrefix) == 0 :
                fileNameStr = fileNameStr[len(self.currentPrefix):]
            
            fileNameItem = FileTableCellItem(fileNameStr, self)  #name
            isPrefix = item[1]
            if isPrefix is not True:
                fileNameItem.setIcon(QtGui.QIcon(':/file_icon.png'))
                sha1Item = FileTableCellItem(item[2], self)  #sha1
#                 expiration_time = item[3]
                ''' time zone!!! '''
                modifyItem = FileTableCellItem(item[4].strftime('%Y-%m-%d %H:%M:%S'), self)  #modify
#                 owner = item[5]
                md5Item = FileTableCellItem(item[6], self)  #md5
#                 content_type = item[7]
                sizeItem = FileTableCellItem(filesizeformat(item[8]), self)  #size "%d KB" % (int((item[8] + 1023) / 1024))
            else:
                fileNameItem.setIcon(QtGui.QIcon(':/folder_icon.png'))
                sha1Item = FileTableCellItem('--', self)  #sha1
                modifyItem = FileTableCellItem('--', self)  #modify
                md5Item = FileTableCellItem('--', self)  #md5
                sizeItem = FileTableCellItem('--', self)  #size
    
            fileNameItem.setFlags(fileNameItem.flags() & ~QtCore.Qt.ItemIsEditable)
            sha1Item.setFlags(sha1Item.flags() & ~QtCore.Qt.ItemIsEditable)
            modifyItem.setFlags(modifyItem.flags() & ~QtCore.Qt.ItemIsEditable)
            md5Item.setFlags(md5Item.flags() & ~QtCore.Qt.ItemIsEditable)
            sizeItem.setFlags(sizeItem.flags() & ~QtCore.Qt.ItemIsEditable)
    
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, fileNameItem)
            self.setItem(row, 1, sha1Item)
            self.setItem(row, 2, modifyItem)
            self.setItem(row, 3, md5Item)
            self.setItem(row, 4, sizeItem)
        
        self.openner.setWindowTitle('%s/%s'%(self.currentBucketName,self.currentPrefix))
        self.setSortingEnabled(True)
        
class FileTableCellItem(QtGui.QTableWidgetItem) :
    def __init__(self, text, openner, type = QtGui.QTableWidgetItem.Type):
        super(FileTableCellItem, self).__init__(text, type)
        self.openner = openner
        self.userInfo = {}  #用于添加其他信息

    def __ge__(self, other):
#         print '====__ge__========',self.text() >= other.text()
        return self.text() >= other.text()
        
    def __lt__(self, other):
        sortColumnNo = self.openner.horizontalHeader().sortIndicatorSection()
        sortOrder = self.openner.horizontalHeader().sortIndicatorOrder()
        
        fileName1 = u'%s'%self.openner.item(self.row(), 0).text()
        fileName2 = u'%s'%self.openner.item(other.row(), 0).text()
        
#         print '=====__lt__=======',fileName1,'   ',fileName2
        
#         if sortColumnNo == 0:
        if sortOrder == 0:#QtCore.Qt.SortOrder.AscendingOrder:
            if cmp(fileName1,'..') == 0:
                return True
            elif cmp(fileName2,'..') == 0:
                return False
        else:
            if cmp(fileName1,'..') == 0:
                return False
            elif cmp(fileName2,'..') == 0:
                return True
            
        if sortColumnNo == 4: #file size
            str1 = u'%s'%self.text()
            str2 = u'%s'%other.text()
            
            return bytesFromFilesizeFormat(str1) < bytesFromFilesizeFormat(str2)
            
        else:    
            return self.text() < other.text()
            
class FileSizeCellItem(FileTableCellItem) :
    def __init__(self, text, openner):
        super(FileSizeCellItem, self).__init__(text, openner)
         
    def __lt__(self, other):
        str1 = u'%s'%self.text()
        str2 = u'%s'%other.text()
        
        return bytesFromFilesizeFormat(str1) < bytesFromFilesizeFormat(str2)
        
