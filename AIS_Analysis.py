# @ File (label="Input directory", style="directory") inputdir 
# @ File (label="Output directory", style="directory") outputdir 
# @ Integer (label="Nucleus channel", min=1, max=5) nucleus_chno
# @ Integer (label="AIS channel", min=1, max=5) ais_chno
# @ Integer (label="AIS segmentation line width", min=1, max=10, value=10) ais_linewidth
# @ String (label="AIS cross-section analysis", choices=["Mean", "Median", "Sum"], value="Mean") ais_method
# @ Float (label="AIS rel. intensity threshold (0-100% of max)", min=0.0, max=100, stepSize=1, value=10) ais_threshold
# @ Integer (label="Rolling average", min=1, max=250, value=10) average
# @ Boolean (label="Show image", value=True) show_img
# @ Boolean (label="Show intensity profile", value=True) show_plot
# @ Boolean (label="Clear Summary", value=False) clear_summary

import sys
import math

from ij import IJ, Prefs, ImagePlus
from loci.plugins import BF
from loci.plugins.in import ImporterOptions
from ij.plugin.frame import RoiManager
from ij.plugin import Straightener
from ij import WindowManager
from ij.process import ImageStatistics as IS
from ij.measure import ResultsTable
from java.awt import Polygon, Color
from ij.gui import Overlay, Roi, Line, PolygonRoi, Plot
from sc.fiji.analyzeSkeleton import AnalyzeSkeleton_, Edge, Point
from java.lang import Double
from java.util import ArrayList
from itertools import islice

import os
from os import path

AIS_SUMMARY_TABLE = 'AIS Summary'

DIST_RAW_COL = 'Distance (raw)'
INT_RAW_COL = 'Intensity (raw)'
DIST_AVG_COL = 'Distance (avg)'
INT_AVG_COL = 'Intensity (avg)'
DIST_TRIM_COL = 'Distance (trimmed)'
INT_TRIM_COL = 'Intensity (trimmed)'

def get_file_pairs(inputdir, img_ext="nd2", roi_ext="zip"):
    pairs = []
    files = os.listdir(inputdir)
    img_files = [f for f in files if f.split(".")[-1] == img_ext]
    for imgf in img_files:
    	roifile =  os.path.join(inputdir, os.path.splitext(imgf)[0] + '.' + roi_ext)
        if os.path.isfile(roifile):
            pairs.append({'img':os.path.join(inputdir, imgf), 'roi':roifile})
    return pairs


def open_image(imgfile):
	options = ImporterOptions()
	options.setId(imgfile)
	options.setSplitChannels(False)
	options.setColorMode(ImporterOptions.COLOR_MODE_COMPOSITE)
	imps = BF.openImagePlus(options)
	splitimps = [ImagePlus("%s-C-%i" % (imps[0].getTitle(), i),imps[0].getStack().getProcessor(i)) for i in range(1,imps[0].getNChannels()+1)] 
	for si in splitimps:
		si.setCalibration(imps[0].getCalibration().copy())
	return imps[0], splitimps


def load_rois(roifile):
	rm = RoiManager(False)
	rm.reset()
	rm.runCommand("Open", roifile)
	rois = rm.getRoisAsArray()
	return rois


def local_angles(points, scope=1):
	angles = []
	orthogonals = []
	for i,p in enumerate(points):
		#localpoly = Polygon()
		#or j in range(0, i-scope):
		#	localpoly.addPoint(int(points[j].x), int(points[j].y))
		#localpoly.addPoint(int(p.x), int(p.y))
		#for j in range(i, min(i+scope,len(points))):
		#	localpoly.addPoint(int(points[j].x), int(points[j].y))
		#polygon = PolygonRoi(localpoly, PolygonRoi.POLYLINE)	
		#angle = polygon.getAngle()
		p1 = points[max(0,i-scope)]
		p2 = points[min(len(points)-1, i+scope)]
		shiftx = 0.5*(p1.x+p2.x)
		shifty = 0.5*(p1.y+p2.y)
		ortho1 = Point(int(-(p1.y-shifty)+shiftx), int(p1.x-shiftx+shifty),0)
		ortho2 = Point(int(-(p2.y-shifty)+shiftx), int(p2.x-shiftx+shifty),0)
		orthogonals.append([ortho1, ortho2])
		dummyroi = Roi(p1.x, p1.y, p2.x, p2.y)
		angle = dummyroi.getAngle(p1.x, p1.y, p2.x, p2.y)
		angles.append(angle)
	return angles, orthogonals


