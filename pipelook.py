#!/usr/bin/env python3


# BSD 3-Clause License
#
# Copyright (c) 2019, Andre Perina
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import datetime, getopt, json, math, re, sys
from PIL import Image, ImageDraw, ImageFont


# Print this tool's usage
def printUsage(printToError=False):
	usageStr = (
		"Usage: {} [OPTION]... RPTFILE JSONFILE\n"
		"  where:\n"
		"    [OPTION]...: one or more of the following:\n"
		"      -h       , --help           this message\n"
		"      -o PNG   , --output=PNG     output pipeline report to PNG\n"
		"      -p PIPE  , --pipe=PIPE      set custom pipeline ID (default is \"Pipeline-0\")\n"
		"      -i II    , --ii=II          set custom initiation interval\n"
		"      -s STATE , --state=STATE    override RPT file info and create pipeline from header state\n"
		"                                  STATE. Requires manual insertion of II with \"--ii\"\n".format(sys.argv[0])
	)

	if printToError:
		sys.stderr.write("{}\n".format(usageStr))
	else:
		print(usageStr)


def drawRoundedRectangle(draw, start, size, bcolor, fcolor, borderSize = 5, roundedEdge = 20):
	draw.pieslice(
		[
			(start[0], start[1]),
			(start[0] + 2 * (borderSize + roundedEdge), start[1] + 2 * (borderSize + roundedEdge))
		], 180, 270, fill=bcolor
	)
	draw.pieslice(
		[
			(start[0] + borderSize, start[1] + borderSize),
			(start[0] + borderSize + 2 * roundedEdge, start[1] + borderSize + 2 * roundedEdge)
		], 180, 270, fill=fcolor
	)

	draw.rectangle(
		[
			(start[0], start[1] + borderSize + roundedEdge),
			(start[0] + borderSize, start[1] + size[1] - (borderSize + roundedEdge))
		], fill=bcolor
	)

	draw.rectangle(
		[
			(start[0] + borderSize, start[1] + borderSize + roundedEdge),
			(start[0] + borderSize + roundedEdge, start[1] + size[1] - (borderSize + roundedEdge))
		], fill=fcolor
	)

	draw.pieslice(
		[
			(start[0], start[1] + size[1] - 2 * (borderSize + roundedEdge)),
			(start[0] + 2 * (borderSize + roundedEdge), start[1] + size[1])
		], 90, 180, fill=bcolor
	)

	draw.pieslice(
		[
			(start[0] + borderSize, start[1] + size[1] - (2 * roundedEdge + borderSize)),
			(start[0] + borderSize + 2 * roundedEdge, start[1] + size[1] - borderSize)
		], 90, 180, fill=fcolor
	)

	draw.rectangle(
		[
			(start[0] + borderSize + roundedEdge, start[1]),
			(start[0] + size[0] - (borderSize + roundedEdge), start[1] + borderSize)
		], fill=bcolor
	)

	draw.rectangle(
		[
			(start[0] + borderSize + roundedEdge, start[1] + borderSize),
			(start[0] + size[0] - (borderSize + roundedEdge), start[1] + size[1] - borderSize)
		], fill=fcolor
	)

	draw.rectangle(
		[
			(start[0] + borderSize + roundedEdge, start[1] + size[1] - borderSize),
			(start[0] + size[0] - (borderSize + roundedEdge), start[1] + size[1])
		], fill=bcolor
	)

	draw.pieslice(
		[
			(start[0] + size[0] - 2 * (borderSize + roundedEdge), start[1]),
			(start[0] + size[0], start[1] + 2 * (borderSize + roundedEdge))
		], 270, 0, fill=bcolor
	)

	draw.pieslice(
		[
			(start[0] + size[0] - (2 * roundedEdge + borderSize), start[1] + borderSize),
			(start[0] + size[0] - borderSize, start[1] + borderSize + 2 * roundedEdge)
		], 270, 0, fill=fcolor
	)

	draw.rectangle(
		[
			(start[0] + size[0] - borderSize, start[1] + borderSize + roundedEdge),
			(start[0] + size[0], start[1] + size[1] - (borderSize + roundedEdge))
		], fill=bcolor
	)

	draw.rectangle(
		[
			(start[0] + size[0] - (borderSize + roundedEdge), start[1] + borderSize + roundedEdge),
			(start[0] + size[0] - borderSize, start[1] + size[1] - (borderSize + roundedEdge))
		], fill=fcolor
	)

	draw.pieslice(
		[
			(start[0] + size[0] - 2 * (roundedEdge + borderSize), start[1] + size[1] - 2 * (roundedEdge + borderSize)),
			(start[0] + size[0], start[1] + size[1])
		], 0, 90, fill=bcolor
	)

	draw.pieslice(
		[
			(start[0] + size[0] - (2 * roundedEdge + borderSize), start[1] + size[1] - (2 * roundedEdge + borderSize)),
			(start[0] + size[0] - borderSize, start[1] + size[1] - borderSize)
		], 0, 90, fill=fcolor
	)


