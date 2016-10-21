=========
 Read Me
=========

Transplant is a free and open-source CalDAV and CardDAV server migration tool.

The aim is to simply try to discover all calendars and addressbooks on a given server.
then get them all and put them back to the new one.

It is very slow and naive, but should work ok.

This project initial aim is to migrate data from Radicale server 1.x to Radicale server 2.x


.. code:: bash
    migration.py <from_url> <to_url>
