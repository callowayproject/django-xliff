===================
Django XML to XLIFF
===================

Heading
=======

.. code-block:: xml

    <django-objects version="1.0">

.. code-block:: xml

    <xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
           version="1.2"
           xmlns:d="https://docs.djangoproject.com/">

The XLIFF header is technically one line, just like the django-objects tag. I've added a Django namespace (``d``) for a few Django-specific attributes used later on.


Object
======

.. code-block:: xml

    <object pk="1" model="simpleapp.article">

.. code-block:: xml

    <file datatype="database"
          source-language="en-us"
          original="simpleapp.article.1">
      <body>
        <group resname="simpleapp.article.1" restype="row">

The ``source-language`` attribute is assigned Django's ``LANGUAGE_CODE`` setting. I decided the incorporate the id or primary key into the naming and identification within the XLIFF file, thus ``<file originial="">`` and ``<group resname="">`` both use the ``app.model.pk`` dotted notation for identity.

Why are ``<file originial="">`` and ``<group resname="">`` the same? Initially ``<file>`` was going to be equivalent to a database and use ``app.model`` and the ``<group>``'s would be rows and use ``app.model.pk``. However several translating tools I used for testing got confused, so now every object is redundantly enclosed in ``<file><body><group>`` tags.


Field
=====

.. code-block:: xml

    <field to="simpleapp.author" name="author" rel="ManyToOneRel">2</field>
    <field type="CharField" name="headline">Poker has no place on ESPN</field>
    <field type="DateTimeField" name="pub_date">2006-06-16T11:00:00</field>
    <field to="simpleapp.category" name="categories" rel="ManyToManyRel">
      <object pk="3"></object>
      <object pk="1"></object>
    </field>

.. code-block:: xml

    <trans-unit restype="x-ForeignKey"
                d:keytype="pk"
                d:to="simpleapp.author"
                d:rel="ManyToOneRel"
                translate="no"
                resname="author"
                id="author">
      <source>2</source>
    </trans-unit>
    <trans-unit restype="x-CharField"
                maxwidth="50"
                size-unit="char"
                translate="yes"
                resname="headline"
                id="headline">
      <source>Poker has no place on ESPN</source>
    </trans-unit>
    <trans-unit restype="x-DateTimeField"
                translate="no"
                resname="pub_date"
                id="pub_date">
      <source>2006-06-16T11:00:00</source>
    </trans-unit>
    <trans-unit restype="x-ManyToManyField"
                d:keytype="pk"
                d:to="simpleapp.category"
                d:rel="ManyToManyRel"
                translate="no"
                resname="categories"
                id="1.3">
      <source>3</source>
    </trans-unit>
    <trans-unit restype="x-ManyToManyField"
                d:keytype="pk"
                d:to="simpleapp.category"
                d:rel="ManyToManyRel"
                translate="no"
                resname="categories"
                id="1.1">
      <source>1</source>
    </trans-unit>

Common attributes
-----------------

Django's default XML export doesn't contain any indication of the field's type. That metadata might be useful during translation, so I put in the ``restype`` attribute with an ``x-`` prefix, the allowable way to extend that attribute.

The ``resname`` attribute contains the field's name. The ``id`` attribute is also the field's name, except for :class:`ManyToManyField`s. The ``id``\ s need to be unique across all the siblings, so I use the record's id and the relation's id.

Most fields do not require translation, so only :class:`CharField`\ s and :class:`TextField`\ s have the ``translate`` attribute set to "yes". All other fields have it set to "no".


Character fields
----------------

Character fields also include two additional attributes: ``maxwidth`` and ``size-unit``. ``maxwidth`` is the length allowed for that character field, (you don't want to make a translation that won't fit) and ``size-unit`` specifies that the width is in Unicode characters.


Relations
---------

:class:`ForeignKey`\ s and :class:`ManyToManyField`\ s require a few extra attributes. The default Django XML uses the ``rel`` and ``to`` attributes to specify the type of relation and the related model. And, if the export is using natural keys, it includes extra tags for those.

I achieve this in XLIFF using a separate Django namespace (``d``). ``d:keytype`` specifies if it is using the primary key (``pk``) or the natural key (``natural``). ``d:to`` and ``d:rel`` are equivalent to the ``to`` and ``rel`` attributes in the default Django XML.

Natural keys are encoded in the ``<source>`` tag by concatenating multiple values with the ``NATURAL_KEY_SEPARATOR`` setting. It defaults to ``;``.