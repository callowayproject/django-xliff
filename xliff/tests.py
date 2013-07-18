from __future__ import absolute_import, unicode_literals

# -*- coding: utf-8 -*-
import datetime
from xml.dom import minidom

from django.conf import settings
from django.core import serializers
from django.db import transaction, connection
from django.test import TestCase, TransactionTestCase, Approximate
from django.utils import six
from django.utils import unittest

from django.core.serializers import SerializerDoesNotExist
from django.db import models
from django.http import HttpResponse
from django.utils.functional import curry

from simpleapp.models import (BooleanData, CharData, DateData, DateTimeData, EmailData,
    FileData, FilePathData, DecimalData, FloatData, IntegerData, IPAddressData,
    GenericIPAddressData, NullBooleanData, PositiveIntegerData,
    PositiveSmallIntegerData, SlugData, SmallData, TextData, TimeData,
    GenericData, Anchor, UniqueAnchor, FKData, M2MData, O2OData,
    FKSelfData, M2MSelfData, FKDataToField, FKDataToO2O, M2MIntermediateData,
    Intermediate, BooleanPKData, CharPKData, EmailPKData, FilePathPKData,
    DecimalPKData, FloatPKData, IntegerPKData, IPAddressPKData,
    GenericIPAddressPKData, PositiveIntegerPKData,
    PositiveSmallIntegerPKData, SlugPKData, SmallPKData,
    AutoNowDateTimeData, ModifyingSaveData, InheritAbstractModel, BaseModel,
    ExplicitInheritBaseModel, InheritBaseModel, ProxyBaseModel,
    ProxyProxyBaseModel, BigIntegerData, LengthModel, Tag, ComplexModel,
    NaturalKeyAnchor, FKDataNaturalKey)

from simpleapp.models import (Category, Author, Article, AuthorProfile, Actor, Movie,
    Score, Player, Team)


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


class SerializerRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.old_SERIALIZATION_MODULES = getattr(settings, 'SERIALIZATION_MODULES', None)
        self.old_serializers = serializers._serializers

        serializers._serializers = {}
        settings.SERIALIZATION_MODULES = {
            'xliff': 'xliff.xliff_serializer'
        }

    def tearDown(self):
        serializers._serializers = self.old_serializers
        if self.old_SERIALIZATION_MODULES:
            settings.SERIALIZATION_MODULES = self.old_SERIALIZATION_MODULES
        else:
            delattr(settings, 'SERIALIZATION_MODULES')

    def test_register(self):
        "Registering a new serializer populates the full registry. Refs #14823"
        serializers.register_serializer('xliff', 'xliff.xliff_serializer')

        public_formats = serializers.get_public_serializer_formats()
        self.assertIn('xliff', public_formats)

    def test_unregister(self):
        "Unregistering a serializer doesn't cause the registry to be repopulated. Refs #14823"
        serializers.unregister_serializer('xliff')

        public_formats = serializers.get_public_serializer_formats()

        self.assertNotIn('xliff', public_formats)