class TLGen():
	#    reportViolations: if True, interface violations are reported to the user
	#    abortWhenViolate: if True, violations will cause this tool to abort
	# pipelineStartHeight: initial height allocated for the pipeline sub-image. Might be trimmed/extended during runtime
	#          borderSize: size of borders/separators
	#         roundedEdge: width/height of the rounded corner of rounded rectangles
	#        sizePerCycle: width allocated for each clock cycle
	#            laneStep: when two operations overlap, laneStep is the height difference between both operations (so that they are nicely placed)
	#     operationHeight: height of a single operation
	#     separatorHeight: height between two pipeline instances
	#          clockEvery: show clock edge every X cycles
	#            dashSize: size of the dashes used in clock edges
	#              opInfo: operations info, composed by the following elements:
	#                        key: operation name
	#                        values:
	#                          "colour": color used for this operation
	#                          "limitgroup": define which group this operation makes part, used for violation analysis. See limitGroups for more info
	#         limitGroups: groups used for violation analysis. Each group has a resource budget. If pipeline creates a hardware where more operations
	#                      of a same group are allocated than the available budget, a violation occurs
	#                        key: group name
	#                        value: available budget
	#      defaultOpColor: default color used for several default things
	#      headerFontSize: ditto
	#          headerFont: font used for header
	#   operationFontSize: ditto
	#       operationFont: font used for primary texts
	# descriptionFontSize: ditto
	#     descriptionFont: font used for secondary texts
	def __init__(
		self,
		reportViolations = False, abortWhenViolate = False,
		pipelineStartHeight = 500, borderSize = 5, roundedEdge = 10, sizePerCycle = 50, laneStep = 50, operationHeight = 100, separatorHeight = 10,
		clockEvery = 5, dashSize = 10,
		opInfo = {
			"ReadReq": {"colour": (0, 0, 255, 255), "limitgroup": "ddrread"},
			"Read": {"colour": (0, 0, 255, 255), "limitgroup": "ddrread"},
			"WriteReq": {"colour": (0, 255, 0, 255), "limitgroup": "ddrwrite"},
			"Write": {"colour": (0, 255, 0, 255), "limitgroup": "ddrwrite"},
			"WriteResp": {"colour": (0, 255, 0, 255), "limitgroup": "ddrwrite"},
			"load": {"colour": (0, 0, 127, 255), "limitgroup": "brmread"},
			"store": {"colour": (0, 127, 0, 255), "limitgroup": "brmwrite"},
			"fadd": {"colour": (255, 0, 0, 255), "limitgroup": None},
			"fsub": {"colour": (255, 0, 0, 255), "limitgroup": None},
			"fmul": {"colour": (255, 0, 0, 255), "limitgroup": None},
			"fdiv": {"colour": (255, 0, 0, 255), "limitgroup": None}
		},
		limitGroups = {
			"ddrread": 1,
			"ddrwrite": 1,
			"brmread": 2,
			"brmwrite": 1
		},
		defaultOpColor = (200, 200, 200, 255),
		headerFontSize = 48,
		headerFont = "/usr/share/fonts/TTf/DejaVuSansMono.ttf",
		operationFontSize = 40,
		operationFont = "/usr/share/fonts/TTf/DejaVuSansMono.ttf",
		descriptionFontSize = 28,
		descriptionFont = "/usr/share/fonts/TTf/DejaVuSansMono.ttf"
	):
		self._reportViolations = reportViolations
		self._abortWhenViolate = abortWhenViolate
		self._pipelineStartHeight = pipelineStartHeight
		self._borderSize = borderSize
		self._roundedEdge = roundedEdge
		self._sizePerCycle = sizePerCycle
		self._laneStep = laneStep
		self._operationHeight = operationHeight
		self._separatorHeight = separatorHeight
		self._clockEvery = clockEvery
		self._dashSize = dashSize
		self._opInfo = opInfo
		self._limitGroups = limitGroups
		self._defaultOpColor = defaultOpColor
		self._headerFontSize = headerFontSize
		self._headerFont = ImageFont.truetype(headerFont, self._headerFontSize)
		self._operationFontSize = operationFontSize
		self._operationFont = ImageFont.truetype(operationFont, self._operationFontSize)
		self._descriptionFontSize = descriptionFontSize
		self._descriptionFont = ImageFont.truetype(descriptionFont, self._descriptionFontSize)

		self.reset()


	def reset(self):
		self._title = "Untitled"
		self._ops = set()
		self._maxOps = {}
		self._opLanes = [[]]
		self._noOfCycles = -1
		self._II = -1
		self._pipelineImg = None
		self._pipelineStRg = [9999999999999, 0]
		self._pipelineWidth = None
		self._pipelineHeight = None
		self._imageHeight = None
		self._headerHeight = None
		self._noOfPipeLanes = None
		self._maxOps = {}


	def setTitle(self, title):
		self._title = title


	def setII(self, II):
		self._II = II


	def getNoOfStates(self):
		return self._pipelineStRg[1] - self._pipelineStRg[0] + 1


	# Insert an operation on the pipeline instance
	def insertOperation(self, img, draw, operation, start, end, *others):
		# Find for an available lane to allocate this operation (or create a new lane if all are occupied)
		drawLane = None
		for lane in range(len(self._opLanes)):
			overlaps = False
			for occupied in self._opLanes[lane]:
				if occupied[2] >= start and end >= occupied[1]:
					overlaps = True
					break
			if not overlaps:
				self._opLanes[lane].append((operation, start, end))
				drawLane = lane
				break
		if drawLane is None:
			drawLane = len(self._opLanes)
			self._opLanes.append([(operation, start, end)])
		drawStep = drawLane * self._laneStep

		r, g, b, a = self._opInfo[operation]["colour"] if operation in self._opInfo else self._defaultOpColor
		ncyc = (end - start) + 1

		if drawStep + self._operationHeight > img.size[1]:
			tmpImg = Image.new("RGBA", (self.getNoOfStates() * self._sizePerCycle, drawStep + self._operationHeight), (0, 0, 0, 255))
			tmpImg.paste(self._pipelineImg)

			self._pipelineImg = tmpImg		

		drawRoundedRectangle(draw,
			[start * self._sizePerCycle, drawStep],
			[ncyc * self._sizePerCycle, self._operationHeight], (r, g, b, a), (int(0.8 * r), int(0.8 * g), int(0.8 * b), a),
			borderSize = self._borderSize, roundedEdge = self._roundedEdge
		)

		draw.text(
			(start * self._sizePerCycle + self._borderSize + self._roundedEdge, drawStep + self._borderSize), 
			#"{} ({} cycle{})".format(operation, ncyc, "" if 1 == ncyc else "s"),
			operation,
			font=self._operationFont
		)

		draw.text(
			(start * self._sizePerCycle + self._borderSize + self._roundedEdge, drawStep + 2 * self._borderSize + self._operationFontSize), 
			", ".join(others),
			font=self._descriptionFont
		)


	# Generate a pipeline instance
	def generatePipeline(self, operations):
		# Find the state range of the operations
		for st in operations:
			if int(st) < self._pipelineStRg[0]:
				self._pipelineStRg[0] = int(st)
			for st2 in operations[st]:
				if int(st2[0]) > self._pipelineStRg[1]:
					self._pipelineStRg[1] = int(st2[0])

		self._pipelineWidth = self.getNoOfStates() * self._sizePerCycle
		self._pipelineImg = Image.new("RGBA", (self._pipelineWidth, self._pipelineStartHeight), (0, 0, 0, 255))
		pipelineImgDraw = ImageDraw.Draw(self._pipelineImg)
		offset = self._pipelineStRg[0]

		# Special logic for header
		for op in operations[str(self._pipelineStRg[0])]:
			for op2 in operations[str(self._pipelineStRg[0] + 1)]:
				# Merge operations if they're mergeable
				if op[1] == op2[1]:
					op[0] = op2[0]
					operations[str(self._pipelineStRg[0] + 1)].remove(op2)

		# Insert all operations
		for st in range(self._pipelineStRg[0], self._pipelineStRg[1] + 1):
			if str(st) in operations:
				for op in operations[str(st)]:
					self._ops.add(op[1][1])
					#self.insertOperation(self._pipelineImg, pipelineImgDraw, op[1][1], int(st), op[0], *op[1])
					self.insertOperation(self._pipelineImg, pipelineImgDraw, op[1][1], int(st) - offset, op[0] - offset, "{} cycles".format(op[0] - int(st) + 1))

		# Trim pipeline sub-image
		self._pipelineHeight = self._operationHeight + (len(self._opLanes) - 1) * self._laneStep
		self._pipelineImg = self._pipelineImg.crop((0, 0, self._pipelineWidth, self._pipelineHeight))


	# Draw a pipeline instance on a given offset position
	def drawPipeline(self, img, offset, lane):
		img.paste(self._pipelineImg, (self._sizePerCycle * offset, (self._pipelineHeight + self._separatorHeight) * lane + self._headerHeight))


	# Draw clock edges
	def drawClockBorder(self, draw, offset, clock):
		if 0 == offset % self._clockEvery:
			draw.text(
				(self._sizePerCycle * offset, self._headerHeight - self._descriptionFontSize - self._separatorHeight),
				"{}".format(clock),
				font=self._descriptionFont,
				fill=self._defaultOpColor
			)

			for base in range(self._headerHeight, self._imageHeight, self._dashSize * 2):
				draw.rectangle([
						(self._sizePerCycle * offset, base),
						(self._sizePerCycle * offset + self._borderSize, base + self._dashSize),
					],
					fill = self._defaultOpColor
				)


	# Generate header with violation information
	def generateHeader(self, img, operations):
		draw = ImageDraw.Draw(img)

		draw.text((0, 0), self._title, font = self._headerFont, fill = self._defaultOpColor)
		draw.text(
			(0, self._headerFontSize + self._borderSize), "Generated at {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
			font = self._descriptionFont,
			fill = self._defaultOpColor
		)

		maxAmtPerGroup = {}

		# O(n^5) it is!
		for st in range(self.getNoOfStates()):
			amtPerGroup = {}
			for op in self._ops:
				amt = 0
				for st1 in range(st, -1, -(self._II)):
					for st2 in operations:
						if int(st2) == (st1 + self._pipelineStRg[0]):
							for op1 in operations[st2]:
								if op1[1][1] == op:
									amt += 1
				if op not in self._maxOps or amt > self._maxOps[op][0]:
					self._maxOps[op] = (amt, "max # par. {}: {} at cycle {}".format(op, amt, st + self._pipelineStRg[0]))

					if self._reportViolations:
						limitGroup = self._opInfo[op]["limitgroup"]
						if limitGroup is not None:
							if limitGroup not in amtPerGroup:
								amtPerGroup[limitGroup] = 0
							amtPerGroup[limitGroup] += amt

			for group in amtPerGroup:
				if group not in maxAmtPerGroup:
					maxAmtPerGroup[group] = (-1, -1)
				if amtPerGroup[group] > maxAmtPerGroup[group][1]:
					maxAmtPerGroup[group] = (st + self._pipelineStRg[0], amtPerGroup[group])

		for group in maxAmtPerGroup:
			if maxAmtPerGroup[group][1] > self._limitGroups[group]:
				violation = "Violation at cycle {}: {} simultaneously allocated for class \"{}\"".format(maxAmtPerGroup[group][0], maxAmtPerGroup[group][1], group)
				if self._abortWhenViolate:
					raise RuntimeError(violation)
				else:
					print(violation)

		i = 0
		for op in self._maxOps:
			draw.text(
				(0, self._headerFontSize + self._borderSize + (self._descriptionFontSize + self._borderSize) * (i + 1)),
				self._maxOps[op][1],
				font = self._descriptionFont,
				fill = self._defaultOpColor
			)
			i += 1


	# Generate timeline with several pipeline instances according to II
	def generate(self, operations, pngFile = None):
		if self._pipelineImg is None:
			self.generatePipeline(operations)

		self._headerHeight = self._headerFontSize + (len(self._ops) + 1) * (self._operationFontSize + self._borderSize) + self._descriptionFontSize
		# _=.=_
		self._noOfPipeLanes = int((math.ceil((self.getNoOfStates() + 1) / self._II)))
		self._imageHeight = self._noOfPipeLanes * (self._pipelineHeight + self._separatorHeight) + self._headerHeight
		img = Image.new("RGBA", (
			self._pipelineWidth,
			self._imageHeight,
		), (0, 0, 0, 255))

		self.generateHeader(img, operations)

		if pngFile is not None:
			for i in range(self._noOfPipeLanes):
				self.drawPipeline(img, i * self._II, i)

			draw = ImageDraw.Draw(img)

			for i in range(self.getNoOfStates()):
				self.drawClockBorder(draw, i, i + self._pipelineStRg[0])

			img.save(pngFile)


