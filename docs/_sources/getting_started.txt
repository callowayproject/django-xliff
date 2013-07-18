===============
Getting Started
===============

Installation
============

#. Using ``pip`` or ``easy_install``.

   .. code-block:: bash

       pip install django-xliff

   or

   .. code-block:: bash

       easy_install django-xliff


#. Add ``"xliff",`` to your ``INSTALLED_APPS`` setting.

#. Create a ``SERIALIZATION_MODULES`` setting where the key is the file extension (``xliff`` or ``xlf``) and the value is ``'xliff.xliff_serializer'``:

   .. code-block:: python

      SERIALIZATION_MODULES = {'xliff': 'xliff.xliff_serializer'}




Exporting and Importing
=======================

Use Django's serialization_ tools. For example, using the dumpdata_ command::

    django-admin.py dumpdata --format=xliff simpleapp > data.xliff

You can use the loaddata_ command as well::

    django-admin.py loaddata data.xliff


.. _serialization: https://docs.djangoproject.com/en/1.5/topics/serialization/
.. _loaddata: https://docs.djangoproject.com/en/1.5/ref/django-admin/#django-admin-loaddata
.. _dumpdata: https://docs.djangoproject.com/en/1.5/ref/django-admin/#dumpdata-appname-appname-appname-model