class SerializersTestBase(object):
    @staticmethod
    def _comparison_value(value):
        return value

    def setUp(self):
        sports = Category.objects.create(name="Sports")
        music = Category.objects.create(name="Music")
        op_ed = Category.objects.create(name="Op-Ed")

        self.joe = Author.objects.create(name="Joe")
        self.jane = Author.objects.create(name="Jane")

        self.a1 = Article(
            author=self.jane,
            headline="Poker has no place on ESPN",
            pub_date=datetime.datetime(2006, 6, 16, 11, 00)
        )
        self.a1.save()
        self.a1.categories = [sports, op_ed]

        self.a2 = Article(
            author=self.joe,
            headline="Time to reform copyright",
            pub_date=datetime.datetime(2006, 6, 16, 13, 00, 11, 345)
        )
        self.a2.save()
        self.a2.categories = [music, op_ed]

    def test_serialize(self):
        """Tests that basic serialization works."""
        serial_str = serializers.serialize(self.serializer_name,
                                           Article.objects.all())
        self.assertTrue(self._validate_output(serial_str))

    def test_serializer_roundtrip(self):
        """Tests that serialized content can be deserialized."""
        serial_str = serializers.serialize(self.serializer_name,
                                           Article.objects.all())
        modellist = list(serializers.deserialize(self.serializer_name, serial_str))
        self.assertEqual(len(modellist), 2)

    def test_altering_serialized_output(self):
        """
        Tests the ability to create new objects by
        modifying serialized content.
        """
        old_headline = "Poker has no place on ESPN"
        new_headline = "Poker has no place on television"
        serial_str = serializers.serialize(self.serializer_name,
                                           Article.objects.all())
        serial_str = serial_str.replace(old_headline, new_headline)
        modellist = list(serializers.deserialize(self.serializer_name, serial_str))

        # Prior to saving, old headline is in place
        self.assertTrue(Article.objects.filter(headline=old_headline))
        self.assertFalse(Article.objects.filter(headline=new_headline))

        for model in modellist:
            model.save()

        # After saving, new headline is in place
        self.assertTrue(Article.objects.filter(headline=new_headline))
        self.assertFalse(Article.objects.filter(headline=old_headline))

    def test_one_to_one_as_pk(self):
        """
        Tests that if you use your own primary key field
        (such as a OneToOneField), it doesn't appear in the
        serialized field list - it replaces the pk identifier.
        """
        return

        # I don't understand the importance of this test or how the others do
        # it. It doesn't seem to matter either way.
        profile = AuthorProfile(author=self.joe,
                                date_of_birth=datetime.datetime(1970, 1, 1))
        profile.save()
        serial_str = serializers.serialize(self.serializer_name,
                                           AuthorProfile.objects.all())
        self.assertFalse(self._get_field_values(serial_str, 'author'))

        for obj in serializers.deserialize(self.serializer_name, serial_str):
            self.assertEqual(obj.object.pk, self._comparison_value(self.joe.pk))

    def test_serialize_field_subset(self):
        """Tests that output can be restricted to a subset of fields"""
        valid_fields = ('headline', 'pub_date')
        invalid_fields = ("author", "categories")
        serial_str = serializers.serialize(self.serializer_name,
                                    Article.objects.all(),
                                    fields=valid_fields)
        for field_name in invalid_fields:
            self.assertFalse(self._get_field_values(serial_str, field_name))

        for field_name in valid_fields:
            self.assertTrue(self._get_field_values(serial_str, field_name))

    def test_serialize_unicode(self):
        """Tests that unicode makes the roundtrip intact"""
        actor_name = "Za\u017c\u00f3\u0142\u0107"
        movie_title = 'G\u0119\u015bl\u0105 ja\u017a\u0144'
        ac = Actor(name=actor_name)
        mv = Movie(title=movie_title, actor=ac)
        ac.save()
        mv.save()

        serial_str = serializers.serialize(self.serializer_name, [mv])
        self.assertEqual(self._get_field_values(serial_str, "title")[0], movie_title)
        self.assertEqual(self._get_field_values(serial_str, "actor")[0], actor_name)

        obj_list = list(serializers.deserialize(self.serializer_name, serial_str))
        mv_obj = obj_list[0].object
        self.assertEqual(mv_obj.title, movie_title)

    def test_serialize_superfluous_queries(self):
        """Ensure no superfluous queries are made when serializing ForeignKeys

        #17602
        """
        ac = Actor(name='Actor name')
        ac.save()
        mv = Movie(title='Movie title', actor_id=ac.pk)
        mv.save()

        with self.assertNumQueries(0):
            serial_str = serializers.serialize(self.serializer_name, [mv])

    def test_serialize_with_null_pk(self):
        """
        Tests that serialized data with no primary key results
        in a model instance with no id
        """
        category = Category(name="Reference")
        serial_str = serializers.serialize(self.serializer_name, [category])
        pk_value = self._get_pk_values(serial_str)[0]
        self.assertFalse(pk_value)

        cat_obj = list(serializers.deserialize(self.serializer_name,
                                               serial_str))[0].object
        self.assertEqual(cat_obj.id, None)

    def test_float_serialization(self):
        """Tests that float values serialize and deserialize intact"""
        sc = Score(score=3.4)
        sc.save()
        serial_str = serializers.serialize(self.serializer_name, [sc])
        deserial_objs = list(serializers.deserialize(self.serializer_name,
                                                serial_str))
        self.assertEqual(deserial_objs[0].object.score, Approximate(3.4, places=1))

    def test_custom_field_serialization(self):
        """Tests that custom fields serialize and deserialize intact"""
        team_str = "Spartak Moskva"
        player = Player()
        player.name = "Soslan Djanaev"
        player.rank = 1
        player.team = Team(team_str)
        player.save()
        serial_str = serializers.serialize(self.serializer_name,
                                           Player.objects.all())
        team = self._get_field_values(serial_str, "team")
        self.assertTrue(team)
        self.assertEqual(team[0], team_str)

        deserial_objs = list(serializers.deserialize(self.serializer_name, serial_str))
        self.assertEqual(deserial_objs[0].object.team.to_string(),
                         player.team.to_string())

    def test_pre_1000ad_date(self):
        """Tests that year values before 1000AD are properly formatted"""
        # Regression for #12524 -- dates before 1000AD get prefixed
        # 0's on the year
        a = Article.objects.create(
            author=self.jane,
            headline="Nobody remembers the early years",
            pub_date=datetime.datetime(1, 2, 3, 4, 5, 6)
        )

        serial_str = serializers.serialize(self.serializer_name, [a])
        date_values = self._get_field_values(serial_str, "pub_date")
        self.assertEqual(date_values[0].replace('T', ' '), "0001-02-03 04:05:06")

    def test_pkless_serialized_strings(self):
        """
        Tests that serialized strings without PKs
        can be turned into models
        """
        deserial_objs = list(serializers.deserialize(self.serializer_name,
                                                     self.pkless_str))
        for obj in deserial_objs:
            self.assertFalse(obj.object.id)
            obj.save()
        self.assertEqual(Category.objects.all().count(), 5)


