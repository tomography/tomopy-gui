import os
import sys
import logging
import pkg_resources
import tifffile
import dxchange as dx
import tomopyui.widgets
import tomopyui.process
import tomopyui.util as util
import tomopyui.config as config
import tomopyui.reco as reco

from argparse import ArgumentParser
import numpy as np
from contextlib import contextmanager
from PyQt4 import QtGui, QtCore, uic


LOG = logging.getLogger(__name__)


def set_last_file(path, line_edit, last_file):
    if os.path.exists(str(path)):
        line_edit.clear()
        line_edit.setText(path)
        last_file = str(line_edit.text())
    return last_file

def set_last_dir(path, line_edit, last_file):
    if os.path.exists(str(path)):
        line_edit.clear()
        line_edit.setText(path)
        last_dir = os.path.dirname(str(path))
    return last_dir

def set_output_dir(path, line_edit, last_file):
    output_dir = os.path.splitext(str(path))[0] + os.sep
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    line_edit.clear()
    line_edit.setText(output_dir)
    return output_dir

class CallableHandler(logging.Handler):
    def __init__(self, func):
        logging.Handler.__init__(self)
        self.func = func

    def emit(self, record):
        self.func(self.format(record))

def check_filename(fname):
    result = False

    try:
        os.path.isfile(fname)
        result = True
    except OSError:
        return False

    return result

@contextmanager
def spinning_cursor():
    QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
    yield
    QtGui.QApplication.restoreOverrideCursor()


class ApplicationWindow(QtGui.QMainWindow):
    def __init__(self, app, params):
        QtGui.QMainWindow.__init__(self)
        self.params = params
        self.app = app
        ui_file = pkg_resources.resource_filename(__name__, 'gui.ui')
        self.ui = uic.loadUi(ui_file, self)
        self.ui.show()

        self.ui.tab_widget.setCurrentIndex(0)
        self.ui.slice_dock.setVisible(False)
        self.ui.volume_dock.setVisible(False)
        self.ui.axis_view_widget.setVisible(False)

        self.get_values_from_params()
        self.ui.binning_box.setEnabled(False)
        self.ui.slice_start.setEnabled(False)
        self.ui.slice_end.setEnabled(False)
        self.axis_calibration = None
    
        # set up run-time widgets
        self.slice_viewer = tomopyui.widgets.ImageViewer()
        self.volume_viewer = tomopyui.widgets.VolumeViewer()
        self.overlap_viewer = tomopyui.widgets.OverlapViewer()

        self.ui.overlap_layout.addWidget(self.overlap_viewer)
        self.ui.slice_dock.setWidget(self.slice_viewer)
        self.ui.volume_dock.setWidget(self.volume_viewer)

        # connect signals
        self.overlap_viewer.slider.valueChanged.connect(self.axis_slider_changed)
        self.ui.slice_box.clicked.connect(self.slice_box_clicked)
        self.ui.dx_file_name_button.clicked.connect(self.dx_file_name_clicked)
        self.ui.path_button_rec.clicked.connect(self.dx_file_name_clicked)
        self.ui.calibrate_dx_button.clicked.connect(self.calibrate_dx)
        self.ui.show_slices_button.clicked.connect(self.on_show_slices_clicked)
        self.ui.show_projection_button.clicked.connect(self.on_show_projection_clicked)
        self.ui.ffc_box.clicked.connect(self.on_ffc_box_clicked)
        self.ui.ffc_options.currentIndexChanged.connect(self.change_ffc_options)
        self.ui.method_box.currentIndexChanged.connect(self.change_method)
        self.ui.binning_box.currentIndexChanged.connect(self.change_binning)
        #self.ui.slice_start.valueChanged.connect(lambda value: self.change_value('slice_start', value))
        #self.ui.slice_end.valueChanged.connect(lambda value: self.change_value('slice_end', value))
        self.ui.slice_start.valueChanged.connect(lambda value: self.change_start('slice_start', value))
        self.ui.slice_end.valueChanged.connect(lambda value: self.change_end('slice_end', value))
        self.ui.axis_spin.valueChanged.connect(self.change_axis_spin)
        self.ui.reco_button.clicked.connect(self.on_reconstruct)

        self.ui.open_action.triggered.connect(self.on_open_from)
        self.ui.save_action.triggered.connect(self.on_save_as)
        self.ui.close_action.triggered.connect(self.close)
        self.ui.about_action.triggered.connect(self.on_about)

        # set up log handler
        log_handler = CallableHandler(self.output_log)
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
        root_logger = logging.getLogger('')
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers = [log_handler]

    def slice_box_clicked(self):
        self.ui.slice_start.setEnabled(self.ui.slice_box.isChecked())

    def output_log(self, record):
        self.ui.text_browser.append(record)

    def get_filename(self, caption, type_filter):
        return QtGui.QFileDialog.getOpenFileName(self, caption, self.last_file, type_filter)

    def dx_file_name_clicked(self, checked):
        path = self.get_filename('Open DX file', 'Images (*.hdf *.h5)')

        self.data_size = util.read_dx_dims(str(path), 'data')
        self.data_dark_size = util.read_dx_dims(str(path), 'data_dark')
        self.data_white_size = util.read_dx_dims(str(path), 'data_white')
        self.ui.label_data_size.setText(str(self.data_size))
        self.ui.label_data_dark_size.setText(str(self.data_dark_size))
        self.ui.label_data_white_size.setText(str(self.data_white_size))

        self.dsize = (self.data_size[1]/np.power(2, float(self.params.binning))).astype(np.int)

        self.ui.slice_start.setRange(0, self.dsize)
        self.ui.slice_start.setValue(self.dsize/2)
        self.ui.slice_start.setRange(0, self.dsize)
        self.ui.slice_end.setRange(self.dsize/2+1, self.dsize)
        self.ui.slice_end.setValue(self.dsize/2+1)

        self.ui.dx_file_name_line.setText(path)
        self.ui.input_path_line.setText(path)
        self.on_show_projection_clicked()

        self.last_file = os.path.dirname(str(path))

        self.params.last_file = set_last_file(path, self.ui.dx_file_name_line, self.params.last_file)
        self.params.last_dir = set_last_dir(path, self.ui.input_path_line, self.params.last_dir)  
        self.params.output_dir = set_output_dir(path, self.ui.output_path_line, self.params.output_dir)
        self.ui.binning_box.setEnabled(True)
        self.ui.slice_start.setEnabled(True)
        self.ui.slice_end.setEnabled(True)

    def calibrate_dx(self):
        fname = str(self.ui.dx_file_name_line.text())
        last_ind = util.read_dx_dims(str(fname), 'theta')
        if (last_ind == None):
            last_ind = util.read_dx_dims(str(fname), 'data')
    
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(0, 1))
        self.ui.angle_step.setValue((theta[1] - theta[0]).astype(np.float))

        first = proj[0,:,:].astype(np.float)
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(last_ind[0]-1, last_ind[0]))
        last = proj[0,:,:].astype(np.float)

        with spinning_cursor():
            self.axis_calibration = tomopyui.process.AxisCalibration(first, last)

        position = self.axis_calibration.position
        self.overlap_viewer.set_images(first, last)
        self.overlap_viewer.set_position(position)

    def axis_slider_changed(self):
        val = self.overlap_viewer.slider.value()
        self.axis_calibration.position = val
        self.ui.axis_num.setText('{} px'.format(self.axis_calibration.axis))
        self.ui.axis_spin.setValue(self.axis_calibration.axis)

    def on_show_slices_clicked(self):
        self.on_show_projection_clicked()

    def on_show_projection_clicked(self):
        path = str(self.ui.dx_file_name_line.text())
        self.ui.slice_dock.setVisible(True)

        if not self.slice_viewer:
            self.slice_viewer = tomopyui.widgets.ImageViewer(path)
            self.slice_dock.setWidget(self.slice_viewer)
            self.ui.slice_dock.setVisible(True)
        else:
            self.slice_viewer.load_files(path)

    def change_value(self, name, value):
        setattr(self.params, name, value)

    def change_start(self, name, value):
        setattr(self.params, name, value)
        self.ui.slice_end.setRange(value+1, self.dsize)
