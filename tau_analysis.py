# @ File (label="Input directory", style="directory") inputdir 
# @ File (label="Output directory", style="directory") outputdir 

from ij import IJ
from ij import WindowManager
from ij.plugin import RGBStackMerge
import os
from os import path

def analyze(imagefile, outdir, size=10000):
	"""Opens a file and creates masks."""
	masks = []
	image = IJ.openImage(imagefile)
	imagetitle = image.getTitle().split(".")[0]

	# close existing Summary window
	rtframe = WindowManager.getFrame("Summary")
	if rtframe is not None:
	    rtframe.close()
	
	# segmentation
	IJ.setAutoThreshold(image, "Default dark");
	IJ.run(image, "Options...", "iterations=1 count=1 do=Nothing");
	#IJ.run(mask, "Convert to Mask", "");
	IJ.run(image, "Analyze Particles...", "size=0-"+str(size)+" show=Masks summarize");
	masks.append(IJ.getImage())
	IJ.run(image, "Analyze Particles...", "size="+str(size)+"-infinity show=Masks summarize");
	masks.append(IJ.getImage())
	
	# get ResultsTable object and save it
	rt = WindowManager.getFrame("Summary").getTextPanel().getResultsTable()
	rtfile = path.join(outdir, str(size)+"Summary_" + imagetitle + ".csv")
	rt.save(rtfile)

	# create multi-color merged mask
	mergedmask = RGBStackMerge.mergeChannels(masks, False)
	for m in masks:
	    m.close()
	mergedmask.setTitle(imagetitle + "-mask.tif")
	outputfile = path.join(outdir, mergedmask.getTitle())
	IJ.saveAs(mergedmask, "TIFF", outputfile)

	 
# Main code
inputdir = str(inputdir) # convert from File object to String
outputdir = str(outputdir) # convert from File object to String
if not path.isdir(inputdir):
    print inputdir, " does not exist or is not a directory."
else:
	if not path.isdir(outputdir):
	    # create output directory if it does not exist
		os.makedirs(outputdir)
	filenames = os.listdir(inputdir) # get list of files to process
	imagefiles =[f for f in filenames if f.split(".")[-1] == 'tif']
	for img_file in imagefiles:
	    # execute the following block for each file
		fullpath = path.join(inputdir, img_file)
		print "Analyzing...", fullpath	
		analyze(fullpath, outputdir)
	print "Done.\n"