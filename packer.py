#!/usr/bin/python3
# coding: utf-8
import os, sys
import datetime, time
import hashlib
import subprocess
import shutil
import re
import json
import pprint
import pyinotify
import getopt
import threading
import http
from http.server import HTTPServer, SimpleHTTPRequestHandler


def run(cmd):
    print(cmd)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE) 
    p.wait()
    code = p.returncode
    data = p.stdout.read()
    return code, data

def md5sum(filename):
    m = hashlib.md5()
    with open(filename) as f:
        m.update(f.read())
    return m.hexdigest()

def md5str(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()



def copy_file(frompath, topath, filemd5=True):
    dirname = os.path.dirname(topath)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

    val = md5sum(frompath)
    k = topath.split('.')[-1]
    filename  = os.path.basename(topath)
    filename2 = filename[:(len(k)+1)*-1] + ".%s.%s" % (val[-8:], k)
    topath2 = os.path.join(os.path.dirname(topath), filename2)
    
    if filemd5:
        if os.path.isfile(topath2):
            print('skip:', topath2)
            return filename, filename2
        print('copy:', topath2)
        shutil.copyfile(frompath, topath2)
    else:
        if os.path.isfile(topath):
            val2 = md5sum(topath)
            if val == val2:
                print('skip:', topath)
                return filename, filename2
        print('copy:', topath)
        shutil.copyfile(frompath, topath)

    return filename, filename2


def html_replace(out, tofiles, tpl='css'):
    outtpl = {
        'js':'<script type="text/javascript" src="%s"></script>\n',
        'css':'<link href="%s" rel="stylesheet">\n'
    }

    ret = re.search('\<\!\-\-%s:([a-zA-Z0-9\/\.\,]+)\-\-\>' % (tpl), out)
    ret2 = re.search('\<\!\-\-%s\-\-\>' % (tpl), out)
    if ret:
        items = ret.groups()[0].split(',')
        s = ''.join([ outtpl[tpl] % (tofiles[x]) for x in items ])
        out = out.replace(ret.group(), s)
    elif ret2:
        items = [ x for x in tofiles.keys() if x.endswith('.css')]
        s = ''.join([ outtpl[tpl] % (tofiles[x]) for x in items ])
        out = out.replace(ret2.group(), s)

    return out


class FileCache:
    def __init__(self, path):
        self._cache = {}
        self._cache_file = path 
        if os.path.isfile(self._cache_file):
            with open(self._cache_file) as f:
                s = f.read()
            self._cache = json.loads(s)

    def dump(self):
        s = json.dumps(self._cache)
        with open(self._cache_file, 'w+') as f:
            f.write(s)

    def ismodify(self, filepath, checkmd5=False):
        c = self._cache.get(filepath)
        if not c:
            return True
        
        size, mtime, mstr = c
        fs = os.stat(filepath)

        if fs.st_size != size:
            return True

        if fs.mtime != mtime:
            return True

        if checkmd5:
            if md5sum(filepath) != mstr:
                return True
            
        return False

    def add(self, filepath):
        fs = os.stat(filepath)
        size = fs.st_size
        mtime = fs.st_mtime
        mstr = md5sum(filepath)
        self._cache[filepath] = [size, mtime, mstr]

    def remove(self, filepath):
        try:
            self._cache.pop(filepath)
        except:
            pass



class Packer:
    def get_files(self):
        allfiles = {'html':[], 'js':[], 'css':[], 'sass':[], 'image':[]}

        for root,dirs,files in os.walk(self.fromdir):
            for fn in files:
                key = ''
                if fn.endswith(('.html', '.js', '.css')):
                    key = fn.split('.')[-1]
                elif fn.endswith(('.sass', '.scss')):
                    key = 'sass'
                elif fn.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico')):
                    key = 'image'

                if not key:
                    continue
                    
                fpath = os.path.join(root, fn)

                if fpath.startswith(self.todir):
                    continue

                allfiles[key].append(fpath)

        print('found files:')
        pprint.pprint(allfiles)
        print()

        return allfiles



    def apply_sass(self):
        # apply sass to css
        for fn in self.files['sass']:
            if not self._cache.ismodify(fn):
                print('not modify:', fn)
                continue
            topath = os.path.join(self.todir, fn[len(self.fromdir)+1:])
            topath = topath[:-4] + 'css'
            #print topath
            
            dirname = os.path.dirname(topath)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
       
            cmd = "sass %s %s" % (fn, topath)
            run(cmd) 
           
            val = md5sum(topath)

            topath2 = topath[:-4] + ".%s.css" % (val[-8:])
            print('copy:', topath2)
            os.rename(topath, topath2)
            
            mapfile = topath + '.map'
            if os.path.isfile(mapfile):
                os.rename(mapfile, topath2+'.map')


    def apply_file(self, k='js'):
        # copy css/js/image
        for fn in self.files[k]:
            if not self._cache.ismodify(fn):
                print('not modify:', fn)
                continue

            topath = os.path.join(self.todir, fn[len(self.fromdir)+1:])
            filename, filename2 = copy_file(fn, topath)
            if k in ('css', 'js'):
                self.tofiles[k+'/'+filename] = k+'/'+filename2

    def apply_css(self):
        return self.apply_file('css')

    def apply_js(self):
        return self.apply_file('js')

    def apply_image(self):
        # copy image
        for fn in self.files['image']:
            if not self._cache.ismodify(fn):
                print('not modify:', fn)
                continue

            topath = os.path.join(self.todir, fn[len(self.fromdir)+1:])
            if topath.endswith('.ico'):
                copy_file(fn, os.path.join(self.todir, os.path.basename(fn)), False)
                continue

            filename, filename2 = copy_file(fn, topath)


    def apply_html(self):
        # create html
        for fn in self.files['html']:
            if not self._cache.ismodify(fn):
                print('not modify:', fn)
                continue

            out = ''
            with open(fn) as f:
                out = f.read() 
            out = html_replace(out, self.tofiles, 'css')
            out = html_replace(out, self.tofiles, 'js')

            topath = os.path.join(self.todir, os.path.basename(fn))
            dirname = os.path.dirname(topath)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)

            with open(topath, 'w+') as f:
                f.write(out)
            print('create:', topath)



    def __init__(self, fromdir, todir):
        self.fromdir = fromdir 
        self.todir   = todir 

        self.files = self.get_files()
        self.tofiles = {}

        self._cache_file = os.path.join(fromdir, '.fcache')
        self._cache = FileCache(self._cache_file)

    def run(self):
        self.apply_sass()
        self.apply_css()
        self.apply_js()
        self.apply_image()
        self.apply_html()

        self._cache.dump()



