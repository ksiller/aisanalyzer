#drag in the image of interest, ensure split channel is unchecked 
#to make the mask
from ij.plugin import ChannelSplitter # this needs to be done at the beginning of each script so it can import the channel splitter to be used
from ij import IJ # this needs to be done at the beginning of each script so it can import the IJ to be used
from ij import Prefs
from ij.measure import ResultsTable
from ij import WindowManager
from sc.fiji.coloc import Colocalisation_Test

#get the image, will be unsplit
imp = IJ.getImage();
#command to split the images, open up the record then search on the help "split channels"
channels = ChannelSplitter.split(imp);
#duplicate the images for the mask and red and green images
mask = channels[3].duplicate();
green = channels[1].duplicate();
red = channels[3].duplicate();
mask.setTitle("mask")
mask.show()
green.show()
red.show()
#apply median filter
IJ.run(mask, "Median...", "radius=2")
#set threshold
IJ.setAutoThreshold(mask, "Otsu")
#make a mask
Prefs.blackBackground = False
IJ.run(mask, "Make Binary", "")
IJ.run(mask, "Invert", "")
#Colocalization Test
IJ.run(red, "Colocalization Test", "channel_1=["+red.getTitle()+"] channel_2=["+green.getTitle()+"] roi=mask randomization=[Fay (x,y,z translation)]");
red.close()
green.close()
mask.changes = False
mask.close()
#get ResultsTable object and save it
textpanel = WindowManager.getFrame("Results").getTextPanel()
resultline = textpanel.getLine(textpanel.getLineCount()-1)
value = float(resultline.split('\t')[1])
print value
allResultsTitle = "Summary"
frame = WindowManager.getFrame(allResultsTitle)
summaryrt = None
if frame is not None:
  summaryrt = frame.getTextPanel().getResultsTable()
else:
  summaryrt = ResultsTable()
summaryrt.incrementCounter()
summaryrt.addValue("Image", imp.getTitle())
summaryrt.addValue("R(obs)", value)
summaryrt.show(allResultsTitle)
#imagetitle = image.getTitle().split(".")[0]
#rtfile = path.join(outputdir, str(size)+"Summary_" + imagetitle + ".csv")
