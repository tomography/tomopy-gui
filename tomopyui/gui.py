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


def set_gui_startup(self, path):
        data_size = util.read_dx_dims(str(path), 'data')
        data_dark_size = util.read_dx_dims(str(path), 'data_dark')
        data_white_size = util.read_dx_dims(str(path), 'data_white')
        theta_size = util.read_dx_dims(str(path), 'theta')
        self.ui.label_data_size.setText(str(data_size))
        self.ui.label_data_dark_size.setText(str(data_dark_size))
        self.ui.label_data_white_size.setText(str(data_white_size))
        self.ui.label_theta_size.setText(str(theta_size))


        fname = str(self.ui.dx_file_name_line.text())
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(0, 1))
        self.ui.theta_step.setText(str((180.0 / np.pi * (theta[1] - theta[0]).astype(np.float)))) #$$$

        self.dsize = (data_size[1]/np.power(2, float(self.params.binning))).astype(np.int)

        self.ui.slice_start.setRange(0, self.dsize)
        self.ui.slice_start.setValue(self.dsize/2)
        self.ui.slice_start.setRange(0, self.dsize)
        self.ui.slice_end.setRange(self.dsize/2+1, self.dsize)
        self.ui.slice_end.setValue(self.dsize/2+1)

        self.ui.dx_file_name_line.setText(path)
        self.ui.input_path_line.setText(path)

        self.last_file = os.path.dirname(str(path))

        self.params.last_file = set_last_file(path, self.ui.dx_file_name_line, self.params.last_file)
        self.params.last_dir = set_last_dir(path, self.ui.input_path_line, self.params.last_dir)  
        self.params.output_dir = set_output_dir(path, self.ui.output_path_line, self.params.output_dir)

        self.ui.preprocessing_container.setVisible(True)
        self.ui.reconstruction_container.setVisible(True)
        self.ui.output_container.setVisible(True)
        self.ui.ffc_box.setVisible(True)
        self.on_ffc_box_clicked()
        self.on_pre_processing_box_clicked()
        self.ui.calibrate_dx.setVisible(True)
        
        self.ui.pre_processing_box.setVisible(True)

        self.on_show_projection_clicked()

