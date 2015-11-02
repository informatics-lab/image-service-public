#!/usr/bin/env python

import argparse as ap
import iris
import iris.util
import io
import numpy as np
import os
import tempfile
import boto.sqs
import json

import sys
sys.path.append(".")

import dataproc
import imageproc
import networking

sys.path.append(".")
from config import analysis_config as conf

iris.FUTURE.cell_datetime_objects = True


""" 
serveupimage.py is the top level module for processing
Thredds server data and positing it as an image on the
data service. This includes: 

1. Retrieving data from the Thredds server
2. Processing the data of each time slice
3. Converting this processed data to a tiled image
4. Posting the tiled image to the data server

"""

def procDataToImage(data,
                    image_dest,
                    profile):
    """
    Main processing function. Processes an model_level_number, lat, lon cube,
    including all regridding and restratification of data,
    calculates shadows, and then ultimately posts a tiled
    image to the data service.

    Args:
        * data (iris cube): lat, lon, model_level_number cube 
        * image_dest (str): URL to the data service image destination
        * regrid_shape (tuple): lon, lat, alt dimensions to regrid to

    """

    # # tidy up any problems arising from the on-the-fly altitude calc
    # print "Sanitizing data after altitude restratification"
    # san_data = dataproc.sanitizeAlt(data) #TESTING ONLY
    # # regrid and restratify the data
    print "Regridding data to " + str(data.shape)
    rg_data = dataproc.regridData(data,
                                len(data.coords(axis="Y")[0].points),
                                len(data.coords(axis="X")[0].points),
                                len(data.coords(axis="Z")[0].points),
                                extent=profile.extent)
    # # do any further processing (saturation etc) and convert to 8 bit uints
    # try:
    #     print "Applying custom data processing from profile"
    #     rg_data = profile.proc_fn(rg_data)
    # except AttributeError:
    #     pass


    print "Applying standard data processing (e.g. 8 bit scaling)"
    proced_data = dataproc.procDataCube(rg_data)

    print "Tiling data"
    data_tiled = imageproc.tileArray(proced_data.data)

    return data_tiled, proced_data


def loadCube(data_file, topog_file, **kwargs):
    """
    Loads cube and reorders axes into appropriate structure

    The Iris altitude conversion only works on pp files
    at load time, so we need to pull the nc file from
    OpenDAP, save a local temporary pp file and then
    load in with the topography.

    """
    opendapcube = iris.load_cube(data_file, **kwargs)
    tempfilep = os.path.join(tempfile.gettempdir(), "temporary.pp")
    iris.save(opendapcube, tempfilep)
    data, topography = iris.load([tempfilep, topog_file])

    if "altitude" not in [_.name() for _ in data.derived_coords]:
        # raise IOError("Derived altitude coord not present - probelm with topography?")
        print "Derived altitude coord not present - probelm with topography?"

    xdim, = data.coord_dims(data.coords(dim_coords=True, axis="X")[0])
    ydim, = data.coord_dims(data.coords(dim_coords=True, axis="Y")[0])
    zdim, = data.coord_dims(data.coords(dim_coords=True, axis="Z")[0])
    try: 
        tdim, = data.coord_dims(data.coords(dim_coords=True, axis="T")[0])
        data.transpose([tdim, xdim, ydim, zdim])
    except IndexError:
        data.transpose([xdim, ydim, zdim])

    return data


class NoJobsError(Exception):
    def __init__(self, value=""):
        self.value = value
    def __str__(self):
        return repr(self.value)


class Job(object):
    def __init__(self, message, time_crd_name="time"):
        body = json.loads(message.get_body())
        self.data_file = body["data_file"]
        self.profile_name = body["profile_name"]
        self.time_step = body["time_step"]
        self.frame = body["frame"]
        self.open_dap = body["open_dap"]
        self.variable = body["variable"]
        self.model = body["model"]
        self.nframes = body["nframes"]
        self.time_constraint = iris.Constraint(coord_values={time_crd_name:
                                            lambda t: t.point.isoformat() == self.time_step})
        self.message = message

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)


def getJob(queue, visibility_timeout=5*60):
    messages = queue.get_messages(1, visibility_timeout=visibility_timeout)
    try:
        message = messages[0]
    except IndexError:
        raise NoJobsError()

    job = Job(message)
    
    return job


def postImgReady(msg, queue):
    print "Adding " + str(msg) + " to the image ready queue"
    m = boto.sqs.message.Message()
    m.set_body(json.dumps(str(msg)))
    queue.write(m)


def getQueue(queue_name):
    conn = boto.sqs.connect_to_region(os.getenv("AWS_REGION"),
                                      aws_access_key_id=os.getenv("AWS_KEY"),
                                      aws_secret_access_key=os.getenv("AWS_SECRET_KEY"))
    queue = conn.get_queue(queue_name)
    return queue


if __name__ == "__main__":
    image_ready_queue = getQueue("image_ready_queue")
    image_service_queue = getQueue("image_service_queue")

    job = getJob(image_service_queue)
    print "Picked up " + str(job)

    profile = ap.Namespace(**conf.profiles[job.profile_name]) # get settings for this type of analysis

    print "Loading data into Iris"
    print "job: ", job
    print "conf: ", conf
    print "profile: ", profile 
    data = loadCube(os.path.join(os.getenv("DATA_DIR"), job.data_file), conf.topog_file,
                    constraint=profile.data_constraint&job.time_constraint,
                    callback=profile.load_call_back)
    print "Loaded cube ", data
    img_array, proced_data = procDataToImage(data,
                                             conf.img_data_server,
                                             profile)

    post_object = networking.postImage(img_array, proced_data, job)

    postImgReady(job, image_ready_queue)
    print "Image " + str(job) + " posted successfully. Exiting..."
    
    image_service_queue.delete_message(job.message)
    sys.exit()