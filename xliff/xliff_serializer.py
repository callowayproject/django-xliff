# -*- coding: utf-8 -*-
"""
XLIFF serializer.
"""

from __future__ import unicode_literals

from django.conf import settings
from django.core.serializers import base
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.db import models, DEFAULT_DB_ALIAS
from django.utils.xmlutils import SimplerXMLGenerator
from django.utils.encoding import smart_text
from xml.dom import pulldom
from xml.sax import handler
from xml.sax.expatreader import ExpatParser as _ExpatParser
from collections import defaultdict

NATURAL_KEY_JOINER = u";"


class Serializer(base.Serializer):
    """
    Serializes a QuerySet to XML.
    """

    def _get_obj_pk(self, obj):
        """
        returns the objects pk or the natural key, joined
        """
        if self.use_natural_keys and hasattr(obj, 'natural_key'):
            raw_nat_key = obj.natural_key()
            obj_pk = smart_text(NATURAL_KEY_JOINER.join(raw_nat_key))
            keytype = 'natural'
        else:
            obj_pk = obj._get_pk_val()
            keytype = 'pk'

        return obj_pk, keytype

    def indent(self, level):
        if self.options.get('indent', None) is not None:
            self.xml.ignorableWhitespace('\n' + ' ' * self.options.get('indent', None) * level)

    def start_serialization(self):
        """
        Start serialization -- open the XML document and the root element.
        """
        self.xml = SimplerXMLGenerator(self.stream, self.options.get("encoding", settings.DEFAULT_CHARSET))
        self.xml.startDocument()
        self.xml.startElement("xliff", {
            "version": "1.2",
            "xmlns": "urn:oasis:names:tc:xliff:document:1.2",
            "xmlns:d": "https://docs.djangoproject.com/"
        })

    def start_fileblock(self, obj):
        """
        Start the <file><body> block
        """
        self.indent(1)
        obj_key, keytype = self._get_obj_pk(obj)
        self.xml.startElement("file", {
            "original": "%s.%s" % (smart_text(obj._meta), obj_key),
            "datatype": "database",
            "source-language": settings.LANGUAGE_CODE,
            "d:keytype": keytype,
        })
        self.xml.startElement("body", {})

    def end_fileblock(self):
        """
        End the <file><body> block
        """
        self.indent(1)
        self.xml.endElement("body")
        self.xml.endElement("file")

    def end_serialization(self):
        """
        End serialization -- end the document.
        """
        self.indent(0)
        self.xml.endElement("xliff")
        self.xml.endDocument()

    def start_object(self, obj):
        """
        Called as each object is handled.
        """
        if not hasattr(obj, "_meta"):
            raise base.SerializationError("Non-model object (%s) encountered during serialization" % type(obj))

        self.start_fileblock(obj)

        self.indent(2)

        obj_pk, keytype = self._get_obj_pk(obj)
        attrs = {
            "restype": "row",
            "d:keytype": keytype
        }
        if obj_pk is not None:
            attrs["resname"] = "%s.%s" % (smart_text(obj._meta), obj_pk)
        else:
            attrs["resname"] = smart_text(obj._meta)

        self.xml.startElement("group", attrs)

        if obj._meta.pk.__class__.__name__ != "AutoField":
            self.handle_field(obj, obj._meta.pk)

    def end_object(self, obj):
        """
        Called after handling all fields for an object.
        """
        self.indent(2)
        self.xml.endElement("group")
        self.indent(1)
        self.end_fileblock()

    def handle_field(self, obj, field):
        """
        Called to handle each field on an object (except for ForeignKeys and
        ManyToManyFields)
        """
        self.indent(3)
        internal_type = field.get_internal_type()
        attrs = {
            "id": field.name,
            "resname": field.name,
            "restype": "x-%s" % internal_type,
            "translate": "no",
        }
        if internal_type in ("CharField", "TextField"):
            attrs["translate"] = "yes"

        if internal_type == "CharField":
            attrs["size-unit"] = "char"
            attrs["maxwidth"] = str(field.max_length)

        self.xml.startElement("trans-unit", attrs)
        self.indent(4)
        self.xml.startElement("source", {})
        # Get a "string version" of the object's data.
        if getattr(obj, field.name) is not None:
            self.xml.characters(field.value_to_string(obj))
        else:
            self.xml.addQuickElement("None")

        self.xml.endElement("source")
        self.indent(3)
        self.xml.endElement("trans-unit")

    def handle_fk_field(self, obj, field):
        """
        Called to handle a ForeignKey (we need to treat them slightly
        differently from regular fields).
        """
        related_att = getattr(obj, field.get_attname())
        if related_att is not None:
            if self.use_natural_keys and hasattr(field.rel.to, 'natural_key'):
                self._start_relational_field(field, keytype="natural")
                related = getattr(obj, field.name)
                # If related object has a natural key, use it
                related = related.natural_key()
                nat_key = NATURAL_KEY_JOINER.join(related)
                self.xml.characters(smart_text(nat_key))
                # Iterable natural keys are rolled out as subelements
                # for key_value in related:
                #     self.xml.startElement("natural", {})
                #     self.xml.characters(smart_text(key_value))
                #     self.xml.endElement("natural")
            else:
                self._start_relational_field(field)
                self.xml.characters(smart_text(related_att))
        else:
            self._start_relational_field(field)
            self.xml.addQuickElement("None")
        self.xml.endElement("source")
        self.indent(3)
        self.xml.endElement("trans-unit")

    def handle_m2m_field(self, obj, field):
        """
        Called to handle a ManyToManyField. Related objects are only
        serialized as references to the object's PK (i.e. the related *data*
        is not dumped, just the relation).
        """
        if field.rel.through._meta.auto_created:
            # self._start_relational_field(field)
            if self.use_natural_keys and hasattr(field.rel.to, 'natural_key'):
                # If the objects in the m2m have a natural key, use it
                def handle_m2m(value):
                    natural = value.natural_key()
                    nat_key = NATURAL_KEY_JOINER.join(natural)
                    field_id = "%s.%s" % (obj.pk, nat_key)
                    self._start_relational_field(field, field_id=field_id, keytype="natural")
                    self.xml.characters(smart_text(nat_key))
                    self.xml.endElement("source")
                    self.indent(3)
                    self.xml.endElement("trans-unit")
                    # Iterable natural keys are rolled out as subelements
                    # self.xml.startElement("object", {})
                    # for key_value in natural:
                        # self.xml.startElement("natural", {})
                        # self.xml.characters(smart_text(key_value))
                        # self.xml.endElement("natural")
                    # self.xml.endElement("object")
            else:
                def handle_m2m(value):
                    field_id = "%s.%s" % (obj.pk, value._get_pk_val())
                    self._start_relational_field(field, field_id)
                    self.xml.characters(smart_text(value._get_pk_val()))
                    self.xml.endElement("source")
                    self.indent(3)
                    self.xml.endElement("trans-unit")
                    # self.xml.addQuickElement("object", attrs={
                    #     'pk' : smart_text(value._get_pk_val())
                    # })
            for relobj in getattr(obj, field.name).iterator():
                handle_m2m(relobj)

    def handle_gfk_field(self, obj, field):
        """
        Handle the GenericForeignKey
        <trans-unit id=<gfk.name>
        """
        obj_pk, keytype = self._get_obj_pk(getattr(obj, field.ct_field))
        attrs = {
            "id": field.name,
            "resname": field.name,
            "restype": "x-%s" % field.__class__.__name__,
            "translate": "no",
            "d:keytype": keytype,
            "d:rel": "GenericManyToOneRel",
            "d:to": obj_pk,
        }
        self.xml.startElement("trans-unit", attrs)
        self.indent(4)
        self.xml.startElement("source", {})
        # Get a "string version" of the object's data.
        gfk_obj = getattr(obj, field.name)
        if gfk_obj is not None:
            gfk_pk, keytype = self._get_obj_pk(gfk_obj)
            self.xml.characters(gfk_pk)
        else:
            self.xml.addQuickElement("None")

        self.xml.endElement("source")
        self.indent(3)
        self.xml.endElement("trans-unit")

    def _start_relational_field(self, field, field_id="", keytype="pk"):
        """
        Helper to output the <trans-unit> element for relational fields
        """
        self.indent(3)
        internal_type = field.get_internal_type()
        attrs = {
            "id": field_id or field.name,
            "resname": field.name,
            "restype": "x-%s" % internal_type,
            "translate": "no",
            "d:rel": field.rel.__class__.__name__,
            "d:to": smart_text(field.rel.to._meta),
            "d:keytype": keytype,
        }
        self.xml.startElement("trans-unit", attrs)
        self.indent(4)
        self.xml.startElement("source", {})