def get_filtered_filenames(path, exts=['.tif', '.tiff']):
    result = []

    try:
        for ext in exts:
            result += [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ext)]
    except OSError:
        return []

    return sorted(result)

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
        self.ui.projection_dock.setVisible(False)
        self.ui.slice_dock.setVisible(False)
        self.ui.volume_dock.setVisible(False)
        self.ui.axis_view_widget.setVisible(False)

        self.get_values_from_params()

        self.ui.preprocessing_container.setVisible(False)
        self.ui.reconstruction_container.setVisible(False)
        self.ui.output_container.setVisible(False)
        self.ui.ffc_box.setVisible(False)
        self.ui.pre_processing_box.setVisible(False)
        self.ui.calibrate_dx.setVisible(False)
        self.axis_calibration = None
    
        # set up run-time widgets
        self.projection_viewer = tomopyui.widgets.ProjectionViewer()
        self.slice_viewer = None
        #self.slice_viewer = tomopyui.widgets.SliceViewer()
        self.volume_viewer = tomopyui.widgets.VolumeViewer()
        self.overlap_viewer = tomopyui.widgets.OverlapViewer()

        self.ui.overlap_layout.addWidget(self.overlap_viewer)
        self.ui.projection_dock.setWidget(self.projection_viewer)
        self.ui.slice_dock.setWidget(self.slice_viewer)
        self.ui.volume_dock.setWidget(self.volume_viewer)

        # connect signals
        self.overlap_viewer.slider.valueChanged.connect(self.axis_slider_changed)
        self.ui.slice_box.clicked.connect(self.on_slice_box_clicked)
        self.ui.manual_box.clicked.connect(self.on_manual_box_clicked)
        
        self.ui.dx_file_select.clicked.connect(self.dx_file_select_clicked)
        self.ui.dx_file_load.clicked.connect(self.dx_file_load_clicked)

        self.ui.path_select_rec.clicked.connect(self.dx_file_select_clicked)
        self.ui.path_load_rec.clicked.connect(self.dx_file_load_clicked)

        self.ui.calibrate_dx.clicked.connect(self.on_calibrate_dx)
        self.ui.show_slices_button.clicked.connect(self.on_show_slices_clicked)
        self.ui.show_projection_button.clicked.connect(self.on_show_projection_clicked)
        self.ui.ffc_box.clicked.connect(self.on_pre_processing_box_clicked)
        self.ui.ffc_box.clicked.connect(self.on_ffc_box_clicked)
        self.ui.ffc_options_box.currentIndexChanged.connect(self.change_ffc_options)
        self.ui.manual_box.clicked.connect(self.on_manual_box_clicked)
        self.ui.method_box.currentIndexChanged.connect(self.change_method)
        self.ui.binning_box.currentIndexChanged.connect(self.change_binning)
        self.ui.filter_box.currentIndexChanged.connect(self.change_filter)
        self.ui.slice_start.valueChanged.connect(lambda value: self.change_start('slice_start', value))
        self.ui.slice_end.valueChanged.connect(lambda value: self.change_end('slice_end', value))

        self.ui.pixel_size_box.valueChanged.connect(lambda value: self.change_value('pixel_size', value))
        self.ui.distance_box.valueChanged.connect(lambda value: self.change_value('propagation_distance', value))
        self.ui.energy_box.valueChanged.connect(lambda value: self.change_value('energy', value))

        self.ui.axis_spin.valueChanged.connect(self.change_axis_spin)
        self.ui.reco_button.clicked.connect(self.on_reconstruct)
        self.ui.phase_correction_box.clicked.connect(self.on_phase_correction_box_clicked)

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


    def output_log(self, record):
        self.ui.text_browser.append(record)

    def get_filename(self, caption, type_filter):
        return QtGui.QFileDialog.getOpenFileName(self, caption, self.last_file, type_filter)

    def dx_file_select_clicked(self, checked):
        path = self.get_filename('Open DX file', 'Images (*.hdf *.h5)')
        set_gui_startup(self, path)

    def dx_file_load_clicked(self, checked):
        path = str(self.ui.dx_file_name_line.text())
        set_gui_startup(self, path)

    def on_calibrate_dx(self):
        fname = str(self.ui.dx_file_name_line.text())
        last_ind = util.read_dx_dims(str(fname), 'theta')
        if (last_ind == None):
            last_ind = util.read_dx_dims(str(fname), 'data')
    
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(0, 1))
        ##self.ui.theta_step.setText(str((180.0 / np.pi * theta[1] - theta[0]).astype(np.float)))

        if self.params.ffc_correction:
            first = proj[0,:,:].astype(np.float)/flat[0,:,:].astype(np.float)
        else:
            first = proj[0,:,:].astype(np.float)
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(last_ind[0]-1, last_ind[0]))
        if self.params.ffc_correction:
            last = proj[0,:,:].astype(np.float)/flat[0,:,:].astype(np.float)
        else:
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
        path = str(self.ui.output_path_line.text())
        filenames = get_filtered_filenames(path)
        print(path)
        print(filenames)
        if not self.slice_viewer:
            self.slice_viewer = tomopyui.widgets.SliceViewer(filenames)
            self.slice_dock.setWidget(self.slice_viewer)
            self.ui.slice_dock.setVisible(True)
        else:
            self.slice_viewer.load_files(filenames)

    def on_show_projection_clicked(self):
        path = str(self.ui.dx_file_name_line.text())
        self.ui.projection_dock.setVisible(True)

        if not self.projection_viewer:
            self.projection_viewer = tomopyui.widgets.ProjectionViewer(path)
            self.projection_dock.setWidget(self.projection_viewer)
            self.ui.projection_dock.setVisible(True)
        else:
            self.projection_viewer.load_files(path, self.params.ffc_correction)

    def change_value(self, name, value):
        setattr(self.params, name, value)
        print(name, value)

    def change_start(self, name, value):
        setattr(self.params, name, value)
        self.ui.slice_end.setMinimum(value+1)

    def change_end(self, name, value):
        setattr(self.params, name, value)


    def on_ffc_box_clicked(self):
        checked = self.ui.ffc_box.isChecked()
        self.params.ffc_correction = checked

    def on_pre_processing_box_clicked(self):
        checked = self.ui.pre_processing_box.isChecked()
        self.ui.preprocessing_container.setVisible(checked)
        self.params.pre_processing = checked

    def on_phase_correction_box_clicked(self):
        checked = self.ui.phase_correction_box.isChecked()
        self.params.phase_correction = checked 
        self.ui.pixel_size_label.setVisible(checked)
        self.ui.pixel_size_box.setVisible(checked)
        self.ui.distance_label.setVisible(checked)
        self.ui.distance_box.setVisible(checked)
        self.ui.energy_label.setVisible(checked)
        self.ui.energy_box.setVisible(checked)

    def on_manual_box_clicked(self):
        checked = self.ui.manual_box.isChecked()

        #for w in (self.ui.start_label, self.ui.end_label):
        #    w.setVisible(not checked)
        self.params.manual = checked

    def get_values_from_params(self):
        self.last_dir = self.params.last_dir
        self.last_file = self.params.last_file

        self.ui.input_path_line.setText(self.params.last_file or '.')
        self.ui.dx_file_name_line.setText(self.params.last_file or '.')
        self.ui.output_path_line.setText(self.params.output_dir or '.')
        self.ui.theta_step.setText(str(self.params.angle) if self.params.angle else str(0.0))
        self.ui.slice_start.setValue(self.params.slice_start if self.params.slice_start else 1)
        self.ui.slice_end.setValue(self.params.slice_end if self.params.slice_end else 2)
        self.ui.axis_spin.setValue(self.params.axis if self.params.axis else 0.0)
        self.ui.pixel_size_box.setValue(self.params.pixel_size if self.params.pixel_size else 1.0)
        self.ui.distance_box.setValue(self.params.propagation_distance if self.params.propagation_distance else 1.0)
        self.ui.energy_box.setValue(self.params.energy if self.params.energy else 10.0)

        if self.params.ffc_correction:
            self.ui.ffc_box.setChecked(True)
        self.on_ffc_box_clicked()

        if self.params.pre_processing:
            self.ui.pre_processing_box.setChecked(True)
        self.on_pre_processing_box_clicked()

        if self.params.phase_correction:
            self.ui.phase_correction_box.setChecked(True)
        self.on_phase_correction_box_clicked()
        
        if self.params.manual:
            self.ui.manual_box.setChecked(True)
        self.on_manual_box_clicked()

        self.ui.slice_box.setChecked(True)

        if self.params.ffc_options == "default":
            self.ui.ffc_options_box.setCurrentIndex(0)
        elif self.params.ffc_options == "background":
            self.ui.ffc_options_box.setCurrentIndex(1)
        elif self.params.ffc_options == "roi":
            self.ui.ffc_options_box.setCurrentIndex(2)

        self.change_ffc_options()

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

        if self.params.filter == "none":
            self.ui.filter_box.setCurrentIndex(0)
        elif self.params.filter == "shepp":
            self.ui.filter_box.setCurrentIndex(1)
        elif self.params.filter == "cosine":
            self.ui.filter_box.setCurrentIndex(2)
        elif self.params.filter == "hann":
            self.ui.filter_box.setCurrentIndex(3)
        elif self.params.filter == "hamming":
            self.ui.filter_box.setCurrentIndex(4)
        elif self.params.filter == "ramlak":
            self.ui.filter_box.setCurrentIndex(5)
        elif self.params.filter == "parzen":
            self.ui.filter_box.setCurrentIndex(6)
        elif self.params.filter == "butterworth":
            self.ui.filter_box.setCurrentIndex(7)

        self.change_filter()
        
        self.ui.on_slice_box_clicked()
        self.ui.minus_log_box.setChecked(self.params.minus_log)

    def change_ffc_options(self):
        self.params.ffc_options = str(self.ui.ffc_options_box.currentText()).lower()

    def change_method(self):
        self.params.method = str(self.ui.method_box.currentText()).lower()
        is_gridrec = self.params.method == 'gridrec'
        is_fbp = self.params.method == 'fbp'
        is_mlem = self.params.method == 'mlem'
        is_sirt = self.params.method == 'sirt'
        is_sartfbp = self.params.method == 'sartfbp'

        for w in (self.ui.iterations, self.ui.iterations_label):
            w.setVisible(is_mlem or is_sirt or is_sartfbp)
        if (is_mlem or is_sirt or is_sartfbp) :
            self.ui.iterations.setValue(self.params.num_iterations)

        for w in (self.ui.filter_box, self.ui.filter_label):
            w.setVisible(is_gridrec or is_fbp)

    def change_binning(self):
        self.params.binning = str(self.ui.binning_box.currentIndex())
        fname = str(self.ui.dx_file_name_line.text())
        try:
            data_size = util.read_dx_dims(str(fname), 'data')
            dsize = (data_size[1]/np.power(2, float(self.params.binning))).astype(np.int)
        except:
            dsize = 1024
        self.ui.slice_start.setRange(0, dsize)
        self.ui.slice_start.setValue(dsize/2)
        self.ui.slice_end.setRange(dsize/2+1, dsize)
        self.ui.slice_end.setValue(dsize/2+1)

    def change_filter(self):
        self.params.filter = str(self.ui.filter_box.currentText()).lower()

    def change_axis_spin(self):
        if self.ui.axis_spin.value() == 0:
            self.params.axis = None
        else:
            self.params.axis = self.ui.axis_spin.value()

    def closeEvent(self, event):
        try:
            print(self.params.propagation_distance)
            print(self.params.energy)
            print(self.params.pixel_size)

            sections = config.TOMO_PARAMS + ('gui', 'retrieve-phase')
            print(sections)
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

    def on_slice_box_clicked(self):
        self.ui.slice_end.setVisible(not self.ui.slice_box.isChecked())
        self.ui.slice_end_label.setVisible(not self.ui.slice_box.isChecked())
        if self.ui.slice_box.isChecked():
            self.params.full_reconstruction = False
        else:
            self.params.full_reconstruction = True
    
        self.params.slice_start = self.ui.slice_start.value()
        self.params.slice_end = self.ui.slice_end.value()

    def on_manual_box_clicked(self):
        self.ui.data_start_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_end_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_end.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_dark_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_dark_end.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_white_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_white_end.setVisible(self.ui.manual_box.isChecked())
        self.ui.theta_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.theta_end.setVisible(self.ui.manual_box.isChecked())
        #self.ui.theta_unit_label.setVisible(self.ui.manual_box.isChecked())

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
