import os
import sys
import logging
import pkg_resources
import tifffile
import dxchange as dx
import ufot.widgets
import ufot.process
import ufot.util as util
import ufot.config as config
import ufot.reco as reco

from argparse import ArgumentParser
import numpy as np
from contextlib import contextmanager
from PyQt4 import QtGui, QtCore, uic


LOG = logging.getLogger(__name__)



def set_gui_startup(self, path):
        data_size = util.get_dx_dims(str(path), 'data')
        data_dark_size = util.get_dx_dims(str(path), 'data_dark')
        data_white_size = util.get_dx_dims(str(path), 'data_white')
        theta_size = util.get_dx_dims(str(path), 'theta')

        self.ui.data_size.setText(str(data_size))
        self.ui.data_dark_size.setText(str(data_dark_size))
        self.ui.data_white_size.setText(str(data_white_size))
        self.ui.theta_size.setText(str(theta_size))

        self.ui.dx_file_name_line.setText(path)
        self.ui.input_path_line.setText(path)
        self.input_file_path = os.path.dirname(str(path))

        fname = str(self.ui.dx_file_name_line.text())

        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(0, 1))
        self.ui.theta_step.setText(str(np.rad2deg((theta[1] - theta[0]))))
        self.params.theta_start = theta[0]
        self.params.theta_end = theta[-1]
        self.params.projection_number = data_size[0]

        self.ui.theta_start.setValue(np.rad2deg(theta[0]))
        self.ui.theta_end.setValue(np.rad2deg(theta[-1]))

        self.dsize = data_size[1]
        self.dsize_bin = (data_size[1]/np.power(2, float(self.params.binning))).astype(np.int)

        self.ui.slice_start.setRange(0, self.dsize_bin)
        self.ui.slice_start.setValue(self.dsize_bin/2)

        self.ui.slice_center.setRange(0, self.dsize)
        self.ui.slice_center.setValue(self.dsize/2)

        self.params.input_file_path = set_input_file_path(path, self.ui.dx_file_name_line, self.params.input_file_path)
        self.params.input_path = set_input_path(path, self.ui.input_path_line, self.params.input_path)  
        self.params.output_path = set_output_path(path, self.ui.output_path_line, self.params.output_path)

        self.ui.preprocessing_container.setVisible(True)
        self.ui.reconstruction_container.setVisible(True)
        self.ui.output_container.setVisible(True)
        self.ui.ffc_box.setVisible(True)        
        self.ui.calibrate_dx.setVisible(True)


        self.ui.calibrate_container.setVisible(True)

        self.ui.dx_data_label.setVisible(True)
        self.ui.dx_data_white_label.setVisible(True)
        self.ui.dx_data_dark_label.setVisible(True)
        self.ui.dx_theta_label.setVisible(True)
        
        self.ui.pre_processing_box.setVisible(True)

        self.on_ffc_box_clicked()
        self.on_pre_processing_box_clicked()
        self.on_show_projection_clicked()

def get_filtered_filenames(path, exts=['.tif', '.tiff']):
    result = []

    try:
        for ext in exts:
            result += [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ext)]
    except OSError:
        return []

    return sorted(result)

def set_input_file_path(path, line_edit, input_file_path):
    if os.path.exists(str(path)):
        line_edit.clear()
        line_edit.setText(path)
        input_file_path = str(line_edit.text())
    return input_file_path

def set_input_path(path, line_edit, input_file_path):
    if os.path.exists(str(path)):
        line_edit.clear()
        line_edit.setText(path)
        input_path = os.path.dirname(str(path))
    return input_path

def set_output_path(path, line_edit, input_file_path):
    output_path = os.path.splitext(str(path))[0] + os.sep
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    line_edit.clear()
    line_edit.setText(output_path)
    return output_path

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

class RoiDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self,parent)

        ui_file = pkg_resources.resource_filename(__name__, 'roi.ui')
        self.ui = uic.loadUi(ui_file, self)
        self.ui.show()    

        self.roi_tx = 0
        self.roi_ty = 0
        self.roi_bx = 1
        self.roi_by = 1

        # connect signals
        self.ui.roi_ok_button.clicked.connect(self.on_roi_save_clicked)
        self.ui.roi_top_x.valueChanged.connect(self.on_change_tx)
        self.ui.roi_top_y.valueChanged.connect(self.on_change_ty)

    def on_change_tx(self):
        value = self.ui.roi_top_x.value()
        self.ui.roi_bottom_x.setMinimum(value+1)

    def on_change_ty(self):
        value = self.ui.roi_top_y.value()
        self.ui.roi_bottom_y.setMinimum(value+1)

    def on_roi_save_clicked(self):
        self.roi_tx = self.ui.roi_top_x.value()
        self.roi_ty = self.ui.roi_top_y.value()
        self.roi_bx = self.ui.roi_bottom_x.value()
        self.roi_by = self.ui.roi_bottom_y.value()
        self.close()
        return self.roi_tx, self.roi_ty, self.roi_bx, self.roi_by

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
        self.ui.center_view_widget.setVisible(False)

        self.get_values_from_params()

        self.ui.preprocessing_container.setVisible(False)
        self.ui.reconstruction_container.setVisible(False)
        self.ui.output_container.setVisible(False)
        self.ui.ffc_box.setVisible(False)
        self.ui.pre_processing_box.setVisible(False)
        #self.ui.calibrate_dx.setVisible(False)
        self.ui.calibrate_container.setVisible(False)

        self.ui.dx_data_label.setVisible(False)
        self.ui.dx_data_white_label.setVisible(False)
        self.ui.dx_data_dark_label.setVisible(False)
        self.ui.dx_theta_label.setVisible(False)

        self.ui.theta_step.setVisible(False)
        self.ui.theta_step_label.setVisible(False)

        self.center_calibration = None
    
        # set up run-time widgets
        self.projection_viewer = ufot.widgets.ProjectionViewer()
        self.slice_viewer = None
        self.volume_viewer = None
        self.overlap_viewer = ufot.widgets.OverlapViewer()
        #self.slice_viewer = ufot.widgets.SliceViewer()
        #self.volume_viewer = ufot.widgets.VolumeViewer()
        #self.overlap_viewer = ufot.widgets.OverlapViewer()

        self.ui.overlap_layout.addWidget(self.overlap_viewer)
        self.ui.projection_dock.setWidget(self.projection_viewer)
        self.ui.slice_dock.setWidget(self.slice_viewer)
        self.ui.volume_dock.setWidget(self.volume_viewer)

        # connect signals
        self.overlap_viewer.slider.valueChanged.connect(self.center_slider_changed)
        self.ui.slice_box.clicked.connect(self.on_slice_box_clicked)
        ###self.ui.manual_box.clicked.connect(self.on_manual_box_clicked)
        
        self.ui.dx_file_select.clicked.connect(self.dx_file_select_clicked)
        self.ui.dx_file_load.clicked.connect(self.dx_file_load_clicked)

        self.ui.path_select_rec.clicked.connect(self.dx_file_select_clicked)
        self.ui.path_load_rec.clicked.connect(self.dx_file_load_clicked)

        self.ui.calibrate_dx.clicked.connect(self.on_calibrate_dx)
        self.ui.show_slices_button.clicked.connect(self.on_show_slices_clicked)
        self.ui.show_projection_button.clicked.connect(self.on_show_projection_clicked)
        self.ui.ffc_box.clicked.connect(self.on_pre_processing_box_clicked)
        self.ui.ffc_method.currentIndexChanged.connect(self.change_ffc_method)
        self.ui.cut_off.valueChanged.connect(lambda value: self.change_value('cut_off', value))
        self.ui.air.valueChanged.connect(lambda value: self.change_value('air', value))

        self.ui.nan_and_inf_box.clicked.connect(self.on_nan_and_inf_box_clicked)
        self.ui.minus_log_box.clicked.connect(self.on_minus_log_box_clicked)

        self.ui.phase_method.currentIndexChanged.connect(self.change_phase_method)
        self.ui.manual_box.clicked.connect(self.on_manual_box_clicked)
        self.ui.rec_method.currentIndexChanged.connect(self.change_rec_method)
        self.ui.binning_box.currentIndexChanged.connect(self.change_binning)
        self.ui.filter_box.currentIndexChanged.connect(self.change_filter)
        self.ui.slice_start.valueChanged.connect(lambda value: self.change_start('slice_start', value))
        self.ui.slice_end.valueChanged.connect(lambda value: self.change_end('slice_end', value))
        self.ui.slice_center.valueChanged.connect(lambda value: self.change_center('slice_center', value))

        self.ui.theta_start.valueChanged.connect(lambda value: self.change_start('theta_start', value))
        self.ui.theta_end.valueChanged.connect(lambda value: self.change_end('theta_end', value))

        self.ui.pixel_size.valueChanged.connect(lambda value: self.change_value('pixel_size', value))
        self.ui.distance.valueChanged.connect(lambda value: self.change_value('propagation_distance', value))
        self.ui.energy.valueChanged.connect(lambda value: self.change_value('energy', value))
        self.ui.alpha.valueChanged.connect(lambda value: self.change_value('alpha', value))

        self.ui.center_spin.valueChanged.connect(self.change_center_spin)
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


    def output_log(self, record):
        self.ui.text_browser.append(record)

    def get_filename(self, caption, type_filter):
        return QtGui.QFileDialog.getOpenFileName(self, caption, self.input_file_path, type_filter)

    def dx_file_select_clicked(self, checked):
        path = self.get_filename('Open DX file', 'Images (*.hdf *.h5)')
        set_gui_startup(self, path)

    def dx_file_load_clicked(self, checked):
        path = str(self.ui.dx_file_name_line.text())
        set_gui_startup(self, path)

    def on_calibrate_dx(self):
        fname = str(self.ui.dx_file_name_line.text())
        last_ind = util.get_dx_dims(str(fname), 'theta')
        if (last_ind == None):
            last_ind = util.get_dx_dims(str(fname), 'data')
    
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(0, 1))
        ##self.ui.theta_step.setText(str((180.0 / np.pi * theta[1] - theta[0]).astype(np.float)))

        if self.params.ffc_calibration:
            first = proj[0,:,:].astype(np.float)/flat[0,:,:].astype(np.float)
        else:
            first = proj[0,:,:].astype(np.float)
        proj, flat, dark, theta = dx.read_aps_32id(fname, proj=(last_ind[0]-1, last_ind[0]))
        if self.params.ffc_calibration:
            last = proj[0,:,:].astype(np.float)/flat[0,:,:].astype(np.float)
        else:
            last = proj[0,:,:].astype(np.float)

        with spinning_cursor():
            self.center_calibration = ufot.process.CenterCalibration(first, last)

        position = self.center_calibration.position
        self.overlap_viewer.set_images(first, last)
        self.overlap_viewer.set_position(position)

    def center_slider_changed(self):
        val = self.overlap_viewer.slider.value()
        self.center_calibration.position = val
