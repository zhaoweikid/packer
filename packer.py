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
import urllib
import posixpath

def run(cmd):
    print(cmd)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE) 
    p.wait()
    code = p.returncode
    data = p.stdout.read()
    return code, data

def md5sum(filename):
    #print('md5sum:', filename)
    m = hashlib.md5()
    with open(filename, 'rb+') as f:
        s = f.read()
        m.update(s)
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
        'css':'<link href="%s" rel="stylesheet">\n',
        'html':'%s\n',
    }

    while True:
        ret = re.search('\<\!\-\-[ ]*packer:%s:([a-zA-Z0-9\/\.\,]+)[ ]*\-\-\>' % (tpl), out)
        ret2 = re.search('\<\!\-\-[ ]*packer:%s[ ]*\-\-\>' % (tpl), out)

        if not ret and not ret2:
            break

        if ret:
            items = ret.groups()[0].split(',')
            try:
                s = ''.join([ outtpl[tpl] % (tofiles[x]) for x in items ])
            except Exception as e:
                print('< Error: not found ', str(e), '>')
                raise
            out = out.replace(ret.group(), s)
        elif ret2:
            items = [ x for x in tofiles.keys() if x.endswith('.css')]
            s = ''.join([ outtpl[tpl] % (tofiles[x]) for x in items ])
            out = out.replace(ret2.group(), s)

    return out



class Html:
    def __init__(self, files, tofiles):
        # html源文件路径
        self.files = files
        # 目标文件路径
        self.tofiles = tofiles
        self.tpl = '\<\!\-\-[ ]*packer:([a-z]+):([a-zA-Z0-9_\,\.]+)[ ]*\-\-\>'
        
        # 所有源文件内容
        self.file_content = {}

        # 入口主html
        self.file_main = []
        # html生成顺序
        self.file_seq = []

        self.scan()

    def scan(self):
        # 文件包含哪些文件
        filedeps = {}
        # 文件被哪些文件包含
        filedeps_rev = {}

        for fn in self.files:
            with open(fn) as f:
                s = f.read()
                self.file_content[fn] = s
                basedir = os.path.dirname(fn)

                ret = re.findall(self.tpl, s)
                print(ret)
                if ret:
                    for item in ret:
                        for x in item[1].split(','): 
                            if fn not in filedeps:
                                filedeps[fn] = [os.path.join(basedir, x)]
                            else:
                                filedeps[fn].append(os.path.join(basedir, x))
                else:
                    filedeps[fn] = []

        print('filedeps:', filedeps)

        for fn in filedeps:
            filedeps_rev[fn] = []
            for k,v in filedeps.items():
                if fn in v:
                    filedeps_rev[fn].append(k)

        print('filedeps_rev:', filedeps_rev)

        for k,v in filedeps_rev.items():
            if not v:
                self.file_main.append(k)

        print('file_main:', self.file_main)
        
        tmpfiles = []
        for k,v in filedeps.items():
            if not v:
                tmpfiles.append(k)
        
        while tmpfiles:
            one = tmpfiles.pop(0)
            self.file_seq.append(one)
            
            v = filedeps_rev[one]
            if v:
                for x in v:
                    if x not in tmpfiles:
                        tmpfiles.append(x)
        
        print('file_seq:', self.file_seq)



    def template(self, filepath):
        outtpl = {
            'js':'<script type="text/javascript" src="%s"></script>\n',
            'css':'<link href="%s" rel="stylesheet">\n',
            'html':'<!-- %s start -->\n%s\n<!-- %s end -->\n\n',
        }

        content = self.file_content[filepath]
        p1 = re.split(self.tpl, content) 
        p2 = re.findall(self.tpl, content)

        if not p2:
            return content

            #topath = self.make_topath(filepath)
            #with open(topath, 'w+') as f:
            #    f.write(content)
            #return

        dname = os.path.dirname(filepath)
        s = ''
        for i in range(0, len(p2)):
            s += p1[i]
            filetype, files = p2[i]
            if filetype == 'html':
                for fname in files.split(','):
                    print("fname:", fname)
                    fpath = os.path.join(dname, fname)
                    fs = self.file_content[fpath]
                    s += outtpl[filetype] % (fname, fs, fname)
            elif filetype == 'css':
                pass
            elif filetype == 'js':
                pass
        
        print("p1:", p1, " p2:", p2, " i:", i)
        s += p1[i+1]
        return s

        #topath = self.make_topath(filepath)
        #with open(topath, 'w+') as f:
        #    f.write(s)


    def make_topath(self, filepath):
        global config
        topath = os.path.join(config.dest, os.path.basename(filepath))
        dirname = os.path.dirname(topath)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        
        return topath
 

    def create(self):
        for fn in self.file_seq:
            print('create:', fn)
            content = self.template(fn)
            if fn in self.file_main:
                topath = self.make_topath(fn)
                print('write:', topath)
                with open(topath, 'w+') as f:
                    f.write(content)


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
        filetypes = {
            'html': ('.html', '.htm'),
            'js': ('.js',),
            'css': ('.css',),
            'sass': ('.sass', '.scss'),
            'image': ('.jpg', '.jpeg', '.png', '.gif', '.ico'),
        }
        allfiles = {'html':[], 'js':[], 'css':[], 'sass':[], 'image':[]}

        for root,dirs,files in os.walk(self.fromdir):
            for fn in files:
                key = ''
                #if 'html' in self.config.fileext and fn.endswith(('.html', '.js', '.css')):
                #    key = fn.split('.')[-1]
                #elif 'css' in self.config.fileext and fn.endswith('.css'):
                #    key = 'css'
                #elif 'css' in self.config.fileext and fn.endswith('.css'):
                #    key = 'css'
                #elif 'sass' in self.config.fileext and fn.endswith(('.sass', '.scss')):
                #    key = 'sass'
                #elif 'image' in self.config.fileext and fn.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico')):
                #    key = 'image'

                for k in self.config.filetype:
                    if fn.endswith(filetypes[k]):
                        key = k

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
                self.tofiles[os.path.join(k,filename)] = os.path.join(k,filename2)

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



    def __init__(self):
        global config
        self.config  = config
        self.fromdir = config.src
        self.todir   = config.dest

        self.files = self.get_files()
        self.tofiles = {}

        self._cache_file = os.path.join(self.fromdir, '.fcache')
        self._cache = FileCache(self._cache_file)

    def run(self):
        self.apply_sass()
        self.apply_css()
        self.apply_js()
        self.apply_image()
        #self.apply_html()

        h = Html(self.files['html'], self.tofiles)
        h.create()

        self._cache.dump()