class SerializersTransactionTestBase(object):
    def test_forward_refs(self):
        """
        Tests that objects ids can be referenced before they are
        defined in the serialization data.
        """
        # The deserialization process needs to be contained
        # within a transaction in order to test forward reference
        # handling.
        transaction.enter_transaction_management()
        transaction.managed(True)
        objs = serializers.deserialize(self.serializer_name, self.fwd_ref_str)
        with connection.constraint_checks_disabled():
            for obj in objs:
                obj.save()
        transaction.commit()
        transaction.leave_transaction_management()

        for model_cls in (Category, Author, Article):
            self.assertEqual(model_cls.objects.all().count(), 1)
        art_obj = Article.objects.all()[0]
        self.assertEqual(art_obj.categories.all().count(), 1)
        self.assertEqual(art_obj.author.name, "Agnes")


class XliffSerializerTestCase(SerializersTestBase, TestCase):
    serializer_name = "xliff"
    pkless_str = """<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns:d="https://docs.djangoproject.com/" version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
    <file datatype="database" source-language="en-us" original="simpleapp.category"><body>
        <group resname="simpleapp.category" restype="row">
            <trans-unit maxwidth="20" restype="x-CharField" size-unit="char" resname="name" translate="yes" id="name">
                <source>Reference</source>
            </trans-unit>
        </group>
    </body></file>
    <file datatype="database" source-language="en-us" original="simpleapp.category"><body>
        <group resname="simpleapp.category" restype="row">
            <trans-unit maxwidth="20" restype="x-CharField" size-unit="char" resname="name" translate="yes" id="name">
                <source>Non-fiction</source>
            </trans-unit>
        </group>
    </body></file>
</xliff>"""

    @staticmethod
    def _comparison_value(value):
        # The XML serializer handles everything as strings, so comparisons
        # need to be performed on the stringified value
        return six.text_type(value)

    @staticmethod
    def _validate_output(serial_str):
        try:
            minidom.parseString(serial_str)
        except Exception:
            return False
        else:
            return True

    @staticmethod
    def _get_pk_values(serial_str):
        ret_list = []
        dom = minidom.parseString(serial_str)
        fields = dom.getElementsByTagName("group")
        for field in fields:
            bits = field.getAttribute("resname").split(".")
            if len(bits) == 3:
                ret_list.append(bits[2])
            else:
                ret_list.append(None)
        return ret_list

    @staticmethod
    def _get_field_values(serial_str, field_name):
        ret_list = []
        dom = minidom.parseString(serial_str)
        fields = dom.getElementsByTagName("trans-unit")
        for field in fields:
            if field.getAttribute("resname") == field_name:
                temp = []
                for child in field.childNodes:
                    temp.append(getInnerText(child))
                ret_list.append("".join(temp))
        return ret_list

    def test_import_translation(self):
        """
        It should import the target text, if available
        """
        orig = "Poker has no place on ESPN"
        old_headline = "<source>%s</source>" % orig
        translation = "Poker hat keinen Platz im Fernsehen"
        new_headline = '%s<target xml:lang="de">%s</target>' % (old_headline, translation)
        serial_str = serializers.serialize(self.serializer_name,
                                           Article.objects.all())
        serial_str = serial_str.replace(old_headline, new_headline)
        modellist = list(serializers.deserialize(self.serializer_name, serial_str))

        # Prior to saving, old headline is in place
        self.assertTrue(Article.objects.filter(headline=orig))
        self.assertFalse(Article.objects.filter(headline=translation))

        for model in modellist:
            model.save()

        # After saving, new headline is in place
        self.assertTrue(Article.objects.filter(headline=translation))
        self.assertFalse(Article.objects.filter(headline=orig))


