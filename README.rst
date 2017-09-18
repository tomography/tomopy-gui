ufot
####

**ufot** is `tofu <https://github.com/ufo-kit/tofu>`_ for `tomopy <https://github.com/tomopy/tomopy>`_

an open-source Python package for tomographic data 
processing and image reconstruction.


About
=====

This repository contains a customized version of `tofu <https://github.com/ufo-kit/tofu>`_'s data processing scripts to be used with the `tomopy <https://github.com/tomopy/tomopy>`_ framework. 

Installation
============

Run

    python setup.py install

in a prepared virtualenv or as root for system-wide installation.

.. warning:: If your python installation is in a location different from #!/usr/bin/env python please edit the first line of the bin/ufot file to match yours.

Dependencies
============

please install the following packages:

- conda install -c dgursoy tomopy
- conda install pyqt=4

Usage
=====

Reconstruction
--------------

To do a tomographic reconstruction you simply call

    $ ufot rec --last-file $PATH_TO_DATA_EXCHANGE_FILE

from the command line. To get correct results, you may need to append
options such as `--axis/-a` to set the rotation axis position. 

    $ tofu tomo --axis=1024.0 --last-file /local/data.h5

You can get a help for all options by running

    $ ufot rec -h

You can also load reconstruction parameters from a configuration file called
`ufot.conf`. You may create a template with

    $ ufot init

GUI
---

Besides scripted reconstructions, one can also run a standalone GUI for both
reconstruction and quick assessment of the reconstructed data via

    $ ufot gui
