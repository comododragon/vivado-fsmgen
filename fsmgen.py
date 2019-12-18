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


import networkx as nx
import getopt, re, sys


# Print this tool's usage
def printUsage(printToError=False):
	usageStr = (
		"Usage: {} [OPTION]... RPTFILE DOTFILE\n"
		"  where:\n"
		"    [OPTION]...: one or more of the following:\n"
		"      -h, --help                  this message\n"
		"      -f FILTER, --filter=FILTER  show together with the graph some operations of interest:\n"
		"                                    ddr    show DDR transactions\n"
		"                                    float  show floating-point transactions\n"
		"                                  NOTE: you can repeat this argument\n"
		"      -c CSV   , --csv=CSV        save filtered operations to a csv file with name CSV\n".format(sys.argv[0])
	)

	if printToError:
		sys.stderr.write("{}\n".format(usageStr))
	else:
		print(usageStr)


if "__main__" == __name__:
	rptFile = None
	dotFile = None
	activeFilters = []
	csvFile = None

	if len(sys.argv) < 3:
		printUsage()
		exit(1)

	# Get command line options
	opts, args = getopt.getopt(sys.argv[1:-2], "f:c:h", ["filter=", "csv=", "help"])

	# Parse command line options
	for o, a in opts:
		if o in ("-f", "--filter"):
			activeFilters.append(a) 
		elif o in ("-c", "--csv"):
			csvFile = a
		else:
			printUsage()
			exit(1)

	rptFile = sys.argv[-2]
	dotFile = sys.argv[-1]

	# Filters. Interesting information should be saved using groups (with parentheses)
	#
	# The first group is always allocated to the whole match
	# The second group in this case should isolate the state number (i.e. ST_(\d+))
	# All remaining groups are user-defined and used to show the information on the graph
	# Each filter is composed of one or more tuples. Each tuple is composed of one compiled
	# regex (following the recommendations above) and one array for group reordering.
	# Apart from the first two groups that are reserved, the remaining groups can be reordered
	# to make the information readable. Separators can be created with None
	# If no reordering is required, simply pass None
	#
	# Example:
	# Let's say that the regex matched to the following groups (including the reserved values): [8, 164, %foo, 5]
	# Using a reordering vector of [1, None, None, 0], the final vector will be [8, 164, 5, ---, ---, %foo]
	# Note that the index elements from the reorder vector consider position 0 as the first non-reserved group
	#
	# NOTE: To avoid confusing grouping of operations, you must create enough groups to
	#       ensure that each operation is uniquely identifiable
	# Gerar dois projectos de banking diferentes, baseados no rw-add2-np: um usando arrays completamente ortogonais para leitura, e outro usando indices diferentes do que >> 1 (eu acho que pode ta rolando um burst nao intencional ali)
	filters = {
		"ddr": [
			(re.compile(r"ST_(\d+) : Operation \d+ \[\d+/(\d+)\].*--->.*=.*@_ssdm_op_(ReadReq).m_axi.i(\d+)P\(i\d+ addrspace\(1\)\* ([^ ]+), i\d+ ([^ ]+)\).*"), [0, 1, None, 2, 3]),
			(re.compile(r"ST_(\d+) : Operation \d+ \[\d+/(\d+)\].*--->.*\"([^ ]+).*=.*@_ssdm_op_(Read).m_axi.i(\d+)P\(i\d+ addrspace\(1\)\* ([^\)]+)\).*"), [1, 2, 0, 3, None]),
			(re.compile(r"ST_(\d+) : Operation \d+ \[\d+/(\d+)\].*--->.*=.*@_ssdm_op_(WriteReq).m_axi.i(\d+)P\(i\d+ addrspace\(1\)\* ([^ ]+), i\d+ ([^ ]+)\).*"), [0, 1, None, 2, 3]),
			(re.compile(r"ST_(\d+) : Operation \d+ \[\d+/(\d+)\].*--->.*@_ssdm_op_(Write).m_axi.i(\d+)P\(i\d+ addrspace\(1\)\* ([^ ]+), i\d+ ([^ ]+), i\d+ ([^ ]+)\).*"), None),
			(re.compile(r"ST_(\d+) : Operation \d+ \[\d+/(\d+)\].*--->.*\"([^ ]+).*=.*@_ssdm_op_(WriteResp).m_axi.i(\d+)P\(i\d+ addrspace\(1\)\* ([^\)]+)\).*"), [1, 2, 0, 3, None])
		],
		"float": [
			(re.compile(r"ST_(\d+) : Operation \d+ \[\d+/(\d+)\].*--->.*\"([^ ]+).*= (fadd|fsub|fmul|fdiv) [^ ]+ ([^ ]+), ([^ ]+)\".*"), [1, None, 0, 2, 3])
		]
	}

	# Sanity check
	for activeFilter in activeFilters:
		if activeFilter not in filters:
			raise RuntimeError("Unknown filter requested: {}".format(activeFilter))

	with open(rptFile, "r") as inF, open(dotFile, "w") as outF:
		currentNode = -2
		endNodeID = None
		nodeRegex = re.compile("(\\d+) --> \n")
		edgeRegex = re.compile("\t(\\d+)[ ]*/ (.*)")
		endNodeRegex = re.compile("ST_(\\d+) : .*\"ret void\".*<Predicate = (.*)> <Delay.*")

		G = nx.DiGraph()
		filteredLines = {}

		for line in inF:
			# Searching for beginning of FSM
			if -2 == currentNode:
				if "* FSM state transitions: \n" == line:
					currentNode = 0
			# End of FSM, searching for end node and also nodes of interest
			elif -1 == currentNode:
				# If we reached the end of the operation list, we stop
				if "============================================================\n" == line:
					break

				# First, we search for end node
				endNodeMatch = endNodeRegex.match(line)
				# End node found, add it and the incoming edge
				if endNodeMatch is not None:
					endNodeID = str(len(G.nodes()) + 1)
					G.add_node(endNodeID, label="end")
					G.add_edge(str(endNodeMatch.group(1)), endNodeID, label=endNodeMatch.group(2))

				# Now, we search for active filters (if any)
				for activeFilterSet in activeFilters:
					for activeFilter in filters[activeFilterSet]:
						filterMatch = activeFilter[0].match(line)
						# Filter matched, we save the groups for later use
						if filterMatch is not None:
							stateNo = int(filterMatch[1])
							if stateNo not in filteredLines:
								filteredLines[stateNo] = []

							# If reordering vector is supplied, we reorder the group
							if activeFilter[1] is None:
								filteredLines[stateNo].append(filterMatch.groups()[1:])
							else:
								reorderedMatch = [filterMatch.group(2)]
								for relem in activeFilter[1]:
									reorderedMatch.append("---" if relem is None else filterMatch.group(relem + 3))
								filteredLines[stateNo].append(tuple(reorderedMatch))
			# Inside FSM
			else:
				# FSM states were already found, if the header is found again, this is unexpected
				if "* FSM state transitions: \n" == line:
					raise RuntimeError("Input file is corrupt")
				# This indicates the end of the FSM. Will proceed to the next search now
				elif "* FSM state operations: \n" == line:
					currentNode = -1

				nodeMatch = nodeRegex.match(line)
				# A node description was detected, create this node
				if nodeMatch is not None:
					currentNode = int(nodeMatch.group(1))
					G.add_node(str(currentNode), label=str(currentNode))
				else:
					edgeMatch = edgeRegex.match(line)
					# A edge description was detected, add this edge
					if edgeMatch is not None:
						G.add_edge(str(currentNode), edgeMatch.group(1), label=edgeMatch.group(2))

		# Add root node just to simplify the logic for merging node 1 with others if needed
		G.add_edge(str(0), str(1), label="true")

		sequence = []
		origNodes = len(G.nodes())
		# Iterate through all nodes (we are assuming that the FSM flows through the states in a crescent manner)
		i = 0
		while i <= origNodes:
			state = 0
			iStr = str(i)
			imStr = None if 0 == i else str(i - 1)
			ipStr = str(i + 1)

			if G.has_node(iStr):
				# Simplification sequence is empty
				if 0 == len(sequence):
					# If simplification sequence is empty, current node has only one incoming and one outcoming edge and the next edge is i + 1, change to "START SIMPLIFICATION" state
					if (1 == G.in_degree(iStr)) and (1 == G.out_degree(iStr)) and G.has_edge(iStr, ipStr):
						state = 1
				else:
					# Simplification sequence is not empty, if this node has only one incoming and one outcoming edge, add this node to simplification
					if (1 == G.in_degree(iStr)) and (1 == G.out_degree(iStr)) and G.has_edge(imStr, iStr):
						state = 1
					# Else, finish simplification ("SIMPLIFICATION FLUSH" state)
					else:
						state = 2

				# State 1: START SIMPLIFICATION
				if 1 == state:
					sequence.append(i)
				# State 2: SIMPLIFICATION FLUSH
				elif 2 == state:
					# Simplification should only be performed when 2 or more states are present for simplification
					if len(sequence) > 1:
						# Get smallest and biggest node
						minElem = min(sequence)
						maxElem = max(sequence)

						# The sequence array must always be continuous (e.g. [1, 2, 3, ..., 9]). If not, this is an error
						if ((maxElem - minElem) + 1) != len(sequence):
							raise RuntimeError("Attempt to perform simplification in a non-continuous sequence: smallest is {}, largest is {} and sequence has {} nodes".format(minElem, maxElem, len(sequence)))

						# Create supernode
						superNode = "{}to{}".format(minElem, maxElem)
						G.add_node(superNode, label="{}-{}".format(minElem, maxElem))

						# Populate list of new incoming edges
						sources = []
						edges = []
						for e in G.in_edges(str(minElem), data=True):
							sources.append((e[0], e[2]["label"]))
							edges.append(e)
						# Remove old incoming edges
						G.remove_edges_from(edges)
						# Create incoming edges to supernode
						for n in sources:
							G.add_edge(n[0], superNode, label=n[1])

						# Populate list of new outgoing edges
						destinations = []
						edges = []
						for e in G.out_edges(str(maxElem), data=True):
							destinations.append((e[1], e[2]["label"]))
							edges.append(e)
						# Remove old outgoing edges
						G.remove_edges_from(edges)
						# Create outgoing edges from supernode
						for n in destinations:
							G.add_edge(superNode, n[0], label=n[1])

						# Remove all nodes present in the sequence
						for n in sequence:
							G.remove_node(str(n))

					# Clean simplification list
					sequence = []

					# Re-visit this node
					i = i - 1

			i = i + 1

		# Your work is done root node, farewell :')
		G.remove_node(str(0))

		# Write .dot header
		outF.write("digraph \"FSM\" {\n\tgraph [fontname = \"monospace\"];\n\tnode [fontname = \"monospace\"];\n\tedge [fontname = \"monospace\"];\n\n")

		digitsInNoOfNodes = len(str(len(G)))
		noOfDigitsInState = len(str(origNodes - 1))
		formatStrSingle = "\\l{}(state {{:0{}}}) ".format(" " * (4 + noOfDigitsInState), noOfDigitsInState)
		formatStrSuper = "\\l(states {{:0{}}} - {{:0{}}}) ".format(noOfDigitsInState, noOfDigitsInState)
		csvBody = ""

		# Write nodes
		for n in G.nodes(data=True):
			# Special treatment for end node
			if endNodeID == n[0]:
				outF.write("\tn{} [label=\"{}\"];\n".format(n[0], n[1]["label"]))
			else:
				label = n[1]["label"]
				interval = list(map(lambda x: int(x), n[0].split("to")))

				if csvFile is not None:
					csvBody += "{}\n".format(n[1]["label"])

				# If there are filtered lines, we should print them as well
				mergedFilteredLines = {}
				for i in range(interval[0], (interval[1] if 2 == len(interval) else interval[0]) + 1):
					if i in filteredLines:
						filteredLines2 = filteredLines[i]

						# Check for mergeable lines
						for filteredLine in filteredLines2:
							hasMerged = False

							for mergedIdx in mergedFilteredLines:
								for mergedLine in mergedFilteredLines[mergedIdx]:
									# We merge only if the list of operations is exactly the same and if there is continuity on the node count
									if mergedLine[1] == filteredLine and (mergedLine[0] + 1) == i:
										mergedLine[0] += 1
										hasMerged = True
										break

							# If no merge happened, we create a new element for this [super-]node
							if not hasMerged:
								if i not in mergedFilteredLines:
									mergedFilteredLines[i] = []
								mergedFilteredLines[i].append([i, filteredLine])

				for mergedIdx in mergedFilteredLines:
					for mergedLine in mergedFilteredLines[mergedIdx]:
						# Transaction not merged
						if mergedIdx == mergedLine[0]:
							# I apologise for this next line
							label += formatStrSingle.format(mergedIdx)
							if csvFile is not None:
								csvBody += "---,{},".format(mergedIdx)
						# Transaction merged
						else:
							label += formatStrSuper.format(mergedIdx, mergedLine[0])
							if csvFile is not None:
								csvBody += "{},{},".format(mergedIdx, mergedLine[0])

						label += ", ".join(mergedLine[1])
						if csvFile is not None:
							csvBody += ",".join(mergedLine[1])
							csvBody += "\n"

				if csvFile is not None:
					csvBody += "\n\n\n"

				outF.write("\tn{} [shape=record,label=\"{}\\l\"];\n".format(n[0], label))

		# Write edges
		for e in G.edges(data=True):
			if "true" == e[2]["label"]:
				outF.write("\tn{} -> n{};\n".format(e[0], e[1]))
			else:
				outF.write("\tn{} -> n{} [label=\"{}\"];\n".format(e[0], e[1], e[2]["label"]))

		# Finish .dot file
		outF.write("}\n")

		# Write csv file if applicable
		if csvFile is not None:
			with open(csvFile, "w") as csvF:
				csvF.write(csvBody)
