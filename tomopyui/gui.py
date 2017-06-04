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

from argparse import ArgumentParser
import numpy as np
from contextlib import contextmanager
from PyQt4 import QtGui, QtCore, uic


LOG = logging.getLogger(__name__)


def set_last_dir(path, line_edit, last_dir):
    if os.path.exists(str(path)):
        line_edit.clear()
        line_edit.setText(path)
        last_dir = str(line_edit.text())

    return last_dir

class CallableHandler(logging.Handler):
    def __init__(self, func):
        logging.Handler.__init__(self)
        self.func = func

    def emit(self, record):
        self.func(self.format(record))


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

        self.axis_calibration = None
    
        #self.params.angle = 0

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
        self.ui.ffc_box.clicked.connect(self.ffc_box_clicked)

        self.ui.path_button_dx.clicked.connect(self.path_dx_clicked)
        self.ui.path_button_rec.clicked.connect(self.path_dx_clicked)

        self.ui.calibrate_dx_button.clicked.connect(self.calibrate_dx)
        self.ui.show_slices_button.clicked.connect(self.on_show_slices_clicked)
        self.ui.show_projection_button.clicked.connect(self.on_show_projection_clicked)
        self.ui.ffc_box.clicked.connect(self.on_ffc_box_clicked)

        #self.ui.path_line_0.textChanged.connect(lambda value: self.change_value('deg0', str(self.ui.path_line_0.text())))
        #self.ui.angle_step.valueChanged.connect(self.change_angle_step)
        self.ui.open_action.triggered.connect(self.on_open_from)
        self.ui.close_action.triggered.connect(self.close)
        self.ui.about_action.triggered.connect(self.on_about)

        self.ui.y_step.valueChanged.connect(lambda value: self.change_value('y_step', value))

        # set up log handler
        log_handler = CallableHandler(self.output_log)
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
        root_logger = logging.getLogger('')
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers = [log_handler]

        #self.ui.open_action.triggered.connect(self.on_open_from)
        self.ui.close_action.triggered.connect(self.close)
        self.ui.about_action.triggered.connect(self.on_about)


    def slice_box_clicked(self):
        self.ui.y_step.setEnabled(self.ui.slice_box.isChecked())

    def ffc_box_clicked(self):
        self.ui.preprocessing_container.setEnabled(self.ui.ffc_box.isChecked())

    def output_log(self, record):
        self.ui.text_browser.append(record)

    def get_filename(self, caption, type_filter):
        return QtGui.QFileDialog.getOpenFileName(self, caption, self.last_dir, type_filter)

    def path_dx_clicked(self, checked):
        path = self.get_filename('Open DX file', 'Images (*.hdf *.h5)')

        data_size = util.read_dx_dims(str(path), 'data')
        data_dark_size = util.read_dx_dims(str(path), 'data_dark')
        data_white_size = util.read_dx_dims(str(path), 'data_white')
        self.ui.label_data_size.setText(str(data_size))
        self.ui.label_data_dark_size.setText(str(data_dark_size))
        self.ui.label_data_white_size.setText(str(data_white_size))

        self.ui.y_step.setValue(data_size[1]/2)
        self.ui.y_step.setRange(0, data_size[1])

        self.ui.path_line_dx.setText(path)
        self.ui.input_path_line.setText(path)
        self.on_show_projection_clicked()
        self.last_dir = path
        self.params.last_dir = set_last_dir(path, self.ui.path_line_dx, self.params.last_dir)

    def calibrate_dx(self):
        path = str(self.ui.path_line_dx.text())
        last_ind = util.read_dx_dims(str(path), 'theta')
        if (last_ind == None):
            last_ind = util.read_dx_dims(str(path), 'data')
    
        proj, flat, dark, theta = dx.read_aps_32id(path, proj=(0, 1))
        self.ui.angle_step.setValue((theta[1] - theta[0]).astype(np.float))

        first = proj[0,:,:].astype(np.float)
        proj, flat, dark, theta = dx.read_aps_32id(path, proj=(last_ind[0]-1, last_ind[0]))
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
        path = str(self.ui.path_line_dx.text())
        self.ui.slice_dock.setVisible(True)

        if not self.slice_viewer:
            self.slice_viewer = tomopyui.widgets.ImageViewer(path)
            self.slice_dock.setWidget(self.slice_viewer)
            self.ui.slice_dock.setVisible(True)
        else:
            self.slice_viewer.load_files(path)
    #def change_angle_step(self):
    #    if self.ui.angle_step.value() == 0:
    #        self.params.angle = None
    #    else:
    #        self.params.angle = self.ui.angle_step.value()

    def change_value(self, name, value):
        setattr(self.params, name, value)

    def on_ffc_box_clicked(self):
        checked = self.ui.ffc_box.isChecked()
        #self.ui.preprocessing_container.setVisible(checked)
        print("CHECKED")
        self.params.ffc_correction = checked

    def get_values_from_params(self):
        self.last_dir = self.params.last_dir

        self.ui.input_path_line.setText(self.params.sinograms or self.params.projections or '.')
        self.ui.angle_step.setValue(self.params.angle if self.params.angle else 0.0)
        self.ui.y_step.setValue(self.params.y_step if self.params.y_step else 1)

        if self.params.y_step > 0 :
            self.ui.slice_box.setChecked(True)
        else:
            self.ui.slice_box.setChecked(False)
        self.ui.on_slice_box_clicked()
        self.ui.minus_log_box.setChecked(self.params.minus_log)

    def closeEvent(self, event):
        try:
            sections = config.TOMO_PARAMS + ('gui',)
            config.write('reco.conf', args=self.params, sections=sections)
        except IOError as e:
            self.gui_warn(str(e))
            self.on_save_as()


    def on_open_from(self):
        config_file = QtGui.QFileDialog.getOpenFileName(self, 'Open ...', self.params.last_dir)
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
            config.write('tomopyui.conf', args=self.params, sections=sections)
        except IOError as e:
            self.gui_warn(str(e))
            self.on_save_as()

    def on_slice_box_clicked(self):
        self.ui.y_step.setEnabled(self.ui.slice_box.isChecked())
        if self.ui.slice_box.isChecked():
            self.params.y_step = self.ui.y_step.value()
        else:
            self.params.y_step = 1

def main(params):
    app = QtGui.QApplication(sys.argv)
    ApplicationWindow(app,params)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
    #main(params)