#        self.ui.center.setText('{} px'.format(self.center_calibration.center))
        self.ui.center.setText(str(self.center_calibration.center))
        self.ui.center_spin.setValue(self.center_calibration.center)

    def on_show_slices_clicked(self):
        path = str(self.ui.output_path_line.text())
        filenames = get_filtered_filenames(path)
        LOG.warn("Loading {}".format(filenames))
        if not self.slice_viewer:
            self.slice_viewer = ufot.widgets.SliceViewer(filenames)
            self.slice_dock.setWidget(self.slice_viewer)
            self.ui.slice_dock.setVisible(True)
        else:
            self.slice_viewer.load_files(filenames)

    def on_show_projection_clicked(self):
        path = str(self.ui.dx_file_name_line.text())
        self.ui.projection_dock.setVisible(True)

        if not self.projection_viewer:
            self.projection_viewer = ufot.widgets.ProjectionViewer(path)
            self.projection_dock.setWidget(self.projection_viewer)
            self.ui.projection_dock.setVisible(True)
        else:
            self.projection_viewer.load_files(path, self.params.ffc_calibration)

    def change_value(self, name, value):
        setattr(self.params, name, value)

    def change_start(self, name, value):
        if(name == 'slice_start'):
            self.ui.slice_end.setMinimum(value+1)
        elif(name == 'theta_start'):
            self.ui.theta_end.setMinimum(value+0.01)
            self.ui.theta_step.setText(str(util.theta_step(value, np.rad2deg(self.params.theta_end), self.params.projection_number)))
            #$$$$$$
            value = np.deg2rad(value)
        setattr(self.params, name, value)

    def change_end(self, name, value):
        if(name == 'slice_end'):
            self.ui.slice_start.setMaximum(value-1)
        elif(name == 'theta_end'):
            self.ui.theta_start.setMaximum(value-0.01)
            self.ui.theta_step.setText(str(util.theta_step(np.rad2deg(self.params.theta_start), value, self.params.projection_number)))
            value = np.deg2rad(value)
        setattr(self.params, name, value)

    def change_center(self, name, value):
        setattr(self.params, name, value)

    def on_ffc_box_clicked(self):
        checked = self.ui.ffc_box.isChecked()
        self.params.ffc_calibration = checked

    def on_pre_processing_box_clicked(self):
        checked = self.ui.pre_processing_box.isChecked()
        self.ui.preprocessing_container.setVisible(checked)
        self.params.pre_processing = checked

    def on_nan_and_inf_box_clicked(self):
        checked = self.ui.nan_and_inf_box.isChecked()
        self.params.nan_and_inf = checked

    def on_minus_log_box_clicked(self):
        checked = self.ui.minus_log_box.isChecked()
        self.params.minus_log = checked

    def on_manual_box_clicked(self):
        checked = self.ui.manual_box.isChecked()

        #for w in (self.ui.start_label, self.ui.end_label):
        #    w.setVisible(not checked)
        self.params.manual = checked

    def get_values_from_params(self):
        self.input_path = self.params.input_path
        self.input_file_path = self.params.input_file_path

        self.ui.input_path_line.setText(self.params.input_file_path or '.')
        self.ui.dx_file_name_line.setText(self.params.input_file_path or '.')
        self.ui.output_path_line.setText(self.params.output_path or '.')

        self.ui.roi_tx.setText(self.params.roi_tx if self.params.roi_tx else str(0))
        self.ui.roi_ty.setText(self.params.roi_ty if self.params.roi_ty else str(0))
        self.ui.roi_bx.setText(self.params.roi_bx if self.params.roi_bx else str(1))
        self.ui.roi_by.setText(self.params.roi_by if self.params.roi_by else str(1))
        self.ui.cut_off.setValue(self.params.cut_off if self.params.cut_off else 1.0)
        self.ui.air.setValue(self.params.air if self.params.air else 1.0)

        self.ui.theta_start.setValue(self.params.theta_start if self.params.theta_start else 0.0)
        self.ui.theta_end.setValue(self.params.theta_end if self.params.theta_end else np.pi)

        self.ui.slice_start.setValue(self.params.slice_start if self.params.slice_start else 1)
        self.ui.slice_end.setValue(self.params.slice_end if self.params.slice_end else 2)
        self.ui.slice_center.setValue(self.params.slice_center if self.params.slice_center else 1)
        self.ui.center_spin.setValue(self.params.center if self.params.center else 0.0)
        self.ui.pixel_size.setValue(self.params.pixel_size if self.params.pixel_size else 1.0)
        self.ui.distance.setValue(self.params.propagation_distance if self.params.propagation_distance else 1.0)
        self.ui.energy.setValue(self.params.energy if self.params.energy else 10.0)
        self.ui.alpha.setValue(self.params.alpha if self.params.alpha else 0.001)

        if self.params.ffc_calibration:
            self.ui.ffc_box.setChecked(True)
        self.on_ffc_box_clicked()

        if self.params.pre_processing:
            self.ui.pre_processing_box.setChecked(True)
        self.on_pre_processing_box_clicked()
       
        if self.params.manual:
            self.ui.manual_box.setChecked(True)
        self.on_manual_box_clicked()

        if self.params.minus_log:
            self.ui.minus_log_box.setChecked(True)
        self.on_minus_log_box_clicked()

        if self.params.nan_and_inf:
            self.ui.nan_and_inf_box.setChecked(True)
        self.on_nan_and_inf_box_clicked()

        self.ui.slice_box.setChecked(True)

        if self.params.ffc_method == "default":
            self.ui.ffc_method.setCurrentIndex(0)
        elif self.params.ffc_method == "background":
            self.ui.ffc_method.setCurrentIndex(1)
        elif self.params.ffc_method == "roi":
            self.ui.ffc_method.setCurrentIndex(2)

        self.change_ffc_method()


        if self.params.phase_method == "none":
            checked = False
            self.ui.phase_method.setCurrentIndex(0)
        elif self.params.phase_method == "paganin":
            checked = True
            self.ui.phase_method.setCurrentIndex(1)

        self.ui.pixel_size_label.setVisible(checked)
        self.ui.pixel_size.setVisible(checked)
        self.ui.distance_label.setVisible(checked)
        self.ui.distance.setVisible(checked)
        self.ui.energy_label.setVisible(checked)
        self.ui.energy.setVisible(checked)
        self.ui.alpha_label.setVisible(checked)
        self.ui.alpha.setVisible(checked)


        self.change_phase_method()
      
        if self.params.reconstruction_algorithm == "gridrec":
            self.ui.rec_method.setCurrentIndex(0)
        elif self.params.reconstruction_algorithm == "fbp":
            self.ui.rec_method.setCurrentIndex(1)
        elif self.params.reconstruction_algorithm == "mlem":
            self.ui.rec_method.setCurrentIndex(2)
        elif self.params.reconstruction_algorithm == "sirt":
            self.ui.rec_method.setCurrentIndex(3)
        elif self.params.reconstruction_algorithm == "sirtfbp":
            self.ui.rec_method.setCurrentIndex(4)

        self.change_rec_method()

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
        self.ui.nan_and_inf_box.setChecked(self.params.nan_and_inf)

    def change_roi(self):
        if (self.params.ffc_method == "roi"):
            roi_dlg = RoiDialog()
            roi_dlg.exec_()
            if roi_dlg.result() == 0:
                roi_tx, roi_ty, roi_bx, roi_by = roi_dlg.on_roi_save_clicked()
                self.ui.roi_tx.setText(str(roi_tx))
                self.ui.roi_ty.setText(str(roi_ty))
                self.ui.roi_bx.setText(str(roi_bx))
                self.ui.roi_by.setText(str(roi_by))
                self.params.roi_tx = str(self.ui.roi_tx)
                self.params.roi_ty = str(self.ui.roi_ty)
                self.params.roi_bx = str(self.ui.roi_bx)
                self.params.roi_by = str(self.ui.roi_by)
            # Do stuff with values

    def change_ffc_method(self):
        self.params.ffc_method = str(self.ui.ffc_method.currentText()).lower()
        is_default = self.params.ffc_method == 'default'
        is_background = self.params.ffc_method == 'background'
        is_roi = self.params.ffc_method == 'roi'

        for w in (self.ui.roi_tx_label, self.ui.roi_ty_label, 
                  self.ui.roi_bx_label, self.ui.roi_by_label,  
                  self.ui.roi_tx, self.ui.roi_ty, 
                  self.ui.roi_bx, self.ui.roi_by):
            w.setVisible(is_roi)

        if is_roi:
            roi_dlg = RoiDialog()
            roi_dlg.exec_()
            if roi_dlg.result() == 0:
                roi_tx, roi_ty, roi_bx, roi_by = roi_dlg.on_roi_save_clicked()
                self.ui.roi_tx.setText(str(roi_tx))
                self.ui.roi_ty.setText(str(roi_ty))
                self.ui.roi_bx.setText(str(roi_bx))
                self.ui.roi_by.setText(str(roi_by))
                self.params.roi_tx = roi_tx
                self.params.roi_ty = roi_ty
                self.params.roi_bx = roi_bx
                self.params.roi_by = roi_by

        for w in (self.ui.cut_off_label, self.ui.cut_off):
            w.setVisible(is_default)

        for w in (self.ui.air_label, self.ui.air):
            w.setVisible(is_background)

    def change_phase_method(self):
        self.params.phase_method = str(self.ui.phase_method.currentText()).lower()
        is_none = self.params.phase_method == 'none'
        is_paganin = self.params.phase_method == 'paganin'

        for w in (self.ui.pixel_size_label, self.ui.pixel_size,  
                  self.ui.distance_label, self.ui.distance, 
                  self.ui.energy_label, self.ui.energy, 
                  self.ui.alpha_label, self.ui.alpha):
            w.setVisible(is_paganin)
      
    def change_rec_method(self):
        self.params.reconstruction_algorithm = str(self.ui.rec_method.currentText()).lower()
        is_gridrec = self.params.reconstruction_algorithm == 'gridrec'
        is_fbp = self.params.reconstruction_algorithm == 'fbp'
        is_mlem = self.params.reconstruction_algorithm == 'mlem'
        is_sirt = self.params.reconstruction_algorithm == 'sirt'
        is_sirtfbp = self.params.reconstruction_algorithm == 'sirtfbp'

        for w in (self.ui.iterations, self.ui.iterations_label):
            w.setVisible(is_mlem or is_sirt or is_sirtfbp)
        if (is_mlem or is_sirt or is_sirtfbp) :
            self.ui.iterations.setValue(self.params.num_iterations)

        for w in (self.ui.filter_box, self.ui.filter_label):
            w.setVisible(is_gridrec or is_fbp)

    def change_binning(self):
        self.params.binning = str(self.ui.binning_box.currentIndex())
        fname = str(self.ui.dx_file_name_line.text())
        try:
            data_size = util.get_dx_dims(str(fname), 'data')
            dsize = (data_size[1]/np.power(2, float(self.params.binning))).astype(np.int)
        except:
            dsize = 1024
        self.ui.slice_start.setRange(0, dsize)
        self.ui.slice_start.setValue(dsize/2)
        self.ui.slice_end.setRange(dsize/2+1, dsize)
        self.ui.slice_end.setValue(dsize/2+1)

    def change_filter(self):
        self.params.filter = str(self.ui.filter_box.currentText()).lower()

    def change_center_spin(self):
        if self.ui.center_spin.value() == 0:
            self.params.center = None
        else:
            self.params.center = self.ui.center_spin.value()

    def closeEvent(self, event):
        try:
            self.params.ffc_method = 'default'
            sections = config.TOMO_PARAMS + ('gui', 'retrieve-phase')
            config.write('ufot.conf', args=self.params, sections=sections)
            config.write(str(self.params.input_path)+'.conf', args=self.params, sections=sections)
        except IOError as e:
            self.gui_warn(str(e))
            self.on_save_as()

    def on_save_as(self):
        if os.path.exists(self.params.input_file_path):
            config_file = str(self.params.input_file_path + "/ufot.conf")
        else:
            config_file = str(os.getenv('HOME') + "ufot.conf")
        save_config = QtGui.QFileDialog.getSaveFileName(self, 'Save as ...', config_file)
        if save_config:
            sections = config.TOMO_PARAMS + ('gui',)
            config.write(save_config, args=self.params, sections=sections)

    def on_open_from(self):
        config_file = QtGui.QFileDialog.getOpenFileName(self, 'Open ...', self.params.input_file_path)
        parser = ArgumentParser()
        params = config.Params(sections=config.TOMO_PARAMS + ('gui',))
        parser = params.add_arguments(parser)
        self.params = parser.parse_known_args(config.config_to_list(config_name=config_file))[0]
        self.get_values_from_params()

    def on_about(self):
        message = "GUI is part of tomopy {}.".format(__version__)
        QtGui.QMessageBox.about(self, "About tomopy", message)

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
        self.ui.data_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_start_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_end_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_end.setVisible(self.ui.manual_box.isChecked())

        self.ui.data_dark_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_dark_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_dark_end.setVisible(self.ui.manual_box.isChecked())
 
        self.ui.data_white_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_white_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.data_white_end.setVisible(self.ui.manual_box.isChecked())
 
        self.ui.theta_label.setVisible(self.ui.manual_box.isChecked())
        self.ui.theta_start.setVisible(self.ui.manual_box.isChecked())
        self.ui.theta_end.setVisible(self.ui.manual_box.isChecked())
        self.ui.theta_step.setVisible(self.ui.manual_box.isChecked())
        self.ui.theta_step_label.setVisible(self.ui.manual_box.isChecked())
        
    def on_reconstruct(self):
        with spinning_cursor():
            self.ui.centralWidget.setEnabled(False)
            self.repaint()
            self.app.processEvents()

            input_images = check_filename(str(self.params.input_file_path))
            if not input_images:
                self.gui_warn("No data found in {}".format(str(self.ui.input_path_line.text())))
                self.ui.centralWidget.setEnabled(True)
                return

            is_mlem = self.params.reconstruction_algorithm == 'mlem'
            is_sirt = self.params.reconstruction_algorithm == 'sirt'
            is_sirtfbp = self.params.reconstruction_algorithm == 'sirtfbp'
            if (is_mlem or is_sirt or is_sirtfbp) :
                self.params.num_iterations = self.ui.iterations.value()
            
            data_size = util.get_dx_dims(str(self.ui.input_path_line.text()), 'data')

            try:
                 reco.tomo(self.params)
            except Exception as e:
                self.gui_warn(str(e))

            self.ui.centralWidget.setEnabled(True)

    def gui_warn(self, message):
        QtGui.QMessageBox.warning(self, "Warning", message)

def main(params):
    app = QtGui.QApplication(sys.argv)
    ApplicationWindow(app, params)
    sys.exit(app.exec_())