def webserver(docroot, port):
    #print("webserver:", docroot, port)
    class MyHandler (SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split('?',1)[0]
            path = path.split('#',1)[0]
            trailing_slash = path.rstrip().endswith('/')
            try:
                path = urllib.parse.unquote(path, errors='surrogatepass')
            except UnicodeDecodeError:
                path = urllib.parse.unquote(path)
            path = posixpath.normpath(path)
            words = path.split('/')
            words = filter(None, words)
            path = docroot
            for word in words:
                if os.path.dirname(word) or word in (os.curdir, os.pardir):
                    continue
                path = os.path.join(path, word)
            if trailing_slash:
                path += '/'
            return path


    server_address = ('', port)
    httpd = HTTPServer(server_address, MyHandler)
    print('webserver at:', port)
    httpd.serve_forever()

def monitor_file():
    global config
    fromdir = config.src
    todir = config.dest
    port = config.port

    print('from:', fromdir, 'to:', todir)
    print('monitor mode')
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
                Packer().run()


    handler = EventHandler()
    #mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MODIFY
    mask = pyinotify.IN_DELETE | pyinotify.IN_MODIFY

    wm = pyinotify.WatchManager()
    notifier = pyinotify.Notifier(wm, handler)
    wm.add_watch(fromdir, mask, rec=True)
    #notifier.loop()

    while True:
        try:
            notifier.process_events()
            if notifier.check_events():
                notifier.read_events()
        except KeyboardInterrupt:
            notifier.stop()
            break


def usage():
    print('packer.py [options]')
    print('options:')
    print('\t-h help')
    print('\t-s source directory')
    print('\t-d destination directory, convert source to here')
    print('\t-m monitor mode. copy to destination directory as soon as file changes')
    print('\t-f which files can be found. default: html,js,css,sass,image')
    print('\t-b backend server route. eg: "/uc=127.0.0.1:1200,/api=127.0.0.1:2000"')


class Config:
    def __init__(self, data=None):
        if data and isinstance(data, dict):
            self._data = data
        else:
            self._data = {}

    def __getattr__(self, key):
        return self._data.get(key)

    def __getitem__(self, key):
        return self._data.get(key)

    def __str__(self):
        return str(sel._data)


def main():
    params = {
        'src': '',
        'dest': '', 
        'filetype': 'html,js,css,sass,image'.split(','),
        'monitor': False,
        'port': 8000,
        'mode': 'dev', # dev为开发模式, product为生产模式。生产模式会合并js,css文件
    }

    try:
        opts, args = getopt.getopt(sys.argv[1:],"hs:d:m:f:b:",["src=","dest=","file=","backend="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit(0)
        elif opt in ('-s', '--src'):
            params['src'] = arg
        elif opt in ('-d', '--dest'):
            params['dest'] = arg
        elif opt in ('-f', '--file'):
            params['filetype'] = arg.split(',')
        elif opt in ('-b', '--backend'):
            params['backend'] = arg
        elif opt == '-m':
            params['monitor'] = True
            params['port'] = int(arg)
    
    if not params['src'] or not params['dest']:
        usage()
        sys.exit(2)

    global config

    config = Config(params)


    if config.monitor:
        try:
            monitor_file()
        except KeyboardInterrupt as e:
            print('keyboard interrypt, quit')
            os.kill(os.getpid(), 9)
        except:
            raise
    else:
        Packer().run()

    print('success!')


if __name__ == '__main__':
    main()



