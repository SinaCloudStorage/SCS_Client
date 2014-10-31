#-*- coding:UTF-8 -*-
#!/usr/bin/env python
'''
Created on 2014年5月26日

@author: hanchao
'''

# This is only needed for Python v2 but is harmless for Python v3.
import sip
import urllib2
sip.setapi('QVariant', 2)
import os
from PyQt4 import QtCore, QtGui

from Views import FileInfoDialog, LoginWindow, OperationLogTable, FilesTable, BucketTable

import sinastorage

from Utils import (filesizeformat, bytesFromFilesizeFormat, getFileAmount, 
                   getValueFromWindowsRegistryByKey, addKeyValueToWindowsRegistry,
                   removeKeyFromWindowsRegistry)


from Runnables import (RunnableState, FileUploadRunnable, FileMultipartUploadRunnable, 
                       FileInfoRunnable, UpdateFileACLRunnable, 
                       ListDirRunnable, ListBucketRunnable, DeleteObjectRunnable,
                       DownloadObjectRunnable, DeleteBucketRunnable, BucketInfoRunnable,
                       CreateFolderRunnable, CreateBucketRunnable,CheckNewVersionRunnable)

MAX_WINDOW_SIZE_WIDTH = 800
MAX_WINDOW_SIZE_HIGHT = 600

USER_ACCESS_KEY      = ''
USER_ACCESS_SECRET   = ''

USE_SECURE_CONNECTION = False

VERSION_CODE = 3
VERSION_NAME = u'v0.0.3'

def gcHistogram(): 
        """Returns per-class counts of existing objects.""" 
        result = {} 
        import gc
        for o in gc.get_objects(): 
                t = type(o) 
                count = result.get(t, 0) 
                result[t] = count + 1 
        return result 

def diffHists(h1, h2): 
        """Prints differences between two results of gcHistogram().""" 
        for k in h1: 
                if h1[k] != h2[k]: 
                        print "%s: %d -> %d (%s%d)" % ( 
                                k, h1[k], h2[k], h2[k] > h1[k] and "+" or "", h2[k] - h1[k]) 

# try:
#     import sdi_rc3
# except ImportError:
#     import sdi_rc2

import resource

class MainWindow(QtGui.QMainWindow):
#     sequenceNumber = 1
#     windowList = []
    USE_HTTPS_CONNECTION = False

    def __init__(self, fileName=None):
        super(MainWindow, self).__init__()
        self.threadPool = QtCore.QThreadPool(self)
        self.threadPool.setMaxThreadCount(4)
        
        self.commonOperationthreadPool = QtCore.QThreadPool(self)
        self.commonOperationthreadPool.setMaxThreadCount(1)
        
        self.lastOpenPath = ''
        
        self.runnables = []     #保存所有上传、下载的runnable列表
        
#         h1 = gcHistogram() 
        self.init()
#         h2 = gcHistogram() 
#         diffHists(h1, h2) 
        self.checkNewVersion()

    def startOperationRunnable(self, operationRunnable):
        if operationRunnable is not None :
            if isinstance(operationRunnable, (FileUploadRunnable, DownloadObjectRunnable, FileMultipartUploadRunnable)):
                if isinstance(operationRunnable, DownloadObjectRunnable):
                    #检查是否有相同tmpFilePath的正在执行的runnable
                    for runnable in self.runnables:
                        if isinstance(runnable, DownloadObjectRunnable) and cmp(runnable.tmpFilePath, operationRunnable.tmpFilePath)==0 and (runnable.state == RunnableState.WAITING or runnable.state == RunnableState.RUNNING) :
                            QtGui.QMessageBox.information(self, u"操作取消", u'<p>有相同的下载任务正在执行，请稍后再试。</p>')
                            return False
                
                self.threadPool.start(operationRunnable)
                self.runnables.append(operationRunnable)
            else:
                self.commonOperationthreadPool.start(operationRunnable)
        else:
            return False
        
        return True

    def closeEvent(self, event):
        ''' 关闭事件 '''
