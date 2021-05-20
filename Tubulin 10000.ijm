dir = getDirectory("Choose a Directory ");
dir2 = getDirectory("Choose Destination Directory");
list = getFileList(dir);
setBatchMode(true);
for (i=0; i<list.length; i++) {

	title = getTitle();
	setAutoThreshold("Default dark");
	run("Threshold...");
	setOption("BlackBackground", false);
	run("Convert to Mask");
	run("Analyze Particles...", "size=0-10000 show=Masks summarize");
	selectWindow(title);
	run("Analyze Particles...", "size=10000-infinity show=Masks summarize");
	selectWindow("Summary");
	saveAs("Text", dir2 + "10000Summary_" + title);
	close();
	selectWindow(title);
	close();
	selectWindow("Mask of " + title);
	close();
	selectWindow("Threshold");
	run("Close");
}
