from __future__ import division

from math import trunc, log, ceil

"""
packer.py calculates the optimum dimension of an image for tilings 
a three dimensional data array. Assumed image dimensions must 
be square power of two numbers.

"""

def find_i_j(x, y, z, nchannels=3, maxdimsize=4096):
	"""
	finds the combination of i and j which minimizes the number of wasted
	pixels for input images of dimensions x and y with number of images z

	"""
	z = ceil(z/nchannels) # take account having different layers of tiles

	if x*y*z > maxdimsize**2:
		raise ValueError("Tiled array range not big enough")

	max_n = int(ceil(log(maxdimsize, 2))) # n value required if max images in i direction
	max_m = int(ceil(log(maxdimsize, 2))) # m value required if max images in j direction

	solutions = [] # hold n, m and the number of wasted pixels for a solution
	sol_num = 0

	for n in range(1, max_n + 1):
		for m in range(1, max_m + 1):
			if(trunc(2**n / x) * trunc(2**m / y) >= z):
				# determines if a tile of with dimesions of n and m can contain
				# all the images

				sol_info = []
				sol_info.append(n)
				sol_info.append(m)
				sol_info.append(waste_det(x, y, z, n, m))

				solutions.append(sol_info)

				sol_num += 1

	sol_total = sol_num # records total number of solutions

	opt = find_waste_min(sol_total, solutions) # gets properties of optimal solution

	i = 2**opt[1]
	j = 2**opt[2]

	tile_dim = [i, j]

	return tile_dim


def find_waste_min(sol_total, solutions):
	"""
	finds solution with the lowest number of wasted pixels
	"""

	waste_min = solutions[0][2] + 1

	for sol_num in range(0, sol_total): # finds solution with lowest waste
		if(waste_min > solutions[sol_num][2]):
			opt = []

			waste_min = solutions[sol_num][2]
			n = solutions[sol_num][0]
			m = solutions[sol_num][1]

			opt.append(waste_min)
			opt.append(n)
			opt.append(m)

	return opt


def waste_det(x, y, z, n, m):
	"""
	determines the number of dead pixels for given image properties (x, y, z)
	and tile properties (n, m)
	"""
	dead_pixels = 2**(n+m) - x * y * z
	return dead_pixels