class Deserializer(base.Deserializer):
    """
    Deserialize XML.
    """

    def __init__(self, stream_or_string, **options):
        super(Deserializer, self).__init__(stream_or_string, **options)
        self.event_stream = pulldom.parse(self.stream, self._make_parser())
        self.db = options.pop('using', DEFAULT_DB_ALIAS)

    def _make_parser(self):
        """Create a hardened XML parser (no custom/external entities)."""
        return DefusedExpatParser()

    def __next__(self):
        for event, node in self.event_stream:
            if event == "START_ELEMENT" and node.nodeName == "group":
                self.event_stream.expandNode(node)
                return self._handle_object(node)
        raise StopIteration

    def next(self):
        """Iteration iterface -- return the next item in the stream"""
        return self.__next__()

    def _handle_object(self, node):
        """
        Convert an <group> node to a DeserializedObject.
        """
        # Look up the model using the model loading mechanism. If this fails,
        # bail.
        Model = self._get_model_from_node(node, "resname")

        # Start building a data dictionary from the object.
        # If the node is missing the pk set it to None
        bits = node.getAttribute("resname").split(".")
        keytype = node.getAttribute("d:keytype") or 'pk'
        if len(bits) == 3:
            pk = bits[2]
        else:
            pk = None

        data = {}

        if keytype == 'pk':
            data[Model._meta.pk.attname] = Model._meta.pk.to_python(pk)
        else:
            try:
                data[Model._meta.pk.attname] = Model.objects.get_by_natural_key(pk).pk
            except (Model.DoesNotExist, AttributeError):
                pass

        # Also start building a dict of m2m data (this is saved as
        # {m2m_accessor_attribute : [list_of_related_objects]})
        m2m_data = defaultdict(list)

        # Create a reference for genericForeignKeys, if necessary
        virtual_fields = dict([(x.name, x) for x in Model._meta.virtual_fields])

        # Deseralize each field.
        for field_node in node.getElementsByTagName("trans-unit"):
            # If the field is missing the name attribute, bail (are you
            # sensing a pattern here?)
            field_name = field_node.getAttribute("resname")
            if not field_name:
                raise base.DeserializationError("<trans-unit> node is missing the 'resname' attribute")

            # Get the field from the Model. This will raise a
            # FieldDoesNotExist if, well, the field doesn't exist, which will
            # be propagated correctly.
            try:
                field = Model._meta.get_field(field_name)
            except:
                if field_name in virtual_fields:
                    field = virtual_fields[field_name]
                else:
                    raise

            # As is usually the case, relation fields get the special treatment.
            if isinstance(field, GenericForeignKey):
                data[field.name] = self._handle_gfk_field_node(field_node, field)
            elif field.rel and isinstance(field.rel, models.ManyToManyRel):
                # There can be multiple instances since each relation has its own tag
                m2m_data[field.name].append(self._handle_m2m_field_node(field_node, field))
            elif field.rel and isinstance(field.rel, models.ManyToOneRel):
                data[field.attname] = self._handle_fk_field_node(field_node, field)
            else:
                if field_node.getElementsByTagName('None'):
                    value = None
                else:
                    tag = field_node.getElementsByTagName('target')
                    if len(tag) == 0:
                        tag = field_node.getElementsByTagName('source')
                    if len(tag) != 0:
                        value = field.to_python(getInnerText(tag[0]).strip())
                    else:
                        value = None
                data[field.name] = value

        # Return a DeserializedObject so that the m2m data has a place to live.
        return base.DeserializedObject(Model(**data), m2m_data)

    def _handle_fk_field_node(self, node, field):
        """
        Handle a <trans-unit> node for a ForeignKey
        """
        # Check if there is a child node named 'None', returning None if so.
        if node.getElementsByTagName('None'):
            return None
        else:
            if hasattr(field.rel.to._default_manager, 'get_by_natural_key'):
                keytype = node.getAttribute('d:keytype')
                value = getInnerText(node).strip()
                if keytype == 'natural':
                    field_value = value.split(NATURAL_KEY_JOINER)
                    obj = field.rel.to._default_manager.db_manager(self.db).get_by_natural_key(*field_value)
                    obj_pk = getattr(obj, field.rel.field_name)
                    # If this is a natural foreign key to an object that
                    # has a FK/O2O as the foreign key, use the FK value
                    if field.rel.to._meta.pk.rel:
                        obj_pk = obj_pk.pk
                else:
                    obj_pk = field.rel.to._meta.get_field(field.rel.field_name).to_python(value)
                return obj_pk
            else:
                field_value = getInnerText(node).strip()
                return field.rel.to._meta.get_field(field.rel.field_name).to_python(field_value)

    def _handle_m2m_field_node(self, node, field):
        """
        Handle a <trans-unit> node for a ManyToManyField.
        """
        if hasattr(field.rel.to._default_manager, 'get_by_natural_key'):
            keytype = node.getAttribute('d:keytype')
            value = getInnerText(node).strip()
            if keytype == 'natural':
                field_value = value.split(NATURAL_KEY_JOINER)
                obj_pk = field.rel.to._default_manager.db_manager(self.db).get_by_natural_key(*field_value).pk
            else:
                obj_pk = field.rel.to._meta.pk.to_python(value)
            return obj_pk
        else:
            return field.rel.to._meta.pk.to_python(getInnerText(node).strip())

    def _handle_gfk_field_node(self, node, field):
        """
        Handle a <trans-unit> for a GenericForeignKey
        """
        if node.getElementsByTagName('None'):
            return None
        ct_key = node.getAttribute("d:to").split(NATURAL_KEY_JOINER)
        ctype = ContentType.objects.get_by_natural_key(*ct_key)
        Model = ctype.model_class()
        if hasattr(Model._default_manager, 'get_by_natural_key'):
            value = getInnerText(node).strip()
            field_value = value.split(NATURAL_KEY_JOINER)
            obj = Model._default_manager.db_manager(self.db).get_by_natural_key(*field_value)
            return obj
        else:
            field_value = getInnerText(node).strip()
            return Model._default_manager.db_manager(self.db).get(pk=Model._meta.pk.to_python(field_value))

    def _get_model_from_node(self, node, attr):
        """
        Helper to look up a model from a <group resname=...> or a <trans-unit
        d:rel=... d:to=...> node.
        """
        model_identifier = node.getAttribute(attr)
        if not model_identifier:
            raise base.DeserializationError(
                "<%s> node is missing the required '%s' attribute" \
                    % (node.nodeName, attr))
        try:
            Model = models.get_model(*model_identifier.split(".")[:2])
        except TypeError:
            Model = None
        if Model is None:
            raise base.DeserializationError(
                "<%s> node has invalid model identifier: '%s'" % \
                    (node.nodeName, model_identifier))
        return Model