#         if self.maybeSave():
#             event.accept()
#         else:
#             event.ignore()
#         event.accept()

        ''' 停止所有下载线程 '''
        for runnable in self.runnables:
            if runnable.state == RunnableState.WAITING or runnable.state == RunnableState.RUNNING :
                runnable.cancel()

        QtGui.qApp.closeAllWindows()

    def uploadFile(self):
        ''' 上传文件 '''
        fileNames = QtGui.QFileDialog.getOpenFileNames(self, u'请选择上传文件', self.lastOpenPath)
        if not fileNames:
            return False
        
        fileNamesArray = []
        for fileName in fileNames:
            fileName = u'%s'%fileName
            if os.name == 'nt':
                fileName = fileName.replace('\\','/')
            fileNamesArray.append(fileName)
        
        
        self.openFilesPath = fileNamesArray[0]
        basePath = os.path.dirname(self.openFilesPath)
        
        if self.filesTable :
            self.filesTable.uploadMultiObjectAction(fileNamesArray,basePath+'/')
        
    def newfolder(self):
        folderName, ok = QtGui.QInputDialog.getText(self, u"新建目录" if self.filesTable == self.central_widget.currentWidget() else u'新建bucket',
                u"目录名称:" if self.filesTable == self.central_widget.currentWidget() else u'bucket 名称:', 
                QtGui.QLineEdit.Normal,
                '')
        if ok and folderName != '':
            folderName = u'%s'%folderName#unicode(folderName,'utf-8','ignore')
            
            import re
            p = re.compile(r'^[^\\/:\\\\?*<>\"\\t]+$')
            match = p.match(folderName)
            if match is not None:
                if self.filesTable == self.central_widget.currentWidget() :
                    self.filesTable.createFolder(folderName)
                elif self.bucketsTable == self.central_widget.currentWidget() :
                    self.bucketsTable.createBucket(folderName)
            else:
                ''' 名称不合法 '''
                reply = QtGui.QMessageBox.information(self,
                u"名称不合法", 
                u'<p>名称不合法</p><p>请选择正确的名称</p>')
        
    def objectInfo(self):
        if self.filesTable :
            self.filesTable.fileInfoAction(None)
        
    def reload(self):
        self.central_widget.currentWidget().refreshTableList()
        
        
    def showLogWindow(self):
        ''' 显示历史操作列表 '''
        if self.operationLogTable is None:
            self.operationLogTable = OperationLogTable(self)

        if self.operationLogTable.isVisible():
            self.operationLogTable.setHidden(True)
        else:
            self.operationLogTable.move(self.x() + self.width() + 5, self.y())
            self.operationLogTable.show()

    def about(self):
        QtGui.QMessageBox.about(self, "SCS client",
                "<b>SCS client</b> .")

    def init(self):
        self.central_widget = QtGui.QStackedWidget()
        self.setCentralWidget(self.central_widget)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.filesTable = None

        self.createBucketTable()
        self.operationLogTable = OperationLogTable(self)
        self.loginWindow = LoginWindow(self)
        self.createActions()
        self.createMenus()
        self.createToolBars()
        self.createStatusBar()

        self.readSettings()
        self.central_widget.addWidget(self.loginWindow)


    def createActions(self):
        self.uploadAct = QtGui.QAction(QtGui.QIcon(':/upload.png'), u"&上传文件",
                self, enabled=False, shortcut=QtGui.QKeySequence.New,
                statusTip=u"上传文件至当前目录", triggered=self.uploadFile)
        
        self.newfolderAct = QtGui.QAction(QtGui.QIcon(':/newfolder.png'), u"&新建目录",
                self, enabled=False, shortcut=QtGui.QKeySequence.New,
                statusTip=u"新建目录", triggered=self.newfolder)
        
        self.objectInfoAct = QtGui.QAction(QtGui.QIcon(':/info.png'), u"&信息",
                self, enabled=False, shortcut=QtGui.QKeySequence.New,
                statusTip=u"显示文件信息", triggered=self.objectInfo)
        
        self.reloadAct = QtGui.QAction(QtGui.QIcon(':/reload.png'), u"&刷新",
                self, enabled=False, shortcut=QtGui.QKeySequence.New,
                statusTip=u"刷新当前目录", triggered=self.reload)

        self.logWindowAct = QtGui.QAction(QtGui.QIcon(':/queue.png'),
                u"操作列表", self, shortcut=QtGui.QKeySequence.Paste,
                statusTip=u"显示历史操作任务",
                triggered=self.showLogWindow)

        self.aboutAct = QtGui.QAction("&About", self,
                statusTip="Show the application's About box",
                triggered=self.about)
        
        self.exitAct = QtGui.QAction("E&xit", self, shortcut="Ctrl+Q",
                statusTip=u"Exit the application",
                triggered=QtGui.qApp.closeAllWindows)

    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu("&File")
        self.fileMenu.addAction(self.uploadAct)
        self.fileMenu.addAction(self.newfolderAct)
        self.fileMenu.addAction(self.objectInfoAct)
        self.fileMenu.addAction(self.exitAct)

        self.editMenu = self.menuBar().addMenu("&View")
        self.editMenu.addAction(self.logWindowAct)

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.aboutAct)

    def createToolBars(self):
        self.toolBar = QtGui.QToolBar(self)
        self.toolBar.setAllowedAreas(QtCore.Qt.TopToolBarArea)
        self.toolBar.setMovable(False)
        self.toolBar.setFloatable(False)
        self.addToolBar(QtCore.Qt.ToolBarArea(QtCore.Qt.TopToolBarArea), self.toolBar)

        self.spacer = QtGui.QWidget()
        self.spacer.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)

        self.toolBar.addAction(self.uploadAct)
        self.toolBar.addAction(self.newfolderAct)
        self.toolBar.addAction(self.objectInfoAct)
        self.toolBar.addAction(self.reloadAct)
        self.toolBar.addWidget(self.spacer)
        self.toolBar.addAction(self.logWindowAct)
        

    def createStatusBar(self):
        self.statusBar().showMessage(u"Ready")

    def readSettings(self):
        settings = QtCore.QSettings(u'Trolltech', 'SCS client')
        pos = settings.value('pos', QtCore.QPoint(200, 200))
        size = settings.value('size', QtCore.QSize(400, 400))
        self.move(pos)
        self.resize(size)


    def strippedName(self, fullFileName):
        return QtCore.QFileInfo(fullFileName).fileName()

    def findMainWindow(self, fileName):
        canonicalFilePath = QtCore.QFileInfo(fileName).canonicalFilePath()

        for widget in QtGui.qApp.topLevelWidgets():
            if isinstance(widget, MainWindow) and widget.curFile == canonicalFilePath:
                return widget

        return None

    ''' ============== private method ====================='''
    
    ''' create window '''
    def createBucketTable(self):
        self.bucketsTable = BucketTable(self)
    
    def openBucketOfTableItem(self, bucketName):
        currentBucketName = bucketName
        if self.filesTable is None:
            self.filesTable = FilesTable(currentBucketName, self)
        else:
            self.filesTable.currentBucketName = currentBucketName
            self.filesTable.refreshTableList()
        
        self.central_widget.addWidget(self.filesTable)
        self.central_widget.setCurrentWidget(self.filesTable)
        
        self.uploadAct.setEnabled(True)
        self.newfolderAct.setEnabled(True)
    
    
    def showBuckets(self, buckets_generator):
        self.uploadAct.setEnabled(False)
        self.bucketsTable.setBuckets(buckets_generator)
    
    def loginBtnAction(self):
        ''' 登录按钮事件 '''
        USE_SECURE_CONNECTION = self.loginWindow.isSecureConnectionCheckBox.isChecked()
        USER_ACCESS_KEY = u'%s'%self.loginWindow.accessKeyEdit.text()
        USER_ACCESS_SECRET = u'%s'%self.loginWindow.accessSecretEdit.text()

        sinastorage.setDefaultAppInfo(USER_ACCESS_KEY, USER_ACCESS_SECRET, True if USE_SECURE_CONNECTION == 1 else False)
        
        listBucketRunnable = ListBucketRunnable(self)
        QtCore.QObject.connect(listBucketRunnable.emitter,QtCore.SIGNAL('ListBucketRunnable(PyQt_PyObject)'),self.loginDidFinished)
        QtCore.QObject.connect(listBucketRunnable.emitter,QtCore.SIGNAL('ListBucketRunnableDidFailed(PyQt_PyObject,PyQt_PyObject)'),self.loginDidFailed)
        self.startOperationRunnable(listBucketRunnable)
        
        self.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'处理中',
                                                   'thread':listBucketRunnable})
        
    def loginDidFinished(self, runnable):
        self.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'完成',
                                                   'thread':runnable})
        
        ''' 登录成功，保存登录信息 '''
        addKeyValueToWindowsRegistry(u'accessKey',u'%s'%self.loginWindow.accessKeyEdit.text())
        
        if self.loginWindow.saveSecretCheckBox.isChecked():
            addKeyValueToWindowsRegistry(u'accessSecret',u'%s'%self.loginWindow.accessSecretEdit.text())
            addKeyValueToWindowsRegistry(u'isSaveSecret',u'1')
        else:
            removeKeyFromWindowsRegistry(u'accessSecret')
            removeKeyFromWindowsRegistry(u'isSaveSecret')
        
        
        
        self.central_widget.addWidget(self.bucketsTable)
        self.showBuckets(runnable.bucketIter())
        self.central_widget.removeWidget(self.loginWindow)
        sip.delete(self.loginWindow)
        
        self.reloadAct.setEnabled(True)
        self.newfolderAct.setEnabled(True)
        
    def loginDidFailed(self, runnable, errorMsg):
        self.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'失败',
                                                   'thread':runnable})
        reply = QtGui.QMessageBox.information(self,
                u"登录失败", 
                u'<p>登录失败</p><p>请检查Access Key和Access Secrect是否正确</p>')
                
    def checkNewVersion(self):
        checkNewVersionRunnable = CheckNewVersionRunnable()
        QtCore.QObject.connect(checkNewVersionRunnable.emitter,QtCore.SIGNAL('CheckNewVersion(PyQt_PyObject)'),self.checkVersionResult)
        self.startOperationRunnable(checkNewVersionRunnable)
                
    def checkVersionResult(self, verDict):
        '''
            {
                "version_name": "v1.0",
                "version_code": 1,
                "download_url": "http://open.sinastorage.cn"
            }
        '''
        if verDict['version_code'] > VERSION_CODE:
            reply = QtGui.QMessageBox.information(self,
                u"发现新版本", 
                u'<p>发现新版本</p><p>点击进行下载<a href=%s>%s</p>'%(verDict['download_url'],verDict['version_name']))
        
        del verDict
        
                
if __name__ == '__main__':
    import sys

    app = QtGui.QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.setMinimumSize(800, 600)
    mainWin.show()
    sys.exit(app.exec_())