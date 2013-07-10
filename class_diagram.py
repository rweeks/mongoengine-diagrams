from collections import defaultdict
from cStringIO import StringIO

# List of module names to process
MODULES=["model"]

# Maps fully-qualified field name to a document type, indicating an assocation
# between classes.
# Useful for fields like ObjectIdField or fields which reference other documents
# but not by ReferenceField.
#
# for example,
# OID_MAP={
#     "model.User.username": "model.legacy.User"
# }
OID_MAP={
    "model.drugs.StandardFrequencies.active_ingredient":"model.drugs.ActiveIngredient",
    "model.meds.MedOrder.active_ingredient":"model.drugs.ActiveIngredient",
    "model.allergies.AllergyUpdate.substance_din":"model.drugs.Drug",
    "model.allergies.DrugAllergy.substance_din":"model.drugs.Drug",
    "model.visit.Visit.patient_id":"model.patient.Patient",
    "model.sphafib.requisitions.Requisition.visit_id":"model.visit.Visit",
    "model.sphafib.requisitions.Requisition.pt_id":"model.patient.Patient",
    "model.sphafib.charts.ModalityFilter.user":"model.user.User",
    "model.sphafib.allergies.Assessment.visit_id":"model.visit.Visit",
    "model.sphafib.allergies.Assessment.pt_id":"model.patient.Patient"
}

class Edge():
    def __init__(self, dst, **kwargs):
        self.dst = dst
        self.props = kwargs

    @property
    def style(self):
        from cStringIO import StringIO
        out = StringIO()
        out.write('[')
        out.write(
            ', '.join([
                '%s="%s"' % (k, str(v)) for k, v in self.props.iteritems()
                ]
            )
        )
        out.write(']')
        return out.getvalue()

def process_fields(clazz):
    """Process all of the MongoEngine fields in a given class"""
    from mongoengine.base.fields import BaseField
    return dict(filter(lambda x:isinstance(x[1], BaseField),
                       clazz.__dict__.iteritems()))

def process_module(module):
    """Process all of the BaseDocument subclasses in a given module"""
    import inspect
    from mongoengine.base.document import BaseDocument
    m_classes = inspect.getmembers(module, inspect.isclass)
    nested_classes = []
    for m_class in m_classes:
        nested_classes += inspect.getmembers(m_class[1], inspect.isclass)
    m_classes += nested_classes # class namespace problem here... oh well
    m_docs = filter(lambda x:issubclass(x[1], BaseDocument), m_classes)
    m_docs = filter(lambda x:not x[1].__module__.startswith('mongoengine'), m_docs)
    return dict(map(lambda x: (x, process_fields(x)), map(lambda x:x[1], m_docs)))

def one_to_one(dst):
    return Edge(dst, arrowhead='none', arrowtail='none')

def one_to_many(dst):
    return Edge(dst, arrowhead='none', arrowtail='none', headlabel="*",
                taillabel="1")

def superclass(dst): # dst is the parent class
    return Edge(dst, arrowhead='normal', arrowtail='normal')

def fullname(clazz):
    return clazz.__module__ + "." + clazz.__name__

def get_association(clazz, field_name, field, edge_fac=one_to_one):
    from mongoengine.fields import ReferenceField, ListField, \
        EmbeddedDocumentField, ObjectIdField
    from utils import load_class
    dst = None
    fq_field = fullname(clazz) + "." + field_name
    if isinstance(field, ListField):
        return get_association(clazz, field_name, field.field, one_to_many)
    elif isinstance(field, ReferenceField):
        dst = field.document_type
    elif isinstance(field, EmbeddedDocumentField):
        dst = field.document_type
    elif fq_field in OID_MAP:
        dst = load_class(OID_MAP.get(fq_field, None))
    if field_name != "id" and isinstance(field, ObjectIdField) and dst is None:
        print "Warning: %s does not have mapping" % fq_field
    return edge_fac(dst) if dst is not None else None

def find_associations(nodes):
    edges = defaultdict(lambda:[])
    for clazz, fields in nodes.iteritems():
        for field_name, field in fields.iteritems():
            edge = get_association(clazz, field_name, field)
            if edge is not None:
                edges[clazz].append(edge)
    return edges

def find_class_hierarchy(nodes):
    edges=defaultdict(lambda:[])
    for clazz in nodes:
        for super_clazz in clazz.__bases__:
            if super_clazz in nodes:
                edges[clazz].append(superclass(super_clazz))
    return edges

def create_dot(nodes, assocs, hierarchy):
    """Generates a graphviz .dot file based on the given nodes, object associations
    and class hierarchy"""
    def field_names(fields):
        return ' | '.join(sorted(fields))
    out = StringIO()
    print >> out, "digraph phemi_class_diagram {"
    print >> out, "  node[shape=record];"
    for clazz, fields in nodes.iteritems():
        print >> out, '  "%s" [label="{%s | %s}"];' % (
            fullname(clazz), clazz.__name__, field_names(fields)
        )
    for edgemap in [assocs, hierarchy]:
        for clazz, edges in edgemap.iteritems():
            for edge in edges:
                print >> out, '  "%s" -> "%s" %s' % (
                    fullname(clazz), fullname(edge.dst), edge.style
                )
    print >> out, "}"
    return out.getvalue()

def main():
    from pkgutil import iter_modules
    from importlib import import_module
    nodes = {}
    to_import = [(m_name,None) for m_name in MODULES]
    modules = []
    while len(to_import):
        m_name, parent = to_import.pop()
        if parent is not None:
            module = import_module('.' + m_name, parent.__name__)
        else:
            module = import_module(m_name)
        modules.append(module)
        if hasattr(module,"__path__"):    # it's a package
            for submod in iter_modules(module.__path__):
                to_import.append((submod[1], module))
    for module in modules:
        nodes.update(process_module(module))
    assocs = find_associations(nodes)
    hierarchy = find_class_hierarchy(nodes)
    print create_dot(nodes, assocs, hierarchy)

if __name__ == "__main__":
    # MongoEngine classes won't load unless a DB connection is available
    # (but we don't actually hit the DB for anything)
    from argparse import ArgumentParser
    parser = ArgumentParser(description="""
    Generate a UML Class Diagram of a MongoEngine document model. The diagram
    is in .dot format and is emitted on stdout."""
    )
    parser.add_argument('db_host', help="Mongo DB Host")
    parser.add_argument('db_name', help="Mongo DB Name")
    parser.add_argument('--db_port', type=int, help="Mongo DB Port",
                        default=27017)
    args = parser.parse_args()
    from mongoengine.connection import connect
    connect(args.db_name, host=args.db_host, port=args.db_port)
    main()