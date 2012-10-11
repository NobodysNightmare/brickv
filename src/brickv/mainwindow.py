# -*- coding: utf-8 -*-  
"""
brickv (Brick Viewer) 
Copyright (C) 2009-2010 Olaf Lüke <olaf@tinkerforge.com>
Copyright (C) 2012 Matthias Bolte <matthias@tinkerforge.com>

mainwindow.py: New/Removed Bricks are handled here and plugins shown if clicked 

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License 
as published by the Free Software Foundation; either version 2 
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

from PyQt4.QtCore import pyqtSignal, QAbstractTableModel, QVariant, Qt, QTimer
from PyQt4.QtGui import QMainWindow, QMessageBox, QIcon, QPushButton, QSortFilterProxyModel, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QSpacerItem, QSizePolicy
from ui_mainwindow import Ui_MainWindow
from plugin_system.plugin_manager import PluginManager
from bindings.ip_connection import IPConnection, Error
from updates import UpdatesWindow
from flashing import FlashingWindow
from advanced import AdvancedWindow

import socket
import signal
import sys
import operator

HOST_HISTORY_SIZE = 5

if sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
    import config_linux as config
elif sys.platform == 'darwin':
    import config_macosx as config
elif sys.platform == 'win32':
    import config_windows as config
else:
    print "Unsupported platform: " + sys.platform
    import config
    def get_host(): return config.DEFAULT_HOST
    def set_host(host): pass
    def get_host_history(size): return []
    def set_host_history(history): pass
    def get_port(): return config.DEFAULT_PORT
    def set_port(port): pass

class MainTableModel(QAbstractTableModel):
    def __init__(self, header, data, parent=None, *args): 
        QAbstractTableModel.__init__(self, parent, *args) 
        self.header = header
        self.data = data

    def rowCount(self, parent): 
        return len(self.data) 

    def columnCount(self, parent): 
        return len(self.header) 
 
    def data(self, index, role): 
        if not index.isValid(): 
            return QVariant() 
        elif role != Qt.DisplayRole: 
            return QVariant() 
        return QVariant(self.data[index.row()][index.column()]) 

    def setData(self, index, value, role):
        if index.isValid() and role == Qt.DisplayRole:
            self.data[index.row()][index.column()] = value
            self.dataChanged.emit(index, index)

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header[col])
        return QVariant()

class MainWindow(QMainWindow, Ui_MainWindow):
    callback_enumerate_signal = pyqtSignal(str, str, int, bool)
    
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon("brickv-icon.png"))
        signal.signal(signal.SIGINT, self.exit_brickv) 
        signal.signal(signal.SIGTERM, self.exit_brickv) 
        
        self.setWindowTitle("Brick Viewer " + config.BRICKV_VERSION)
        
        self.table_view_header = ['Stack ID', 'Device Name', 'UID', 'FW Version']

        # Remove dummy tab
        self.tab_widget.removeTab(1)
        self.last_tab = 0
        
        self.plugins = [(self, None, None, None)]
        self.ipcon = None
        self.updates_window = None
        self.flashing_window = None
        self.advanced_window = None
        self.reset_view()
        self.button_advanced.setDisabled(True)

        self.callback_enumerate_signal.connect(self.callback_enumerate)

        self.tab_widget.currentChanged.connect(self.tab_changed)
        self.connect.pressed.connect(self.connect_pressed)
        self.button_updates.pressed.connect(self.updates_pressed)
        self.button_flashing.pressed.connect(self.flashing_pressed)
        self.button_advanced.pressed.connect(self.advanced_pressed)
        self.plugin_manager = PluginManager()

        self.combo_host.addItem(config.get_host())
        self.combo_host.addItems(config.get_host_history(HOST_HISTORY_SIZE - 1))
        self.spinbox_port.setValue(config.get_port())

        self.table_view.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)

        self.mtm = None

    def closeEvent(self, event):
        self.exit_brickv()
        
    def exit_brickv(self, signl=None, frme=None):
        host = str(self.combo_host.currentText())
        history = []

        for i in range(self.combo_host.count()):
            h = str(self.combo_host.itemText(i))

            if h != host and h not in history:
                history.append(h)

        config.set_host(host)
        config.set_host_history(history[:HOST_HISTORY_SIZE - 1])
        config.set_port(self.spinbox_port.value())

        if self.ipcon != None:
            self.reset_view()
            
        if signl != None and frme != None:
            print "Received SIGINT or SIGTERM, shutting down."
            sys.exit()

    def start(self):
        pass
    
    def stop(self):
        pass
    
    def destroy(self):
        pass
        
    def tab_changed(self, i):
        self.plugins[i][0].start()
        self.plugins[self.last_tab][0].stop()
        self.last_tab = i
        
    def reset_view(self):
        self.tab_widget.setCurrentIndex(0)
        for i in reversed(range(1, len(self.plugins))):
            try:
                self.plugins[i][0].stop()
                self.plugins[i][0].destroy()
            except AttributeError:
                pass
        
            self.tab_widget.removeTab(i)
            
        self.plugins = [(self, None, None, None)]
        
        self.update_table_view()
        
        if self.ipcon:
            self.ipcon.destroy()
        self.ipcon = None

    def updates_pressed(self):
        if self.updates_window is None:
            self.updates_window = UpdatesWindow(self, config)

        self.update_updates_window()
        self.updates_window.show()
        self.updates_window.refresh()

    def flashing_pressed(self):
        first = False

        if self.flashing_window is None:
            first = True
            self.flashing_window = FlashingWindow(self)

        self.update_flashing_window()
        self.flashing_window.show()

        if first:
            self.flashing_window.refresh_firmwares_and_plugins()

    def advanced_pressed(self):
        if self.advanced_window is None:
            self.advanced_window = AdvancedWindow(self)

        self.update_advanced_window()
        self.advanced_window.show()

    def connect_pressed(self):
        if not self.ipcon:
            try:
                host = self.combo_host.currentText()
                self.ipcon = IPConnection(host, self.spinbox_port.value())
                self.ipcon.enumerate(self.callback_enumerate_signal.emit)
                self.connect.setText("Disconnect")
                self.combo_host.setDisabled(True)
                self.spinbox_port.setDisabled(True)

                index = self.combo_host.findText(host)
                if index >= 0:
                    self.combo_host.removeItem(index)
                self.combo_host.insertItem(-1, host)
                self.combo_host.setCurrentIndex(0)

                while self.combo_host.count() > HOST_HISTORY_SIZE:
                    self.combo_host.removeItem(self.combo_host.count() - 1)
            except (Error, socket.error):
                self.ipcon = None
                box_head = 'Could not connect'
                box_text = 'Please check host, check port and ' + \
                           'check if brickd is running.'
                QMessageBox.critical(self, box_head, box_text)
        else:
            self.reset_view()
            
            self.connect.setText("Connect")
            self.button_advanced.setDisabled(True)
            self.combo_host.setDisabled(False)
            self.spinbox_port.setDisabled(False)

    def create_plugin_container(self, plugin, stack_id, name, uid):
        container = QWidget()
        layout = QVBoxLayout(container)
        info = QHBoxLayout()

        info.addWidget(QLabel('Stack ID:'))
        info.addWidget(QLabel('{0}'.format(stack_id)))

        info.addSpacerItem(QSpacerItem(1, 1, QSizePolicy.Expanding))

        info.addWidget(QLabel('UID:'))
        label = QLabel('{0}'.format(uid))
        label.setTextInteractionFlags(Qt.TextSelectableByMouse |
                                      Qt.TextSelectableByKeyboard)
        info.addWidget(label)

        info.addSpacerItem(QSpacerItem(1, 1, QSizePolicy.Expanding))

        info.addWidget(QLabel('FW Version:'))
        info.addWidget(QLabel('{0}'.format(plugin.version)))

        if ' Brick ' in name:
            button = QPushButton('Reset')
            if plugin.has_reset_device():
                button.clicked.connect(plugin.reset_device)
            else:
                button.setDisabled(True)
            info.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding))
            info.addWidget(button)

        layout.addLayout(info)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        plugin.layout().setContentsMargins(0, 0, 0, 0)

        layout.addWidget(line)
        layout.addWidget(plugin)

        return container

    def callback_enumerate(self, uid, name, stack_id, is_new):
        if is_new:
            for plugin in self.plugins:
                # Plugin already loaded
                if plugin[3] == uid:
                    return
            plugin = self.plugin_manager.get_plugin_from_name(name, self.ipcon, uid)
            if plugin is not None:
                self.tab_widget.addTab(self.create_plugin_container(plugin, stack_id, name, uid), name)
                self.plugins.append((plugin, stack_id, name, uid))
        else:
            for i in range(len(self.plugins)):
                if self.plugins[i][3] == uid:
                    self.tab_widget.setCurrentIndex(0)
                    self.plugins[i][0].stop()
                    self.plugins[i][0].destroy()
                    self.tab_widget.removeTab(i)
                    self.plugins.remove(self.plugins[i])
                    self.update_table_view()
                    return
                
        self.update_table_view()
    
    def update_table_view(self):
        data = []
        for p in self.plugins[1:]:
            if p[0] is not None:
                data.append([p[1], p[2], p[3], p[0].version])

        self.table_view.setSortingEnabled(False)
        self.mtm = MainTableModel(self.table_view_header, data)
        sfpm = QSortFilterProxyModel()
        sfpm.setSourceModel(self.mtm)
        self.table_view.setModel(sfpm)
        self.table_view.setSortingEnabled(True)
        self.update_updates_window()
        self.update_flashing_window()
        self.update_advanced_window()

    def update_updates_window(self):
        devices = []
        for plugin in self.plugins[1:]:
            devices.append((str(plugin[2]), str(plugin[3]), plugin[0].version.split('.')))

        if self.updates_window is not None:
            self.updates_window.set_devices(devices)

    def update_flashing_window(self):
        if self.flashing_window is not None:
            devices = []
            for plugin in self.plugins[1:]:
                if ' Brick ' in plugin[2]:
                    devices.append(('{0} [{1}]'.format(plugin[2], plugin[3]), plugin[0].device))
            self.flashing_window.set_devices(devices)

    def update_advanced_window(self):
        devices = []
        for plugin in self.plugins[1:]:
            if ' Brick ' in plugin[2]:
                devices.append(('{0} [{1}]'.format(plugin[2], plugin[3]), plugin[0].device))

        self.button_advanced.setEnabled(len(devices) > 0)

        if self.advanced_window is not None:
            self.advanced_window.set_devices(devices)