def getInnerText(node):
    """
    Get all the inner text of a DOM node (recursively).
    """
    # inspired by http://mail.python.org/pipermail/xml-sig/2005-March/011022.html
    inner_text = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE or child.nodeType == child.CDATA_SECTION_NODE:
            inner_text.append(child.data)
        elif child.nodeType == child.ELEMENT_NODE:
            inner_text.extend(getInnerText(child))
        else:
            pass
    return "".join(inner_text)


# Below code based on Christian Heimes' defusedxml


class DefusedExpatParser(_ExpatParser):
    """
    An expat parser hardened against XML bomb attacks.

    Forbids DTDs, external entity references

    """
    def __init__(self, *args, **kwargs):
        _ExpatParser.__init__(self, *args, **kwargs)
        self.setFeature(handler.feature_external_ges, False)
        self.setFeature(handler.feature_external_pes, False)

    def start_doctype_decl(self, name, sysid, pubid, has_internal_subset):
        raise DTDForbidden(name, sysid, pubid)

    def entity_decl(self, name, is_parameter_entity, value, base,
                    sysid, pubid, notation_name):
        raise EntitiesForbidden(name, value, base, sysid, pubid, notation_name)

    def unparsed_entity_decl(self, name, base, sysid, pubid, notation_name):
        # expat 1.2
        raise EntitiesForbidden(name, None, base, sysid, pubid, notation_name)

    def external_entity_ref_handler(self, context, base, sysid, pubid):
        raise ExternalReferenceForbidden(context, base, sysid, pubid)

    def reset(self):
        _ExpatParser.reset(self)
        parser = self._parser
        parser.StartDoctypeDeclHandler = self.start_doctype_decl
        parser.EntityDeclHandler = self.entity_decl
        parser.UnparsedEntityDeclHandler = self.unparsed_entity_decl
        parser.ExternalEntityRefHandler = self.external_entity_ref_handler


