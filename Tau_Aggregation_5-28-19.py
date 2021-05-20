# @ File (label="Input directory", style="directory") inputdir 
# @ File (label="Output directory", style="directory") outputdir 
# @ Integer (label="Channel no", value=2) ch_no

from ij import IJ, ImagePlus
from ij import WindowManager
from ij.plugin import RGBStackMerge
from loci.plugins import BF 
from loci.plugins.in import ImporterOptions
import os
from os import path

def analyze(image, outdir, index, size=10000):
	"""Opens a file and creates masks."""
	masks = []
	imagetitle = image.getTitle().split(".")[0]

	# segmentation
	IJ.setAutoThreshold(image, "Default dark");
	IJ.run(image, "Options...", "iterations=1 count=1 do=Nothing");
	#IJ.run(mask, "Convert to Mask", "");
	IJ.run(image, "Analyze Particles...", "size=0-"+str(size)+" show=Masks summarize display");
	masks.append(IJ.getImage())
	IJ.run(image, "Analyze Particles...", "size="+str(size)+"-infinity show=Masks summarize display");
	masks.append(IJ.getImage())
	
	# create multi-color merged mask
	mergedmask = RGBStackMerge.mergeChannels(masks, False)
	for m in masks:
	    m.close()
	mergedmask.setTitle(imagetitle + "-"+str(index)+"-mask.tif")
	outputfile = path.join(outdir, mergedmask.getTitle())
	IJ.saveAs(mergedmask, "TIFF", outputfile)

	 
# Main code
inputdir = str(inputdir) # convert from File object to String
outputdir = str(outputdir) # convert from File object to String
if not path.isdir(inputdir):
    print inputdir, " does not exist or is not a directory."
else:
	size = 10000
	imp_options = ImporterOptions()
	imp_options.setOpenAllSeries(True)
	imp_options.setConcatenate(True)
	if not path.isdir(outputdir):
	    # create output directory if it does not exist
		os.makedirs(outputdir)
	filenames = os.listdir(inputdir) # get list of files to process
	imagefiles = [f for f in filenames if f.split(".")[-1] in ['tif','tiff','nd2']]
	# close existing Summary window

	rtframe = WindowManager.getFrame("Summary")
	if rtframe is not None:
		rtframe.close()
	
	for img_file in imagefiles:
	    # execute the following block for each file
		fullpath = path.join(inputdir, img_file)
		imp_options.setId(fullpath)
		image_series = BF.openImagePlus(imp_options)
		print image_series[0].getTitle(), image_series[0].getNChannels(), image_series[0].getNSlices(), image_series[0].getNFrames()
		for frame_no in range(1, image_series[0].getNFrames() + 1):
			for slice_no in range(1, image_series[0].getNSlices() + 1):
				index = image_series[0].getStackIndex(ch_no, slice_no, frame_no)
				ip = image_series[0].getStack().getProcessor(index)
				image = ImagePlus(img_file, ip)
				print "Analyzing...", fullpath, "frame=", frame_no, "slice=", slice_no	
				analyze(image, outputdir, index, size=size)
	# get ResultsTable object and save it
	rt = WindowManager.getFrame("Summary").getTextPanel().getResultsTable()
	imagetitle = image.getTitle().split(".")[0]
	rtfile = path.join(outputdir, str(size)+"Summary_" + imagetitle + ".csv")
	rt.save(rtfile)

	print "Done.\n"