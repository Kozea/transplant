#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
import ssl
import urllib.request

from urllib.error import HTTPError

NS = {
    "D": "DAV:",
    "C": "urn:ietf:params:xml:ns:caldav",
    "CS": "http://calendarserver.org/ns/",
    "ICAL": "http://apple.com/ns/ical/",
    "CR": "urn:ietf:params:xml:ns:carddav"}


class CalendarServer(object):

    def __init__(self, config=None, url_root=None):
        self.config = config or {
            'CALENDAR': 'http://localhost:5232/'
        }
        if url_root is not None:
            self.url_host = url_root
            self.url_root = url_root
        else:
            self.url_host = self.config['CALENDAR']
            self.url_root = self.config['CALENDAR']
        self.opener = self.get_opener()

    @property
    def url(self):
        return self.url_root

    def get_opener(self):
        handlers = []
        if self.url_root.startswith('https'):
            context = ssl._create_unverified_context()
            https_handler = urllib.request.HTTPSHandler(context=context)
            handlers.append(https_handler)
        if self.config.get('CALENDAR_PASSWORD'):
            auth_handler = urllib.request.HTTPBasicAuthHandler()
            auth_handler.add_password(
                'Radicale',
                self.config['CALENDAR'].split('%')[0],
                'radicale',
                self.config['CALENDAR_PASSWORD'])
            handlers.append(auth_handler)
        return urllib.request.build_opener(*handlers)

    def open(self, method='GET', data=None, path=None, headers=None):
        if path:
            if self.url_host not in path:
                url = self.url_host + path
            else:
                url = path
            assert self.url in url
        else:
            url = self.url

        # print(
        #     'Radicale %s on %s' % (method, url))

        kw = dict(
            url=url,
            method=method,
        )
        if headers:
            kw['headers'] = headers

        if data:
            kw['data'] = data.encode('utf-8')
        request = urllib.request.Request(**kw)

        with self.opener.open(request) as answer:
            response = answer.read().decode('utf-8')
            if 200 <= answer.status < 300:
                return response
            raise HTTPError(
                request.full_url, answer.status, response,
                request.headers, request.fp)

    def get_all_things(self, href=None):
        path, xml = self.report(href)
        root = ET.fromstring(xml)
        for response in root.findall('.//D:response', NS):
            href = response.find('./D:href', NS).text
            data = response.find('.//C:calendar-data', NS)
            if data is None:
                continue
            yield href, data.text

    def propfind(self, href=None, raise_if_not_found=False):
        # print('Propfinding %r %s' % (self, href))
        try:
            kw = {}
            if href is not None:
                kw['path'] = href
            kw['headers'] = {'depth': 1}
            return href, self.open('PROPFIND', **kw)
        except HTTPError as e:
            if e.code == 404 and not raise_if_not_found:
                return
            raise

    def report(self, href=None, raise_if_not_found=False):
        data = ("""<c:calendar-query xmlns:d="DAV:" """
                """xmlns:c="urn:ietf:params:xml:ns:caldav">"""
                """<d:prop> <d:getetag /> <c:calendar-data /> </d:prop>"""
                """<c:filter> <c:comp-filter name="VCALENDAR" />"""
                """</c:filter> </c:calendar-query>""")
        try:
            kw = {}
            if href is not None:
                kw['path'] = href
            return href, self.open('REPORT', data, **kw)
        except HTTPError as e:
            if e.code == 404 and not raise_if_not_found:
                return
            raise

    def put(self, href, data):
        try:
            return self.open('PUT', data, href)
        except HTTPError as e:
            print("Error while putting to %s" % href)

    def find_children_path(self, href=None):
        """ Return list of tuple: (path, is_calendar_resource) """
        if href is None:
            href = '/'
        path, xml = self.propfind(href)
        root = ET.fromstring(xml)
        children = []
        for response in root.findall('.//D:response', NS):
            if response.find('D:href', NS).text != path:
                uri = "D:propstat/D:prop/D:resourcetype/"
                if (response.find(uri + 'C:calendar', NS) is not None or
                        response.find(uri + 'CR:addressbook', NS) is not None):
                    children.append(
                        (response.find('D:href', NS).text, False))
                else:
                    children.append((response.find('D:href', NS).text, True))
        return children

    def calendar_iterator(self, path=None):
        results = []
        path_list = self.find_children_path(path)
        for path, is_dir in path_list:
            if is_dir:
                results.extend(self.calendar_iterator(path))
            else:
                results.append(path)
        return results


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        usage="migration.py <from_url> <to_url>",
        description=(
            "Get all calendars and addressbooks from source server and put "
            "them to destination server. This tool is intended for help "
            "migrating data from Radicale1.x to Radicale 2.x but we hope it "
            "can be used to migrate any caldav server."))
    parser.add_argument('from_url', help="URL of source caldav server")
    parser.add_argument('to_url', help="URL of destination caldav server")
    args = parser.parse_args()
    from_server = CalendarServer({'CALENDAR': args.from_url})
    to_server = CalendarServer({'CALENDAR': args.to_url})
    for path in from_server.calendar_iterator():
        for path, data in from_server.get_all_things(path):
            to_server.put(path, data)
