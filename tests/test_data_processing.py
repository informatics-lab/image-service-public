import unittest
import argparse as ap
import subprocess as sp
from iris.tests import IrisTest
import imageservice
from imageservice import serveupimage
from imageservice import networking
from imageservice import imageproc
from imageservice import packer
from imageservice import dataproc
from imageservice import config as conf
import numpy as np
import iris
from numpy.testing import assert_array_equal

import os
import shutil
import time
fileDir = os.path.dirname(__file__)

class UnitTests(unittest.TestCase):
    def setUp(self):
        self.profile = ap.Namespace(**conf.profiles["default"])
        self.data = serveupimage.loadCube(os.path.join(fileDir, "data", "test_input.nc"),
                                          conf.topog_file,
                                          self.profile.data_constraint)
        self.proced_data = iris.load_cube(os.path.join(fileDir, "data", "proced_data.nc"))
        self.tiled_data = iris.load_cube(os.path.join(fileDir, "data", "tiled_data.nc")).data

    def test_dataproc(self):
        # tidy up any problems arising from the on-the-fly altitude calc
        san_data = dataproc.sanitizeAlt(self.data)
        # regrid and restratify the data
        rg_data = dataproc.regridData(san_data,
                                      regrid_shape=self.profile.regrid_shape,
                                      extent=self.profile.extent)
        # do any further processing (saturation etc) and convert to 8 bit uint
        proced_data = dataproc.procDataCube(rg_data)

        self.assertTrue(proced_data.data.max() <= conf.max_val)
        assert_array_equal(self.proced_data.data, proced_data.data)

    def test_packer(self):
        self.assertEquals(packer.find_i_j(10, 20, 15, nchannels=3), [16, 128])

    def test_imageproc(self):
        data_tiled = imageproc.tileArray(self.proced_data.data)
        assert_array_equal(self.tiled_data, data_tiled)

    def test_networking(self):
        networking.postImage(self.tiled_data, self.data)


class IntegrationTest(unittest.TestCase):

    def test_integration(self):
        inputfile = os.path.join(fileDir, "data", "test_input.nc")
        sp.call(["imageservice/serveupimage.py",
                          "--profile=default",
                          inputfile])


def resetTestData(new_data_array, test_data_file):
    _ = iris.cube.Cube(new_data_array)
    iris.save(_, test_data_file)


if __name__ == '__main__':
    unittest.main()
