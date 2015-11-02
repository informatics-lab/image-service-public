import numpy as np
import png

import sys
sys.path.append(".")
import packer

"""
imageproc.py is the top level program called by the imageservice.py. It contains
functionality dealing with the image. Called by serveupimage.py

"""
    

def tileArray(a, nchannels=3, padxy=True):
    """
    Flattens an x,y,z 3D array into an array of x,y tiles
    
    Tiling order is column, followed by row, followed by channel
    
    Note that png textures coordinates increase top left to
    bottom right so we also need to take this into account.
    
    Args:
        * a (numpy array): a 3d numpy array of data
        * nchannels(int)L is either 1 (Grayscale), 3 (RGB) or 4 (RGBA)
        
    This could be made more efficient using stride tricks
    
    """

    maxx, maxy = packer.find_i_j(*a.shape, nchannels=nchannels)
    maxz = nchannels

    if type(a) is not np.ndarray:
        raise ValueError("a must be a np.Array, not a %s" % type(a))
    
    if padxy:
        padded_a = np.zeros([a.shape[0]+2, a.shape[1]+2, a.shape[2]])
        padded_a[1:-1, 1:-1, :] = a
    else:
        padded_a = a
    tiled_array = np.zeros([maxx, maxy, maxz])
    datax, datay, dataz = padded_a.shape
    maxitiles = int(maxx/datax)
    maxjtiles = int(maxy/datay)
    tilesperlayer = maxitiles * maxjtiles

    for zslice in range(dataz):
        ztile = np.floor(zslice/tilesperlayer)
        ytile = np.floor((zslice - (ztile * tilesperlayer)) / maxitiles)
        xtile = np.mod(zslice - (ztile * tilesperlayer), maxitiles)
        
        try:
            tiled_array[xtile*datax:(xtile+1)*datax,
                     ytile*datay:(ytile+1)*datay,
                     ztile] = padded_a[:, :, zslice]
        except IndexError:
            print "Output array saturated at slice", zslice
            break

    # swap from row major to column (or vice versa, not sure which way round this is!)
    tiled_array = tiled_array.transpose([1, 0, 2])

    is_pot = lambda n: ((n & (n - 1)) == 0) and n != 0
    if (not is_pot(tiled_array.shape[0]) or not is_pot(tiled_array.shape[1])):
        raise ValueError("Dimensions for a texture must be power of two")

    # revese first axis to be compatible with textures which read from top left
    return tiled_array[::-1, ...]

    
def writePng(array, f, nchannels=3, alpha="RGB"):
    """
    Writes a tiled array to a png image

    args:
        * array: x, y, rgb(a) array
        * f: output filelike object

    """
    print "Writing image"
    height, width = array.shape[:2]
    
    png_writer = png.Writer(height=height, width=width, bitdepth=8, alpha=alpha, colormap=True)
    flat_array = array.reshape(-1, width*nchannels)
    png_writer.write(f, flat_array)