class XliffSerializerTransactionTestCase(SerializersTransactionTestBase, TransactionTestCase):
    serializer_name = "xliff"
    fwd_ref_str = """<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns:d="https://docs.djangoproject.com/" version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
    <file datatype="database" source-language="en-us" original="simpleapp.article.1"><body>
        <group resname="simpleapp.article.1" restype="row">
            <trans-unit d:keytype="pk" d:to="simpleapp.author" restype="x-ForeignKey" d:rel="ManyToOneRel" resname="author" translate="no" id="author">
                <source>1</source>
            </trans-unit>
            <trans-unit maxwidth="50" restype="x-CharField" size-unit="char" resname="headline" translate="yes" id="headline">
                <source>Forward references pose no problem</source>
            </trans-unit>
            <trans-unit resname="pub_date" translate="no" id="pub_date" restype="x-DateTimeField">
                <source>2006-06-16T15:00:00</source>
            </trans-unit>
            <trans-unit d:keytype="pk" d:to="simpleapp.category" restype="x-ManyToManyField" d:rel="ManyToManyRel" resname="categories" translate="no" id="1.1">
                <source>1</source>
            </trans-unit>
        </group>
    </body></file>
    <file datatype="database" source-language="en-us" original="simpleapp.author.1"><body>
        <group resname="simpleapp.author.1" restype="row">
            <trans-unit maxwidth="20" restype="x-CharField" size-unit="char" resname="name" translate="yes" id="name">
                <source>Agnes</source>
            </trans-unit>
        </group>
    </body></file>
    <file datatype="database" source-language="en-us" original="simpleapp.category.1"><body>
        <group resname="simpleapp.category.1" restype="row">
            <trans-unit maxwidth="20" restype="x-CharField" size-unit="char" resname="name" translate="yes" id="name">
                <source>Reference</source>
            </trans-unit>
        </group>
    </body></file>
</xliff>"""


"""
A test spanning all the capabilities of all the serializers.

This class defines sample data and a dynamically generated
test case that is capable of testing the capabilities of
the serializers. This includes all valid data values, plus
forward, backwards and self references.
"""

import decimal
from django.core.serializers.xml_serializer import DTDForbidden


# A set of functions that can be used to recreate
# test data objects of various kinds.
# The save method is a raw base model save, to make
# sure that the data in the database matches the
# exact test case.
def data_create(pk, klass, data):
    instance = klass(id=pk)
    instance.data = data
    models.Model.save_base(instance, raw=True)
    return [instance]


def generic_create(pk, klass, data):
    instance = klass(id=pk)
    instance.data = data[0]
    models.Model.save_base(instance, raw=True)
    for tag in data[1:]:
        instance.tags.create(data=tag)
    return [instance]


def fk_create(pk, klass, data):
    instance = klass(id=pk)
    setattr(instance, 'data_id', data)
    models.Model.save_base(instance, raw=True)
    return [instance]


def m2m_create(pk, klass, data):
    instance = klass(id=pk)
    models.Model.save_base(instance, raw=True)
    instance.data = data
    return [instance]


def im2m_create(pk, klass, data):
    instance = klass(id=pk)
    models.Model.save_base(instance, raw=True)
    return [instance]


def im_create(pk, klass, data):
    instance = klass(id=pk)
    instance.right_id = data['right']
    instance.left_id = data['left']
    if 'extra' in data:
        instance.extra = data['extra']
    models.Model.save_base(instance, raw=True)
    return [instance]


def o2o_create(pk, klass, data):
    instance = klass()
    instance.data_id = data
    models.Model.save_base(instance, raw=True)
    return [instance]


def pk_create(pk, klass, data):
    instance = klass()
    instance.data = data
    models.Model.save_base(instance, raw=True)
    return [instance]


def inherited_create(pk, klass, data):
    instance = klass(id=pk, **data)
    # This isn't a raw save because:
    #  1) we're testing inheritance, not field behavior, so none
    #     of the field values need to be protected.
    #  2) saving the child class and having the parent created
    #     automatically is easier than manually creating both.
    models.Model.save(instance)
    created = [instance]
    for klass, field in instance._meta.parents.items():
        created.append(klass.objects.get(id=pk))
    return created


# A set of functions that can be used to compare
# test data objects of various kinds
def data_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    testcase.assertEqual(data, instance.data,
         "Objects with PK=%d not equal; expected '%s' (%s), got '%s' (%s)" % (
            pk, data, type(data), instance, type(instance.data))
    )


