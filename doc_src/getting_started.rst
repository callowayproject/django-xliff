
Getting Started
===============

Django XML to XLIFF

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

    <field type="CharField" name="headline">Social media collapses. World still turns.</field>

.. code-block:: xml

    <trans-unit d:keytype="pk"
                d:to="simpleapp.author"
                restype="x-ForeignKey"
                d:rel="ManyToOneRel"
                resname="author"
                translate="no"
                id="author">
        <source>500</source>
    </trans-unit>
    <trans-unit maxwidth="50"
                restype="x-CharField"
                size-unit="char"
                resname="headline"
                translate="yes"
                id="headline">
        <source>Social media collapses. World still turns.</source>
    </trans-unit>
