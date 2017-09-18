import os
import logging
import glob
import tempfile
import sys
import numpy as np
import tomopy
import dxchange

LOG = logging.getLogger(__name__)

def tomo(params):
    print("XXXXXXXXXXXXXXXXXXXXXXXXX")
    print("slice:", str(params.slice_start))
    print("slice:", str(params.slice_end))
    #print("normalize", str(params.ffc_correction))
    print("binning", str(params.binning))
    print("rot axis", str(params.axis))
    print("rec output dir", str(params.output_dir))
    print("raw data file dir", str(params.last_file))
    print("rec method", str(params.method))
    print("rec filter", str(params.filter))
    print("rec iteration", str(params.num_iterations))
    print("full reconstruction", str(params.full_reconstruction))
    print("XXXXXXXXXXXXXXXXXXXXXXXXX")
    fname = str(params.last_file)

    start = params.slice_start
    end = params.slice_end

   # Read raw data.
    if  (params.full_reconstruction == False) : 
        end = start + 1
    
    print("START-END", start, end)

    proj, flat, dark, theta = dxchange.read_aps_32id(fname, sino=(start, end))
    LOG.info('Data successfully imported: %s', fname)
    print(proj.shape)
    print(flat.shape)
    print(dark.shape)

    # Flat-field correction of raw data.
    data = tomopy.normalize(proj, flat, dark)
    print("NORMALIZED")

    data = tomopy.downsample(data, level=int(params.binning))
    print("BINNING: ", params.binning)

    # remove stripes
    data = tomopy.remove_stripe_fw(data,level=5,wname='sym16',sigma=1,pad=True)
    print("REMOVE STRIPE")    

    # phase retrieval
    #data = tomopy.prep.phase.retrieve_phase(data,pixel_size=detector_pixel_size_x,dist=sample_detector_distance,energy=monochromator_energy,alpha=8e-3,pad=True)

    # Find rotation center
    #rot_center = tomopy.find_center(proj, theta, init=290, ind=0, tol=0.5)

    # Set rotation center.
    rot_center = params.axis/np.power(2, float(params.binning))
    print ("ROT:", rot_center)

    data = tomopy.minus_log(data)
    print("MINUS LOG")

    # Reconstruct object using Gridrec algorithm.
    if (str(params.method) == 'sirt'):
        print("SIRT")
        print("Iteration: ", params.num_iterations)
        rec = tomopy.recon(data, theta,  center=rot_center, algorithm='sirt', num_iter=params.num_iterations)
    else:
        print("gridrec")
        rec = tomopy.recon(data, theta, center=rot_center, algorithm='gridrec', filter_name=params.filter)

    print("REC DONE:", rec.shape)

    # Mask each reconstructed slice with a circle.
    rec = tomopy.circ_mask(rec, axis=0, ratio=0.95)

    
    if (params.dry_run == False):
         # Write data as stack of TIFs.
        fname = str(params.output_dir) + 'reco'
        dxchange.write_tiff_stack(rec, fname=fname, overwrite=True)
        print("REC SAVED:", fname)

    if  (params.full_reconstruction == False) :
        return rec