def generic_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    testcase.assertEqual(data[0], instance.data)
    testcase.assertEqual(data[1:], [t.data for t in instance.tags.order_by('id')])


def fk_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    testcase.assertEqual(data, instance.data_id)


def m2m_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    testcase.assertEqual(data, [obj.id for obj in instance.data.order_by('id')])


def im2m_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    #actually nothing else to check, the instance just should exist


def im_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    testcase.assertEqual(data['left'], instance.left_id)
    testcase.assertEqual(data['right'], instance.right_id)
    if 'extra' in data:
        testcase.assertEqual(data['extra'], instance.extra)
    else:
        testcase.assertEqual("doesn't matter", instance.extra)


def o2o_compare(testcase, pk, klass, data):
    instance = klass.objects.get(data=data)
    testcase.assertEqual(data, instance.data_id)


def pk_compare(testcase, pk, klass, data):
    instance = klass.objects.get(data=data)
    testcase.assertEqual(data, instance.data)


def inherited_compare(testcase, pk, klass, data):
    instance = klass.objects.get(id=pk)
    for key, value in data.items():
        testcase.assertEqual(value, getattr(instance, key))

# Define some data types. Each data type is
# actually a pair of functions; one to create
# and one to compare objects of that type
data_obj = (data_create, data_compare)
generic_obj = (generic_create, generic_compare)
fk_obj = (fk_create, fk_compare)
m2m_obj = (m2m_create, m2m_compare)
im2m_obj = (im2m_create, im2m_compare)
im_obj = (im_create, im_compare)
o2o_obj = (o2o_create, o2o_compare)
pk_obj = (pk_create, pk_compare)
inherited_obj = (inherited_create, inherited_compare)