def find_closest_roi(x,y, roi_list):
	if len(roi_list) == 0:
		return None
	mindist = sys.float_info.max
	minidx = -1
	for idx in range(len(roi_list)):
		r = roi_list[idx]
		rx = r.getContourCentroid()[0]
		ry = r.getContourCentroid()[1]
		deltax = rx-x
		deltay = ry-y 
		dist = math.sqrt((deltax*deltax) + (deltay*deltay))
		if dist < mindist:
			mindist = dist
			minidx = idx
	return roi_list[minidx], mindist
	

def create_skeleton(image, name, min_branch_length=10, nuclei_rois=None, sample_width=4):
	print "Creating skeleton for %s, new name %s" %(image.getTitle(), name)
	# analyze skeleton
	skel = AnalyzeSkeleton_()
	skel.setup("", image)
	skelResult = skel.run(AnalyzeSkeleton_.NONE, False, True, None, True, False)
	
	# create copy of input image
	pruned_img = image.duplicate()
	outStack = pruned_img.getStack()
	
	# get graphs (one per skeleton in the image)
	graph = skelResult.getGraph()
	
	# list of end-points
	endPoints = skelResult.getListOfEndPoints()

	if graph:
		for i in range(len(graph)):
			listEdges = graph[i].getEdges()
			# go through all branches and remove branches < min_branch_length in duplicate image
			for  e in listEdges:
				p = e.getV1().getPoints();
				v1End = endPoints.contains( p.get(0) )
				p2 = e.getV2().getPoints();
				# print "p=",p, "p2=",p2
				v2End = endPoints.contains( p2.get(0) )
				# if any of the vertices is end-point 
				if v1End or v2End :
					if e.getLength() < min_branch_length:
						if v1End:
							outStack.setVoxel( p.get(0).x, p.get(0).y, p.get(0).z, 0 )
						if v2End:
							outStack.setVoxel( p2.get(0).x, p2.get(0).y, p2.get(0).z, 0 )
						for p in e.getSlabs():
							outStack.setVoxel( p.x, p.y, p.z, 0 )
	pruned_img.setTitle(image.getTitle()+"-longestpath")

	sppoints = skel.getShortestPathPoints()
	if len(sppoints) == 0:
		return None, None, None, None, None, None

	ais_skeleton = pruned_img.duplicate()
	ais_skeleton.setTitle(name);
	IJ.run(ais_skeleton, "Select All", "")
	IJ.run(ais_skeleton, "Clear", "slice")
	points = []
	angle = []
	b_length = [len(b) for b in sppoints]
	longest_branch_idx = b_length.index(max(b_length))
	points = [p for p in sppoints[longest_branch_idx]]
	closest_nucleus = None
	if nuclei_rois is not None:
		nroi1,dist1 = find_closest_roi(points[0].x, points[0].y, nuclei_rois)
		nroi2,dist2 = find_closest_roi(points[len(points)-1].x, points[len(points)-1].y, nuclei_rois)
		if nroi1 != nroi2 and dist2<dist1:
			# reverse order
		    points = points[::-1]
		    closest_nucleus = nroi2
		else:
		    closest_nucleus = nroi1
		closest_nucleus.setName('%s-nucleus-ROI' % (name))


	poly = Polygon()
	for p in points:
		poly.addPoint(int(p.x), int(p.y))

	#for branch in sppoints:
	#	print "Branch %s, len=%d" % (branch, len(branch))
	#	for p in branch:
	#		poly.addPoint(int(p.x), int(p.y))
	#		points.append(p)
	angles,orthogonals = local_angles(points, scope=sample_width//2)
	ais_roi = PolygonRoi(poly, PolygonRoi.POLYLINE)
	ais_roi.setFillColor(Color(0.0,1.0,1.0,0.5));
	ais_roi.setStrokeColor(Color(0.0,1.0,1.0,0.5));
	ais_roi.setName('%s-AIS-ROI' % (name))
	#ais_roi.setStrokeWidth(sample_width)
	IJ.run(ais_skeleton, "Analyze Particles...", "size=20-Infinity pixel exclude clear add");
	IJ.run(ais_skeleton, "Clear", "slice")

	ip = ais_skeleton.getProcessor()
	for n in nuclei_rois:
		ais_skeleton.setRoi(n)
		if n == closest_nucleus:
			ip.setValue(128)
		else:
			ip.setValue(255)		
		ip.fill(n.getMask())
		
	ais_skeleton.setRoi(ais_roi)
	#ip.setValue(200)
	#ip.fill()
	
	#rois = RoiManager.getInstance2().getRoisAsArray()
	#for roi in rois:
	#	ais_skeleton.setRoi(roi)
	#	ip.setValue(255)
	#	ip.fill(roi.getMask());

	for p,a,o in zip(points,angles,orthogonals):
		# print "p=%s, a=%s, o=%s" % (p,a,o)
		ip.set(int(p.x), int(p.y), int(33+a/2))
		ip.set(int(o[0].x), int(o[0].y),255)
		ip.set(int(o[1].x), int(o[1].y),255)

	IJ.run(ais_skeleton, "Fire", "")
	# pruned_img.setRoi(ais_roi)
	print "Created ais=%s" % ais_skeleton.getTitle()
	print len(skel.getShortestPathPoints()), len(points), len(orthogonals)
	return ais_skeleton, skel.getShortestPathPoints(), points, orthogonals, ais_roi, closest_nucleus



def rolling_seq(seq, window):
    """Returns a sliding window (of width n) over data from the iterable seq
    s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ..."""
    it = iter(seq)
    result = tuple(islice(it, window))
    if len(result) == window:
        yield result    
    for elem in it:
        result = result[1:] + (elem,)
        yield result


def rolling_average(x, y, window):
	grouped_x = rolling_seq(x, window)
	# newx = [sum(elements)/len(elements) for elements in grouped_x]
	grouped_y = rolling_seq(y, window)
	newx = ArrayList()
	for elements in grouped_x:
		newx.add(sum(elements)/len(elements))
	newy = ArrayList()
	for elements in grouped_y:
		newy.add(sum(elements)/len(elements))
	return newx, newy


def median(iterable):
	iterable.sort()
	middle = len(iterable) // 2
	if len(iterable) % 2 == 0:
		median1 = iterable[middle-1]
		median2 = iterable[middle]
		return (median1 + median2)/2
	else:
		return iterable[middle]


def cross_section_intensity(imp, method='median'):
	ip = imp.getProcessor()
	ip.setInterpolate(False)
	height = ip.height
	width = ip.width
	# read pixels on horizontal line because it's faster
	alines = [ip.getLine(0, y, width-1, y) for y in range(height)]
	# now calculate for each column along length of straightened AIS
	method = method.lower()
	if method == 'median':
		return [median([alines[y][col] for y in range(height)]) for col in range(width)]
	elif method == 'sum':		
		return [sum([alines[y][col] for y in range(height)]) for col in range(width)]
	else:
		# mean as default
		return [sum([alines[y][col] for y in range(height)])/height for col in range(width)]
		

def get_thresholded_idx(values, threshold=0.1):
    firstidx = -1
    lastidx = -1
    maxvalue = -1
    if (len(values)) > 0:
    	maxvalue = max(values)
    threshold_value = threshold*maxvalue
    for i,v in enumerate(values):
    	if firstidx == -1 and v>=threshold_value:
    		firstidx = i
    		break
    for i in range(len(values)-1, -1, -1):
    	if lastidx == -1 and values[i]>=threshold_value:
    		lastidx = i
    		break
    print "First Idx=%d, Last Idx=%d, len(values)=%d" % (firstidx, lastidx, len(values))
    return firstidx, lastidx, threshold_value

	 
def create_plot(imp, method, average, threshold=0.1):
	intensity = cross_section_intensity(imp, method)
	cal = imp.getCalibration()
	x_inc = cal.pixelWidth;
	units = cal.getUnits();
	x_label = "Distance (%s)" % units
	y_label = 'Intensity' # cal.getValueUnit()
	x_values = [i*x_inc for i in range(len(intensity))]

	lastindex = len(x_values)-1
	for i in range(1, len(x_values)+1):
		index = len(x_values)-i
		if intensity[index] == 0:
			lastindex = index-1
		else:
			break
	ax = [x_values[i] for i in range(lastindex)]
	ay = [intensity[i] for i in range(lastindex)]
	average_x, average_y = rolling_average(ax, ay, average)

	firstidx, lastidx, threshold_intensity = get_thresholded_idx(average_y, threshold=threshold)
	perform_trim = firstidx!=-1 and lastidx!=-1
	if perform_trim:
	    trim_x = [average_x[i] for i in range(firstidx, lastidx+1)]
	    trim_y = [average_y[i] for i in range(firstidx, lastidx+1)]

	# raw data
	flags = Plot.getDefaultFlags()
	flags = flags - Plot.Y_GRID - Plot.X_GRID
	plot = Plot("%s-Plot" % imp.getTitle(), x_label, y_label, flags)
	plot.setLineWidth(1)
	plot.setColor(Color.BLACK)
	plot.addPoints(x_values, intensity,Plot.LINE)

	# threshold line
	plot.setLineWidth(2)
	plot.setColor(Color.BLACK)
	plot.addPoints([0,x_inc * imp.getWidth()], [threshold_intensity,threshold_intensity],Plot.LINE)

	# rolling average
	plot.setLineWidth(2)
	plot.setColor(Color.MAGENTA)
	plot.addPoints(average_x,average_y,Plot.LINE)

	# standard legend labels
	labels = "\t".join(['Raw Data (%s)' % method, 'Intensity threshold (%d%s)' % (100*threshold, '%'), 'Rolling Average (n=%d)' % average])

	# trimmed rolling average
	if perform_trim:
	    plot.setLineWidth(2)
	    plot.setColor(Color.GREEN)
	    plot.addPoints(trim_x,trim_y,Plot.LINE)
	    labels+='\tTrimmed Rolling Average (n=%d)' % average

	plot.setColor(Color.BLACK)
	plot.setLimitsToFit(False)
	plot.addLegend(labels)

	rt = ResultsTable()
	for row,x in enumerate(x_values):
		rt.setValue(DIST_RAW_COL, row, x)
		rt.setValue(INT_RAW_COL, row, intensity[row])
	for row,x in enumerate(average_x):
		rt.setValue(DIST_AVG_COL, row, x)
		rt.setValue(INT_AVG_COL, row, average_y[row])
	if perform_trim:
	    for row,x in enumerate(trim_x):
		    rt.setValue(DIST_TRIM_COL, row, x)
		    rt.setValue(INT_TRIM_COL, row, trim_y[row])
    
	return plot, rt


def process_image(imps, rois, ais_chno, nucleus_chno, bg_roino=3, sample_width=3, method='mean', dilations=3, average=1, threshold=0.1):
	"""Opens a file and applies a Gaussian filter."""
	orig_title = imps[ais_chno-1].getTitle()
	print ",".join([i.getTitle() for i in imps])
	print "Processing", orig_title
	options = IS.MEAN | IS.MEDIAN  # many others
	
	nucleus_imp = imps[nucleus_chno-1].duplicate()
	IJ.run(nucleus_imp, "Median...", "radius=10")
	IJ.setAutoThreshold(nucleus_imp, "Default");
	IJ.run(nucleus_imp, "Make Binary", "")
	IJ.run(nucleus_imp, "Invert", "")
	IJ.run(nucleus_imp, "Options...", "iterations=1 count=1 black do=Nothing");
	IJ.run(nucleus_imp, "Watershed", "");
	IJ.run(nucleus_imp, "Analyze Particles...", "size=20-Infinity clear add");
	rm = RoiManager.getInstance2()
	nuclei = rm.getRoisAsArray()

	ais_imp = imps[ais_chno-1].duplicate()
	print ais_imp.getTitle()
	IJ.run(ais_imp, "8-bit","")
	IJ.run(ais_imp, "Median...", "radius=1")
	bg = 0
	for i in range(bg_roino):
	    bg_roi = rois[i]
	    ais_imp.setRoi(bg_roi)
	    stats = ais_imp.getStatistics(options)
	    bg += stats.mean
	    print "Bg Roi %s, %s: %s" % (bg_roi.getName(), bg_roi, stats)
	background = (int)(bg / bg_roino)
	results = []
	for i in range(bg_roino, len(rois)):
		roiresult = {}
		print i, rois[i].getName()
		mimp = ais_imp.duplicate()
		mimp.setTitle("%s-%s-AIS-Skeleton" % (orig_title, rois[i].getName()))
		# IJ.run(mimp, "Median...", "radius=3")
		
		mimp.setRoi(rois[i])

		# IJ.setAutoThreshold(mimp, "Huang dark")
		IJ.run(mimp, "Auto Local Threshold", "method=Phansalkar radius=15 parameter_1=0 parameter_2=0 white")

		IJ.setBackgroundColor(0,0,0)
		IJ.run(mimp, "Clear Outside", "")

		Prefs.blackBackground = True
		for j in range(dilations):
			IJ.run(mimp, "Dilate", "")
		IJ.run(mimp, "Skeletonize", "")
		#IJ.run(mimp, "Analyze Skeleton (2D/3D)", "prune=none prune_0 calculate show display");
		ais_skeleton, ais_points, points, orthogonals, ais_roi, nucleus_roi = create_skeleton(mimp, '%s-%s-AIS' % (orig_title, rois[i].getName()), nuclei_rois=nuclei, sample_width=sample_width)
		if ais_skeleton is None:
		    print "Skipping -- AIS skeleton segmentation failed for ROI", rois[i].getName()
		    continue
		#images['ais-skeleton-' + rois[i].getName()] = ais_skeleton

		# subtract background
		print "Subtracting background: bg=%d" % background
		IJ.run(ais_imp, "Subtract...", "value=%d" % int(background))

		ais_imp.setRoi(ais_roi)
		ip = Straightener().straightenLine(ais_imp, sample_width)
		straight_imp = ImagePlus('%s-%s-AIS-Straight' % (orig_title, rois[i].getName()), ip)
		straight_imp.setCalibration(imps[ais_chno-1].getCalibration().copy())
		IJ.run(straight_imp, "Green Fire Blue", "")

		roiresult = {
			'roi-name': rois[i].getName(),
			'ais-image': straight_imp,
			'ais-roi': ais_roi,
			'nucleus-roi': nucleus_roi,
		}
		# plot
		if len(points) > 1:
			if method == 'sum':
				threshold *= sample_width
			plot, rt = create_plot(straight_imp, method, average, threshold=threshold)
			roiresult['plot'] = plot
			roiresult['table'] = rt
			
		results.append(roiresult)	
	return results, background


def save_as_tif(directory, title, image):
	"""Saves an ImagePlus object in a specific directory."""
	outputfile = path.join(directory, title)
	IJ.saveAs(image, "TIFF", outputfile)
	print "Saved", outputfile 


def save_roi(directory, name, roi):
    """Saves ROI object in specific directory"""
    if roi is not None:
        rm = RoiManager(False)
        print roi.getName()
        roifile = path.join(directory, name+".zip")
        rm.addRoi(roi)
        rm.runCommand("Save", roifile)
    else:
        print "skipping saving ROI"

def add_to_summary(summary_rt, imgname, roiname, rt):
    ais_start = 'na'
    ais_length = 'na'
    if DIST_AVG_COL in rt.getColumnHeadings():
        col_idx = 4 #rt.getColumnIndex​(DIST_AVG_COL)
        avg_dist = rt.getColumn(col_idx)
        if len(avg_dist) > 0:
            ais_start = avg_dist[0]
            ais_length = max(avg_dist)-ais_start  
    row = summary_rt.getCounter()
    summary_rt.setValue('Image', row, imgname)
    summary_rt.setValue('ROI', row, roiname)
    summary_rt.setValue('AIS start', row, ais_start)
    summary_rt.setValue('AIS length', row, ais_length)

# Main code
inputdir = str(inputdir)
outputdir = str(outputdir)
ais_method = ais_method.lower()
ais_threshold /=100
if not path.isdir(inputdir):
    print inputdir, 'does not exist or is not a directory.'
else:
	summary_rt = ResultsTable.getResultsTable(AIS_SUMMARY_TABLE)
	if summary_rt is None:
	    summary_rt = ResultsTable()
	elif clear_summary:
		summary_rt.reset()
	if not path.isdir(outputdir):
		os.makedirs(outputdir)
	file_pairs = get_file_pairs(inputdir)
	for item in file_pairs:
	  try:
		overlay = Overlay()
		composite,imps = open_image(item['img'])
		rois = load_rois(item['roi'])
		if len(imps) < ais_chno or len(imps) < nucleus_chno:
		    print 'Image %s has %d channels. Cannot process AIS segmentation for channel %d. Skipping.' % (item['img'], len(imps), ais_chno) 
		else:
			if show_img:
				composite.show()
				#for i in imps:
				#	i.show()
			results, background = process_image(imps, rois, ais_chno, nucleus_chno, bg_roino=3, average=average, sample_width=ais_linewidth, method=ais_method, threshold=ais_threshold)
			for roiresult in results:
				ais_roi = roiresult['ais-roi']
				nucleus_roi = roiresult['nucleus-roi']
				ais_image = roiresult['ais-image']
				overlay.add(ais_roi)
				overlay.add(nucleus_roi)
				rt = roiresult['table']
				rt_title = '%s-%s-Results' % (composite.getTitle(), roiresult['roi-name'])
				rt.saveAs(os.path.join(outputdir, '%s.csv' % rt_title))
				add_to_summary(summary_rt, composite.getTitle(), roiresult['roi-name'], rt)
				if show_plot:
					rt.show(rt_title)
					roiresult['plot'].show()
				save_as_tif(outputdir, '%s-%s-AIS-straight' % (composite.getTitle(), roiresult['roi-name']), ais_image)
				save_roi(outputdir, '%s-%s-AIS-ROI' % (composite.getTitle(), roiresult['roi-name']), ais_roi)
				save_roi(outputdir, '%s-%s-nucleus-ROI' % (composite.getTitle(), roiresult['roi-name']), nucleus_roi)
				if show_img:
					ais_image.show()
		composite.setOverlay(overlay)
	  except:
	    print 'Skipping', item
	summary_rt.show(AIS_SUMMARY_TABLE)
	print 'Done.\n'
