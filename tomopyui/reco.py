import os
import logging
import glob
import tempfile
import sys
import numpy as np
import tomopy
import dxchange

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
    print("XXXXXXXXXXXXXXXXXXXXXXXXX")
    print("slice:", str(params.slice_start))
    print("slice:", str(params.slice_end))
    print("normalize", str(params.ffc_correction))
    print("binning", str(params.binning))
    print("rot axis", str(params.axis))
    print("rec output dir", str(params.output_dir))
    print("raw data file dir", str(params.last_file))
    print("rec method", str(params.method))
    print("rec iteration", str(params.num_iterations))
    print("full reconstruction", str(params.full_reconstruction))

    print("XXXXXXXXXXXXXXXXXXXXXXXXX")
    print("OK")
    fname = str(params.last_file)

    # Read raw data.
    if  (params.full_reconstruction == False) : 
        start = params.slice_start
        end = start + 1
    print("START-END", start, end)

    proj, flat, dark, theta = dxchange.read_aps_32id(fname, sino=(start, end))

    print(proj.shape)
    print(flat.shape)
    print(dark.shape)

    # Flat-field correction of raw data.
    data = tomopy.normalize(proj, flat, dark)
    print("NORMALIZED")

    data = tomopy.downsample(data, level=int(params.binning))
    print("BINNING: ", params.binning)

    # remove stripes    
    #data = tomopy.prep.stripe.remove_stripe_fw(data,level=5,wname='sym16',sigma=1,pad=True)

    # phase retrieval
    #data = tomopy.prep.phase.retrieve_phase(data,pixel_size=detector_pixel_size_x,dist=sample_detector_distance,energy=monochromator_energy,alpha=8e-3,pad=True)

    # Set rotation center.
    rot_center = params.axis/np.power(2, float(params.binning))
    print ("ROT:", rot_center)

    data = tomopy.minus_log(data)
    print("MINUS LOG")

    # Reconstruct object using Gridrec algorithm.
    rec = tomopy.recon(data, theta, center=rot_center, algorithm='gridrec')
    print("REC:", rec.shape)

    # Mask each reconstructed slice with a circle.
    #rec = tomopy.circ_mask(rec, axis=0, ratio=0.95)

    # Write data as stack of TIFs.
    dxchange.write_tiff_stack(rec, fname='recon_dir/aps_nik', overwrite=True)

   #width, height = get_projection_reader(params)

    #axis = params.axis or width / 2.0

    #if params.resize:
    #    width /= params.resize
    #    height /= params.resize
    #    axis /= params.resize

    #LOG.debug("Input dimensions: {}x{} pixels".format(width, height))
    if  (params.full_reconstruction == False) :
        return rec