test_data = [
    # Format: (data type, PK value, Model Class, data)
    (data_obj, 5, BooleanData, True),
    (data_obj, 6, BooleanData, False),
    (data_obj, 10, CharData, "Test Char Data"),
    (data_obj, 11, CharData, ""),
    (data_obj, 12, CharData, "None"),
    (data_obj, 13, CharData, "null"),
    (data_obj, 14, CharData, "NULL"),
    (data_obj, 15, CharData, None),
    # (We use something that will fit into a latin1 database encoding here,
    # because that is still the default used on many system setups.)
    (data_obj, 16, CharData, '\xa5'),
    (data_obj, 20, DateData, datetime.date(2006, 6, 16)),
    (data_obj, 21, DateData, None),
    (data_obj, 30, DateTimeData, datetime.datetime(2006, 6, 16, 10, 42, 37)),
    (data_obj, 31, DateTimeData, None),
    (data_obj, 40, EmailData, "hovercraft@example.com"),
    (data_obj, 41, EmailData, None),
    (data_obj, 42, EmailData, ""),
    (data_obj, 50, FileData, 'file:///foo/bar/whiz.txt'),
#     (data_obj, 51, FileData, None),
    (data_obj, 52, FileData, ""),
    (data_obj, 60, FilePathData, "/foo/bar/whiz.txt"),
    (data_obj, 61, FilePathData, None),
    (data_obj, 62, FilePathData, ""),
    (data_obj, 70, DecimalData, decimal.Decimal('12.345')),
    (data_obj, 71, DecimalData, decimal.Decimal('-12.345')),
    (data_obj, 72, DecimalData, decimal.Decimal('0.0')),
    (data_obj, 73, DecimalData, None),
    (data_obj, 74, FloatData, 12.345),
    (data_obj, 75, FloatData, -12.345),
    (data_obj, 76, FloatData, 0.0),
    (data_obj, 77, FloatData, None),
    (data_obj, 80, IntegerData, 123456789),
    (data_obj, 81, IntegerData, -123456789),
    (data_obj, 82, IntegerData, 0),
    (data_obj, 83, IntegerData, None),
    #(XX, ImageData
    (data_obj, 90, IPAddressData, "127.0.0.1"),
    (data_obj, 91, IPAddressData, None),
    (data_obj, 95, GenericIPAddressData, "fe80:1424:2223:6cff:fe8a:2e8a:2151:abcd"),
    (data_obj, 96, GenericIPAddressData, None),
    (data_obj, 100, NullBooleanData, True),
    (data_obj, 101, NullBooleanData, False),
    (data_obj, 102, NullBooleanData, None),
    (data_obj, 120, PositiveIntegerData, 123456789),
    (data_obj, 121, PositiveIntegerData, None),
    (data_obj, 130, PositiveSmallIntegerData, 12),
    (data_obj, 131, PositiveSmallIntegerData, None),
    (data_obj, 140, SlugData, "this-is-a-slug"),
    (data_obj, 141, SlugData, None),
    (data_obj, 142, SlugData, ""),
    (data_obj, 150, SmallData, 12),
    (data_obj, 151, SmallData, -12),
    (data_obj, 152, SmallData, 0),
    (data_obj, 153, SmallData, None),
    (data_obj, 160, TextData, """This is a long piece of text.
It contains line breaks.
Several of them.
The end."""),
    (data_obj, 161, TextData, ""),
    (data_obj, 162, TextData, None),
    (data_obj, 170, TimeData, datetime.time(10, 42, 37)),
    (data_obj, 171, TimeData, None),

    (generic_obj, 200, GenericData, ['Generic Object 1', 'tag1', 'tag2']),
    (generic_obj, 201, GenericData, ['Generic Object 2', 'tag2', 'tag3']),

    (data_obj, 300, Anchor, "Anchor 1"),
    (data_obj, 301, Anchor, "Anchor 2"),
    (data_obj, 302, UniqueAnchor, "UAnchor 1"),

    (fk_obj, 400, FKData, 300),  # Post reference
    (fk_obj, 401, FKData, 500),  # Pre reference
    (fk_obj, 402, FKData, None),  # Empty reference

    (m2m_obj, 410, M2MData, []),  # Empty set
    (m2m_obj, 411, M2MData, [300, 301]),  # Post reference
    (m2m_obj, 412, M2MData, [500, 501]),  # Pre reference
    (m2m_obj, 413, M2MData, [300, 301, 500, 501]),  # Pre and Post reference

    (o2o_obj, None, O2OData, 300),  # Post reference
    (o2o_obj, None, O2OData, 500),  # Pre reference

    (fk_obj, 430, FKSelfData, 431),  # Pre reference
    (fk_obj, 431, FKSelfData, 430),  # Post reference
    (fk_obj, 432, FKSelfData, None),  # Empty reference

    (m2m_obj, 440, M2MSelfData, []),
    (m2m_obj, 441, M2MSelfData, []),
    (m2m_obj, 442, M2MSelfData, [440, 441]),
    (m2m_obj, 443, M2MSelfData, [445, 446]),
    (m2m_obj, 444, M2MSelfData, [440, 441, 445, 446]),
    (m2m_obj, 445, M2MSelfData, []),
    (m2m_obj, 446, M2MSelfData, []),

    (fk_obj, 450, FKDataToField, "UAnchor 1"),
    (fk_obj, 451, FKDataToField, "UAnchor 2"),
    (fk_obj, 452, FKDataToField, None),

    (fk_obj, 460, FKDataToO2O, 300),

    (im2m_obj, 470, M2MIntermediateData, None),

    #testing post- and prereferences and extra fields
    (im_obj, 480, Intermediate, {'right': 300, 'left': 470}),
    (im_obj, 481, Intermediate, {'right': 300, 'left': 490}),
    (im_obj, 482, Intermediate, {'right': 500, 'left': 470}),
    (im_obj, 483, Intermediate, {'right': 500, 'left': 490}),
    (im_obj, 484, Intermediate, {'right': 300, 'left': 470, 'extra': "extra"}),
    (im_obj, 485, Intermediate, {'right': 300, 'left': 490, 'extra': "extra"}),
    (im_obj, 486, Intermediate, {'right': 500, 'left': 470, 'extra': "extra"}),
    (im_obj, 487, Intermediate, {'right': 500, 'left': 490, 'extra': "extra"}),

    (im2m_obj, 490, M2MIntermediateData, []),

    (data_obj, 500, Anchor, "Anchor 3"),
    (data_obj, 501, Anchor, "Anchor 4"),
    (data_obj, 502, UniqueAnchor, "UAnchor 2"),

    (pk_obj, 601, BooleanPKData, True),
    (pk_obj, 602, BooleanPKData, False),
    (pk_obj, 610, CharPKData, "Test Char PKData"),
#     (pk_obj, 620, DatePKData, datetime.date(2006,6,16)),
#     (pk_obj, 630, DateTimePKData, datetime.datetime(2006,6,16,10,42,37)),
    (pk_obj, 640, EmailPKData, "hovercraft@example.com"),
#     (pk_obj, 650, FilePKData, 'file:///foo/bar/whiz.txt'),
    (pk_obj, 660, FilePathPKData, "/foo/bar/whiz.txt"),
    (pk_obj, 670, DecimalPKData, decimal.Decimal('12.345')),
    (pk_obj, 671, DecimalPKData, decimal.Decimal('-12.345')),
    (pk_obj, 672, DecimalPKData, decimal.Decimal('0.0')),
    (pk_obj, 673, FloatPKData, 12.345),
    (pk_obj, 674, FloatPKData, -12.345),
    (pk_obj, 675, FloatPKData, 0.0),
    (pk_obj, 680, IntegerPKData, 123456789),
    (pk_obj, 681, IntegerPKData, -123456789),
    (pk_obj, 682, IntegerPKData, 0),
#     (XX, ImagePKData
    (pk_obj, 690, IPAddressPKData, "127.0.0.1"),
    (pk_obj, 695, GenericIPAddressPKData, "fe80:1424:2223:6cff:fe8a:2e8a:2151:abcd"),
    # (pk_obj, 700, NullBooleanPKData, True),
    # (pk_obj, 701, NullBooleanPKData, False),
    (pk_obj, 720, PositiveIntegerPKData, 123456789),
    (pk_obj, 730, PositiveSmallIntegerPKData, 12),
    (pk_obj, 740, SlugPKData, "this-is-a-slug"),
    (pk_obj, 750, SmallPKData, 12),
    (pk_obj, 751, SmallPKData, -12),
    (pk_obj, 752, SmallPKData, 0),
#     (pk_obj, 760, TextPKData, """This is a long piece of text.
# It contains line breaks.
# Several of them.
# The end."""),
#    (pk_obj, 770, TimePKData, datetime.time(10,42,37)),
#     (pk_obj, 790, XMLPKData, "<foo></foo>"),

    (data_obj, 800, AutoNowDateTimeData, datetime.datetime(2006, 6, 16, 10, 42, 37)),
    (data_obj, 810, ModifyingSaveData, 42),

    (inherited_obj, 900, InheritAbstractModel, {'child_data': 37, 'parent_data': 42}),
    (inherited_obj, 910, ExplicitInheritBaseModel, {'child_data': 37, 'parent_data': 42}),
    (inherited_obj, 920, InheritBaseModel, {'child_data': 37, 'parent_data': 42}),

    (data_obj, 1000, BigIntegerData, 9223372036854775807),
    (data_obj, 1001, BigIntegerData, -9223372036854775808),
    (data_obj, 1002, BigIntegerData, 0),
    (data_obj, 1003, BigIntegerData, None),
    (data_obj, 1004, LengthModel, 0),
    (data_obj, 1005, LengthModel, 1),
]