def webserver(docroot, port):
    #print("webserver:", docroot, port)
    class MyHandler (SimpleHTTPRequestHandler):
        pass

    server_address = ('', port)
    httpd = HTTPServer(server_address, MyHandler)
    print('webserver at:', port)
    httpd.serve_forever()

def monitor_file(fromdir, todir, port=8000):
    t = threading.Thread(target=webserver, args=(todir, port), daemon=True)
    t.start()

    class EventHandler(pyinotify.ProcessEvent):
        def process_IN_CREATE(self, event):
            self.apply(event.pathname, 'create')
            #print("Creating:", event.pathname)

        def process_IN_DELETE(self, event):
            self.apply(event.pathname, 'delete')
            #print("Removing:", event.pathname)

        def process_IN_MODIFY(self, event):
            self.apply(event.pathname, 'modify')
            #print("Modify:", event.pathname)

        def apply(self, fpath, action):
            #print('fpath:', fpath, action)
            fname = os.path.basename(fpath)
            if fpath.endswith(('.swp', '.swpx', '~')) or \
               fname[0] == '.': # ignore vim temp file
                return

            print('change:', fpath)
            if action == 'modify':
                Packer(fromdir, todir).run()


    handler = EventHandler()
    #mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MODIFY
    mask = pyinotify.IN_DELETE | pyinotify.IN_MODIFY

    wm = pyinotify.WatchManager()
    notifier = pyinotify.Notifier(wm, handler)
    wm.add_watch(fromdir, mask, rec=True)
    notifier.loop()


def usage():
    print('packer.py [options]')
    print('options:')
    print('\t-h help')
    print('\t-f source directory')
    print('\t-t destination directory, convert source to here')
    print('\t-m monitor mode. copy to destination directory as soon as file changes')


def main():
    fromdir = ''
    todir   = ''
    monitor = False

    try:
        opts, args = getopt.getopt(sys.argv[1:],"hf:t:m",["from=","to="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit(0)
        elif opt in ('-f', '--from'):
            fromdir = arg
        elif opt in ('-t', '--to'):
            todir = arg
        elif opt == '-m':
            monitor = True
    
    if not fromdir or not todir:
        usage()
        sys.exit(2)

    if monitor:
        monitor_file(fromdir, todir)
    else:
        Packer(fromdir, todir).run()

    print('success!')


if __name__ == '__main__':
    main()



