# -*- coding: utf-8 -*-  
"""
brickv (Brick Viewer) 
Copyright (C) 2011-2012 Olaf Lüke <olaf@tinkerforge.com>
Copyright (C) 2012 Bastian Nordmeyer <bastian@tinkerforge.com>
Copyright (C) 2012 Matthias Bolte <matthias@tinkerforge.com>

advanced.py: GUI for advanced features

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

from ui_advanced import Ui_widget_advanced

from PyQt4.QtCore import Qt, QTimer
from PyQt4.QtGui import QFrame

import infos

NO_BRICK = 'No Brick found'

class AdvancedWindow(QFrame, Ui_widget_advanced):
    def __init__(self, parent):
        QFrame.__init__(self, parent, Qt.Popup | Qt.Window | Qt.Tool)
        self.setupUi(self)

        self.button_calibrate.setEnabled(False)

        self.brick_infos = []
        
        self.parent = parent
        self.button_calibrate.pressed.connect(self.calibrate_pressed)
        self.combo_brick.currentIndexChanged.connect(self.brick_changed)
        self.check_enable_calibration.stateChanged.connect(self.enable_calibration_changed)

    def update_bricks(self):
        self.brick_infos = []
        self.combo_brick.clear()

        for info in infos.infos.values():
            if info.type == 'brick':
                self.brick_infos.append(info)
                self.combo_brick.addItem(info.get_combo_item())

        if self.combo_brick.count() == 0:
            self.combo_brick.addItem(NO_BRICK)

        self.update_calibration()
        self.update_ui_state()

    def calibrate_pressed(self):
        port_names = ['a', 'b', 'c', 'd']

        self.parent.ipcon.adc_calibrate(self.current_device(),
                                        port_names[self.combo_port.currentIndex()])
        
        self.update_calibration()

    def current_device(self):
        try:
            return self.brick_infos[self.combo_brick.currentIndex()].plugin.device
        except:
            return None

    def update_calibration(self):
        device = self.current_device()

        if device is None:
            self.label_offset.setText('-')
            self.label_gain.setText('-')
        else:
            def slot():
                offset, gain = self.parent.ipcon.get_adc_calibration(device)
                self.label_offset.setText(str(offset))
                self.label_gain.setText(str(gain))
            QTimer.singleShot(0, slot)
        
    def brick_changed(self, index):
        self.combo_port.clear()

        if self.combo_brick.currentIndex() < 0 or len(self.brick_infos) == 0:
            self.combo_port.addItems(['A', 'B', 'C', 'D'])
            return

        info = self.brick_infos[index]

        for key in sorted(info.bricklets.keys()):
            if info.bricklets[key] is None:
                self.combo_port.addItem(key.upper())
            else:
                self.combo_port.addItem('{0}: {1}'.format(key.upper(), info.bricklets[key].get_combo_item()))

        self.update_calibration()

    def enable_calibration_changed(self, state):
        self.button_calibrate.setEnabled(state == Qt.Checked)

    def update_ui_state(self):
        enabled = len(self.brick_infos) > 0

        self.combo_brick.setEnabled(enabled)
        self.check_enable_calibration.setEnabled(enabled)
        self.button_calibrate.setEnabled(enabled and self.check_enable_calibration.isChecked())