natural_key_test_data = [
    (data_obj, 1100, NaturalKeyAnchor, "Natural Key Anghor"),
    (fk_obj, 1101, FKDataNaturalKey, 1100),
    (fk_obj, 1102, FKDataNaturalKey, None),
]

# Because Oracle treats the empty string as NULL, Oracle is expected to fail
# when field.empty_strings_allowed is True and the value is None; skip these
# tests.
if connection.features.interprets_empty_strings_as_nulls:
    test_data = [data for data in test_data
                 if not (data[0] == data_obj and
                         data[2]._meta.get_field('data').empty_strings_allowed and
                         data[3] is None)]

# Regression test for #8651 -- a FK to an object iwth PK of 0
# This won't work on MySQL since it won't let you create an object
# with a primary key of 0,
if connection.features.allows_primary_key_0:
    test_data.extend([
        (data_obj, 0, Anchor, "Anchor 0"),
        (fk_obj, 465, FKData, 0),
    ])

# Dynamically create serializer tests to ensure that all
# registered serializers are automatically tested.
class SerializerTests(TestCase):
    def test_get_unknown_serializer(self):
        """
        #15889: get_serializer('nonsense') raises a SerializerDoesNotExist
        """
        with self.assertRaises(SerializerDoesNotExist):
            serializers.get_serializer("nonsense")

        with self.assertRaises(KeyError):
            serializers.get_serializer("nonsense")

        # SerializerDoesNotExist is instantiated with the nonexistent format
        with self.assertRaises(SerializerDoesNotExist) as cm:
            serializers.get_serializer("nonsense")
        self.assertEqual(cm.exception.args, ("nonsense",))

    def test_unregister_unkown_serializer(self):
        with self.assertRaises(SerializerDoesNotExist):
            serializers.unregister_serializer("nonsense")

    def test_get_unkown_deserializer(self):
        with self.assertRaises(SerializerDoesNotExist):
            serializers.get_deserializer("nonsense")

    def test_serialize_proxy_model(self):
        BaseModel.objects.create(parent_data=1)
        base_objects = BaseModel.objects.all()
        proxy_objects = ProxyBaseModel.objects.all()
        proxy_proxy_objects = ProxyProxyBaseModel.objects.all()
        base_data = serializers.serialize("json", base_objects)
        proxy_data = serializers.serialize("json", proxy_objects)
        proxy_proxy_data = serializers.serialize("json", proxy_proxy_objects)
        self.assertEqual(base_data, proxy_data.replace('proxy', ''))
        self.assertEqual(base_data, proxy_proxy_data.replace('proxy', ''))


