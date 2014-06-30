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

from Runnables import ListBucketRunnable

MAX_WINDOW_SIZE_WIDTH = 800
MAX_WINDOW_SIZE_HIGHT = 600

USER_ACCESS_KEY      = ''
USER_ACCESS_SECRET   = ''

USE_SECURE_CONNECTION = False

# try:
#     import sdi_rc3
# except ImportError:
#     import sdi_rc2

import resource

class MainWindow(QtGui.QMainWindow):
    sequenceNumber = 1
    windowList = []

    def __init__(self, fileName=None):
        super(MainWindow, self).__init__()
        self.threadPool = QtCore.QThreadPool(self)
        self.threadPool.setMaxThreadCount(4)
        
        self.init()

    def startOperationRunnable(self, operationRunnable):
        if operationRunnable is not None :
            self.threadPool.start(operationRunnable)

    def closeEvent(self, event):
        ''' 关闭事件 '''
#         if self.maybeSave():
#             event.accept()
#         else:
#             event.ignore()
#         event.accept()
        QtGui.qApp.closeAllWindows()

    def uploadFile(self):
        ''' 上传文件 '''
        fileName = QtGui.QFileDialog.getOpenFileName(self)
        if not fileName:
            return False
        
        if self.filesTable :
            self.filesTable.uploadFile(u'%s'%fileName)#unicode(fileName,'utf-8','ignore'))
        
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
        USER_ACCESS_KEY = u'%s'%self.loginWindow.accessKeyEdit.text()#unicode(self.loginWindow.accessKeyEdit.text(),'utf-8','ignore')
        USER_ACCESS_SECRET = u'%s'%self.loginWindow.accessSecretEdit.text()#unicode(self.loginWindow.accessSecretEdit.text(),'utf-8','ignore')

        print USER_ACCESS_KEY+'    '+USER_ACCESS_SECRET+('      %i'%USE_SECURE_CONNECTION)
        sinastorage.setDefaultAppInfo(USER_ACCESS_KEY, USER_ACCESS_SECRET)
        
        listBucketRunnable = ListBucketRunnable(self)
        QtCore.QObject.connect(listBucketRunnable.emitter,QtCore.SIGNAL('ListBucketRunnable(PyQt_PyObject)'),self.loginDidFinished)
        QtCore.QObject.connect(listBucketRunnable.emitter,QtCore.SIGNAL('ListBucketRunnableDidFailed(PyQt_PyObject)'),self.loginDidFailed)
        self.startOperationRunnable(listBucketRunnable)
        
        self.operationLogTable.updateLogDict({'operation':'list bucket', 
                                                   'result':u'完成',
                                                   'thread':listBucketRunnable})
        
    def loginDidFinished(self, runnable):
        self.central_widget.addWidget(self.bucketsTable)
        self.showBuckets(runnable.bucketIter())
        self.central_widget.removeWidget(self.loginWindow)
        
        self.reloadAct.setEnabled(True)
        self.newfolderAct.setEnabled(True)
        
    def loginDidFailed(self, runnable):
        reply = QtGui.QMessageBox.information(self,
                u"登录失败", 
                u'<p>登录失败</p><p>请检查Access Key和Access Secrect是否正确</p>')
                
if __name__ == '__main__':
    import sys

    app = QtGui.QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.setMinimumSize(800, 600)
    mainWin.show()
    sys.exit(app.exec_())