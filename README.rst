ToPy
####

**ToPy** is `tofu <https://github.com/ufo-kit/tofu>`_ for `tomopy <https://github.com/tomopy/tomopy>`_

an open-source Python package for tomographic data 
processing and image reconstruction.


## About

This repository contains a customized version of `tofu <https://github.com/ufo-kit/tofu>`_'s data processing scripts to be used with the `tomopy <https://github.com/tomopy/tomopy>`_ framework. 

## Installation

Run

    python setup.py install

in a prepared virtualenv or as root for system-wide installation.

## Usage

### Reconstruction

To do a tomographic reconstruction you simply call

    $ topy rec --last-file $PATH_TO_DATA_EXCHANGE_FILE

from the command line. To get correct results, you may need to append
options such as `--axis/-a` to set the rotation axis position. 

    $ tofu tomo --axis=1024.0 --last-file /local/data.h5

You can get a help for all options by running

    $ topy rec -h

You can also load reconstruction parameters from a configuration file called
`topy.conf`. You may create a template with

    $ topy init


Besides scripted reconstructions, one can also run a standalone GUI for both
reconstruction and quick assessment of the reconstructed data via

    $ topy gui