def serializerTest(format, self):

    # Create all the objects defined in the test data
    objects = []
    instance_count = {}
    for (func, pk, klass, datum) in test_data:
        with connection.constraint_checks_disabled():
            objects.extend(func[0](pk, klass, datum))

    # Get a count of the number of objects created for each class
    for klass in instance_count:
        instance_count[klass] = klass.objects.count()

    # Add the generic tagged objects to the object list
    objects.extend(Tag.objects.all())

    # Serialize the test database
    serialized_data = serializers.serialize(format, objects, indent=2)

    for obj in serializers.deserialize(format, serialized_data):
        obj.save()

    # Assert that the deserialized data is the same
    # as the original source
    for (func, pk, klass, datum) in test_data:
        func[1](self, pk, klass, datum)

    # Assert that the number of objects deserialized is the
    # same as the number that was serialized.
    for klass, count in instance_count.items():
        self.assertEqual(count, klass.objects.count())


def naturalKeySerializerTest(format, self):
    # Create all the objects defined in the test data
    objects = []
    instance_count = {}
    for (func, pk, klass, datum) in natural_key_test_data:
        with connection.constraint_checks_disabled():
            objects.extend(func[0](pk, klass, datum))

    # Get a count of the number of objects created for each class
    for klass in instance_count:
        instance_count[klass] = klass.objects.count()

    # Serialize the test database
    serialized_data = serializers.serialize(format, objects, indent=2,
        use_natural_keys=True)

    for obj in serializers.deserialize(format, serialized_data):
        obj.save()

    # Assert that the deserialized data is the same
    # as the original source
    for (func, pk, klass, datum) in natural_key_test_data:
        func[1](self, pk, klass, datum)

    # Assert that the number of objects deserialized is the
    # same as the number that was serialized.
    for klass, count in instance_count.items():
        self.assertEqual(count, klass.objects.count())

def fieldsTest(format, self):
    obj = ComplexModel(field1='first', field2='second', field3='third')
    obj.save_base(raw=True)

    # Serialize then deserialize the test database
    serialized_data = serializers.serialize(format, [obj], indent=2, fields=('field1','field3'))
    result = next(serializers.deserialize(format, serialized_data))

    # Check that the deserialized object contains data in only the serialized fields.
    self.assertEqual(result.object.field1, 'first')
    self.assertEqual(result.object.field2, '')
    self.assertEqual(result.object.field3, 'third')

def streamTest(format, self):
    obj = ComplexModel(field1='first',field2='second',field3='third')
    obj.save_base(raw=True)

    # Serialize the test database to a stream
    for stream in (six.StringIO(), HttpResponse()):
        serializers.serialize(format, [obj], indent=2, stream=stream)

        # Serialize normally for a comparison
        string_data = serializers.serialize(format, [obj], indent=2)

        # Check that the two are the same
        if isinstance(stream, six.StringIO):
            self.assertEqual(string_data, stream.getvalue())
        else:
            self.assertEqual(string_data, stream.content.decode('utf-8'))

# for format in serializers.get_serializer_formats():
for format in ['xliff']:
    setattr(SerializerTests, 'test_' + format + '_serializer', curry(serializerTest, format))
    setattr(SerializerTests, 'test_' + format + '_natural_key_serializer', curry(naturalKeySerializerTest, format))
    setattr(SerializerTests, 'test_' + format + '_serializer_fields', curry(fieldsTest, format))
    if format != 'python':
        setattr(SerializerTests, 'test_' + format + '_serializer_stream', curry(streamTest, format))


class XmlDeserializerSecurityTests(TestCase):

    def test_no_dtd(self):
        """
        The XML deserializer shouldn't allow a DTD.

        This is the most straightforward way to prevent all entity definitions
        and avoid both external entities and entity-expansion attacks.

        """
        xml = '<?xml version="1.0" standalone="no"?><!DOCTYPE example SYSTEM "http://example.com/example.dtd">'
        with self.assertRaises(DTDForbidden):
            next(serializers.deserialize('xml', xml))