class DefusedXmlException(ValueError):
    """Base exception."""
    def __repr__(self):
        return str(self)


class DTDForbidden(DefusedXmlException):
    """Document type definition is forbidden."""
    def __init__(self, name, sysid, pubid):
        super(DTDForbidden, self).__init__()
        self.name = name
        self.sysid = sysid
        self.pubid = pubid

    def __str__(self):
        tpl = "DTDForbidden(name='{}', system_id={!r}, public_id={!r})"
        return tpl.format(self.name, self.sysid, self.pubid)


class EntitiesForbidden(DefusedXmlException):
    """Entity definition is forbidden."""
    def __init__(self, name, value, base, sysid, pubid, notation_name):
        super(EntitiesForbidden, self).__init__()
        self.name = name
        self.value = value
        self.base = base
        self.sysid = sysid
        self.pubid = pubid
        self.notation_name = notation_name

    def __str__(self):
        tpl = "EntitiesForbidden(name='{}', system_id={!r}, public_id={!r})"
        return tpl.format(self.name, self.sysid, self.pubid)


class ExternalReferenceForbidden(DefusedXmlException):
    """Resolving an external reference is forbidden."""
    def __init__(self, context, base, sysid, pubid):
        super(ExternalReferenceForbidden, self).__init__()
        self.context = context
        self.base = base
        self.sysid = sysid
        self.pubid = pubid

    def __str__(self):
        tpl = "ExternalReferenceForbidden(system_id='{}', public_id={})"
        return tpl.format(self.sysid, self.pubid)
