import iris
import requests
import tempfile
import os
import tempfile
import json
import time

import sys
sys.path.append(".")
import imageproc
from config import analysis_config as conf

"""
newtorking.py contains all the function that deal with
posting to the data service. Called by serveupimage.py

"""

def getPostDict(cube, img_data, job, mime_type="image/png"):
    """
    Converts relevant cube metadata into a dictionary of metadata which is compatable
    with the data service.

    """
    with iris.FUTURE.context(cell_datetime_objects=True):
        lonc, = cube.coords(dim_coords=True, axis="X")
        latc, = cube.coords(dim_coords=True, axis="Y")
        latlons = [{"lat": str(latc.points.min()), "lng": str(lonc.points.min())},
                   {"lat": str(latc.points.max()), "lng": str(lonc.points.min())},
                   {"lat": str(latc.points.max()), "lng": str(lonc.points.max())},
                   {"lat": str(latc.points.min()), "lng": str(lonc.points.max())}]

        payload = {'forecast_reference_time': cube.coord("forecast_reference_time").cell(0).point.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                   'forecast_time' : cube.coord("time").cell(0).point.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                   'phenomenon' : cube.name(),
                   'mime_type' : mime_type,
                   'model' : job.model,
                   'processing_profile': job.profile_name,
                   'data_dimension_x': cube.shape[0],
                   'data_dimension_y': cube.shape[1], 
                   'data_dimension_z': cube.shape[2],
                   'resolution_y': img_data.shape[0], #not entirely sure which
                   'resolution_x': img_data.shape[1], #way round is which
                   'geographic_region': json.dumps(latlons)
                  }

    return payload


def postImage(img_data, data, job):
    """
    Sends the data to the data service via a post

    Args:
        * img_data(np.Array): Numpy array of i x j x channels
        * data (cube): The cube metadata is used for the post
            metadata
        * job (Job): job
    """
    tempfilep = os.path.join(tempfile.gettempdir(), "temp.png")

    with open(tempfilep, "wb") as img:
        imageproc.writePng(img_data, img,
                  nchannels=3, alpha=False)
    payload = getPostDict(data, img_data, job)

    print "Attempting to post image"
    try:
        with open(tempfilep, "rb") as img:
            # for attempt in range(100): # deals with connection errors etc
            r = requests.post(conf.img_data_server, data=payload, files={"data": img})
            time.sleep(2)
                # if r.status_code == 201:
                #     break
        if r.status_code != 201:
            raise IOError(r.status_code, r.text, "for messge", payload)  
        else:
            print "Headers: ", r.headers
            print "Status code: ", r.status_code  
    finally:
        os.remove(tempfilep)