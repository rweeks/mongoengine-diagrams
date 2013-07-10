mongoengine-diagrams
====================

Class diagram generator for MongoEngine document schema

To use, start by editing class_diagram.py

* specify module names in MODULES list
* define custom object mappings in OID_MAP

Then, run `class_diagrams.py <db_host> <db_name>`, ensuring that all the modules in MODULES are in your pythonpath.

class_diagram produces output in [Graphviz .dot](http://www.graphviz.org/Documentation/dotguide.pdf) format.  Output is sent to stdout.  You can use Graphviz to do layout and render the graph to an image, or you can import the .dot file into your favorite diagramming tool (eg. OmniGraffle)