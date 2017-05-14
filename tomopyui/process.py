import numpy as np


def guess_axis(first_projection, last_projection):
    """
    Compute the tomographic rotation axis based on cross-correlation technique.
    *first_projection* is the projection at 0 deg, *last_projection* is the
    projection at 180 deg.
    """
    from scipy.signal import fftconvolve
    width = first_projection.shape[1]
    first_projection = first_projection - first_projection.mean()
    last_projection = last_projection - last_projection.mean()

    # The rotation by 180 deg flips the image horizontally, in order
    # to do cross-correlation by convolution we must also flip it
    # vertically, so the image is transposed and we can apply convolution
    # which will act as cross-correlation
    convolved = fftconvolve(first_projection, last_projection[::-1, :], mode='same')
    center = np.unravel_index(convolved.argmax(), convolved.shape)[1]

    return (width / 2.0 + center) / 2


class AxisCalibration(object):

    def __init__(self, first, last):
        self.axis = guess_axis(first, last)
        self.height, self.width = first.shape

    @property
    def position(self):
        return self.width / 2.0 + self.width - self.axis * 2.0

    @position.setter
    def position(self, p):
        self.axis = (self.width / 2.0 + self.width - p) / 2

