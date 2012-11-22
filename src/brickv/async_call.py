# -*- coding: utf-8 -*-
"""
brickv (Brick Viewer)
Copyright (C) 2012 Olaf Lüke <olaf@tinkerforge.com>

async_call.py: Asynchronous call for Brick/Bricklet functions

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

from PyQt4.QtGui import QApplication 
from PyQt4.QtCore import QThread, QEvent

import traceback

try:
    from Queue import Queue
except ImportError:
    from queue import Queue
    
ASYNC_EVENT = 12345

async_queue = Queue()
async_event_queue = Queue()

def async_call(func_to_call, parameter=None, return_ok=None, return_error=None):
    async_queue.put((func_to_call, parameter, return_ok, return_error))
    
def async_event_handler():
    while not async_event_queue.empty():
        try:
            func = async_event_queue.get(False, 0)
            if func:
                func()
        except:
            pass
                
                
def async_start_thread(parent):
    class AsyncThread(QThread):
        def __init__(self, parent=None):
            QThread.__init__(self, parent)

        def run(self):
            while True:
                func_to_call, parameter, return_ok, return_error = async_queue.get()
                if not func_to_call:
                    continue
                
                return_value = None
                try:
                    if parameter == None:
                        return_value = func_to_call()
                    elif isinstance(parameter, tuple):
                        return_value = func_to_call(*parameter)
                    else:
                        return_value = func_to_call(parameter)
                except:
                    traceback.print_exc()
                    
                    if return_error != None:
                        async_event_queue.put(return_error)
                        with async_queue.mutex:
                            async_queue.queue.clear()
                        
                        QApplication.postEvent(self, QEvent(ASYNC_EVENT))
                        continue
                    
                if return_ok != None:
                    if return_value == None:
                        async_event_queue.put(return_ok)
                        QApplication.postEvent(self, QEvent(ASYNC_EVENT))
                    else:
                        def return_lambda(return_ok, value):
                            return lambda: return_ok(value)
                        
                        async_event_queue.put(return_lambda(return_ok, return_value))
                        QApplication.postEvent(self, QEvent(ASYNC_EVENT))
            
    async_thread = AsyncThread(parent)
    async_thread.start()
    return async_thread
        