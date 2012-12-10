#!/usr/bin/python

# Equivalent of "tail -f" as a webpage using websocket
# Usage: webtail.py PORT FILENAME
# Tested with tornado 2.1

# Thanks to Thomas Pelletier for it's great introduction to tornado+websocket
# http://thomas.pelletier.im/2010/08/websocket-tornado-redis/

from __future__ import with_statement
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import sys
import os
import re
import cgi

colorcodes =   {'bold':{True:'[1m[1m',False:'[1m[22m'},
                'cyan':{True:'[1m[36m',False:'[1m[39m'},
                'blue':{True:'[1m[34m',False:'[1m[39m'},
                'red':{True:'[1m[31m',False:'[1m[39m'},
                'magenta':{True:'[1m[35m',False:'[1m[39m'},
                'green':{True:'[1m[32m',False:'[1m[39m'},
                'underline':{True:'[1m[4m',False:'[1m[24m'}}

def recolor(color, text):
    regexp = "(?:%s)(.*?)(?:%s)" % (colorcodes[color][True], '[0m')
    regexp = regexp.replace('[', r'\[')
    return re.sub(regexp, r'''<span style="color: %s">\1</span>''' % color, text)

def bold(text):
    regexp = "(?:%s)(.*?)(?:%s)" % (colorcodes['bold'][True], colorcodes['bold'][False])
    regexp = regexp.replace('[', r'\[')
    return re.sub(regexp, r'<span style="font-weight:bold">\1</span>', text)

def underline(text):
    regexp = "(?:%s)(.*?)(?:%s)" % (colorcodes['underline'][True], colorcodes['underline'][False])
    regexp = regexp.replace('[', r'\[')
    return re.sub(regexp, r'<span style="text-decoration: underline">\1</span>', text)

def removebells(text):
    return text.replace('\07', '')

def removebackspaces(text):
    backspace_or_eol = r'(.\010)|(\033\[K)'
    n = 1
    while n > 0:
        text, n = re.subn(backspace_or_eol, '', text, 1)
    return text

re_string = re.compile(r'(?P<htmlchars>[<&>])|(?P<space>^[ \t]+)|(?P<lineend>\r\n|\r|\n)|(?P<protocal>(^|\s)((http|ftp)://.*?))(\s|$)', re.S|re.M|re.I)
def plaintext2html(text, tabstop=4):
    def do_sub(m):
        c = m.groupdict()
        if c['htmlchars']:
            return cgi.escape(c['htmlchars'])
        if c['lineend']:
            return '<br>'
        elif c['space']:
            t = m.group().replace('\t', '&nbsp;'*tabstop)
            t = t.replace(' ', '&nbsp;')
            return t
        elif c['space'] == '\t':
            return ' '*tabstop;
        else:
            url = m.group('protocal')
            if url.startswith(' '):
                prefix = ' '
                url = url[1:]
            else:
                prefix = ''
            last = m.groups()[-1]
            if last in ['\n', '\r', '\r\n']:
                last = '<br>'
            return '%s%s' % (prefix, url)
    result = re.sub(re_string, do_sub, text)
    result = recolor('cyan', result)
    result = recolor('blue', result)
    result = recolor('red', result)
    result = recolor('magenta', result)
    result = recolor('green', result)
    result = bold(result)
    result = underline(result)
    result = removebells(result)
    result = removebackspaces(result)

    return result


PORT = int(sys.argv[1])
FILENAME = sys.argv[2]
LISTENERS = []
TEMPLATE = """
<!DOCTYPE>
<html>
<head>
    <title>WebTail: %s</title>
    <style type="text/css">#file {white-space: pre-wrap; font-family: monospace; }</style>
</head>
<body>
    <div id="file">%s</div>
    <script type="text/javascript" charset="utf-8">
        function write_line(l) {
            document.getElementById('file').innerHTML += l;
        }

        if ("MozWebSocket" in window) {
            WebSocket = MozWebSocket;
        }

        if (WebSocket) {
            var ws = new WebSocket("ws://%s/tail/");
            ws.onopen = function() {};
            ws.onmessage = function (evt) {
                write_line(evt.data);
            };
            ws.onclose = function() {};
        } else {
            alert("WebSocket not supported");
        }
    </script>
</body>
</html>
"""

tailed_file = open(FILENAME)
tailed_file.seek(os.path.getsize(FILENAME))


def check_file():
    where = tailed_file.tell()
    bits = []
    line = tailed_file.readline()
    while line:
      bits.append(line)
      line = tailed_file.readline()
    if not bits:
        tailed_file.seek(where)
    else:
        print "File refresh"
        for element in LISTENERS:
            element.write_message(plaintext2html(''.join(bits)))


class TailHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print "WebSocket open"
        LISTENERS.append(self)

    def on_message(self, message):
        pass

    def on_close(self):
        print "WebSocket close"
        try:
            LISTENERS.remove(self)
        except:
            pass


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        tail = os.popen("tail %s" % FILENAME).read()
        self.write(TEMPLATE % (FILENAME, plaintext2html(tail), self.request.host))


application = tornado.web.Application([
    (r'/', MainHandler),
    (r'/tail/', TailHandler),
])

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(PORT)

    tailed_callback = tornado.ioloop.PeriodicCallback(check_file, 100)
    tailed_callback.start()

    io_loop = tornado.ioloop.IOLoop.instance()
    try:
        io_loop.start()
    except SystemExit, KeyboardInterrupt:
        io_loop.stop()
        tailed_file.close()
