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
import re, sys


if "__main__" == __name__:
	if len(sys.argv) != 3:
		sys.stderr.write("Usage: {} RPTFILE DOTFILE\n".format(sys.argv[0]))
		sys.stderr.write("  where:\n")
		sys.stderr.write("    RPTFILE: generated *.verbose.sched.rpt file\n")
		sys.stderr.write("    DOTFILE: output dot file\n")
		exit(1)

	rptFile = sys.argv[1]
	dotFile = sys.argv[2]

	with open(rptFile, "r") as inF, open(dotFile, "w") as outF:
		currentNode = -2
		endNodeID = None
		nodeRegex = re.compile("(\\d+) --> \n")
		edgeRegex = re.compile("\t(\\d+)[ ]*/ (.*)")
		endNodeRegex = re.compile("ST_(\\d+) : .*\"ret void\".*<Predicate = (.*)> <Delay.*")

		G = nx.DiGraph()

		for line in inF:
			# Searching for beginning of FSM
			if -2 == currentNode:
				if "* FSM state transitions: \n" == line:
					currentNode = 0
			# End of FSM, searching for end node
			elif -1 == currentNode:
				endNodeMatch = endNodeRegex.match(line)
				# End node found, add it and the incoming edge
				if endNodeMatch is not None:
					endNodeID = str(len(G.nodes()) + 1)
					G.add_node(endNodeID, label="end")
					G.add_edge(str(endNodeMatch.group(1)), endNodeID, label=endNodeMatch.group(2))
					break
			# Inside FSM
			else:
				# FSM states were already found, if the header is found again, this is unexpected
				if "* FSM state transitions: \n" == line:
					raise RuntimeError("Input file is corrupt")
				# This indicates the end of the FSM. Will search for end node now.
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
		outF.write("digraph \"FSM\" {\n")

		# Write nodes
		for n in G.nodes(data=True):
			# Special treatment for end node
			if endNodeID == n[0]:
				outF.write("\tn{} [label=\"{}\"];\n".format(n[0], n[1]["label"]))
			else:
				outF.write("\tn{} [shape=record,label=\"{}\"];\n".format(n[0], n[1]["label"]))

		# Write edges
		for e in G.edges(data=True):
			if "true" == e[2]["label"]:
				outF.write("\tn{} -> n{};\n".format(e[0], e[1]))
			else:
				outF.write("\tn{} -> n{} [label=\"{}\"];\n".format(e[0], e[1], e[2]["label"]))

		# Finish .dot file
		outF.write("}\n")