#        self.change_end('slice_end', value+1)


    def change_end(self, name, value):
        setattr(self.params, name, value)


    def on_ffc_box_clicked(self):
        checked = self.ui.ffc_box.isChecked()
        self.ui.preprocessing_container.setVisible(checked)
        self.params.ffc_correction = checked

    def get_values_from_params(self):
        self.last_dir = self.params.last_dir
        self.last_file = self.params.last_file

        self.ui.input_path_line.setText(self.params.last_file or '.')
        self.ui.dx_file_name_line.setText(self.params.last_file or '.')
        self.ui.output_path_line.setText(self.params.output_dir or '.')
        self.ui.angle_step.setValue(self.params.angle if self.params.angle else 0.0)
        self.ui.slice_start.setValue(self.params.slice_start if self.params.slice_start else 1)
        self.ui.slice_end.setValue(self.params.slice_end if self.params.slice_end else 2)
        self.ui.axis_spin.setValue(self.params.axis if self.params.axis else 0.0)

        if self.params.ffc_correction:
            self.ui.ffc_box.setChecked(True)

        self.ui.slice_box.setChecked(True)

        if self.params.method == "gridrec":
            self.ui.method_box.setCurrentIndex(0)
        elif self.params.method == "fbp":
            self.ui.method_box.setCurrentIndex(1)
        elif self.params.method == "mlem":
            self.ui.method_box.setCurrentIndex(2)
        elif self.params.method == "sart":
            self.ui.method_box.setCurrentIndex(3)
        elif self.params.method == "sartfbp":
            self.ui.method_box.setCurrentIndex(4)

        self.change_method()

        if self.params.binning == "0":
            self.ui.binning_box.setCurrentIndex(0)
        elif self.params.binning == "1":
            self.ui.binning_box.setCurrentIndex(1)
        elif self.params.binning == "2":
            self.ui.binning_box.setCurrentIndex(2)
        elif self.params.binning == "3":
            self.ui.binning_box.setCurrentIndex(3)

        self.change_binning()
        
        self.ui.on_slice_box_clicked()
        self.ui.minus_log_box.setChecked(self.params.minus_log)

    def change_method(self):
        self.params.method = str(self.ui.method_box.currentText()).lower()
        is_mlem = self.params.method == 'mlem'
        is_sirt = self.params.method == 'sirt'
        is_sartfbp = self.params.method == 'sartfbp'

        for w in (self.ui.iterations, self.ui.iterations_label):
            w.setVisible(is_mlem or is_sirt or is_sartfbp)
        if (is_mlem or is_sirt or is_sartfbp) :
            self.ui.iterations.setValue(self.params.num_iterations)

    def change_binning(self):
        self.params.binning = str(self.ui.binning_box.currentIndex())
        fname = str(self.ui.dx_file_name_line.text())
        data_size = util.read_dx_dims(str(fname), 'data')
        dsize = (data_size[1]/np.power(2, float(self.params.binning))).astype(np.int)
        self.ui.slice_start.setRange(0, dsize)
        self.ui.slice_start.setValue(dsize/2)
        self.ui.slice_start.setRange(0, dsize)
        self.ui.slice_end.setRange(dsize/2+1, dsize)
        self.ui.slice_end.setValue(dsize/2+1)

    def closeEvent(self, event):
        try:
            sections = config.TOMO_PARAMS + ('gui',)
            config.write('tomopyui.conf', args=self.params, sections=sections)
        except IOError as e:
            self.gui_warn(str(e))
            self.on_save_as()

    def on_save_as(self):
        if os.path.exists(self.params.last_file):
            config_file = str(self.params.last_file + "/tomopyui.conf")
            print (config_file)
        else:
            config_file = str(os.getenv('HOME') + "tomopyui.conf")
            print (config_file)
        save_config = QtGui.QFileDialog.getSaveFileName(self, 'Save as ...', config_file)
        if save_config:
            sections = config.TOMO_PARAMS + ('gui',)
            config.write(save_config, args=self.params, sections=sections)

    def on_open_from(self):
        config_file = QtGui.QFileDialog.getOpenFileName(self, 'Open ...', self.params.last_file)
        print(config_file)
        parser = ArgumentParser()
        params = config.Params(sections=config.TOMO_PARAMS + ('gui',))
        parser = params.add_arguments(parser)
        self.params = parser.parse_known_args(config.config_to_list(config_name=config_file))[0]
        self.get_values_from_params()

    def on_about(self):
        message = "GUI is part of ufo-reconstruct {}.".format(__version__)
        QtGui.QMessageBox.about(self, "About ufo-reconstruct", message)

    def closeEvent(self, event):
        try:
            sections = config.TOMO_PARAMS + ('gui',)
            print (sections)
            config.write('tomopyui.conf', args=self.params, sections=sections)
        except IOError as e:
            self.gui_warn(str(e))
            self.on_save_as()

    def on_slice_box_clicked(self):
        self.ui.slice_start.setEnabled(self.ui.slice_box.isChecked())
        self.ui.slice_end.setEnabled(self.ui.slice_box.isChecked())
        if self.ui.slice_box.isChecked():
            self.params.full_reconstruction = False
        else:
            self.params.full_reconstruction = True
    
        self.params.slice_start = self.ui.slice_start.value()
        self.params.slice_end = self.ui.slice_end.value()

    def change_ffc_options(self):
        self.params.normalization_mode = str(self.ui.ffc_options.currentText()).lower()

    def change_axis_spin(self):
        if self.ui.axis_spin.value() == 0:
            self.params.axis = None
        else:
            self.params.axis = self.ui.axis_spin.value()

    def on_reconstruct(self):
        with spinning_cursor():
            self.ui.centralWidget.setEnabled(False)
            self.repaint()
            self.app.processEvents()

            input_images = check_filename(str(self.params.last_file))
            if not input_images:
                self.gui_warn("No data found in {}".format(str(self.ui.input_path_line.text())))
                self.ui.centralWidget.setEnabled(True)
                return

            is_mlem = self.params.method == 'mlem'
            is_sirt = self.params.method == 'sirt'
            is_sartfbp = self.params.method == 'sartfbp'
            if (is_mlem or is_sirt or is_sartfbp) :
                self.params.num_iterations = self.ui.iterations.value()
            
            data_size = util.read_dx_dims(str(self.ui.input_path_line.text()), 'data')

            try:
                 reco.tomo(self.params)
            except Exception as e:
                self.gui_warn(str(e))

            self.ui.centralWidget.setEnabled(True)

    def gui_warn(self, message):
        QtGui.QMessageBox.warning(self, "Warning", message)

def main(params):
    app = QtGui.QApplication(sys.argv)
    ApplicationWindow(app,params)
    sys.exit(app.exec_())
