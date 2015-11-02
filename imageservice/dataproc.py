import iris
import numpy as np
import png

import sys
sys.path.append(".")
from config import analysis_config as conf

"""
dataproc.py contains all functions which process the data
including retratification, regridding, rescaling etc.
Called by serveupimage.py

"""

def sanitizeAlt(c):
    """
    Takes a cube and sanitizes the altitude coordinates,
    including removing negative values or NaNs, and adding
    a log_altitude coordinate, which will be used for the
    restratifying.

    """
    sanitized_alt = c.coord("altitude").points
    sanitized_alt[np.logical_not(np.isfinite(sanitized_alt))] = conf.sea_level
    sanitized_alt[sanitized_alt < conf.sea_level] = conf.sea_level
    logaltcoord = iris.coords.AuxCoord(np.log(sanitized_alt), long_name="log_altitude")
    altcoorddims = c.coord_dims("altitude")
    c.add_aux_coord(logaltcoord, altcoorddims)

    return c


def restratifyAltLevels(c, nalt):
    """
    Restratifies the cube into nalt levels linearly spaced
    between the original min and max alt

    """
    log_levs = np.linspace(c.coord("log_altitude").points.min(),
                              c.coord("log_altitude").points.max(),
                              nalt)
    alt_axis, = c.coord_dims("model_level_number")
    restratified_data = c.data
    
    newcoords = list(c.dim_coords)
    newcoords[alt_axis] = iris.coords.DimCoord(np.exp(log_levs), long_name="altitude", units="m")
    dim_coords_and_dims = tuple([(crd, i) for i, crd in enumerate(newcoords)])
    # restratified_data_cube = iris.cube.Cube(data=np.ma.masked_invalid(restratified_data),
    #                                         dim_coords_and_dims=dim_coords_and_dims)
    restratified_data = np.ma.fix_invalid(restratified_data, fill_value=0.0)
    restratified_data.mask = False
    restratified_data_cube = iris.cube.Cube(data=restratified_data,
                                            dim_coords_and_dims=dim_coords_and_dims)
    restratified_data_cube.add_aux_coord(c.coord("forecast_reference_time"))
    restratified_data_cube.add_aux_coord(c.coord("time"))
    restratified_data_cube.metadata = c.metadata

    restratified_data_cube.coord("grid_latitude").guess_bounds()
    restratified_data_cube.coord("grid_longitude").guess_bounds()
    
    
    return restratified_data_cube


def horizRegrid(c, nlat, nlon, extent):
    """
    Takes a cube (in any projection) and regrids it onto a
    recatilinear nlat x nlon grid spaced linearly between

    """
    u = iris.unit.Unit("degrees")
    cs = iris.coord_systems.GeogCS(iris.fileformats.pp.EARTH_RADIUS)

    lonc = iris.coords.DimCoord(np.linspace(extent[0], extent[1], nlon),
                                    standard_name="longitude",
                                    units=u,
                                    coord_system=cs)
    lonc.guess_bounds()

    latc = iris.coords.DimCoord(np.linspace(extent[2], extent[3], nlat),
                                    standard_name="latitude",
                                    units=u,
                                    coord_system=cs)
    latc.guess_bounds()

    grid_cube = iris.cube.Cube(np.empty([nlat, nlon]))
    grid_cube.add_dim_coord(latc, 0)
    grid_cube.add_dim_coord(lonc, 1)
    
    rg_c = c.regrid(grid_cube, iris.analysis.Linear(extrapolation_mode='mask'))
    
    return rg_c


def trimOutsideDomain(c):
    """
    When we regrid from polar stereographic to rectalinear, the resultant
    shape is non-orthogonal, and is surrounded by masked values. This
    function trims the cube to be an orthogonal region of real data.

    Its a little bespoke and make be unscescesarry if we can swith
    to an AreaWeighted function.

    """
    # assess the top layer as its likely to be free
    # of values that are maksed for terrain.
    altdim, = c.coord_dims("altitude")
    slices = [slice(None)]*c.ndim
    slices[altdim] = -1
    lonmean = np.mean(c.data[slices].mask, axis=1)
    glonmean = np.gradient(lonmean)
    uselat = (lonmean < 1.0) & (np.fabs(glonmean) < 0.004)

    latmean = np.mean(c.data[slices].mask, axis=0)
    glatmean = np.gradient(latmean)
    uselon = (latmean < 1.0) & (np.fabs(glatmean) < 0.004)

    return c[uselat, uselon, :]


def regridData(c, nlat, nlon, nalt, extent):
    """
    Regrids a cube onto a nalt x nlat x nlon recatlinear cube
    """ 
    #c = restratifyAltLevels(c, nalt)
    c = horizRegrid(c, nlat, nlon, extent)
    # remove the to latyer which seems to artificially masked from regridding
    # altdim, = c.coord_dims("altitude")
    # slices = [slice(None)]*c.ndim
    # slices[altdim] = slice(0, -1)
    # c = trimOutsideDomain(c[tuple(slices)])

    return c


def procDataCube(c):
    """
    Processes data such that it is suitable for visualisation.

    Takes a cube of data, and returns a cube of data values *BETWEEN 0 and MAX_VAL (e.g. 255)*
    Other adjustments should be done here, like adjusting range and saturation.
    E.g. for a 15degC potential temperature surface, all values <15 = 0 and >15=255

    NB that all masked values will also be converted to MAX_VAL.

    """

    c.data *= conf.max_val/c.data.max()
    c.data = np.ma.fix_invalid(c.data, fill_value=conf.max_val)
    c.data = np.ma.filled(c.data, fill_value=conf.max_val)

    return c


if __name__ == "__main__":
    pass