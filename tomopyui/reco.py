import os
import logging
import glob
import tempfile
import sys
import numpy as np


LOG = logging.getLogger(__name__)

def get_task(name, **kwargs):
    task = pm.get_task(name)
    task.set_properties(**kwargs)
    return task


def get_dummy_reader(params):
    if params.width is None and params.height is None:
        raise RuntimeError("You have to specify --width and --height when generating data.")

    width, height = params.width, params.height
    reader = get_task('dummy-data', width=width, height=height, number=params.number or 1)
    return reader, width, height


def get_file_reader(params):
    reader = pm.get_task('read')
    set_node_props(reader, params)
    return reader


def get_projection_reader(params):
    reader = get_file_reader(params)
    setup_read_task(reader, params.projections, params)
    width, height = determine_shape(params, params.projections)
    return reader, width, height


def get_sinogram_reader(params):
    reader = get_file_reader(params)
    setup_read_task(reader, params.sinograms, params)
    image = read_image(get_first_filename(params.sinograms))

    if len(image.shape) > 2:
        # this is a probably a multi TIFF/raw
        width, height = image.shape[2], image.shape[1]
    else:
        # this is a directory of sinograms
        width, height = image.shape[1], image.shape[0]

    return reader, width, height


def tomo(params):
    # Create reader and writer
    print("slice:", str(params.slice_number))
    print("normalize", str(params.ffc_correction))
    print("binning", str(params.binning))
    print("rot axis", str(params.axis))
    print("rec output dir", str(params.output_dir))
    print("raw data file dir", str(params.last_file))
    print("rec method", str(params.method))
    print("rec iteration", str(params.num_iterations))

    #width, height = get_projection_reader(params)

    #axis = params.axis or width / 2.0

    #if params.resize:
    #    width /= params.resize
    #    height /= params.resize
    #    axis /= params.resize

    #LOG.debug("Input dimensions: {}x{} pixels".format(width, height))