if "__main__" == __name__:
	rptFile = None
	jsonFile = None
	pngFile = None
	pipeID = "Pipeline-0"
	ii = None
	startState = None
	kernelName = ""

	if len(sys.argv) < 3:
		printUsage()
		exit(1)

	# Get command line options
	opts, args = getopt.getopt(sys.argv[1:-2], "s:i:p:o:h", ["state=", "ii=", "pipe=", "output=", "help"])

	# Parse command line options
	for o, a in opts:
		if o in ("-s", "--state"):
			startState = int(a)
		elif o in ("-i", "--ii"):
			ii = int(a)
			if ii <= 0:
				raise RuntimeError("Invalid value supplied for \"--ii\": {}".format(ii))
		elif o in ("-p", "--pipe"):
			pipeID = a
		elif o in ("-o", "--output"):
			pngFile = a
		else:
			printUsage()
			exit(1)

	rptFile = sys.argv[-2]
	jsonFile = sys.argv[-1]

	kernelInfoRgx = re.compile(r"== Vivado HLS Report for '([^']+)'.*")
	pipeInfoRgx = re.compile(r" +{} +: +II += +(\d+),.*, States = {{ +(\d+).*".format(pipeID))

	with open(rptFile, "r") as rptF, open(jsonFile, "r") as jsonF:
		if startState is None:
			for l in rptF.readlines():
				kernelInfoMatch = kernelInfoRgx.match(l)
				if kernelInfoMatch is not None:
					kernelName = kernelInfoMatch.group(1)
				else:
					pipeInfoMatch = pipeInfoRgx.match(l)
					if pipeInfoMatch is not None:
						if ii is None:
							ii = int(pipeInfoMatch.group(1))
						startState = int(pipeInfoMatch.group(2))
						break

		if ii is None:
			raise RuntimeError("II could not be inferred from RPT file or \"-s\" option is used but no II supplied")
		if startState is None:
			raise RuntimeError("Start state of pipeline could not be inferred from RPT file. Please supply manually with \"-s\"")

		fsmDict = json.load(jsonF)

		if str(startState + 1) not in fsmDict:
			raise RuntimeError("Supplied body state {} is not first state of a FSM basic block".format(startState))
		if str(startState) not in fsmDict:
			fsmDict[str(startState)] = {str(startState): []}

		mergedFsmDict = fsmDict[str(startState + 1)]
		for i in fsmDict[str(startState)]:
			mergedFsmDict[i] = fsmDict[str(startState)][i]

		tlgen = TLGen(reportViolations=True, abortWhenViolate=(pngFile is None))

		tlgen.setTitle("{} (II = {})".format(kernelName, ii))
		tlgen.setII(ii)
		tlgen.generate(mergedFsmDict, pngFile)
